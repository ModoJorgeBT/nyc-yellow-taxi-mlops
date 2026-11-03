"""Politica compartida solo para fixtures; ningun limite esta calibrado para TLC."""

from src.validation.rules import METRICS


def synthetic_policy(config: dict) -> dict:
    config["quality"] = {
        "policy_version": "synthetic-tests-v1",
        "status": "TEST_ONLY",
        "timestamp_policy": "naive_wall_clock",
        "min_rows": 1,
        "min_eligible_rows": 1,
        "duration_max_minutes": 120,
        "zone_catalog": {"version": "synthetic-v1", "ids": [161, 236, 264, 265]},
        "duplicate_action": "measure_only",
        "passenger_range": [0, 6],
        "passenger_action": "measure_only",
        "category_values": {"RatecodeID": [1], "store_and_fwd_flag": ["N", "Y"]},
        "category_action": "measure_only",
        "max_rates": dict.fromkeys(METRICS, 0.5),
    }
    config["quality"]["max_rates"]["passenger_null"] = 1
    return config
