"""T12/T13: causalidad, DST, consistencia y serializacion sobre datos sinteticos."""

import copy
from datetime import UTC, datetime, timedelta

import joblib
import numpy as np
import pyarrow as pa
import pytest
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.exceptions import NotFittedError

from src.features.build import (
    CalendarFeatures,
    feature_values,
    make_model_pipeline,
    make_preprocessor,
    prepare_historical,
)
from src.features.schema import FEATURE_COLUMNS, FeatureError, parse_input
from src.features.target import duration_minutes, localize_historical, nyc_zone
from tests.fixtures.factory import make_table


def payload(**changes):
    return {
        "pickup_datetime": "2024-01-01T08:30:00-05:00",
        "pickup_location_id": 161,
        "passenger_count": 2,
        **changes,
    }


@pytest.mark.parametrize(
    "forbidden",
    [
        "dropoff_datetime",
        "tpep_dropoff_datetime",
        "DOLocationID",
        "dropoff_location_id",
        "trip_duration_minutes",
        "target",
        "fare_amount",
        "total_amount",
        "tip_amount",
        "payment_type",
        "tolls_amount",
        "Airport_fee",
        "cbd_congestion_fee",
        "trip_distance",
        "RatecodeID",
        "store_and_fwd_flag",
        "VendorID",
    ],
)
def test_payload_whitelist_blocks_leakage(forbidden):
    with pytest.raises(FeatureError, match="whitelist"):
        parse_input(payload(**{forbidden: 1}))
    assert forbidden not in FEATURE_COLUMNS


@pytest.mark.parametrize(
    "changes",
    [
        {"pickup_datetime": "2024-01-01T08:30:00"},
        {"pickup_datetime": datetime(2024, 1, 1)},
        {"pickup_datetime": "bad"},
        {"pickup_datetime": None},
        {"pickup_location_id": True},
        {"pickup_location_id": 0},
        {"pickup_location_id": -1},
        {"pickup_location_id": "161"},
        {"passenger_count": True},
        {"passenger_count": -1},
        {"passenger_count": 1.5},
    ],
)
def test_invalid_inputs_are_rejected(changes):
    with pytest.raises(FeatureError):
        parse_input(payload(**changes))


def test_calendar_timezone_and_optional_passengers():
    ordinary = feature_values(payload())
    assert ordinary == ("161", 8, 0, 1, 2, 0)
    assert feature_values(payload(pickup_datetime="2024-01-01T13:30:00Z")) == ordinary
    assert feature_values(payload(pickup_datetime="2024-01-01T07:30:00-06:00")) == ordinary
    assert feature_values(payload(passenger_count=None))[-2:] == (0, 1)
    assert feature_values({k: v for k, v in payload().items() if k != "passenger_count"})[-2:] == (
        0,
        1,
    )
    assert feature_values(payload(passenger_count=0))[-2:] == (0, 0)
    assert parse_input(parse_input(payload()).as_dict()) == parse_input(payload())


@pytest.mark.parametrize(
    "start,end,minutes",
    [
        (datetime(2024, 1, 31, 23, 55), datetime(2024, 2, 1, 0, 5), 10),
        (datetime(2024, 3, 10, 1, 55), datetime(2024, 3, 10, 3, 5), 10),
        (datetime(2024, 11, 3, 0, 55), datetime(2024, 11, 3, 2, 5), 130),
        (datetime(2024, 2, 29, 23, 59, 30), datetime(2024, 3, 1), 0.5),
    ],
)
def test_target_is_elapsed_utc_minutes(start, end, minutes):
    assert duration_minutes(start, end) == minutes


@pytest.mark.parametrize(
    "stamp,reason",
    [
        (datetime(2024, 3, 10, 2, 30), "nonexistent_local_time"),
        (datetime(2024, 11, 3, 1, 30), "ambiguous_local_time"),
        (datetime(2025, 3, 9, 2, 30), "nonexistent_local_time"),
        (datetime(2025, 11, 2, 1, 30), "ambiguous_local_time"),
        (None, "missing_timestamp"),
        (datetime(2024, 1, 1, tzinfo=UTC), "invalid_historical_time"),
    ],
)
def test_historical_time_is_not_guessed(stamp, reason):
    with pytest.raises(FeatureError) as error:
        localize_historical(stamp)
    assert error.value.reason == reason


@pytest.mark.parametrize("end", [datetime(2024, 1, 1, 8), datetime(2024, 1, 1, 7, 59)])
def test_nonpositive_targets_rejected(end):
    with pytest.raises(FeatureError) as error:
        duration_minutes(datetime(2024, 1, 1, 8), end)
    assert error.value.reason == "nonpositive_duration"


def test_explicit_offsets_disambiguate_inference():
    first = parse_input(payload(pickup_datetime="2024-11-03T01:30:00-04:00"))
    second = parse_input(payload(pickup_datetime="2024-11-03T01:30:00-05:00"))
    assert first.pickup_datetime.astimezone(nyc_zone()).fold == 0
    assert second.pickup_datetime.astimezone(nyc_zone()).fold == 1
    assert feature_values(first) == feature_values(second)


