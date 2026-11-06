"""Proceso nativo y Pipeline reales; jamás se abre test/replay para la extensión."""

import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq
import pytest

from src.evaluation.lightgbm_run import evaluate_lightgbm
from src.evaluation.run import evaluate_models
from src.training.baseline import run_baseline
from src.training.lightgbm_train import train_lightgbm
from src.training.models import feature_matrix
from src.training.train import train_candidates
from src.validation.run import _sha256
from tests.integration.test_candidates import prepared


@pytest.fixture(scope="module")
def extension(tmp_path_factory):
    root = tmp_path_factory.mktemp("lightgbm-á")
    source, split = prepared(root, large_train=True)
    original_train = train_candidates(
        source,
        output_dir=root / "old-models",
        report_dir=root / "old-reports",
        test_only=True,
    )
    baseline = run_baseline(
        source,
        output_dir=root / "baseline",
        report_dir=root / "baseline-reports",
        scratch_dir=root / "median",
        test_only=True,
    )
    original = evaluate_models(
        source,
        Path(original_train["output_directory"]),
        Path(baseline["output_directory"]),
        output_dir=root / "original",
        report_dir=root / "original-reports",
        scratch_dir=root / "errors",
        test_only=True,
    )
    assert original["publication_complete"], original.get("error")
    return root, source, split, original


def test_full_native_train_pipeline_and_validation_only(extension, monkeypatch):
    root, source, split, original = extension
    actual_open = Path.open
    forbidden = ("validation", "test", "monitoring_replay")

    def guarded_open(path, *args, **kwargs):
        if any(path.resolve().is_relative_to(source / p) for p in forbidden):
            pytest.fail(f"Acceso futuro no aprobado: {path}")
        return actual_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    trained = train_lightgbm(
        source,
        output_dir=root / "native-model",
        report_dir=root / "native-fit-reports",
        test_only=True,
    )
    assert trained["publication_complete"], trained.get("error")
    assert trained["status"] == "LIGHTGBM_TRAINING_TEST_ONLY"
    assert trained["native"]["range_rows"] == trained["native"]["dataset_rows"] == 6000
    assert trained["native"]["target_sha256"] == trained["learned"]["target_sha256"]
    assert trained["learned"]["blocks"] == 2
    assert trained["learned"]["vocabulary_observation_rows"] == 6000
    assert 0 < trained["native"]["bin_sample_rows"] <= 6000
    assert trained["resources"]["native_peak_rss_bytes"] < 4 * 2**30
    assert trained["resources"]["worker_pid_verified"] is True
    assert trained["resources"]["worker_pid"] > 0
    assert not any(
        trained[k]
        for k in (
            "validation_accessed",
            "test_accessed",
            "monitoring_replay_accessed",
            "approved_for_serving",
        )
    )
    folder = Path(trained["output_directory"])
    model = joblib.load(folder / "lightgbm.joblib")
    X = feature_matrix(pq.read_table(source / "train/features.parquet"))
    context = pq.read_table(source / "train/context.parquet")
    payload = [
        dict(
            pickup_location_id=int(row[0]),
            pickup_datetime=context.column(1)[i].as_py(),
            passenger_count=None if row[5] else int(row[4]),
        )
        for i, row in enumerate(X[:10])
    ]
    fast = model.named_steps["estimator"].predict(model.named_steps["native"].transform(X[:10]))
    np.testing.assert_allclose(fast, model.predict(payload), atol=1e-12)
    with pytest.raises(ValueError):
        model.predict([{**payload[0], "dropoff_datetime": "future"}])
    categories = model.named_steps["native"].categories_.tolist()
    assert categories == sorted(int(v) for v in np.unique(X[:, 0]))
    forbidden = ("test", "monitoring_replay")
    original_dir = Path(original["output_directory"])
    frozen = {
        name: _sha256(original_dir / name)
        for name in ("selection.json", "evaluation_manifest.json")
    }
    evaluated = evaluate_lightgbm(
        source,
        folder,
        original_dir,
        output_dir=root / "extension-eval",
        report_dir=root / "extension-reports",
        test_only=True,
    )
    assert evaluated["publication_complete"], evaluated.get("error")
    assert evaluated["validation_rows"] == split["partitions"]["validation"]["rows"]
    assert not evaluated["test_accessed"] and not evaluated["monitoring_replay_accessed"]
    assert not evaluated["original_selection_changed"]
    assert evaluated["new_independent_final_evaluation"] == "PENDING"
    assert frozen == {name: _sha256(original_dir / name) for name in frozen}
    prediction = pq.read_table(Path(evaluated["output_directory"]) / "validation.parquet")
    target = pq.read_table(source / "validation/target.parquet").column(0).to_numpy()
    error = np.abs(target - prediction.column(1).to_numpy())
    metrics = evaluated["metrics"]["all"]
    assert metrics["mae_minutes"] == pytest.approx(error.mean())
    assert metrics["medae_minutes"] == pytest.approx(np.quantile(error, 0.5, method="linear"))
    assert metrics["p90_absolute_error_minutes"] == pytest.approx(
        np.quantile(error, 0.9, method="linear")
    )
    assert (
        json.loads((Path(evaluated["output_directory"]) / "evaluation_manifest.json").read_text())
        == evaluated
    )
    altered = root / "tampered-model" / folder.name
    shutil.copytree(folder, altered)
    with (altered / "lightgbm.joblib").open("ab") as stream:
        stream.write(b"tampered")
    rejected = evaluate_lightgbm(
        source,
        altered,
        original_dir,
        output_dir=root / "rejected-eval",
        report_dir=root / "rejected-reports",
        test_only=True,
    )
    assert rejected["status"] == "FAIL" and not rejected["publication_complete"]
    assert "ajuste aprobado" in rejected["error"]
    altered_original = root / "tampered-original" / original_dir.name
    shutil.copytree(original_dir, altered_original)
    with (altered_original / "selection.json").open("a") as stream:
        stream.write(" ")
    rejected = evaluate_lightgbm(
        source,
        folder,
        altered_original,
        output_dir=root / "rejected-original-eval",
        report_dir=root / "rejected-original-reports",
        test_only=True,
    )
    assert rejected["status"] == "FAIL" and not rejected["publication_complete"]
    assert "original alterada" in rejected["error"]


def test_native_failure_never_publishes_model(extension, tmp_path, monkeypatch):
    from src.training import lightgbm_train

    def fail(*args, **kwargs):
        raise RuntimeError("native failure")

    monkeypatch.setattr(lightgbm_train, "run_worker", fail)
    result = train_lightgbm(
        extension[1],
        output_dir=tmp_path / "models",
        report_dir=tmp_path / "reports",
        test_only=True,
    )
    assert result["status"] == "FAIL" and not result["publication_complete"]
    assert not list((tmp_path / "models").rglob("training_manifest.json"))


def test_real_requires_original_audit_before_prediction(extension, tmp_path):
    from src.evaluation.lightgbm_run import original_comparison

    original = extension[3]
    directory = Path(original["output_directory"])
    with pytest.raises(ValueError):
        original_comparison(
            directory,
            audit_path=None,
            split_sha256=original["source_split_sha256"],
            test_only=False,
        )
