"""Fronteras de drift, referencias selladas y temporalidad de etiquetas."""

import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import MagicMock, Mock

import numpy as np
import pytest

from src.monitoring import drift
from src.monitoring.performance import identity_arrays
from src.monitoring.protocol import MonitorGuard, maturity_cutoff, month_bounds
from src.training import native_supervisor, resources
from src.validation.run import _sha256
from tests.fixtures.monitoring import prepared


def test_psi_stable_shift_and_invalid_values():
    assert drift.psi([1000, 1000, 0], [1000, 1000, 0]) == 0
    assert drift.psi([1000, 1000, 0], [0, 0, 2000]) > 0.2
    assert np.isfinite(drift.psi([0, 2000], [2000, 0]))
    with pytest.raises(ValueError):
        drift.psi([1, -1], [1, 2])
    with pytest.raises(ValueError):
        drift.psi([1, 2], [1])


def test_threshold_strict_and_low_volume_not_zero(monkeypatch):
    names = drift.FEATURE_COLUMNS
    payload = {
        "counts": {"7": {name: {"1": 2000} for name in names}},
        "domains": {name: ["1", drift.UNKNOWN] for name in names},
    }
    reference = {"reference": payload, "reference_sha256": "f" * 64}
    current = {name: {"1": 2000} for name in names}
    monkeypatch.setattr(drift, "psi", lambda *args, **kwargs: 0.2)
    assert drift.compare_counts(reference, current, 7)["status"] == "OBSERVED"
    monkeypatch.setattr(drift, "psi", lambda *args, **kwargs: 0.200001)
    assert drift.compare_counts(reference, current, 7)["status"] == "ALERT"
    current = {name: {"1": 999} for name in names}
    result = drift.compare_counts(reference, current, 7)
    assert result["status"] == "NOT_AVAILABLE"
    assert all(value["psi"] is None for value in result["features"].values())


def test_reference_tampering_cannot_be_hidden_by_rehashing(tmp_path):
    _, config, _, _ = prepared(tmp_path)
    reference = drift.load_reference(tmp_path / "reference.json", config)
    changed = deepcopy(reference)
    changed["reference"]["counts"]["7"]["pickup_hour"] = {"9": 2000}
    changed["reference_sha256"] = drift.fingerprint(changed["reference"])
    (tmp_path / "reference.json").write_text(json.dumps(changed), encoding="utf-8")
    assert _sha256(tmp_path / "reference.json") != config["reference"]["sha256"]
    with pytest.raises(ValueError, match="sellada"):
        drift.load_reference(tmp_path / "reference.json", config)


def test_ny_dst_boundaries_and_exact_utc_maturity():
    start, end = month_bounds(2025, 3)
    assert (end - start).total_seconds() == 31 * 86400 - 3600
    assert maturity_cutoff(2025, 3) - end == timedelta(hours=24)
    start, end = month_bounds(2025, 11)
    assert (end - start).total_seconds() == 30 * 86400 + 3600


def test_identity_does_not_truncate_long_ids():
    import pyarrow as pa

    context = pa.table(
        {"validated_row_index": [0], "pickup_datetime_utc": [1], "source_feature_id": ["a" * 33]}
    )
    with pytest.raises(ValueError, match="invalidas"):
        identity_arrays(context)


@pytest.mark.parametrize("changed", ["available_ram_bytes", "free_disk_bytes", "peak_rss_bytes"])
def test_monitoring_budget_stops_before_or_during_processing(tmp_path, monkeypatch, changed):
    state = {
        "available_ram_bytes": 8 * 2**30,
        "free_disk_bytes": 100 * 2**30,
        "peak_rss_bytes": 2**29,
    }
    state[changed] = 3 * 2**30 if changed != "free_disk_bytes" else 40 * 2**30
    monkeypatch.setattr(resources, "snapshot", lambda _: state)
    with pytest.raises(resources.ResourceLimitError):
        MonitorGuard(tmp_path).check(start=True)


def test_renderer_limit_includes_parent_process(tmp_path, monkeypatch):
    process = MagicMock(pid=123)
    process.__enter__.return_value = process
    process.poll.return_value = None
    monkeypatch.setattr(native_supervisor.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(
        native_supervisor, "process_peak_rss", lambda pid: (1800 if pid == 123 else 300) * 2**20
    )
    with pytest.raises(resources.ResourceLimitError, match="combinado"):
        native_supervisor.supervise(
            ["synthetic-renderer"],
            policy={"process_rss_limit_gib": 2, "native_process_poll_seconds": 0.01},
            guard=Mock(),
            log_path=tmp_path / "worker.log",
            aggregate_parent_rss=True,
        )
    process.kill.assert_called_once()
