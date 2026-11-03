"""Comprueba limites de lectura y estadisticas con oraculos sinteticos."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from scripts.profile_sample import number_summary, profile_year, sample_file, summarize_table
from tests.fixtures.factory import make_table


def test_sample_is_bounded_per_group_and_preserves_source(tmp_path: Path) -> None:
    source = tmp_path / "source.parquet"
    table = make_table()
    pq.write_table(table, source, row_group_size=6)
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    first = sample_file(source, rows_per_group=2)
    second = sample_file(source, rows_per_group=2)
    assert first["footer_rows"] == 12
    assert first["selected_ranges"] == [
        {"row_group": 0, "start_row_in_group": 0, "rows": 2},
        {"row_group": 1, "start_row_in_group": 0, "rows": 2},
    ]
    assert first["sample_table"].to_pylist() == [table.to_pylist()[i] for i in (0, 1, 6, 7)]
    assert first["sample_sha256"] == second["sample_sha256"]
    assert first["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest() == original


def test_sample_limit_is_validated_before_opening_file(tmp_path: Path) -> None:
    for limit in (0, 2049):
        with pytest.raises(ValueError, match="entre 1 y 2048"):
            sample_file(tmp_path / "missing.parquet", rows_per_group=limit)


def test_known_duration_summary_keeps_anomalies() -> None:
    stats = summarize_table(make_table("nonpositive_duration"), year=2024, month=1)
    assert stats["nonpositive_duration"] == 2
    assert stats["duration_minutes"]["count"] == 12
    assert stats["duration_minutes"]["min"] == -1.0
    assert stats["positive_duration_minutes"]["count"] == 10
    assert number_summary([0.0, 10.0, 20.0, 30.0]) == pytest.approx(
        {
            "count": 4,
            "min": 0.0,
            "p50": 15.0,
            "p95": 28.5,
            "p99": 29.7,
            "max": 30.0,
        }
    )
    assert number_summary([])["p50"] is None


@pytest.mark.parametrize(
    ("case", "expected_key", "expected"),
    [
        ("pickup_outside_month", "pickup_outside_file_month", 1),
        ("duplicate", "duplicate_exact_sample_rows", 1),
    ],
)
def test_known_sample_counts(case: str, expected_key: str, expected: int) -> None:
    stats = summarize_table(make_table(case), year=2024, month=1)
    assert stats[expected_key] == expected


def test_sample_nulls_and_passengers_are_counted() -> None:
    assert (
        summarize_table(make_table("null_zone"), year=2024, month=1)["nulls"]["PULocationID"] == 1
    )
    stats = summarize_table(make_table("null_timestamp"), year=2024, month=1)
    assert stats["nulls"]["tpep_dropoff_datetime"] == 1
    assert stats["duration_minutes"]["count"] == 11
    stats = summarize_table(make_table("invalid_passengers"), year=2024, month=1)
    assert stats["passenger_count"]["negative"] == 1
    assert stats["zones"]["DOLocationID"]["catalog_membership"] == "NOT_EVALUATED"


@pytest.mark.parametrize("case", ["missing_column", "incompatible_type"])
def test_profile_fails_explicitly_on_incompatible_sample(case: str) -> None:
    with pytest.raises(ValueError, match="muestra"):
        summarize_table(make_table(case), year=2024, month=1)


def test_year_profile_does_not_open_2025(tmp_path: Path) -> None:
    for month in range(1, 13):
        path = tmp_path / "2024" / f"{month:02}" / f"yellow_tripdata_2024-{month:02}.parquet"
        path.parent.mkdir(parents=True)
        pq.write_table(make_table(), path, row_group_size=6)
    future = tmp_path / "2025" / "01" / "yellow_tripdata_2025-01.parquet"
    future.parent.mkdir(parents=True)
    future.write_bytes(b"not a Parquet; fail if accidentally opened")
    result = profile_year(tmp_path, rows_per_group=2)
    assert result["sample_rows"] == 48
    assert len(result["files"]) == 12
    assert all("2024-" in file["file"] for file in result["files"])
    assert result["resources"]["docker_limits"] == "NOT_MEASURED"
    json.dumps(result)


def test_cli_rejects_writing_into_raw(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    output = raw / "reports"
    script = Path(__file__).resolve().parents[2] / "scripts/profile_sample.py"
    result = subprocess.run(
        [sys.executable, str(script), "--raw-dir", str(raw), "--output-dir", str(output)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 2
    assert "dentro de raw" in result.stderr
    assert not output.exists()
