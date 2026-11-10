import json
from datetime import datetime, timedelta

import numpy as np
import pyarrow as pa
import pytest

from src.features.artifacts import build_validated_features
from src.retraining.cohorts import prepare
from src.retraining.evaluation import evaluate_pair
from src.retraining.train_challenger import train
from src.validation.run import _sha256
from tests.fixtures.factory import make_table
from tests.integration.test_feature_pipeline import validated_fixture
from tests.integration.test_retraining_cohorts import prepared
from tests.integration.test_retraining_training import trigger


def final_catalog(root, months=(4, 5, 6)):
    entries = []
    base = make_table().to_pylist()[0]
    for month in months:
        pickup = datetime(2026, month, 15, 8)
        rows = [
            {
                **base,
                "tpep_pickup_datetime": pickup + timedelta(minutes=i),
                "tpep_dropoff_datetime": pickup + timedelta(minutes=10 + i),
            }
            for i in range(4)
        ]
        valid = validated_fixture(
            root / f"future-valid-{month}",
            pa.Table.from_pylist(rows, schema=make_table().schema),
            year=2026,
            month=month,
        )
        result = build_validated_features(
            valid, processed_dir=root / f"future-features-{month}", test_only=True
        )
        entries.append(
            {
                "year": 2026,
                "month": month,
                "features_directory": result["output_directory"],
                "validated_directory": str(valid),
            }
        )
    catalog = root / "future-catalog.json"
    catalog.write_text(json.dumps({"batches": entries}), encoding="utf-8")
    return catalog


def test_full_fixture_pair_final_reserved_once_no_fit_or_champion_change(tmp_path):
    config, catalog, profile = prepared(tmp_path)
    cohort, _ = prepare(catalog, "train", profile_path=config, root=tmp_path, test_only=True)
    trained, result = train(
        cohort, trigger(tmp_path, profile), profile_path=config, root=tmp_path, test_only=True
    )
    assert result["publication_complete"], result.get("error")
    training = {
        "path": str((trained / "training_manifest.json").relative_to(tmp_path)),
        "sha256": _sha256(trained / "training_manifest.json"),
    }
    future, _ = prepare(
        final_catalog(tmp_path), "final", profile_path=config, root=tmp_path, test_only=True
    )
    fixture = {
        "champion": (lambda X: (np.full(len(X), 12.0), 0), {"scope": "synthetic"}, lambda: None),
        "smoke_payloads": [
            {
                "pickup_datetime": "2026-02-15T08:00:00-05:00",
                "pickup_location_id": 1,
                "passenger_count": 1,
            }
        ],
    }
    output, evaluated = evaluate_pair(
        future,
        "final",
        training,
        profile_path=config,
        root=tmp_path,
        test_only=True,
        prediction_fixture=fixture,
    )
    assert evaluated["publication_complete"], evaluated.get("error")
    assert evaluated["metrics"]["champion"]["all"]["mae_minutes"] == 2
    assert evaluated["metrics"]["challenger"]["all"]["mae_minutes"] == 0
    assert evaluated["controls"]["same_population_verified"]
    assert not evaluated["champion_changed"] and not evaluated["models_fitted"]
    assert all(not p["labels_read_for_prediction"] for p in evaluated["predictions"].values())
    assert (output / "frozen-before-predictions.json").exists()
    with pytest.raises(FileExistsError):
        evaluate_pair(
            future,
            "final",
            training,
            profile_path=config,
            root=tmp_path,
            test_only=True,
            prediction_fixture=fixture,
        )
