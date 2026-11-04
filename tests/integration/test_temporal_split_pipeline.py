"""T14 completo offline sobre fixtures T10/T13; nunca usa los 24 raw reales."""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.features.artifacts import build_validated_features
from src.ingestion.manifest import describe_parquet
from src.training import resources, split
from tests.fixtures.factory import make_table
from tests.integration.test_feature_pipeline import validated_fixture


def make_catalog(tmp_path, *, all_months=False, durations=None):
    periods = [(2024, 12), (2025, 3), (2025, 6), (2025, 12)]
    if all_months:
        periods = [(y, m) for y in (2024, 2025) for m in range(1, 13)]
    entries = []
    for year, month in periods:
        table = make_table()
        rows = table.to_pylist()
        for index, row in enumerate(rows):
            pickup = datetime(year, month, index + 1, 8)
            row.update(
                tpep_pickup_datetime=pickup,
                tpep_dropoff_datetime=pickup
                + timedelta(minutes=(durations or {}).get((year, month), 10)),
            )
        if (year, month) in [(2024, 12), (2025, 3), (2025, 6), (2025, 12)]:
            cutoff = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
            rows[-1].update(
                tpep_pickup_datetime=cutoff - timedelta(minutes=5),
                tpep_dropoff_datetime=cutoff + timedelta(minutes=5),
            )
        source = validated_fixture(
            tmp_path / f"{year}-{month}",
            pa.Table.from_pylist(rows, schema=table.schema),
            year=year,
            month=month,
        )
        result = build_validated_features(
            source, processed_dir=tmp_path / "processed", test_only=True, batch_size=3
        )
        entries.append(
            {
                "year": year,
                "month": month,
                "features_directory": result["output_directory"],
                "validated_directory": str(source),
            }
        )
    catalog = tmp_path / "inputs.json"
    catalog.write_text(json.dumps({"format_version": 1, "batches": entries}))
    return catalog


def run(catalog, tmp_path, **kwargs):
    return split.prepare_splits(
        catalog,
        output_dir=tmp_path / "splits",
        report_dir=tmp_path / "reports",
        test_only=True,
        **kwargs,
    )


def read(path):
    with pq.ParquetFile(path) as parquet:
        return parquet.read()


def test_all_rows_alignment_cutoff_accounting_and_determinism(tmp_path):
    catalog = make_catalog(tmp_path)
    before = catalog.read_bytes()
    first = run(catalog, tmp_path, batch_size=2)
    assert first["status"] == "SPLIT_TEST_ONLY", first.get("error")
    assert first["counts"]["rows_seen"] == 48
    assert first["counts"]["label_not_available_at_cutoff"] == 4
    assert not first["approved_for_training"] and not first["preprocessor_fitted"]
    assert not first["complete_protocol_coverage"]
    assert len(first["exclusion_examples"]) == 4
    entries = json.loads(catalog.read_text())["batches"]
    catalog.write_text(json.dumps({"format_version": 1, "batches": entries[::-1]}))
    second = run(catalog, tmp_path, batch_size=7)
    assert second["status"] == "SPLIT_TEST_ONLY", second.get("error")
    for part in split.PARTITIONS:
        assert first["partitions"][part]["rows"] == 11
        assert (
            first["partitions"][part]["logical_sha256"]
            == second["partitions"][part]["logical_sha256"]
        )
        folder = Path(first["output_directory"]) / part
        tables = [read(folder / f"{name}.parquet") for name in split.TABLES]
        assert [table.num_rows for table in tables] == [11, 11, 11]
        assert tables[0].column_names == list(split.FEATURE_COLUMNS)
        assert tables[2]["validated_row_index"].to_pylist() == list(range(11))
        assert len(set(tables[2]["source_feature_id"].to_pylist())) == 1
    assert (
        json.loads((Path(first["output_directory"]) / "split_manifest.json").read_text()) == first
    )
    assert before != catalog.read_bytes()  # Solo el catalogo se invirtio; no se alteraron entradas.


def test_source_changed_during_scan_blocks_publication(tmp_path, monkeypatch):
    catalog = make_catalog(tmp_path)
    original = split._scan_source

    def mutate(entry, *args, **kwargs):
        original(entry, *args, **kwargs)
        marker = entry["features_directory"] / "features_manifest.json"
        body = json.loads(marker.read_text())
        body["changed_during_split"] = True
        marker.write_text(json.dumps(body))

    monkeypatch.setattr(split, "_scan_source", mutate)
    report = run(catalog, tmp_path)
    assert report["status"] == "FAIL" and "cambio durante" in report["error"]
    assert not list((tmp_path / "splits").rglob("split_manifest.json"))


