"""T16 sobre fixtures: fit causal completo, serializacion y fallos sin publicacion."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.features.artifacts import build_validated_features
from src.training.models import feature_matrix, predict_matrix
from src.training.train import train_candidates
from tests.fixtures.factory import make_table
from tests.integration.test_feature_pipeline import validated_fixture
from tests.integration.test_temporal_split_pipeline import make_catalog, run


def prepared(tmp_path, *, large_train=False):
    catalog = make_catalog(tmp_path / "inputs")
    if large_train:
        original = make_table()
        template = original.to_pylist()[0]
        rows = []
        for index in range(6000):
            pickup = datetime(2024, 12, 1, 8) + timedelta(seconds=index)
            rows.append(
                {
                    **template,
                    "tpep_pickup_datetime": pickup,
                    "tpep_dropoff_datetime": pickup + timedelta(minutes=1 + index % 10),
                }
            )
        validated = validated_fixture(
            tmp_path / "larger",
            pa.Table.from_pylist(rows, schema=original.schema),
            year=2024,
            month=12,
        )
        feature = build_validated_features(
            validated, processed_dir=tmp_path / "larger-features", test_only=True
        )
        inputs = json.loads(catalog.read_text())
        inputs["batches"][0].update(
            features_directory=feature["output_directory"], validated_directory=str(validated)
        )
        catalog.write_text(json.dumps(inputs))
    split = run(catalog, tmp_path / "preparation", batch_size=3)
    assert split["status"] == "SPLIT_TEST_ONLY", split.get("error")
    return Path(split["output_directory"]), split


def train(source, tmp_path, **kwargs):
    return train_candidates(
        source,
        output_dir=tmp_path / "models",
        report_dir=tmp_path / "reports",
        test_only=True,
        **kwargs,
    )


def test_full_train_and_serialized_pipeline_without_future_access(tmp_path, monkeypatch):
    source, split = prepared(tmp_path, large_train=True)
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if any(
            path.resolve().is_relative_to(source / part)
            for part in ("validation", "test", "monitoring_replay")
        ):
            pytest.fail(f"No abrir futuro durante fit: {path.name}")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    result = train(source, tmp_path)
    assert result["status"] == "TRAINING_TEST_ONLY", result.get("error")
    assert result["publication_complete"] and not result["approved_for_serving"]
    assert not result["validation_accessed"] and not result["test_accessed"]
    expected = split["partitions"]["train"]["rows"]
    assert result["preprocessing"]["scaler_fit_rows"] == expected
    assert result["preprocessing"]["vocabulary_observation_rows"] == expected
    folder = Path(result["output_directory"])
    assert json.loads((folder / "training_manifest.json").read_text()) == result
    with pq.ParquetFile(source / "train/features.parquet") as parquet:
        Xb = next(parquet.iter_batches())
    with pq.ParquetFile(source / "train/context.parquet") as parquet:
        context = next(parquet.iter_batches())
    X = feature_matrix(Xb)
    expected_categories = sorted(str(value) for value in np.unique(X[:, 0]))
    assert result["preprocessing"]["origin_categories"] == expected_categories
    payloads = [
        {
            "pickup_location_id": int(row[0]),
            "pickup_datetime": context.column(1)[i].as_py(),
            "passenger_count": None if row[5] else int(row[4]),
        }
        for i, row in enumerate(X)
    ]
    for name in ("sgd", "mlp"):
        model = joblib.load(folder / f"{name}.joblib")
        assert model.named_steps["estimator"].rows_fitted_ == expected
        assert result["models"][name]["epochs"] == 1
        assert result["models"][name]["blocks"] == 2
        assert model.named_steps["estimator"].estimator_.t_ == expected + (name == "sgd")
        predicted, clipped = predict_matrix(model, X)
        np.testing.assert_allclose(predicted, model.predict(payloads), rtol=1e-6)
        assert np.all(np.isfinite(predicted) & (predicted >= 1 / 60) & (predicted <= 180))
        assert 0 <= clipped <= expected
        before = model.named_steps["scaling"].n_samples_seen_
        assert before == expected
        assert (
            model.named_steps["features"]
            .named_steps["encoding"]
            .named_transformers_["origin"]
            .categories_[0]
            .tolist()
            == expected_categories
        )
        unknown = [{**payloads[0], "pickup_location_id": 999}]
        assert np.isfinite(model.predict(unknown)).all()
        assert model.named_steps["scaling"].n_samples_seen_ == before


def test_fixture_cannot_be_used_as_real_training(tmp_path, monkeypatch):
    source, _ = prepared(tmp_path)
    monkeypatch.setattr("src.training.train.CandidateGuard.check", lambda *a, **k: None)
    result = train_candidates(
        source, output_dir=tmp_path / "models", report_dir=tmp_path / "reports"
    )
    assert result["status"] == "FAIL"
    assert not list((tmp_path / "models").rglob("training_manifest.json"))


def test_resource_failure_during_fit_does_not_publish_complete_model(tmp_path, monkeypatch):
    source, _ = prepared(tmp_path)
    original = (source / "split_manifest.json").read_bytes()
    from src.training import train as module
    from src.training.resources import ResourceLimitError

    def fail(*args, **kwargs):
        raise ResourceLimitError("controlled limit during candidate")

    monkeypatch.setattr(module, "estimator", fail)
    result = train(source, tmp_path)
    assert result["status"] == "FAIL" and not result["publication_complete"]
    assert "controlled limit" in result["error"]
    assert not list((tmp_path / "models").rglob("training_manifest.json"))
    assert not list((tmp_path / "models/_test_only").glob(".train-*"))
    assert (source / "split_manifest.json").read_bytes() == original


def test_altered_train_is_rejected_before_preprocessing(tmp_path, monkeypatch):
    source, _ = prepared(tmp_path)
    file = source / "train/features.parquet"
    with file.open("ab") as stream:
        stream.write(b"tampered")
    monkeypatch.setattr(
        "src.training.train.fit_preprocessing",
        lambda *a, **k: pytest.fail("No fit de entradas alteradas"),
    )
    result = train(source, tmp_path)
    assert result["status"] == "FAIL" and not result["publication_complete"]
