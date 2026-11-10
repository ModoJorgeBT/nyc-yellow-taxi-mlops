from copy import deepcopy
from datetime import UTC, datetime

import pytest

from src.features.schema import FEATURE_COLUMNS
from src.retraining.triggers import decide, signals


def report(*, mae=11.5, rows=1000, psi=0.2):
    return {
        "prediction": {"rows": rows},
        "performance": {
            "status": "OBSERVED",
            "coverage_ratio": 1.0,
            "expected_rows": rows,
            "metrics": {"all": {"rows": rows, "mae_minutes": mae}},
        },
        "drift": {
            "features": {
                f: {"psi": psi, "current_rows": rows, "reference_rows": rows}
                for f in FEATURE_COLUMNS
            }
        },
    }


def window(month, **kwargs):
    return {"year": 2025, "month": month, **signals(report(**kwargs), 10)}


def decision(windows):
    return decide(
        windows,
        as_of=datetime(2026, 1, 2, tzinfo=UTC),
        last_fit_end=datetime(2025, 1, 1, tzinfo=UTC),
    )


def test_exact_thresholds_do_not_trigger_but_epsilon_does():
    assert decision([window(7), window(8)])["decision"] == "NO_ACTION"
    value = decision([window(7, mae=11.500001), window(8, mae=11.500001)])
    assert value["reasons"] == [{"rule": "MAE_TWO_MONTHS", "months": [[2025, 7], [2025, 8]]}]
    assert not value["training_started"] and not value["champion_changed"]


def test_drift_requires_same_feature_in_adjacent_months():
    first, second = report(psi=0), report(psi=0)
    first["drift"]["features"]["passenger_count"]["psi"] = 0.20001
    second["drift"]["features"]["passenger_count_missing"]["psi"] = 0.20001
    windows = [{"year": 2025, "month": m, **signals(r, 10)} for m, r in [(7, first), (8, second)]]
    assert decision(windows)["decision"] == "NO_ACTION"
    second["drift"]["features"]["passenger_count"]["psi"] = 0.21
    windows[1].update(signals(second, 10))
    assert decision(windows)["reasons"][0]["feature"] == "passenger_count"


def test_missing_month_and_low_support_never_bridge_evidence():
    assert decision([window(7, mae=20), window(9, mae=20)])["decision"] == "NO_ACTION"
    assert decision([window(7, mae=20), window(8, mae=20, rows=999)])["decision"] == "NO_ACTION"
    assert decision([window(7, mae=20)])["decision"] == "NO_ACTION"


def test_labels_absent_do_not_invent_mae_but_psi_can_recommend():
    r = report(psi=0.21)
    r["performance"] = {"status": "NOT_AVAILABLE"}
    value = signals(r, 10)
    assert value["mae_deteriorated"] is None
    assert (
        decision([{"year": 2025, "month": m, **value} for m in [7, 8]])["decision"]
        == "RETRAIN_RECOMMENDED"
    )


@pytest.mark.parametrize("mutation", ["coverage", "rows", "nan", "negative", "feature"])
def test_corrupt_evidence_blocks(mutation):
    r = deepcopy(report())
    if mutation == "coverage":
        r["performance"]["coverage_ratio"] = 0.9
    elif mutation == "rows":
        r["performance"]["metrics"]["all"]["rows"] -= 1
    elif mutation == "nan":
        r["drift"]["features"]["pickup_hour"]["psi"] = float("nan")
    elif mutation == "negative":
        r["performance"]["metrics"]["all"]["mae_minutes"] = -1
    else:
        r["drift"]["features"].pop("pickup_hour")
    with pytest.raises(ValueError):
        signals(r, 10)


def test_duplicate_month_and_naive_dates_rejected():
    with pytest.raises(ValueError, match="duplicado"):
        decision([window(7), window(7)])
    with pytest.raises(ValueError, match="Fechas"):
        decide([], as_of=datetime(2026, 1, 1), last_fit_end=datetime(2025, 1, 1, tzinfo=UTC))


def test_quarterly_review_does_not_recommend_training():
    value = decision([window(7), window(8)])
    assert value["quarterly_review"] == "REVIEW_REQUIRED"
    assert value["decision"] == "NO_ACTION"
