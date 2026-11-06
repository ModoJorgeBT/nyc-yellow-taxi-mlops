"""Metricas exactas, ponderacion entre bloques y segmentos sin usar errores para elegir rutas."""

from collections import Counter

import numpy as np
import pyarrow as pa
import pytest

from src.evaluation.metrics import ErrorStore, exact_quantiles
from src.evaluation.run import select_validation
from src.evaluation.segments import DestinationRows, choose_routes


@pytest.mark.parametrize(
    "errors", [[3.0], [0.0, 20.0], [0.0, 1.0, 2.0, 3.0, 99.0], list(np.arange(101.0))]
)
def test_exact_quantiles_and_aggregates_across_unequal_blocks(tmp_path, errors):
    values = np.asarray(errors, dtype=np.float64)
    store = ErrorStore(tmp_path)
    store.add(values[:1], np.zeros(1), {})
    if len(values) > 1:
        store.add(values[1:], np.zeros(len(values) - 1), {})
    result = store.results()["all"]
    assert result["rows"] == len(values)
    assert result["mae_minutes"] == pytest.approx(values.mean())
    assert result["rmse_minutes"] == pytest.approx(np.sqrt(np.mean(values * values)))
    assert result["medae_minutes"] == pytest.approx(np.quantile(values, 0.5, method="linear"))
    assert result["p90_absolute_error_minutes"] == pytest.approx(
        np.quantile(values, 0.9, method="linear")
    )


def test_bad_errors_empty_and_partial_files_are_rejected(tmp_path):
    store = ErrorStore(tmp_path)
    with pytest.raises(ValueError):
        store.add(np.array([np.inf]), np.array([1.0]), {})
    with pytest.raises(ValueError):
        store.results()
    partial = tmp_path / "partial"
    partial.write_bytes(b"0")
    with pytest.raises(ValueError):
        exact_quantiles(partial, 10)


def test_quantile_resource_callback_can_stop_before_sort(tmp_path):
    path = tmp_path / "data.f64"
    np.arange(20.0, dtype="<f8").tofile(path)

    def stop():
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError, match="stop"):
        exact_quantiles(path, 20, resource_check=stop)


def test_frequent_routes_use_frequency_support_and_id_ties_only():
    counts = Counter({1002: 999, 1003: 1000, 1004: 2000, 1005: 1000})
    assert choose_routes(counts, maximum=2) == [1004, 1003]
    assert choose_routes(Counter({1002: 2})) == []


def test_destinations_align_sparse_indices_across_different_batches():
    class Reader:
        def iter_batches(self, **kwargs):
            for values in ([161, 236, 264], [265, 161, 236], [265]):
                yield pa.record_batch([pa.array(values)], names=["DOLocationID"])

    rows = DestinationRows(Reader())
    assert rows.take(np.array([0, 2])).tolist() == [161, 264]
    assert rows.take(np.array([4, 6])).tolist() == [161, 265]
    with pytest.raises(ValueError):
        rows.take(np.array([6]))


@pytest.mark.parametrize(
    "scores,expected",
    [([2.0, 2.0, 2.0], "baseline"), ([3.0, 2.0, 2.0], "sgd"), ([3.0, 4.0, 1.0], "mlp")],
)
def test_validation_ties_are_frozen_by_approved_order(scores, expected):
    result = {
        "metrics": {
            name: {"all": {"mae_minutes": score}}
            for name, score in zip(("baseline", "sgd", "mlp"), scores, strict=True)
        }
    }
    assert select_validation(result) == expected
