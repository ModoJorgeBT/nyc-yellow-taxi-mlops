"""Evaluacion del baseline congelado: no reajusta ni abre test/replay."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.training import baseline, baseline_evaluate, baseline_fit, resources
from tests.integration.test_temporal_split_pipeline import make_catalog


def inputs(tmp_path):
    catalog = make_catalog(tmp_path, durations={(2025, 3): 30, (2025, 6): 100, (2025, 12): 100})
    entries = json.loads(catalog.read_text())["batches"]
    train = tmp_path / "train.json"
    validation = tmp_path / "validation.json"
    train.write_text(
        json.dumps({"format_version": 1, "batches": [e for e in entries if e["year"] == 2024]})
    )
    validation.write_text(
        json.dumps(
            {
                "format_version": 1,
                "batches": [e for e in entries if e["year"] == 2025 and e["month"] == 3],
            }
        )
    )
    fitted = baseline_fit.fit_baseline(
        train,
        output_dir=tmp_path / "fits",
        report_dir=tmp_path / "fit_reports",
        scratch_dir=tmp_path / "scratch",
        test_only=True,
        batch_size=2,
    )
    assert fitted["fit_complete"], fitted.get("error")
    return Path(fitted["output_directory"]), validation


def run(fit, catalog, tmp_path, **kwargs):
    return baseline_evaluate.evaluate_fit(
        fit,
        catalog,
        output_dir=tmp_path / "evaluated",
        report_dir=tmp_path / "evaluation_reports",
        test_only=True,
        **kwargs,
    )


def test_frozen_fit_validation_only_metrics_and_aligned_artifacts(tmp_path, monkeypatch):
    fit, catalog = inputs(tmp_path)
    before = {p.name: p.read_bytes() for p in fit.iterdir()}
    original = pq.ParquetFile

    def permitted(path, *args, **kwargs):
        parts = Path(getattr(path, "name", path)).parts
        assert not any(p in ("test", "monitoring_replay", "2025-6", "2025-12") for p in parts)
        if "2025" in parts:
            assert parts[parts.index("2025") + 1] == "03"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(pq, "ParquetFile", permitted)

    def forbidden(*args, **kwargs):
        pytest.fail("No reajustar la mediana")

    monkeypatch.setattr(baseline, "exact_disk_median", forbidden)
    monkeypatch.setattr(baseline_fit, "exact_disk_median", forbidden)
    first = run(fit, catalog, tmp_path, batch_size=2)
    assert first["status"] == "BASELINE_TEST_ONLY", first.get("error")
    assert first["evaluation_status"] == "COMPLETE_VALIDATION" and first["fit_reused"]
    assert first["validation_rows"] == 11 and first["counts"]["label_not_available_at_cutoff"] == 1
    assert first["model"]["prediction_minutes"] == 10
    assert first["validation_metrics"] == {"mae_minutes": 20.0, "rmse_minutes": 20.0}
    assert not any(
        first[k]
        for k in (
            "test_accessed",
            "monitoring_replay_accessed",
            "t14_complete",
            "t15_complete",
            "approved_for_serving",
            "model_registered",
        )
    )
    folder = Path(first["output_directory"])
    with original(folder / "validation_predictions.parquet") as parquet:
        rows = parquet.read().to_pydict()
    assert rows == {
        "validation_row_index": list(range(11)),
        "predicted_duration_minutes": [10.0] * 11,
    }
    assert all(item["row_count"] == 11 for item in first["artifacts"].values())
    second = run(fit, catalog, tmp_path, batch_size=7)
    assert second["status"] == first["status"], second.get("error")
    assert (
        second["model"] == first["model"]
        and second["validation_metrics"] == first["validation_metrics"]
    )
    assert second["validation_logical_sha256"] == first["validation_logical_sha256"]
    assert before == {p.name: p.read_bytes() for p in fit.iterdir()}


@pytest.mark.parametrize(
    "change", ["model", "target", "marker", "resigned_wrong_median", "future_month"]
)
def test_altered_or_out_of_scope_inputs_are_rejected(tmp_path, change):
    fit, catalog = inputs(tmp_path)
    if change == "model":
        (fit / "model.json").write_text("{}")
    elif change == "target":
        (fit / "train_target.parquet").write_bytes(b"bad")
    elif change == "marker":
        (fit / "fit_manifest.json").unlink()
    elif change == "resigned_wrong_median":
        path = fit / "model.json"
        model = json.loads(path.read_text())
        model["prediction_minutes"] = 30.0
        path.write_text(json.dumps(model))
        marker = fit / "fit_manifest.json"
        doc = json.loads(marker.read_text())
        doc["model"] = model
        doc["model_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        marker.write_text(json.dumps(doc))
    else:
        doc = json.loads(catalog.read_text())
        doc["batches"][0]["month"] = 6
        catalog.write_text(json.dumps(doc))
    report = run(fit, catalog, tmp_path)
    assert report["status"] == "FAIL" and not report["publication_complete"]
    assert not list((tmp_path / "evaluated").rglob("baseline_manifest.json"))


def test_real_requires_all_three_validation_months_before_opening_fit(tmp_path, monkeypatch):
    fit, catalog = inputs(tmp_path)
    monkeypatch.setattr(
        baseline_evaluate, "verify_fit", lambda *a, **k: pytest.fail("Validation incompleta")
    )
    report = baseline_evaluate.evaluate_fit(
        fit, catalog, output_dir=tmp_path / "evaluated", report_dir=tmp_path / "reports"
    )
    assert report["status"] == "FAIL" and "Faltan meses" in report["error"]


@pytest.mark.parametrize("change", ["source", "fit", "catalog"])
def test_changes_during_evaluation_fail_before_completion(tmp_path, monkeypatch, change):
    fit, catalog = inputs(tmp_path)
    original = baseline_evaluate._source_rows

    def mutate(*args, **kwargs):
        yield from original(*args, **kwargs)
        if change == "fit":
            path = fit / "fit_manifest.json"
        elif change == "catalog":
            path = catalog
        else:
            entry = json.loads(catalog.read_text())["batches"][0]
            path = Path(entry["features_directory"]) / "features_manifest.json"
        doc = json.loads(path.read_text())
        doc["changed"] = True
        path.write_text(json.dumps(doc))

    monkeypatch.setattr(baseline_evaluate, "_source_rows", mutate)
    report = run(fit, catalog, tmp_path)
    assert report["status"] == "FAIL" and not report["publication_complete"]
    assert not list((tmp_path / "evaluated").rglob(".evaluate-*"))


@pytest.mark.parametrize("failure", ["resource", "publish"])
def test_failure_preserves_fit_and_publishes_no_marker(tmp_path, monkeypatch, failure):
    fit, catalog = inputs(tmp_path)
    before = (fit / "fit_manifest.json").read_bytes()

    def fail(*args, **kwargs):
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(
        resources.ResourceGuard, "check", fail
    ) if failure == "resource" else monkeypatch.setattr(baseline_evaluate, "publish_file", fail)
    report = run(fit, catalog, tmp_path)
    assert report["status"] == "FAIL" and not report["publication_complete"]
    assert (fit / "fit_manifest.json").read_bytes() == before
    assert not list((tmp_path / "evaluated").rglob("baseline_manifest.json"))


def test_installed_evaluation_cli(tmp_path):
    fit, catalog = inputs(tmp_path)
    command = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "src.training.baseline_evaluate",
        "--fit-batch",
        str(fit),
        "--inputs",
        str(catalog),
        "--output-dir",
        str(tmp_path / "evaluated"),
        "--report-dir",
        str(tmp_path / "reports"),
        "--test-only",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["evaluation_status"] == "COMPLETE_VALIDATION"