def test_historical_serving_same_features_and_label_context_separate():
    table = make_table()
    prepared = prepare_historical(table)
    assert len(prepared.examples) == 12 and not prepared.excluded
    source_rows = table.to_pylist()
    for example, row in zip(prepared.examples, source_rows, strict=True):
        request = example.request.as_dict()
        assert feature_values(request) == feature_values(example.request)
        assert (
            example.target_minutes
            == (row["tpep_dropoff_datetime"] - row["tpep_pickup_datetime"]).total_seconds() / 60
        )
        assert example.label_event_at_utc > example.pickup_utc
        assert "trip_duration_minutes" not in request
    without_optional = prepare_historical(table.drop_columns(["passenger_count", "DOLocationID"]))
    assert all(feature_values(ex.request)[-1] == 1 for ex in without_optional.examples)


def test_future_and_money_changes_do_not_change_X():
    original = make_table()
    prepared = prepare_historical(original)
    changed = original
    for name in ("fare_amount", "total_amount", "tip_amount", "trip_distance"):
        changed = changed.set_column(
            changed.schema.get_field_index(name), name, pa.array([999.0] * 12)
        )
    changed = changed.set_column(
        changed.schema.get_field_index("DOLocationID"),
        "DOLocationID",
        pa.array([1] * 12, type=pa.int32()),
    )
    changed = changed.set_column(
        changed.schema.get_field_index("tpep_dropoff_datetime"),
        "tpep_dropoff_datetime",
        pa.array(
            [
                value + timedelta(minutes=5)
                for value in original["tpep_dropoff_datetime"].to_pylist()
            ],
            type=pa.timestamp("us"),
        ),
    )
    changed = changed.append_column("trip_duration_minutes", pa.array([999999.0] * 12))
    result = prepare_historical(changed)
    assert [ex.request for ex in prepared.examples] == [ex.request for ex in result.examples]
    assert original.column("fare_amount").to_pylist() == [10.0] * 12
    assert [ex.target_minutes for ex in result.examples] == [
        ex.target_minutes + 5 for ex in prepared.examples
    ]


def test_quarantine_reasons_and_source_alignment():
    table = make_table("invalid_passengers")
    values = table["tpep_pickup_datetime"].to_pylist()
    values[1] = datetime(2024, 11, 3, 1, 30)
    table = table.set_column(
        table.schema.get_field_index("tpep_pickup_datetime"),
        "tpep_pickup_datetime",
        pa.array(values, type=pa.timestamp("us")),
    )
    prepared = prepare_historical(table, start_index=100)
    assert prepared.excluded == (
        {"source_row_index": 100, "reason": "invalid_passengers"},
        {"source_row_index": 101, "reason": "ambiguous_local_time"},
    )
    assert prepared.examples[0].source_row_index == 102


def test_encoder_fit_only_train_unknown_does_not_expand_vocabulary():
    train = [payload(), payload(pickup_datetime="2024-01-02T08:30:00-05:00")]
    valid = [payload(pickup_location_id=236, passenger_count=None)]
    original = copy.deepcopy(train)
    pipeline = make_preprocessor()
    encoded = pipeline.fit_transform(train)
    categories = pipeline["encoding"].named_transformers_["origin"].categories_[0].copy()
    transformed = pipeline.transform(valid)
    assert categories.tolist() == ["161"]
    assert pipeline["encoding"].named_transformers_["origin"].categories_[0].tolist() == ["161"]
    assert transformed.shape[1] == encoded.shape[1] == 6
    assert transformed.dtype == np.float32 and transformed[0, 0] == 0
    assert transformed[0, -2:].tolist() == [0, 1]
    assert train == original
    assert pipeline.get_feature_names_out().tolist() == [
        "pickup_location_id_161",
        "pickup_hour",
        "pickup_weekday",
        "pickup_month",
        "passenger_count",
        "passenger_count_missing",
    ]


def test_preprocessor_is_cloneable_and_requires_fit():
    cloned = clone(make_preprocessor())
    with pytest.raises(NotFittedError):
        cloned.transform([payload()])
    assert CalendarFeatures().get_feature_names_out().tolist() == list(FEATURE_COLUMNS)


def test_model_and_preprocessor_roundtrip_together(tmp_path):
    table = prepare_historical(make_table())
    inputs = [ex.request.as_dict() for ex in table.examples]
    y = np.array([ex.target_minutes for ex in table.examples])
    estimator = DummyRegressor()
    pipeline = make_model_pipeline(estimator)
    pipeline.fit(inputs, y)
    assert not hasattr(estimator, "constant_")  # Se ajusto el clon, no el objeto del llamador.
    before = pipeline.predict(inputs)
    path = tmp_path / "fixture-pipeline.joblib"
    joblib.dump(pipeline, path)
    loaded = joblib.load(path)  # Solo el artefacto local confiable creado en este test.
    np.testing.assert_array_equal(loaded.predict(inputs), before)
    np.testing.assert_array_equal(
        loaded["features"].transform(inputs), pipeline["features"].transform(inputs)
    )


def test_extreme_passenger_value_fails_instead_of_inf():
    with pytest.raises(FeatureError):
        make_preprocessor().fit_transform([payload(passenger_count=10**1000)])