def test_full_protocol_coverage_without_claiming_real_training(tmp_path):
    report = run(make_catalog(tmp_path, all_months=True), tmp_path, batch_size=5)
    assert report["status"] == "SPLIT_TEST_ONLY", report.get("error")
    assert report["complete_protocol_coverage"] and report["counts"]["rows_seen"] == 288
    assert sum(report["counts"][part] for part in split.PARTITIONS) == 284
    assert not report["approved_for_training"]


@pytest.mark.parametrize(
    "failure", ["duplicate_month", "wrong_month", "missing_marker", "changed_file", "target_lie"]
)
def test_bad_inputs_do_not_publish_a_completed_split(tmp_path, failure):
    catalog = make_catalog(tmp_path)
    data = json.loads(catalog.read_text())
    entry = data["batches"][0]
    folder = Path(entry["features_directory"])
    if failure == "duplicate_month":
        data["batches"].append(entry)
    if failure == "wrong_month":
        entry["month"] = 11
    if failure == "missing_marker":
        (folder / "features_manifest.json").unlink()
    if failure == "changed_file":
        (folder / "target.parquet").write_bytes(b"changed")
    if failure == "target_lie":
        path = folder / "target.parquet"
        table = read(path)
        values = table.column(0).to_pylist()
        values[0] = 99.0
        pq.write_table(
            pa.Table.from_pydict({"trip_duration_minutes": values}, schema=table.schema), path
        )
        marker = folder / "features_manifest.json"
        manifest = json.loads(marker.read_text())
        manifest["artifacts"]["target"] = describe_parquet(path)
        marker.write_text(json.dumps(manifest))
    catalog.write_text(json.dumps(data))
    report = run(catalog, tmp_path)
    assert report["status"] == "FAIL"
    assert not list((tmp_path / "splits").rglob("split_manifest.json"))
    assert not list((tmp_path / "splits").rglob(".split-*"))


def test_real_mode_rejects_partial_protocol_before_row_decode(tmp_path, monkeypatch):
    catalog = make_catalog(tmp_path)
    monkeypatch.setattr(
        split, "verify_features", lambda *a, **k: pytest.fail("No debe leer lotes incompletos")
    )
    report = split.prepare_splits(
        catalog, output_dir=tmp_path / "splits", report_dir=tmp_path / "reports"
    )
    assert report["status"] == "FAIL" and "24 lotes" in report["error"]


def test_real_low_memory_blocks_before_input_verification(tmp_path, monkeypatch):
    catalog = make_catalog(tmp_path, all_months=True)
    monkeypatch.setattr(
        resources,
        "snapshot",
        lambda directory: {
            "available_ram_bytes": 1,
            "free_disk_bytes": 100 * 2**30,
            "peak_rss_bytes": 1,
        },
    )
    monkeypatch.setattr(
        split, "verify_features", lambda *a, **k: pytest.fail("No debe leer sin presupuesto")
    )
    report = split.prepare_splits(
        catalog, output_dir=tmp_path / "splits", report_dir=tmp_path / "reports"
    )
    assert report["status"] == "FAIL" and "D-02" in report["error"]


def test_publish_failure_leaves_no_completion_marker(tmp_path, monkeypatch):
    catalog = make_catalog(tmp_path)
    monkeypatch.setattr(
        split, "publish_file", lambda *a, **k: (_ for _ in ()).throw(OSError("disk failure"))
    )
    report = run(catalog, tmp_path)
    assert report["status"] == "FAIL" and "disk failure" in report["error"]
    assert not list((tmp_path / "splits").rglob("split_manifest.json"))


def test_resource_abort_during_scan_cleans_staging(tmp_path, monkeypatch):
    catalog = make_catalog(tmp_path)
    calls = 0

    def limited(self, *, start=False):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise resources.ResourceLimitError("D-02: limite durante escaneo")

    monkeypatch.setattr(resources.ResourceGuard, "check", limited)
    report = run(catalog, tmp_path, batch_size=1)
    assert report["status"] == "FAIL" and not report["publication_complete"]
    assert "D-02" in report["error"]
    assert not list((tmp_path / "splits").rglob("split_manifest.json"))
    assert not list((tmp_path / "splits").rglob(".split-*"))


def test_installed_cli_round_trip_and_invalid_catalog_exit(tmp_path):
    catalog = make_catalog(tmp_path)
    command = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "src.training.split",
        "--inputs",
        str(catalog),
        "--output-dir",
        str(tmp_path / "splits"),
        "--report-dir",
        str(tmp_path / "reports"),
        "--test-only",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["status"] == "SPLIT_TEST_ONLY"
    catalog.write_text("{}")
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 1 and json.loads(result.stdout)["status"] == "FAIL"
