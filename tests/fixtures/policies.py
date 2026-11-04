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


def pending_policy(config: dict) -> dict:
    """Perfil pendiente explicito, independiente del perfil real activo."""
    config = synthetic_policy(config)
    config["quality"]["status"] = "PENDIENTE"
    for key in (
        "timestamp_policy",
        "min_rows",
        "min_eligible_rows",
        "duration_max_minutes",
        "zone_catalog",
        "duplicate_action",
        "passenger_range",
        "passenger_action",
        "category_values",
        "category_action",
    ):
        config["quality"][key] = None
    config["quality"]["max_rates"] = dict.fromkeys(METRICS, None)
    return config


def real_fixture_policy(config: dict) -> dict:
    """Motor real con volumen/tolerancias SOLO para oraculos sinteticos."""
    policy = config["quality"]
    policy["policy_version"] = "real-engine-fixtures-v1"
    policy["fail_rates"] = dict.fromkeys(policy["fail_rates"], 1.0)
    policy["volume"] = {
        "min_rows": 1,
        "min_eligible_rows": 1,
        "warn_ratio": [0.5, 2.0],
        "reference_2024": {f"{m:02}": 12 for m in range(1, 13)},
    }
    policy["local_authorizations"] = []
    return config
