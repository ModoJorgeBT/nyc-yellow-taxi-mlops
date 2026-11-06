"""La revisión 6/2 limita inferencia y no permite ampliar otros presupuestos."""

import json
from pathlib import Path

import pytest

from src.evaluation.final_run import resource_review
from src.training import candidate_runtime, resources
from src.training.candidate_runtime import CandidateGuard
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def policy():
    return json.loads(Path("configs/lightgbm-final-resources.yaml").read_text(encoding="utf-8"))[
        "resources"
    ]


@pytest.mark.parametrize(
    "measurement,delta,accept",
    [
        ("available_ram_bytes", 0, True),
        ("available_ram_bytes", -1, False),
        ("peak_rss_bytes", 0, True),
        ("peak_rss_bytes", 1, False),
        ("free_disk_bytes", -1, False),
    ],
)
def test_exact_final_resource_boundaries(tmp_path, monkeypatch, measurement, delta, accept):
    measured = {
        "available_ram_bytes": 6 * 2**30,
        "peak_rss_bytes": 2 * 2**30,
        "free_disk_bytes": 50 * 2**30,
    }
    measured[measurement] += delta
    monkeypatch.setattr(resources, "snapshot", lambda _: measured)
    guard = CandidateGuard(policy(), tmp_path, test_only=False)
    if accept:
        guard.check(start=True)
    else:
        with pytest.raises(resources.ResourceLimitError):
            guard.check(start=True)


def test_final_timeout_still_includes_shared_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(
        resources,
        "snapshot",
        lambda _: {
            "available_ram_bytes": 7 * 2**30,
            "peak_rss_bytes": 1 * 2**30,
            "free_disk_bytes": 60 * 2**30,
        },
    )
    monkeypatch.setattr(candidate_runtime.time, "monotonic", lambda: 1000.0)
    guard = CandidateGuard(policy(), tmp_path, test_only=False, charged_seconds=7201)
    with pytest.raises(resources.ResourceLimitError, match="tiempo"):
        guard.check(start=True)


def test_resource_review_requires_frozen_experiment_and_exact_limits(tmp_path):
    profile = {"models": {"baseline": "fixture"}}
    failed = tmp_path / "failed.json"
    failed.write_text('{"status":"FAIL"}')
    value = {
        "approval_status": "TEST_ONLY",
        "fixture_origin": "synthetic",
        "scope": "frozen_independent_final_inference_only",
        "base_profile_sha256": fingerprint(profile),
        "holdout_manifest_sha256": "a" * 64,
        "failed_report_sha256": _sha256(failed),
        "resources": policy(),
    }
    path = tmp_path / "review.json"
    path.write_text(json.dumps(value))
    effective, _ = resource_review(
        path, profile=profile, holdout_sha="a" * 64, retry_of=failed, test_only=True
    )
    assert effective["preflight_min_free_ram_gib"] == 6
    assert effective["process_rss_limit_gib"] == 2
    value["resources"]["process_rss_limit_gib"] = 3
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="no aprobada"):
        resource_review(
            path, profile=profile, holdout_sha="a" * 64, retry_of=failed, test_only=True
        )
