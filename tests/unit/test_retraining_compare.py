from copy import deepcopy

import pytest

from src.retraining.compare import CONTROLS, gate_metrics


def metrics(value=10, rows=1000):
    return {
        "all": {
            "rows": rows,
            "mae_minutes": value,
            "rmse_minutes": value,
            "medae_minutes": value,
            "p90_absolute_error_minutes": value,
        }
    }


def gate(left, right, segments=(), **changes):
    return gate_metrics(
        left, right, segments, controls={**dict.fromkeys(CONTROLS, True), **changes}
    )


def test_exact_two_percent_passes_but_smaller_gain_does_not():
    assert gate(metrics(), metrics(9.8))["decision"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert gate(metrics(), metrics(9.800001))["decision"] == "CHALLENGER_REJECTED"
    assert gate(metrics(), metrics(11))["decision"] == "CHALLENGER_REJECTED"


@pytest.mark.parametrize("control", CONTROLS)
def test_improvement_never_overrides_failed_controls(control):
    assert gate(metrics(), metrics(5), **{control: False})["decision"] == "CHALLENGER_REJECTED"


@pytest.mark.parametrize("metric", ["rmse_minutes", "p90_absolute_error_minutes"])
def test_global_tail_or_squared_error_regression_rejected(metric):
    right = metrics(9)
    right["all"][metric] = 10.000001
    assert gate(metrics(), right)["decision"] == "CHALLENGER_REJECTED"


def test_segments_five_percent_boundary_and_support():
    left, right = metrics(), metrics(9)
    left["route_1_2"], right["route_1_2"] = (
        deepcopy(metrics()["all"]),
        deepcopy(metrics(10.5)["all"]),
    )
    assert gate(left, right, ["route_1_2"])["decision"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    right["route_1_2"]["mae_minutes"] = 10.500001
    assert gate(left, right, ["route_1_2"])["decision"] == "CHALLENGER_REJECTED"
    left["route_1_2"]["rows"] = right["route_1_2"]["rows"] = 999
    assert gate(left, right, ["route_1_2"])["decision"] == "NOT_EVALUABLE"


def test_missing_segment_coverage_nan_and_zero_reference():
    assert gate(metrics(), metrics(9), ["route_1_2"])["decision"] == "NOT_EVALUABLE"
    right = metrics(9)
    right["all"]["mae_minutes"] = float("nan")
    assert gate(metrics(), right)["decision"] == "NOT_EVALUABLE"
    assert gate(metrics(0), metrics(0))["decision"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert gate(metrics(0), metrics(1))["decision"] == "CHALLENGER_REJECTED"
    assert gate(metrics(rows=1001), metrics(9))["decision"] == "NOT_EVALUABLE"


def test_exhaustive_month_segments_must_cover_global():
    left, right = metrics(rows=3000), metrics(9, rows=3000)
    for name in ["month_2026_04", "month_2026_05"]:
        left[name], right[name] = metrics()["all"], metrics(9)["all"]
    assert gate(left, right, ["month_2026_04", "month_2026_05"])["decision"] == "NOT_EVALUABLE"
