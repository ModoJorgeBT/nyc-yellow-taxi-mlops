"""T08/T09: politicas numericas exclusivamente sinteticas, sin datos TLC ni red."""

import copy
import json
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pytest

from src.validation.rules import METRICS, evaluate_batches
from src.validation.schema import load_config, validate_schema
from tests.fixtures.factory import make_table
from tests.fixtures.policies import synthetic_policy

CONFIG = Path(__file__).resolve().parents[2] / "configs" / "data.yaml"


@pytest.fixture
def config() -> dict:
    return load_config(CONFIG)


@pytest.fixture
def test_policy(config: dict) -> dict:
    """Valores elegidos para casos de 12 filas; no son umbrales TLC."""
    return synthetic_policy(config)


def run(table: pa.Table, config: dict, tmp_path: Path, *, size: int = 6, **period) -> dict:
    return evaluate_batches(
        table.schema,
        table.to_batches(max_chunksize=size),
        year=period.get("year", 2024),
        month=period.get("month", 1),
        config=config,
        scratch_dir=tmp_path / "scratch",
    )


def rule(report: dict, name: str) -> dict:
    return next(check for check in report["checks"] if check["rule"] == name)


def replace(table: pa.Table, name: str, values: list, dtype=None) -> pa.Table:
    index = table.schema.get_field_index(name)
    dtype = dtype or table.schema.field(name).type
    return table.set_column(index, name, pa.array(values, type=dtype))


@pytest.mark.parametrize(
    "case,status",
    [
        ("valid", "PASS"),
        ("extra_column", "PASS"),
        ("missing_column", "FAIL"),
        ("incompatible_type", "FAIL"),
    ],
)
def test_schema_fixtures(config: dict, case: str, status: str) -> None:
    assert validate_schema(make_table(case).schema, config)["status"] == status


def test_schema_essential_only_and_unknown_column(config: dict) -> None:
    table = make_table().select(config["schema"]["required"])
    assert validate_schema(table.schema, config)["status"] == "PASS"
    table = table.append_column("new_field", pa.array([1] * 12))
    report = validate_schema(table.schema, config)
    assert report["status"] == "WARN"
    assert report["checks"][1]["observed"] == ["new_field"]
    assert table.column_names[-1] == "new_field"  # No seleccion/renombrado implicito.


@pytest.mark.parametrize(
    "name,dtype,valid",
    [
        ("PULocationID", pa.int64(), True),
        ("passenger_count", pa.int32(), True),
        ("store_and_fwd_flag", pa.string(), True),
        ("PULocationID", pa.uint32(), False),
        ("passenger_count", pa.float64(), False),
        ("fare_amount", pa.float32(), False),
        ("tpep_pickup_datetime", pa.timestamp("ms"), False),
        ("tpep_pickup_datetime", pa.timestamp("us", "America/New_York"), False),
    ],
)
def test_schema_type_compatibility(config: dict, name: str, dtype, valid: bool) -> None:
    fields = [pa.field(f.name, dtype if f.name == name else f.type) for f in make_table().schema]
    assert (validate_schema(pa.schema(fields), config)["status"] == "PASS") is valid


def test_duplicate_names_block_and_airport_case_is_preserved(config: dict) -> None:
    schema = make_table().schema
    duplicate = schema.append(schema.field("PULocationID"))
    assert validate_schema(duplicate, config)["status"] == "FAIL"
    renamed = pa.schema(
        [pa.field("airport_fee" if f.name == "Airport_fee" else f.name, f.type) for f in schema]
    )
    assert validate_schema(renamed, config)["status"] == "WARN"


