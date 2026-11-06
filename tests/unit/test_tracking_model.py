"""Contrato tabular y verificacion de bytes sin dependencia MLflow obligatoria."""

import hashlib
import json

import numpy as np
import pytest

from src.features.schema import FeatureError
from src.training.tracking import EXAMPLE, local_path
from src.training.tracking_model import FrozenPredictor, canonical_records


def test_optional_passengers_table_representation():
    records = [
        dict(EXAMPLE[0], passenger_count=float("nan")),
        dict(EXAMPLE[0], passenger_count=np.float64(2)),
        dict(EXAMPLE[0], pickup_location_id=np.int64(161)),
    ]
    result = canonical_records(records)
    assert [x["passenger_count"] for x in result] == [None, 2, None]
    assert type(result[2]["pickup_location_id"]) is int


@pytest.mark.parametrize(
    "change",
    [
        {"pickup_datetime": "2026-01-12T08:30:00"},
        {"DOLocationID": 237},
        {"pickup_location_id": 161.0},
        {"pickup_location_id": True},
        {"passenger_count": 1.5},
        {"passenger_count": True},
        {"passenger_count": -1},
    ],
)
def test_table_adapter_rejects_invalid_or_future_information(change):
    with pytest.raises(FeatureError):
        canonical_records([{**EXAMPLE[0], **change}])


def test_baseline_checks_hash_and_validates_the_same_input(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"kind": "exact_global_train_median", "prediction_minutes": 12.0}))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    model = FrozenPredictor("baseline", path, sha)
    np.testing.assert_array_equal(model.predict(EXAMPLE), [12, 12])
    with pytest.raises(FeatureError):
        model.predict([{**EXAMPLE[0], "fare_amount": 5}])
    path.write_text("{}")
    with pytest.raises(ValueError, match="alterado"):
        FrozenPredictor("baseline", path, sha)


def test_local_lineage_cannot_escape_root(tmp_path):
    with pytest.raises(ValueError):
        local_path(tmp_path, "../outside.json")
