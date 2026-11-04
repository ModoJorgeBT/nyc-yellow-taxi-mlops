"""T14 -> T15 con fixtures; test permanece sellado para el baseline."""

import json
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.training import baseline
from src.training.split import prepare_splits
from tests.integration.test_temporal_split_pipeline import make_catalog


def split_fixture(tmp_path, *, durations=None):
    catalog = make_catalog(tmp_path, durations=durations)
    report = prepare_splits(
        catalog,
        output_dir=tmp_path / "splits",
        report_dir=tmp_path / "split_reports",
        test_only=True,
        batch_size=2,
    )
    assert report["status"] == "SPLIT_TEST_ONLY", report.get("error")
    return Path(report["output_directory"])


def run(source, tmp_path, **kwargs):
    return baseline.run_baseline(
        source,
        output_dir=tmp_path / "baselines",
        report_dir=tmp_path / "baseline_reports",
        scratch_dir=tmp_path / "scratch",
        test_only=True,
        **kwargs,
    )


def test_train_only_median_positive_predictions_and_no_test_access(tmp_path, monkeypatch):
    source = split_fixture(tmp_path, durations={(2025, 3): 30, (2025, 6): 100})
    original = pq.ParquetFile
    opened = []

    def permitted(path, *args, **kwargs):
        text = Path(getattr(path, "name", path))
        assert "test" not in text.parts and "monitoring_replay" not in text.parts
        opened.append(text)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pq, "ParquetFile", permitted)
    first = run(source, tmp_path, batch_size=2)
    assert first["status"] == "BASELINE_TEST_ONLY", first.get("error")
    second = run(source, tmp_path, batch_size=7)
    assert second["status"] == "BASELINE_TEST_ONLY", second.get("error")
    assert first["model"] == second["model"]
    assert first["model_sha256"] == second["model_sha256"]
    assert first["model"]["prediction_minutes"] == 10.0
    assert first["learned"]["train_rows"] == first["validation_rows"] == 11
    assert first["validation_metrics"] == {"mae_minutes": 20.0, "rmse_minutes": 20.0}
    assert first["test_accessed"] is False and not first["approved_for_serving"]
    with original(
        Path(first["output_directory"]) / "validation_predictions.parquet"
    ) as predictions:
        values = predictions.read().to_pydict()
    assert values["validation_row_index"] == list(range(11))
    assert values["predicted_duration_minutes"] == [10.0] * 11
    assert (
        json.loads((Path(first["output_directory"]) / "baseline_manifest.json").read_text())
        == first
    )
    assert not list((tmp_path / "scratch").glob("median-*"))
    assert opened


@pytest.mark.parametrize("case", ["missing_marker", "changed_target", "wrong_scope", "incomplete"])
def test_invalid_split_blocked_before_baseline_publication(tmp_path, case):
    source = split_fixture(tmp_path)
    marker = source / "split_manifest.json"
    if case == "missing_marker":
        marker.unlink()
    elif case == "changed_target":
        (source / "train/target.parquet").write_bytes(b"tampered")
    else:
        report = json.loads(marker.read_text())
        report["mode" if case == "wrong_scope" else "publication_complete"] = (
            "REAL" if case == "wrong_scope" else False
        )
        marker.write_text(json.dumps(report))
    report = run(source, tmp_path)
    assert report["status"] == "FAIL" and not report["publication_complete"]
    assert not list((tmp_path / "baselines").rglob("baseline_manifest.json"))


def test_live_resource_abort_cleans_ephemeral_data(tmp_path, monkeypatch):
    source = split_fixture(tmp_path)
    monkeypatch.setattr(
        baseline.ResourceGuard,
        "check",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("D-02 failure")),
    )
    result = run(source, tmp_path)
    assert result["status"] == "FAIL" and "D-02" in result["error"]
    assert not list((tmp_path / "baselines").rglob("baseline_manifest.json"))


def test_baseline_cli_and_model_artifact(tmp_path):
    source = split_fixture(tmp_path)
    command = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "src.training.baseline",
        "--split-batch",
        str(source),
        "--output-dir",
        str(tmp_path / "baseline"),
        "--report-dir",
        str(tmp_path / "baseline_reports"),
        "--scratch-dir",
        str(tmp_path / "scratch"),
        "--test-only",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    assert report["status"] == "BASELINE_TEST_ONLY"
    assert (
        json.loads((Path(report["output_directory"]) / "model.json").read_text())[
            "prediction_minutes"
        ]
        == 10
    )