@pytest.mark.parametrize(
    "case,metric,count,excluded",
    [
        ("null_zone", "zone_null", 1, 1),
        ("null_timestamp", "timestamp_null", 1, 1),
        ("nonpositive_duration", "duration_nonpositive", 2, 2),
        ("pickup_outside_month", "pickup_outside_month", 1, 1),
        ("duplicate", "duplicate", 1, 0),
        ("invalid_passengers", "passenger_negative", 1, 0),
    ],
)
def test_tolerated_rows_are_reported_not_lot_rejection(
    test_policy: dict,
    tmp_path: Path,
    case: str,
    metric: str,
    count: int,
    excluded: int,
) -> None:
    table = make_table(case)
    before = table.to_pydict()
    report = run(table, test_policy, tmp_path)
    result = rule(report, f"rows.{metric}")
    assert result["observed"] == {"count": count, "rate": count / 12}
    assert result["status"] == "WARN"
    assert report["quality_passed"] and report["status"] == "WARN"
    assert report["excluded_rows"] == excluded
    assert report["eligible_rows"] == 12 - excluded
    assert not report["approved_for_training"]
    assert table.to_pydict() == before
    assert list((tmp_path / "scratch").iterdir()) == []


def test_critical_threshold_blocks_and_equality_is_tolerated(
    test_policy: dict, tmp_path: Path
) -> None:
    table = make_table("null_zone")
    test_policy["quality"]["max_rates"]["zone_null"] = 1 / 12
    assert run(table, test_policy, tmp_path)["quality_passed"]
    test_policy["quality"]["max_rates"]["zone_null"] = 0
    report = run(table, test_policy, tmp_path)
    assert report["status"] == "FAIL" and not report["quality_passed"]
    assert rule(report, "rows.zone_null")["severity"] == "critical"
    assert report["excluded_rows"] == 1  # No equivale a rechazar solo una fila.


def test_pending_real_policy_never_approves(config: dict, tmp_path: Path) -> None:
    report = run(make_table(), config, tmp_path)
    assert report["status"] == "FAIL"
    assert not report["quality_passed"] and not report["approved_for_training"]
    assert "zone_catalog" in rule(report, "policy.ready")["observed"]["pending"]
    assert rule(report, "rows.zone_unknown")["observed"]["count"] is None
    assert rule(report, "rows.duration_exceeds_max")["status"] == "WARN"
    json.dumps(report, allow_nan=False)


def test_test_policy_does_not_approve_unmarked_data(test_policy: dict, tmp_path: Path) -> None:
    report = run(make_table().replace_schema_metadata(None), test_policy, tmp_path)
    assert report["status"] == "FAIL" and not report["quality_passed"]


def test_valid_report_has_evidence_and_no_training_approval(
    test_policy: dict, tmp_path: Path
) -> None:
    report = run(make_table(), test_policy, tmp_path)
    assert report["status"] == "PASS" and report["quality_passed"]
    assert report["rows_scanned"] == report["eligible_rows"] == 12
    assert report["zone_catalog_version"] == "synthetic-v1"
    assert report["lineage_status"] == "NOT_CHECKED_T10"
    assert not report["approved_for_training"]
    for item in report["checks"]:
        assert {"rule", "status", "observed", "threshold", "severity", "evidence"} <= item.keys()
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("case", ["missing_column", "incompatible_type"])
def test_structural_failure_does_not_consume_rows(
    test_policy: dict, tmp_path: Path, case: str
) -> None:
    def forbidden():
        pytest.fail("No leer filas tras fallo estructural")
        yield

    report = evaluate_batches(
        make_table(case).schema,
        forbidden(),
        year=2024,
        month=1,
        config=test_policy,
        scratch_dir=tmp_path / "scratch",
    )
    assert report["status"] == "FAIL" and report["eligible_rows"] is None
    assert not (tmp_path / "scratch").exists()


@pytest.mark.parametrize(
    "pickup,dropoff,year,month,outside",
    [
        (datetime(2024, 1, 31, 23, 59), datetime(2024, 2, 1, 0, 10), 2024, 1, 0),
        (datetime(2024, 12, 31, 23, 59), datetime(2025, 1, 1, 0, 10), 2024, 12, 0),
        (datetime(2024, 2, 29, 23, 59), datetime(2024, 3, 1, 0, 10), 2024, 2, 0),
        (datetime(2024, 2, 1), datetime(2024, 2, 1, 0, 10), 2024, 1, 1),
    ],
)
def test_month_boundaries(test_policy: dict, tmp_path: Path, pickup, dropoff, year, month, outside):
    table = make_table().slice(0, 1)
    table = replace(table, "tpep_pickup_datetime", [pickup])
    table = replace(table, "tpep_dropoff_datetime", [dropoff])
    report = run(table, test_policy, tmp_path, year=year, month=month)
    assert rule(report, "rows.pickup_outside_month")["observed"]["count"] == outside
    assert report["excluded_rows"] == outside


