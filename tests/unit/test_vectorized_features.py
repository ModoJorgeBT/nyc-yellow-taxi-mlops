"""Equivalencia diferencial por horas/minutos de todo 2024/2025 y DST."""

import calendar
from datetime import datetime, timedelta

import pyarrow as pa
import pytest

from src.features.build import feature_values, prepare_historical
from src.features.schema import FEATURE_COLUMNS, FeatureError
from src.features.vectorized import real_tables
from src.training.split import SCHEMAS
from tests.fixtures.factory import make_table


def reference(table, start=7):
    prepared = prepare_historical(table, start_index=start)
    assert not prepared.excluded
    values = {name: [] for name in SCHEMAS}
    for row in prepared.examples:
        values["features"].append(
            dict(zip(FEATURE_COLUMNS, map(int, feature_values(row.request)), strict=True))
        )
        values["target"].append({"trip_duration_minutes": row.target_minutes})
        values["context"].append(
            {
                "validated_row_index": row.source_row_index,
                "pickup_datetime_utc": row.pickup_utc,
                "label_event_datetime_utc": row.label_event_at_utc,
            }
        )
    return {name: pa.Table.from_pylist(rows, schema=SCHEMAS[name]) for name, rows in values.items()}


@pytest.mark.parametrize(
    "year,month",
    [(y, m) for y in (2024, 2025) for m in range(1, 13)] + [(2026, m) for m in (1, 2, 3, 11)],
)
def test_every_day_hour_and_dst_matches_reference_exactly(year, month):
    template = make_table()
    base = template.to_pylist()[0]
    rows = []
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        for hour in range(24):
            for minute in (7, 43):
                pickup = datetime(year, month, day, hour, minute, 17, 123456)
                rows.append(
                    {
                        **base,
                        "tpep_pickup_datetime": pickup,
                        "tpep_dropoff_datetime": pickup
                        + timedelta(minutes=17, seconds=13, microseconds=876),
                        "passenger_count": (None, 0, 1, 6)[len(rows) % 4],
                    }
                )
    if month in (3, 11):
        sundays = [day for day in range(1, 15) if datetime(year, month, day).weekday() == 6]
        day = sundays[1] if month == 3 else sundays[0]
        pickup = datetime(year, month, day, 1 if month == 3 else 0, 55)
        dropoff = datetime(year, month, day, 3 if month == 3 else 2, 5)
        rows.append({**base, "tpep_pickup_datetime": pickup, "tpep_dropoff_datetime": dropoff})
    table = pa.Table.from_pylist(rows, schema=template.schema)
    excluded = {row["source_row_index"] for row in prepare_historical(table).excluded}
    table = pa.Table.from_pylist(
        [row for i, row in enumerate(rows) if i not in excluded], schema=template.schema
    )
    expected = reference(table)
    actual = real_tables(
        table.to_batches()[0], year=year, month=month, start_index=7, schemas=SCHEMAS
    )
    assert all(actual[name].equals(expected[name], check_metadata=True) for name in SCHEMAS)


def test_missing_passengers_and_validation_guards():
    table = make_table().drop_columns(["passenger_count"])
    actual = real_tables(table.to_batches()[0], year=2024, month=1, start_index=7, schemas=SCHEMAS)
    expected = reference(table)
    assert all(actual[name].equals(expected[name]) for name in SCHEMAS)
    with pytest.raises(FeatureError):
        real_tables(table.to_batches()[0], year=2025, month=1, start_index=7, schemas=SCHEMAS)
    with pytest.raises(FeatureError):
        real_tables(
            make_table("null_timestamp").to_batches()[0],
            year=2024,
            month=1,
            start_index=7,
            schemas=SCHEMAS,
        )
