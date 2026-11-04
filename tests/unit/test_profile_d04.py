"""D-04: diseno de muestra y conteos conocidos; no depende de TLC real ni red."""

import csv
import hashlib
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from scripts.profile_d04 import (
    allocate_quotas,
    assess,
    profile_2024,
    profile_file,
    weighted_quantiles,
)
from src.validation.schema import load_config
from tests.fixtures.factory import make_table

CONFIG = Path(__file__).resolve().parents[2] / "configs/data.yaml"


def test_quotas_conserve_sample_and_stratum_proportions():
    assert allocate_quotas([100, 300, 0], 20) == [5, 15, 0]
    assert allocate_quotas([3, 5], 4) == [2, 2]
    assert allocate_quotas([3, 5], 100) == [3, 5]
    assert allocate_quotas([0, 0], 2) == [0, 0]
    with pytest.raises(ValueError):
        allocate_quotas([1000, 1], 1)


@pytest.mark.parametrize("sizes,count", [([1], True), ([1], 0), ([-1], 2)])
def test_invalid_sample_before_file_access(sizes, count):
    with pytest.raises(ValueError):
        allocate_quotas(sizes, count)


def test_weighted_empirical_quantiles():
    result = weighted_quantiles([(0.0, 9.0), (100.0, 1.0)])
    assert result == {
        "min": 0.0,
        "p50": 0.0,
        "p95": 100.0,
        "p99": 100.0,
        "p999": 100.0,
        "max": 100.0,
    }
    assert weighted_quantiles([])["p50"] is None


def test_random_strata_are_reproducible_and_source_preserved(tmp_path):
    path = tmp_path / "fixture.parquet"
    pq.write_table(make_table(), path, row_group_size=6)
    original = path.read_bytes()
    options = {
        "month": 1,
        "zone_ids": {161, 236},
        "config": load_config(CONFIG),
        "sample_size": 4,
        "seed": 20241104,
        "batch_size": 2,
    }
    first = profile_file(path, **options)
    second = profile_file(path, **options)
    assert first == second
    assert first["sample_rows"] == 4
    assert [item["sample_rows"] for item in first["selection"]] == [2, 2]
    for item in first["selection"]:
        selected = item["selected_rows_in_group"]
        assert len(set(selected)) == len(selected) == 2
        assert min(selected) >= 0 and max(selected) < 6
        assert item["design_weight"] == 3
    assert path.read_bytes() == original
    assert first["source"]["sha256"] == hashlib.sha256(original).hexdigest()


def test_full_fixture_duplicate_count_is_not_population_estimate(tmp_path):
    path = tmp_path / "fixture.parquet"
    pq.write_table(make_table("duplicate"), path, row_group_size=6)
    result = profile_file(
        path,
        month=1,
        zone_ids={161, 236},
        config=load_config(CONFIG),
        sample_size=12,
        seed=42,
        batch_size=2,
    )
    assert result["metrics"]["duplicate_in_sample"]["sample_count"] == 1
    assert result["metrics"]["duplicate_in_sample"]["estimated_rate"] is None
    assert result["metrics"]["cap_180"]["sample_count"] == 0


def test_profiled_duration_uses_utc_and_detects_dst_without_guessing():
    row = make_table().to_pylist()[0]
    row["tpep_pickup_datetime"] = datetime(2024, 11, 3, 0, 55)
    row["tpep_dropoff_datetime"] = datetime(2024, 11, 3, 2, 5)
    flags, duration = assess(row, month=11, zone_ids={161, 236})
    assert duration == 130.0 and not flags
    row["tpep_pickup_datetime"] = datetime(2024, 11, 3, 1, 30)
    flags, duration = assess(row, month=11, zone_ids={161, 236})
    assert "ambiguous_local_time" in flags and duration is None


def test_metrics_keep_optional_and_special_cases_separate():
    row = make_table().to_pylist()[0]
    row.update(PULocationID=264, DOLocationID=999, passenger_count=7, RatecodeID=99)
    flags, duration = assess(row, month=1, zone_ids={161, 236, 264, 265})
    assert {
        "PU_special",
        "DO_outside_catalog",
        "passenger_above_6",
        "passenger_adjustment_0_6",
    } <= flags
    assert "PU_outside_catalog" not in flags and "passenger_above_8" not in flags
    assert "category_unknown" not in flags and duration > 0
    row.update(passenger_count=None, RatecodeID=None, store_and_fwd_flag=None)
    flags, _ = assess(row, month=1, zone_ids={161, 236, 264, 265})
    assert {"category_null", "passenger_null_and_metadata_null"} <= flags
    assert "category_outside_dictionary" not in flags


def test_year_profiler_never_opens_2025(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    for month in range(1, 13):
        folder = raw / f"2024/{month:02}"
        folder.mkdir(parents=True)
        pq.write_table(
            make_table(), folder / f"yellow_tripdata_2024-{month:02}.parquet", row_group_size=6
        )
    (raw / "2025").mkdir()
    (raw / "2025/do-not-open.parquet").write_bytes(b"not part of the authorized sample")
    catalog = tmp_path / "catalog.csv"
    with catalog.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["LocationID"])
        writer.writerows([[161], [236]])
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert "2025" not in path.parts
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    result = profile_2024(raw, catalog, sample_size=4, batch_size=2, config_path=CONFIG)
    assert result["sample_rows"] == 48 and result["population_footer_rows"] == 144
    assert [item["month"] for item in result["files"]] == list(range(1, 13))
    assert result["metrics"]["pickup_outside_month"]["sample_count"] == 44
    assert result["metrics"]["duplicate_in_sample"]["estimated_rate"] is None
    assert result["status"] == "PROPOSAL_EVIDENCE_NOT_APPLIED"