def test_duration_max_boundary_and_extreme_timestamp(test_policy: dict, tmp_path: Path) -> None:
    table = make_table().slice(0, 1)
    start = pc_int(table["tpep_pickup_datetime"])[0]
    for increment, expected in ((120 * 60_000_000, 0), (120 * 60_000_000 + 1, 1)):
        changed = replace(table, "tpep_dropoff_datetime", [start + increment])
        report = run(changed, test_policy, tmp_path)
        assert rule(report, "rows.duration_exceeds_max")["observed"]["count"] == expected
    extreme = replace(table, "tpep_pickup_datetime", [-(2**63) + 1])
    extreme = replace(extreme, "tpep_dropoff_datetime", [2**63 - 1])
    report = run(extreme, test_policy, tmp_path)
    assert rule(report, "rows.duration_nonpositive")["observed"]["count"] == 0
    assert rule(report, "rows.duration_exceeds_max")["observed"]["count"] == 1


def pc_int(column):
    return column.combine_chunks().view(pa.int64()).to_pylist()


def test_duplicate_repetitions_nulls_and_nan_are_deterministic(test_policy: dict, tmp_path: Path):
    table = make_table("null_zone").slice(0, 1)
    table = replace(table, "fare_amount", [float("nan")])
    table = pa.concat_tables([table, table, table])
    report = run(table, test_policy, tmp_path, size=1)
    assert rule(report, "rows.duplicate")["observed"]["count"] == 2
    assert report["excluded_rows"] == 3
    assert rule(report, "rows.zone_null")["evidence"]["first_row_indexes"] == [0, 1, 2]
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("year,month", [(2024, 0), (2024, 13), (True, 1), (2008, 1)])
def test_invalid_period_has_no_scratch_side_effects(test_policy: dict, tmp_path: Path, year, month):
    with pytest.raises(ValueError):
        run(make_table(), test_policy, tmp_path, year=year, month=month)
    assert not (tmp_path / "scratch").exists()


def test_explicit_disabled_duration_max_is_test_only(test_policy: dict, tmp_path: Path):
    test_policy["quality"]["duration_max_minutes"] = "disabled"
    report = run(make_table(), test_policy, tmp_path)
    assert report["quality_passed"]
    assert rule(report, "rows.duration_exceeds_max")["observed"]["count"] == 0
    test_policy["quality"]["duration_max_minutes"] = None
    assert not run(make_table(), test_policy, tmp_path)["quality_passed"]


def test_unknown_and_special_zones_use_explicit_catalog(test_policy: dict, tmp_path: Path) -> None:
    table = replace(make_table(), "PULocationID", [264, 265, 999] + [161] * 9)
    report = run(table, test_policy, tmp_path)
    assert rule(report, "rows.zone_unknown")["observed"]["count"] == 1
    assert report["excluded_rows"] == 1


def test_passengers_optional_and_explicit_exclusion(test_policy: dict, tmp_path: Path) -> None:
    table = make_table().drop_columns(["passenger_count"])
    report = run(table, test_policy, tmp_path)
    assert rule(report, "rows.passenger_null")["observed"]["count"] == 12
    assert report["eligible_rows"] == 12 and report["quality_passed"]
    table = replace(make_table(), "passenger_count", [None, -1, 0, 7] + [1] * 8)
    test_policy["quality"]["passenger_action"] = "exclude_invalid"
    report = run(table, test_policy, tmp_path)
    assert report["excluded_rows"] == 2  # Ausencia permitida; negativo/7 fuera del rango fixture.
    assert rule(report, "rows.passenger_null")["observed"]["count"] == 1
    assert rule(report, "rows.passenger_out_of_range")["observed"]["count"] == 2


def test_category_policy_and_non_overlapping_excluded_count(test_policy: dict, tmp_path: Path):
    table = replace(make_table("null_zone"), "RatecodeID", [99] + [1] * 11)
    test_policy["quality"]["category_action"] = "exclude_invalid"
    report = run(table, test_policy, tmp_path)
    assert rule(report, "rows.category_invalid")["observed"]["count"] == 1
    assert report["excluded_rows"] == 1  # Dos razones, una sola fila.


