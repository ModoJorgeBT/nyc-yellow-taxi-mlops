"""T11: descarga simulada -> manifiesto -> reporte/dataset TEST_ONLY; sin red real."""

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.ingestion import download
from src.validation import run
from src.validation.schema import load_config
from tests.fixtures.factory import make_table
from tests.fixtures.policies import pending_policy, synthetic_policy

CONFIG = Path(__file__).resolve().parents[2] / "configs/data.yaml"


class Response(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.status = 200
        self.headers = {"Content-Length": str(len(payload))}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No se permite red real en T11")

    monkeypatch.setattr(download.urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(download.time, "sleep", lambda _: None)


@pytest.fixture
def options(tmp_path: Path) -> dict:
    config_path = tmp_path / "test-policy.json"
    config_path.write_text(json.dumps(synthetic_policy(load_config(CONFIG))), encoding="utf-8")
    return {
        "raw_dir": tmp_path / "raw",
        "validated_dir": tmp_path / "validated",
        "report_dir": tmp_path / "reports",
        "scratch_dir": tmp_path / "scratch",
        "config_path": config_path,
        "batch_size": 2,
        "test_only": True,
    }


def ingest(options: dict, monkeypatch: pytest.MonkeyPatch, case="valid", *, unmarked=False):
    table = make_table(case)
    if unmarked:
        table = table.replace_schema_metadata(None)
    buffer = io.BytesIO()
    pq.write_table(table, buffer, row_group_size=6)
    payload = buffer.getvalue()
    calls = []

    def mock(request, *, timeout):
        calls.append(request.full_url)
        return Response(payload)

    monkeypatch.setattr(download.urllib.request, "urlopen", mock)
    result = download.ingest(2024, 1, raw_dir=options["raw_dir"])
    return table, payload, result, calls


def validate(options: dict) -> dict:
    return run.validate(2024, 1, **options)


def output_path(options: dict, report: dict) -> Path:
    return options["validated_dir"] / report["output"]["relative_path"]


def assert_no_dataset(options: dict):
    assert not list(options["validated_dir"].rglob("*.parquet"))
    assert not list(options["validated_dir"].rglob("validation.json"))
    assert not list(options["validated_dir"].rglob(".validation-*"))
    assert not list(options["scratch_dir"].glob("dq-*"))
    assert not list(options["raw_dir"].rglob(".ingestion.lock"))


def test_download_validate_lineage_and_full_content(options, monkeypatch):
    table, payload, result, calls = ingest(options, monkeypatch)
    before_manifest = Path(result["manifest_path"]).read_bytes()
    report = validate(options)
    assert report["status"] == "PASS" and report["execution_status"] == "VALIDATED_TEST_ONLY"
    assert report["quality_passed"] and not report["approved_for_training"]
    assert report["lineage_status"] == "VERIFIED_CONTENT"
    assert report["scan_scope"] == "FULL_PARQUET" and report["rows_scanned"] == 12
    assert report["input"]["manifest"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert report["input"]["manifest_sha256"] == hashlib.sha256(before_manifest).hexdigest()
    path = output_path(options, report)
    assert path.parts[-5:-2] == ("_test_only", "2024", "01")
    with path.open("rb") as stream, pq.ParquetFile(stream) as parquet:
        assert parquet.read().to_pydict() == table.to_pydict()
        assert parquet.schema_arrow.metadata[b"approved_for_training"] == b"false"
    assert Path(result["data_path"]).read_bytes() == payload
    assert Path(result["manifest_path"]).read_bytes() == before_manifest
    assert json.loads(Path(report["report_path"]).read_text()) == report
    assert json.loads((path.parent / "validation.json").read_text()) == report
    assert len(calls) == 1


@pytest.mark.parametrize(
    "case,excluded",
    [("null_zone", 1), ("nonpositive_duration", 2), ("pickup_outside_month", 1), ("duplicate", 0)],
)
def test_tolerated_exclusions_match_written_rows(options, monkeypatch, case, excluded):
    ingest(options, monkeypatch, case)
    report = validate(options)
    assert report["status"] == "WARN" and report["quality_passed"]
    assert report["excluded_rows"] == excluded
    assert report["output"]["row_count"] == report["eligible_rows"] == 12 - excluded
    with output_path(options, report).open("rb") as stream, pq.ParquetFile(stream) as parquet:
        rows = parquet.read().to_pylist()
    if case == "null_zone":
        assert all(row["PULocationID"] is not None for row in rows)
    if case == "duplicate":
        assert rows[0] == rows[-1]  # Medir no significa deduplicar.


def test_critical_gate_persists_rejection_without_dataset(options, monkeypatch):
    ingest(options, monkeypatch, "null_zone")
    config = json.loads(options["config_path"].read_text())
    config["quality"]["max_rates"]["zone_null"] = 0
    options["config_path"].write_text(json.dumps(config))
    report = validate(options)
    assert report["status"] == "FAIL" and not report["quality_passed"]
    assert report["excluded_rows"] == 1 and report["output"] is None
    assert Path(report["report_path"]).exists()
    assert_no_dataset(options)


@pytest.mark.parametrize("case", ["missing_column", "incompatible_type"])
def test_schema_failure_is_preflight_only(options, monkeypatch, case):
    ingest(options, monkeypatch, case)

    def forbidden(*args, **kwargs):
        pytest.fail("No escanear esquema incompatible")

    monkeypatch.setattr(run, "_scan", forbidden)
    report = validate(options)
    assert report["status"] == "FAIL" and report["scan_scope"] == "PREFLIGHT_ONLY"
    assert_no_dataset(options)


@pytest.mark.parametrize("normal_test_config", [False, True])
def test_normal_mode_blocked_without_reading_rows(options, monkeypatch, normal_test_config):
    ingest(options, monkeypatch)
    options["test_only"] = False
    if not normal_test_config:
        options["config_path"].write_text(json.dumps(pending_policy(load_config(CONFIG))))

    def forbidden(*args, **kwargs):
        pytest.fail("D-04 pendiente: no escanear filas")

    monkeypatch.setattr(run, "_scan", forbidden)
    report = validate(options)
    assert report["status"] == "FAIL" and report["scan_scope"] == "PREFLIGHT_ONLY"
    assert not report["approved_for_training"]
    assert_no_dataset(options)


@pytest.mark.parametrize("failure", ["unmarked", "pending_config"])
def test_test_only_cannot_bypass_policy_or_origin_marker(options, monkeypatch, failure):
    ingest(options, monkeypatch, unmarked=failure == "unmarked")
    if failure == "pending_config":
        options["config_path"].write_text(json.dumps(pending_policy(load_config(CONFIG))))
    report = validate(options)
    assert report["status"] == "FAIL" and "--test-only" in report["error"]
    assert_no_dataset(options)


def test_missing_manifest_never_registers_local_file(options):
    directory = options["raw_dir"] / "2024/01"
    directory.mkdir(parents=True)
    pq.write_table(make_table(), directory / "yellow_tripdata_2024-01.parquet")
    report = validate(options)
    assert report["status"] == "FAIL" and "manifiesto" in report["error"]
    assert not (directory / "manifest.json").exists()
    assert_no_dataset(options)


def test_missing_batch_persists_failure_without_creating_raw(options):
    report = validate(options)
    assert report["status"] == "FAIL" and Path(report["report_path"]).exists()
    assert not options["raw_dir"].exists()
    assert_no_dataset(options)


def test_registered_local_fixture_preserves_unknown_provenance(options):
    directory = options["raw_dir"] / "2024/01"
    directory.mkdir(parents=True)
    pq.write_table(make_table(), directory / "yellow_tripdata_2024-01.parquet")
    download.ingest(2024, 1, raw_dir=options["raw_dir"], register_local=True)
    report = validate(options)
    assert report["execution_status"] == "VALIDATED_TEST_ONLY"
    origin = report["input"]["manifest"]
    assert origin["provenance_status"] == "UNVERIFIED_LOCAL"
    assert origin["source_url"] is None and origin["downloaded_at_utc"] is None
    assert not report["approved_for_training"]


@pytest.mark.parametrize("target", ["raw", "manifest"])
def test_changed_input_blocks_publication(options, monkeypatch, target):
    _, _, result, _ = ingest(options, monkeypatch)
    path = Path(result["data_path" if target == "raw" else "manifest_path"])
    if target == "raw":
        path.write_bytes(path.read_bytes() + b"changed")
    else:
        content = json.loads(path.read_text())
        content["row_count"] = 13
        path.write_text(json.dumps(content))
    report = validate(options)
    assert report["status"] == "FAIL" and report["lineage_status"] == "FAILED_OR_INCOMPLETE"
    assert_no_dataset(options)


@pytest.mark.parametrize("target", ["raw", "manifest"])
def test_input_changes_during_scan_are_detected(options, monkeypatch, target):
    _, _, result, _ = ingest(options, monkeypatch)
    original = run._scan

    def changed(*args, **kwargs):
        quality = original(*args, **kwargs)
        path = Path(result["data_path" if target == "raw" else "manifest_path"])
        if target == "raw":
            path.write_bytes(path.read_bytes() + b"changed")
        else:
            content = json.loads(path.read_text())
            content["pipeline_version"] = "changed"
            path.write_text(json.dumps(content))
        return quality

    monkeypatch.setattr(run, "_scan", changed)
    report = validate(options)
    assert report["status"] == "FAIL" and not report["quality_passed"]
    assert_no_dataset(options)


def test_short_scan_cannot_claim_full_dataset(options, monkeypatch):
    ingest(options, monkeypatch)
    original = run._scan

    def shortened(*args, **kwargs):
        report = original(*args, **kwargs)
        report["rows_scanned"] = 6
        return report

    monkeypatch.setattr(run, "_scan", shortened)
    report = validate(options)
    assert report["status"] == "FAIL" and not report["quality_passed"]
    assert next(c for c in report["checks"] if c["rule"] == "input.exhaustive")["status"] == "FAIL"
    assert_no_dataset(options)


@pytest.mark.parametrize("phase", ["read", "write"])
def test_interrupted_read_or_write_cleans_staging(options, monkeypatch, phase):
    ingest(options, monkeypatch)
    if phase == "write":

        def broken(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(run, "_write_eligible", broken)
    else:
        original = pq.ParquetFile.iter_batches

        def interrupted(self, *args, **kwargs):
            iterator = original(self, *args, **kwargs)
            yield next(iterator)
            raise OSError("read interrupted")

        monkeypatch.setattr(pq.ParquetFile, "iter_batches", interrupted)
    report = validate(options)
    assert report["status"] == "FAIL" and Path(report["report_path"]).exists()
    assert_no_dataset(options)


def test_marker_failure_leaves_uncommitted_complete_orphan(options, monkeypatch):
    ingest(options, monkeypatch)
    original = run.publish_manifest

    def failed(path, report):
        if path.name == "validation.json":
            raise OSError("marker publication interrupted")
        return original(path, report)

    monkeypatch.setattr(run, "publish_manifest", failed)
    report = validate(options)
    assert report["status"] == "FAIL" and not report["quality_passed"]
    assert report["execution_status"] == "REJECTED"
    assert report["output"]["status"] == "INCOMPLETE"
    path = output_path(options, report)
    assert path.is_file() and not (path.parent / "validation.json").exists()
    assert not list(options["validated_dir"].rglob(".validation-*"))


def test_publication_race_never_overwrites_competitor(options, monkeypatch):
    ingest(options, monkeypatch)
    original = run.publish_file

    def competitor(source, destination):
        destination.write_bytes(b"competitor")
        original(source, destination)

    monkeypatch.setattr(run, "publish_file", competitor)
    report = validate(options)
    assert report["status"] == "FAIL" and report["output"]["status"] == "INCOMPLETE"
    path = output_path(options, report)
    assert path.read_bytes() == b"competitor"
    assert not (path.parent / "validation.json").exists()


def test_external_report_failure_propagates_without_false_approval(options, monkeypatch):
    ingest(options, monkeypatch)
    original = run.publish_manifest

    def failed(path, report):
        if path.parent.name == "01" and path.name != "validation.json":
            raise OSError("report store unavailable")
        return original(path, report)

    monkeypatch.setattr(run, "publish_manifest", failed)
    with pytest.raises(OSError, match="report store"):
        validate(options)
    markers = list(options["validated_dir"].rglob("validation.json"))
    assert len(markers) == 1
    committed = json.loads(markers[0].read_text())
    assert committed["execution_status"] == "VALIDATED_TEST_ONLY"
    assert not committed["approved_for_training"]


def test_malformed_configuration_persists_error_before_raw_access(options):
    options["config_path"].write_text("{")
    report = validate(options)
    assert report["status"] == "FAIL" and report["scan_scope"] == "NOT_STARTED"
    assert Path(report["report_path"]).exists()
    assert not options["raw_dir"].exists()


def test_repeated_run_keeps_previous_artifacts_and_ingestion_skip(options, monkeypatch):
    _, _, _, calls = ingest(options, monkeypatch)
    first = validate(options)
    path = output_path(options, first)
    before = path.read_bytes(), (path.parent / "validation.json").read_bytes()
    assert download.ingest(2024, 1, raw_dir=options["raw_dir"])["status"] == "SKIPPED"
    second = validate(options)
    assert first["validation_id"] != second["validation_id"]
    assert before == (path.read_bytes(), (path.parent / "validation.json").read_bytes())
    assert len(calls) == 1
    assert len(list(options["report_dir"].rglob("*.json"))) == 2


def test_existing_ingestion_lock_is_preserved(options, monkeypatch):
    _, _, result, _ = ingest(options, monkeypatch)
    lock = Path(result["data_path"]).parent / ".ingestion.lock"
    lock.write_text("another process")
    report = validate(options)
    assert report["status"] == "FAIL" and lock.read_text() == "another process"
    assert not list(options["validated_dir"].rglob("*.parquet"))


@pytest.mark.parametrize("batch_size", [0, True, 65_537])
def test_invalid_arguments_have_no_output_side_effects(options, batch_size):
    options["batch_size"] = batch_size
    with pytest.raises(ValueError):
        validate(options)
    assert not options["report_dir"].exists()


def test_overlapping_roots_are_rejected_before_writes(options):
    options["validated_dir"] = options["raw_dir"] / "output"
    with pytest.raises(ValueError, match="separados"):
        validate(options)
    assert not options["report_dir"].exists()


def test_cli_help_success_and_controlled_failure(options, monkeypatch, tmp_path):
    ingest(options, monkeypatch)
    command = [sys.executable, "-I", "-m", "src.validation.run"]
    help_result = subprocess.run(
        command + ["--help"], capture_output=True, text=True, cwd=tmp_path, timeout=30
    )
    assert help_result.returncode == 0 and "--test-only" in help_result.stdout
    args = [
        "--year",
        "2024",
        "--month",
        "01",
        "--raw-dir",
        str(options["raw_dir"]),
        "--validated-dir",
        str(options["validated_dir"]),
        "--report-dir",
        str(options["report_dir"]),
        "--scratch-dir",
        str(options["scratch_dir"]),
        "--config",
        str(options["config_path"]),
        "--batch-size",
        "2",
    ]
    success = subprocess.run(
        command + args + ["--test-only"], capture_output=True, text=True, cwd=tmp_path, timeout=30
    )
    assert success.returncode == 0, success.stderr
    assert json.loads(success.stdout)["execution_status"] == "VALIDATED_TEST_ONLY"
    rejected = subprocess.run(
        command + args, capture_output=True, text=True, cwd=tmp_path, timeout=30
    )
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["status"] == "FAIL"
    assert "rechazada" in rejected.stderr
