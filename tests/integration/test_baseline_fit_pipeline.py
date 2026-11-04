"""Ajuste T15 separado: train completo, corte causal y evaluacion pendiente."""

import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.ingestion.manifest import describe_parquet
from src.training import baseline_fit, resources
from src.training.baseline import run_baseline
from tests.integration.test_temporal_split_pipeline import make_catalog, read


def train_catalog(tmp_path, *, all_months=False):
    catalog = make_catalog(
        tmp_path,
        all_months=all_months,
        durations={(2024, m): m for m in range(1, 13)} if all_months else None,
    )
    body = json.loads(catalog.read_text())
    body["batches"] = [e for e in body["batches"] if e["year"] == 2024]
    catalog.write_text(json.dumps(body))
    return catalog


def run(catalog, tmp_path, **kwargs):
    return baseline_fit.fit_baseline(
        catalog,
        output_dir=tmp_path / "fits",
        report_dir=tmp_path / "fit_reports",
        scratch_dir=tmp_path / "scratch",
        test_only=True,
        **kwargs,
    )


def test_full_train_only_no_2025_access_cutoff_and_reproducibility(tmp_path, monkeypatch):
    catalog = train_catalog(tmp_path, all_months=True)
    original = pq.ParquetFile
    opened = []

    def train_only(path, *args, **kwargs):
        text = str(getattr(path, "name", path))
        assert not any(part == "2025" or part.startswith("2025-") for part in Path(text).parts)
        opened.append(text)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pq, "ParquetFile", train_only)
    first = run(catalog, tmp_path, batch_size=2)
    assert first["status"] == "BASELINE_FIT_TEST_ONLY_PENDING_VALIDATION", first.get("error")
    assert first["complete_train_coverage"] and not first["complete_protocol_coverage"]
    assert first["counts"] == {"rows_seen": 144, "train": 143, "label_not_available_at_cutoff": 1}
    assert first["model"]["prediction_minutes"] == 6.0
    assert first["learned"]["train_rows"] == 143
    assert first["fit_complete"] and first["publication_complete"]
    assert not first["t14_complete"] and not first["t15_complete"]
    assert first["validation_metrics"] is None
    assert not any(
        first[key]
        for key in (
            "validation_accessed",
            "test_accessed",
            "monitoring_replay_accessed",
            "model_registered",
            "approved_for_serving",
        )
    )
    folder = Path(first["output_directory"])
    assert {p.name for p in folder.iterdir()} == {
        "fit_manifest.json",
        "model.json",
        "train_target.parquet",
    }
    assert json.loads((folder / "fit_manifest.json").read_text()) == first
    assert first["train_target"] == describe_parquet(folder / "train_target.parquet")
    table = read(folder / "train_target.parquet")
    assert (
        table.num_rows == 143
        and table.schema.metadata[b"evaluation_status"] == b"PENDING_VALIDATION"
    )
    body = json.loads(catalog.read_text())
    body["batches"].reverse()
    catalog.write_text(json.dumps(body))
    second = run(catalog, tmp_path, batch_size=7)
    assert second["status"] == first["status"], second.get("error")
    assert second["model"] == first["model"]
    assert second["model_sha256"] == first["model_sha256"]
    assert second["train_logical_sha256"] == first["train_logical_sha256"]
    assert second["target_logical_sha256"] == first["target_logical_sha256"]
    assert first["baseline_fit_id"] != second["baseline_fit_id"]
    assert not list((tmp_path / "scratch").glob("median-*"))
    assert opened


@pytest.mark.parametrize(
    "case",
    [
        "nontrain",
        "duplicate",
        "wrong_month",
        "missing_marker",
        "changed_target",
        "false_target",
        "quality_rejected",
    ],
)
def test_invalid_inputs_are_not_fitted_or_published(tmp_path, case):
    catalog = train_catalog(tmp_path)
    body = json.loads(catalog.read_text())
    entry = body["batches"][0]
    folder = Path(entry["features_directory"])
    if case == "nontrain":
        entry["year"] = 2025
    elif case == "duplicate":
        body["batches"].append(entry)
    elif case == "wrong_month":
        entry["month"] = 11
    elif case == "missing_marker":
        (folder / "features_manifest.json").unlink()
    elif case == "changed_target":
        (folder / "target.parquet").write_bytes(b"corrupted")
    elif case == "false_target":
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
    elif case == "quality_rejected":
        marker = Path(entry["validated_directory"]) / "validation.json"
        manifest = json.loads(marker.read_text())
        manifest["quality_passed"] = False
        marker.write_text(json.dumps(manifest))
    catalog.write_text(json.dumps(body))
    report = run(catalog, tmp_path)
    assert report["status"] == "FAIL" and not report["fit_complete"]
    assert not report["publication_complete"]
    assert not list((tmp_path / "fits").rglob("fit_manifest.json"))
    assert not list((tmp_path / "fits").rglob(".fit-*"))
    assert not list((tmp_path / "scratch").glob("median-*"))


