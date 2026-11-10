import numpy as np
import pytest

from scripts.audit_monitoring import update_cdf
from scripts.audit_retraining import accumulator, verify_metrics


def measured(values):
    return {
        "rows": len(values),
        "mae_minutes": float(np.mean(values)),
        "rmse_minutes": float(np.sqrt(np.mean(values**2))),
        "medae_minutes": float(np.quantile(values, 0.5)),
        "p90_absolute_error_minutes": float(np.quantile(values, 0.9)),
    }


@pytest.mark.parametrize(
    "values", [[0, 0, 0, 0], [0, 1, 2, 3], [2, 2, 2, 9, 10], [0.01, 0.02, 0.03]]
)
def test_full_cdf_audit_accepts_exact_values_and_rejects_wrong_mean(values):
    values = np.asarray(values, dtype=float)
    report = measured(values)
    state = accumulator(report)
    state.update(
        rows=len(values), sums=[float(values.sum())], squares=[float(np.dot(values, values))]
    )
    for q in state["quantiles"].values():
        update_cdf(q, values)
    verify_metrics(state, report)
    with pytest.raises(ValueError, match="MAE/RMSE"):
        verify_metrics(state, {**report, "mae_minutes": report["mae_minutes"] + 0.01})
