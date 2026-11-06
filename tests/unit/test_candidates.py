"""Parametros autorizados, limites y predicciones seguras de candidatos."""

import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.base import BaseEstimator, RegressorMixin

from src.training.candidate_runtime import CandidateGuard, read_candidates
from src.training.models import BoundedRegressor
from src.training.resources import ResourceLimitError


class Constant(RegressorMixin, BaseEstimator):
    def __init__(self, value=0.0):
        self.value = value

    def partial_fit(self, X, y):
        self.fitted_ = True
        return self

    def predict(self, X):
        return np.full(len(X), self.value)


@pytest.mark.parametrize("value,expected", [(-100, 1 / 60), (200, 180), (20, 20)])
def test_output_bounds_are_serialized_estimator_behavior(value, expected):
    model = BoundedRegressor(Constant(value)).partial_fit(np.ones((3, 2)), np.ones(3))
    predictions, count = model.predict_with_diagnostics(np.ones((3, 2)))
    assert np.all(predictions == expected)
    assert count == (3 if value != expected else 0)
    assert model.rows_fitted_ == 3


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_predictions_fail_instead_of_clipping(value):
    model = BoundedRegressor(Constant(value)).partial_fit(np.ones((2, 1)), np.ones(2))
    with pytest.raises(ValueError, match="no finitas"):
        model.predict(np.ones((2, 1)))


@pytest.mark.parametrize("change", ["unapproved", "epochs", "params", "resources", "routes"])
def test_unapproved_training_protocol_is_rejected(tmp_path, change):
    config = json.loads(Path("configs/candidates.yaml").read_text())
    if change == "unapproved":
        config["approval_status"] = "PENDING"
    elif change == "epochs":
        config["epochs"] = 2
    elif change == "params":
        config["candidates"]["mlp"]["hidden_layer_sizes"] = [128]
    elif change == "resources":
        config["resources"]["process_rss_limit_gib"] = 16
    else:
        config["evaluation"]["route_scope"] = "test_frequency"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        read_candidates(path)


@pytest.mark.parametrize("failure", ["ram", "rss", "disk", "timeout"])
def test_candidate_guard_enforces_budget(tmp_path, monkeypatch, failure):
    policy = read_candidates(Path("configs/candidates.yaml"))["resources"]
    measured = {
        "available_ram_bytes": 16 * 2**30,
        "peak_rss_bytes": 2**30,
        "free_disk_bytes": 100 * 2**30,
    }
    if failure == "ram":
        measured["available_ram_bytes"] = 7 * 2**30
    elif failure == "rss":
        measured["peak_rss_bytes"] = 5 * 2**30
    elif failure == "disk":
        measured["free_disk_bytes"] = 49 * 2**30
    monkeypatch.setattr("src.training.resources.snapshot", lambda _: measured)
    guard = CandidateGuard(
        policy, tmp_path, test_only=False, charged_seconds=7201 if failure == "timeout" else 0
    )
    with pytest.raises(ResourceLimitError):
        guard.check(start=True)