@pytest.mark.parametrize(
    "case", ["missing_approval", "quality_override", "changed_policy", "numeric_approval"]
)
def test_unapproved_contract_or_quality_change_fails_before_sources(tmp_path, monkeypatch, case):
    config = json.loads(Path("configs/model.yaml").read_text())
    if case == "missing_approval":
        del config["baseline_fit_only"]
    elif case == "quality_override":
        config["baseline_fit_only"]["source_quality_override"] = True
    elif case == "numeric_approval":
        config["baseline_fit_only"]["allow_before_complete_t14"] = 1
    else:
        config["quality_rules_sha256"] = "0" * 64
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(config))
    monkeypatch.setattr(
        baseline_fit, "_catalog", lambda *a, **k: pytest.fail("No debe abrir fuentes")
    )
    report = run(tmp_path / "nonexistent.json", tmp_path, config_path=model_path)
    assert report["status"] == "FAIL" and not report["publication_complete"]


def test_real_requires_all_train_months_before_source_access(tmp_path, monkeypatch):
    catalog = train_catalog(tmp_path)
    monkeypatch.setattr(
        baseline_fit, "verify_features", lambda *a, **k: pytest.fail("Train incompleto")
    )
    report = baseline_fit.fit_baseline(
        catalog,
        output_dir=tmp_path / "fits",
        report_dir=tmp_path / "fit_reports",
        scratch_dir=tmp_path / "scratch",
    )
    assert report["status"] == "FAIL" and "todos los meses de train" in report["error"]


@pytest.mark.parametrize("low", ["ram", "rss", "disk"])
def test_real_resource_preflight_stops_before_verifying_sources(tmp_path, monkeypatch, low):
    catalog = train_catalog(tmp_path, all_months=True)
    observed = {
        "available_ram_bytes": 5 * 2**30,
        "peak_rss_bytes": 1000,
        "free_disk_bytes": 80 * 2**30,
    }
    observed[
        {"ram": "available_ram_bytes", "rss": "peak_rss_bytes", "disk": "free_disk_bytes"}[low]
    ] = 3 * 2**30
    monkeypatch.setattr(resources, "snapshot", lambda directory: observed)
    monkeypatch.setattr(
        baseline_fit, "verify_features", lambda *a, **k: pytest.fail("Sin recursos")
    )
    report = baseline_fit.fit_baseline(
        catalog,
        output_dir=tmp_path / "fits",
        report_dir=tmp_path / "fit_reports",
        scratch_dir=tmp_path / "scratch",
    )
    assert report["status"] == "FAIL" and "D-02" in report["error"]


@pytest.mark.parametrize("change", ["source", "catalog"])
def test_changes_during_fit_prevent_publication(tmp_path, monkeypatch, change):
    catalog = train_catalog(tmp_path)
    original = baseline_fit.exact_disk_median

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        if change == "source":
            source = json.loads(catalog.read_text())["batches"][0]["features_directory"]
            path = Path(source) / "features_manifest.json"
        else:
            path = catalog
        body = json.loads(path.read_text())
        body["altered"] = True
        path.write_text(json.dumps(body))
        return result

    monkeypatch.setattr(baseline_fit, "exact_disk_median", mutate)
    result = run(catalog, tmp_path)
    assert result["status"] == "FAIL" and "cambio durante" in result["error"]
    assert not list((tmp_path / "fits").rglob("fit_manifest.json"))


@pytest.mark.parametrize("failure", ["resource", "deadline", "publication"])
def test_failure_cleans_scratch_and_never_publishes_complete_fit(tmp_path, monkeypatch, failure):
    catalog = train_catalog(tmp_path)
    if failure == "resource":
        calls = 0

        def exhausted(self, *, start=False):
            nonlocal calls
            calls += 1
            if calls >= 4:
                raise RuntimeError("budget exhausted")

        monkeypatch.setattr(resources.ResourceGuard, "check", exhausted)
    elif failure == "deadline":
        clock = iter(range(0, 100000, 7201))
        monkeypatch.setattr(baseline_fit.time, "monotonic", lambda: next(clock))
    else:
        monkeypatch.setattr(
            baseline_fit,
            "publish_file",
            lambda *a, **k: (_ for _ in ()).throw(OSError("disk failure")),
        )
    result = run(catalog, tmp_path, batch_size=2)
    assert result["status"] == "FAIL" and not result["publication_complete"]
    assert not list((tmp_path / "fits").rglob("fit_manifest.json"))
    assert not list((tmp_path / "fits").rglob(".fit-*"))
    assert not list((tmp_path / "scratch").glob("median-*"))


def test_fit_artifact_cannot_masquerade_as_complete_split(tmp_path):
    fit = run(train_catalog(tmp_path), tmp_path)
    assert fit["fit_complete"]
    report = run_baseline(
        Path(fit["output_directory"]),
        output_dir=tmp_path / "full_baselines",
        report_dir=tmp_path / "full_reports",
        scratch_dir=tmp_path / "full_scratch",
        test_only=True,
    )
    assert report["status"] == "FAIL" and not report["publication_complete"]
    assert not list((tmp_path / "full_baselines").rglob("baseline_manifest.json"))


def test_fit_only_installed_cli_and_error_exit(tmp_path):
    catalog = train_catalog(tmp_path)
    command = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "src.training.baseline_fit",
        "--inputs",
        str(catalog),
        "--output-dir",
        str(tmp_path / "fits"),
        "--report-dir",
        str(tmp_path / "reports"),
        "--scratch-dir",
        str(tmp_path / "scratch"),
        "--test-only",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert (
        report["status"] == "BASELINE_FIT_TEST_ONLY_PENDING_VALIDATION" and report["fit_complete"]
    )
    catalog.write_text("{}")
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 1 and json.loads(result.stdout)["status"] == "FAIL"
