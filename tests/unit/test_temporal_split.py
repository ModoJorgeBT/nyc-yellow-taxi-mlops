"""Oraculos de cortes D-01 y presupuesto D-02; sin datos TLC reales."""

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from src.training import resources
from src.training.split import SplitError, classify, read_model_config, required_months

CONFIG = Path(__file__).resolve().parents[2] / "configs/model.yaml"


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("2024-01-01T00:00:00-05:00", "2024-01-01T00:01:00-05:00", ("train", None)),
        ("2025-01-01T00:00:00-05:00", "2025-01-01T00:01:00-05:00", ("validation", None)),
        ("2025-04-01T00:00:00-04:00", "2025-04-01T00:01:00-04:00", ("test", None)),
        ("2025-07-01T00:00:00-04:00", "2025-07-01T00:01:00-04:00", ("monitoring_replay", None)),
        (
            "2026-01-01T00:00:00-05:00",
            "2026-01-01T00:01:00-05:00",
            (None, "pickup_outside_protocol"),
        ),
        (
            "2024-12-31T23:59:00-05:00",
            "2025-01-01T00:00:00-05:00",
            (None, "label_not_available_at_cutoff"),
        ),
        (
            "2025-03-31T23:59:00-04:00",
            "2025-04-01T00:01:00-04:00",
            (None, "label_not_available_at_cutoff"),
        ),
        ("2024-03-10T01:55:00-05:00", "2024-03-10T03:05:00-04:00", ("train", None)),
        ("2024-11-03T00:55:00-04:00", "2024-11-03T02:05:00-05:00", ("train", None)),
    ],
)
def test_cutoffs_by_utc_events(start, end, expected):
    assert (
        classify(
            datetime.fromisoformat(start), datetime.fromisoformat(end), read_model_config(CONFIG)
        )
        == expected
    )


def test_offset_required_and_nonpositive_labels_rejected():
    config = read_model_config(CONFIG)
    with pytest.raises(SplitError):
        classify(datetime(2024, 1, 1), datetime(2024, 1, 2), config)
    aware = datetime.fromisoformat("2024-01-01T00:00:00-05:00")
    with pytest.raises(SplitError):
        classify(aware, aware, config)
    assert required_months(config) == {(y, m) for y in (2024, 2025) for m in range(1, 13)}


@pytest.mark.parametrize("change", ["offset", "gap", "sampling", "budget", "approval"])
def test_bad_protocol_rejected_before_input_scan(tmp_path, change):
    config = copy.deepcopy(read_model_config(CONFIG))
    if change == "offset":
        config["partitions"]["test"]["start"] = "2025-04-01T00:00:00-05:00"
    if change == "gap":
        config["partitions"]["test"]["start"] = "2025-05-01T00:00:00-04:00"
    if change == "sampling":
        config["data_scope"] = "SAMPLE"
    if change == "budget":
        config["resources"]["threads_total"] = True
    if change == "approval":
        config["approval_status"] = "PENDING"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(SplitError):
        read_model_config(path)


@pytest.mark.parametrize(
    "metric,value,start",
    [
        ("available_ram_bytes", 12 * 2**30 - 1, True),
        ("free_disk_bytes", 50 * 2**30 - 1, False),
        ("peak_rss_bytes", 8 * 2**30 + 1, False),
    ],
)
def test_budget_failures_are_not_sampling_fallbacks(tmp_path, monkeypatch, metric, value, start):
    observed = {
        "available_ram_bytes": 12 * 2**30,
        "free_disk_bytes": 50 * 2**30,
        "peak_rss_bytes": 8 * 2**30,
    }
    monkeypatch.setattr(resources, "snapshot", lambda directory: observed)
    guard = resources.ResourceGuard(
        read_model_config(CONFIG)["resources"], tmp_path, test_only=False
    )
    guard.check(start=True)  # Igualdad permitida.
    observed[metric] = value
    with pytest.raises(resources.ResourceLimitError):
        guard.check(start=start)


def test_native_resource_observation_has_positive_values(tmp_path):
    observed = resources.snapshot(tmp_path)
    assert set(observed) == {"available_ram_bytes", "peak_rss_bytes", "free_disk_bytes"}
    assert all(value > 0 for value in observed.values())
