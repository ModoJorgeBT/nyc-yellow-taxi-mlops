"""D-04: oraculos del perfil real; volumen/tolerancias sinteticas fuera de produccion."""

import copy
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pytest

from src.validation.real import validate_policy
from src.validation.rules import evaluate_batches
from src.validation.schema import load_config
from tests.fixtures.factory import make_table
from tests.fixtures.policies import real_fixture_policy

CONFIG = Path(__file__).resolve().parents[2] / "configs/data.yaml"


@pytest.fixture
def policy():
    return real_fixture_policy(load_config(CONFIG))


def run(table, policy, tmp_path, *, month=1, callback=None, size=6):
    return evaluate_batches(
        table.schema,
        table.to_batches(max_chunksize=size),
        year=2024,
        month=month,
        config=policy,
        scratch_dir=tmp_path,
        on_batch=callback,
    )


def rule(report, name):
    return next(check for check in report["checks"] if check["rule"] == f"rows.{name}")


def test_real_evaluator_cannot_approve_lineage_or_training(policy, tmp_path):
    report = run(make_table(), policy, tmp_path)
    assert report["quality_passed"] and not report["data_quality_approved"]
    assert not report["approved_for_training"] and report["lineage_status"] == "NOT_CHECKED_T10"
    assert report["eligible_rows"] == 12 and list(tmp_path.iterdir()) == []


def test_passenger_normalization_and_duplicates_use_original_values(policy, tmp_path):
    table = make_table()
    rows = table.to_pylist()
    rows[0]["passenger_count"] = -1
    rows[1] = {**rows[0], "passenger_count": 8}
    table = pa.Table.from_pylist(rows, schema=table.schema)
    original = table.to_pydict()
    captured = []
    report = run(table, policy, tmp_path, callback=lambda batch, mask: captured.append(batch))
    output = pa.Table.from_batches(captured)
    assert output["passenger_count"].to_pylist()[:2] == [None, None]
    assert report["normalizations"]["passenger_count"]["count"] == 2
    assert report["normalizations"]["passenger_count"]["in_eligible_rows"] == 2
    assert rule(report, "duplicate_exact")["observed"]["count"] == 0
    assert report["eligible_rows"] == 12 and table.to_pydict() == original


def test_destination_categories_and_special_origin_only_warn(policy, tmp_path):
    table = make_table()
    rows = table.to_pylist()
    rows[0].update(PULocationID=264, DOLocationID=None, payment_type=99)
    rows[1]["PULocationID"] = 265
    report = run(pa.Table.from_pylist(rows, schema=table.schema), policy, tmp_path)
    assert report["quality_passed"] and report["excluded_rows"] == 0
    for metric, count in (
        ("origin_special_264_or_265", 2),
        ("destination_null_or_outside_catalog", 1),
        ("optional_categories_null_or_outside_dictionary", 1),
    ):
        assert rule(report, metric)["observed"]["count"] == count
        assert rule(report, metric)["status"] == "WARN"


def test_exact_repetitions_across_blocks_are_kept(policy, tmp_path):
    report = run(make_table("duplicate"), policy, tmp_path, size=1)
    assert rule(report, "duplicate_exact")["observed"]["count"] == 1
    assert report["eligible_rows"] == 12


def test_rate_boundary_and_union_without_double_counting(policy, tmp_path):
    rows = make_table("null_zone").to_pylist()
    rows[0]["tpep_dropoff_datetime"] = None
    table = pa.Table.from_pylist(rows, schema=make_table().schema)
    policy["quality"]["fail_rates"]["origin_null_or_outside_catalog"] = 1 / 12
    report = run(table, policy, tmp_path)
    assert report["quality_passed"] and report["excluded_rows"] == 1
    assert rule(report, "timestamp_null_or_uninterpretable")["observed"]["count"] == 1
    policy["quality"]["fail_rates"]["origin_null_or_outside_catalog"] = 0
    assert not run(table, policy, tmp_path)["quality_passed"]


@pytest.mark.parametrize(
    "pickup,dropoff,bad,duration_invalid",
    [
        (
            datetime(2024, 3, 10, 1, 55),
            datetime(2024, 3, 10, 3, 5),
            datetime(2024, 3, 10, 2, 30),
            0,
        ),
        (
            datetime(2024, 11, 3, 0, 55),
            datetime(2024, 11, 3, 2, 5),
            datetime(2024, 11, 3, 1, 30),
            0,
        ),
        (
            datetime(2024, 11, 3, 0, 55),
            datetime(2024, 11, 3, 3, 5),
            datetime(2024, 11, 3, 1, 30),
            11,
        ),
    ],
)
def test_dst_quarantine_and_duration_in_utc(
    policy, tmp_path, pickup, dropoff, bad, duration_invalid
):
    table = make_table()
    rows = table.to_pylist()
    for row in rows:
        row.update(tpep_pickup_datetime=pickup, tpep_dropoff_datetime=dropoff)
    rows[0]["tpep_pickup_datetime"] = bad
    report = run(
        pa.Table.from_pylist(rows, schema=table.schema), policy, tmp_path, month=pickup.month
    )
    assert rule(report, "timestamp_ambiguous_or_nonexistent")["observed"]["count"] == 1
    assert rule(report, "duration_above_180")["observed"]["count"] == duration_invalid


def test_extreme_timestamp_is_invalid_without_datetime_overflow(policy, tmp_path):
    table = make_table()
    table = table.set_column(
        table.schema.get_field_index("tpep_pickup_datetime"),
        "tpep_pickup_datetime",
        pa.array([2**63 - 1] + [None] * 11, type=pa.timestamp("us")),
    )
    report = run(table, policy, tmp_path)
    assert report["excluded_rows"] == 12 and not report["quality_passed"]
    assert rule(report, "timestamp_null_or_uninterpretable")["observed"]["count"] == 12


@pytest.mark.parametrize("change", ["catalog", "tzdata", "approval", "missing_rate", "bad_rate"])
def test_malformed_real_policy_is_rejected_before_scan(policy, tmp_path, change):
    policy = copy.deepcopy(policy)
    if change == "catalog":
        policy["quality"]["zone_catalog"]["ids"].append(999)
    if change == "tzdata":
        policy["quality"]["tzdata_version"] = "unknown"
    if change == "approval":
        policy["quality"]["approval"]["user_approved"] = False
    if change == "missing_rate":
        del policy["quality"]["fail_rates"]["union_invalid_rows"]
    if change == "bad_rate":
        policy["quality"]["fail_rates"]["union_invalid_rows"] = True
    with pytest.raises(ValueError):
        validate_policy(policy["quality"])
    assert list(tmp_path.iterdir()) == []