def test_duplicate_count_is_batch_invariant_and_includes_extra_columns(test_policy: dict, tmp_path):
    table = make_table("duplicate")
    first = run(table, test_policy, tmp_path, size=1)
    second = run(table, test_policy, tmp_path, size=12)
    assert first == second
    table = table.append_column("extra_nested", pa.array([[n] for n in range(12)]))
    report = run(table, test_policy, tmp_path)
    assert rule(report, "rows.duplicate")["observed"]["count"] == 0
    assert report["status"] == "WARN"  # Columna adicional, compatible por politica.


def test_empty_and_insufficient_volume_block(test_policy: dict, tmp_path: Path) -> None:
    empty = run(make_table().slice(0, 0), test_policy, tmp_path)
    assert empty["status"] == "FAIL" and not empty["quality_passed"]
    assert rule(empty, "rows.duplicate")["observed"]["rate"] is None
    test_policy["quality"]["min_rows"] = 13
    report = run(make_table(), test_policy, tmp_path)
    assert rule(report, "volume.min_rows")["status"] == "FAIL"


def test_missing_eligible_volume_blocks(test_policy: dict, tmp_path: Path) -> None:
    table = replace(make_table(), "PULocationID", [None] * 12)
    test_policy["quality"]["max_rates"] = dict.fromkeys(METRICS, 1)
    report = run(table, test_policy, tmp_path)
    assert report["eligible_rows"] == 0
    assert rule(report, "volume.min_eligible_rows")["status"] == "FAIL"


def test_batch_schema_change_blocks_and_cleans_scratch(test_policy: dict, tmp_path: Path) -> None:
    table = make_table()
    batches = [table.to_batches()[0], make_table("extra_column").to_batches()[0]]
    report = evaluate_batches(
        table.schema,
        batches,
        year=2024,
        month=1,
        config=test_policy,
        scratch_dir=tmp_path / "scratch",
    )
    assert report["status"] == "FAIL" and report["eligible_rows"] is None
    assert rule(report, "scan.schema_consistency")["status"] == "FAIL"
    assert list((tmp_path / "scratch").iterdir()) == []


def test_iterator_error_cannot_return_approval_and_cleans_scratch(test_policy: dict, tmp_path):
    table = make_table()

    def interrupted():
        yield table.to_batches()[0]
        raise OSError("Lectura interrumpida")

    with pytest.raises(OSError, match="interrumpida"):
        evaluate_batches(
            table.schema,
            interrupted(),
            year=2024,
            month=1,
            config=test_policy,
            scratch_dir=tmp_path / "scratch",
        )
    assert list((tmp_path / "scratch").iterdir()) == []


@pytest.mark.parametrize(
    "key,value",
    [
        ("status", "APPROVED"),
        ("min_rows", 0),
        ("min_rows", True),
        ("duration_max_minutes", -1),
        ("duration_max_minutes", float("nan")),
        ("passenger_range", [6, 0]),
        ("zone_catalog", {"version": "v1", "ids": [True]}),
        ("duplicate_action", "drop"),
        ("timestamp_policy", "utc"),
    ],
)
def test_invalid_policy_fails_before_scratch(test_policy: dict, tmp_path: Path, key, value):
    test_policy["quality"][key] = value
    with pytest.raises(ValueError):
        run(make_table(), test_policy, tmp_path)
    assert not (tmp_path / "scratch").exists()


@pytest.mark.parametrize("value", [-0.1, 1.1, True, "0.5", None])
def test_invalid_or_unset_rate_cannot_approve(test_policy: dict, tmp_path: Path, value):
    test_policy["quality"]["max_rates"]["zone_null"] = value
    if value is None:
        assert not run(make_table(), test_policy, tmp_path)["quality_passed"]
    else:
        with pytest.raises(ValueError):
            run(make_table(), test_policy, tmp_path)


def test_configuration_load_errors(config: dict, tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("format_version: 1", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        load_config(path)
    invalid = copy.deepcopy(config)
    invalid["schema"]["required"].remove("PULocationID")
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="esenciales"):
        load_config(path)
