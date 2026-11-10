"""Protocolo T32-T34 aprobado; separado de los contratos historicos congelados."""

import json
from pathlib import Path

from src.monitoring.protocol import exclusive_json, inside, pinned
from src.validation.schema import fingerprint

TRIGGERS = {
    "mae_ratio_strictly_above": 1.15,
    "psi_strictly_above": 0.2,
    "consecutive_calendar_months": 2,
    "minimum_rows": 1000,
    "quarterly_review_months": 3,
    "automatic_training": False,
    "automatic_promotion": False,
}
GATE = {
    "minimum_mae_improvement": 0.02,
    "maximum_global_rmse_increase": 0.0,
    "maximum_global_p90_increase": 0.0,
    "maximum_segment_mae_increase": 0.05,
    "maximum_segment_p90_increase": 0.05,
    "minimum_segment_rows": 1000,
    "noninferiority_enabled": False,
    "automatic_promotion": False,
}
PERIODS = {
    "train": ["2025-01-01T00:00:00-05:00", "2026-01-01T00:00:00-05:00"],
    "validation": ["2026-01-01T00:00:00-05:00", "2026-04-01T00:00:00-04:00"],
    "final": ["2026-04-01T00:00:00-04:00", "2026-07-01T00:00:00-04:00"],
}
RESOURCES = {
    "preparation": {"preflight_min_free_ram_gib": 4, "process_rss_limit_gib": 2},
    "training": {"preflight_min_free_ram_gib": 8, "process_rss_limit_gib": 4},
    "evaluation": {"preflight_min_free_ram_gib": 6, "process_rss_limit_gib": 2},
}
COMMON_RESOURCES = {
    "preflight_min_free_disk_gib": 50,
    "threads_total": 4,
    "parallel_models": 1,
    "candidate_timeout_seconds": 7200,
    "native_process_poll_seconds": 0.1,
}
DOWNLOADS = {
    "year": 2026,
    "months": [4, 5, 6],
    "max_file_bytes": 512 * 2**20,
    "max_total_bytes": 2**30,
}
APPROVED_PROFILE_SHA256 = "560d2108aa754cfc681e41c5febdd52f7b0708d8357e84a1af8be0dc6c5cab71"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_profile(path=Path("configs/retraining.yaml"), *, test_only=False):
    profile = read_json(path)
    if (
        profile.get("status") != ("TEST_ONLY" if test_only else "APPROVED")
        or profile.get("protocol") != "challenger-2025-v1"
        or profile.get("triggers") != TRIGGERS
        or profile.get("gate") != GATE
        or profile.get("periods") != PERIODS
        or profile.get("resources") != RESOURCES
        or profile.get("downloads") != DOWNLOADS
        or (test_only and profile.get("fixture_origin") != "synthetic")
        or (not test_only and fingerprint(profile) != APPROVED_PROFILE_SHA256)
    ):
        raise ValueError("Protocolo T32-T34 distinto del aprobado")
    return profile


def budget(stage):
    return {**COMMON_RESOURCES, **RESOURCES[stage]}


__all__ = ["budget", "exclusive_json", "inside", "load_profile", "pinned", "read_json"]
