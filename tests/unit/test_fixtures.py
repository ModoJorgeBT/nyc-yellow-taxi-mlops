"""Oraculos independientes para las anomalias conocidas de T04."""

import hashlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from tests.fixtures.factory import CASES, make_table, write_fixtures

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize("case", CASES)
def test_committed_fixture_roundtrip(case: str) -> None:
    table = pq.ParquetFile(FIXTURES / f"{case}.parquet").read()
    assert table.num_rows == 12
    assert table.schema.metadata[b"fixture_origin"] == b"synthetic"
    assert table.equals(make_table(case), check_metadata=True)


def test_valid_historical_contract() -> None:
    table = pq.ParquetFile(FIXTURES / "valid.parquet").read()
    assert table.num_columns == 19
    assert table.schema.field("tpep_pickup_datetime").type == pa.timestamp("us")
    assert table.schema.field("PULocationID").type == pa.int32()
    assert table.schema.field("passenger_count").type == pa.int64()
    for row in table.to_pylist():
        assert row["tpep_dropoff_datetime"] > row["tpep_pickup_datetime"]
        assert row["tpep_pickup_datetime"].month == 1
        assert row["passenger_count"] > 0
        assert row["PULocationID"] == 161
    assert "trip_duration_minutes" not in table.column_names


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("null_zone", 1),
        ("null_timestamp", 1),
        ("nonpositive_duration", 2),
        ("pickup_outside_month", 1),
        ("duplicate", 1),
        ("invalid_passengers", 1),
    ],
)
def test_known_row_anomalies(case: str, expected: int) -> None:
    rows = pq.ParquetFile(FIXTURES / f"{case}.parquet").read().to_pylist()
    if case == "null_zone":
        count = sum(row["PULocationID"] is None for row in rows)
    elif case == "null_timestamp":
        count = sum(row["tpep_dropoff_datetime"] is None for row in rows)
    elif case == "nonpositive_duration":
        count = sum(row["tpep_dropoff_datetime"] <= row["tpep_pickup_datetime"] for row in rows)
    elif case == "pickup_outside_month":
        count = sum(row["tpep_pickup_datetime"].month != 1 for row in rows)
    elif case == "invalid_passengers":
        count = sum(row["passenger_count"] < 0 for row in rows)
    else:
        count = len(rows) - len({tuple(row.items()) for row in rows})
    assert count == expected


def test_schema_mutations_are_observable() -> None:
    missing = pq.read_schema(FIXTURES / "missing_column.parquet")
    incompatible = pq.read_schema(FIXTURES / "incompatible_type.parquet")
    extra = pq.read_schema(FIXTURES / "extra_column.parquet")
    assert "PULocationID" not in missing.names
    assert incompatible.field("PULocationID").type == pa.large_string()
    assert len(extra) == 20
    assert extra.field("cbd_congestion_fee").type == pa.float64()


def test_seed_and_serialization_are_reproducible(tmp_path: Path) -> None:
    first = write_fixtures(tmp_path / "first")
    second = write_fixtures(tmp_path / "second")
    assert [hashlib.sha256(path.read_bytes()).digest() for path in first] == [
        hashlib.sha256(path.read_bytes()).digest() for path in second
    ]
    assert make_table(seed=42).equals(make_table(seed=42), check_metadata=True)
    assert not make_table(seed=42).equals(make_table(seed=43))


def test_factory_preserves_foreign_files(tmp_path: Path) -> None:
    existing = tmp_path / "valid.parquet"
    pq.write_table(pa.table({"foreign": [1]}), existing)
    before = existing.read_bytes()
    with pytest.raises(FileExistsError):
        write_fixtures(tmp_path)
    assert existing.read_bytes() == before


def test_unknown_case_fails() -> None:
    with pytest.raises(ValueError, match="desconocido"):
        make_table("not-a-case")
