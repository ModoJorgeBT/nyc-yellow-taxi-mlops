"""T34: gate de elegibilidad para revision humana; nunca cambia un alias."""

import argparse
import math
import uuid
from pathlib import Path

from src.ingestion.manifest import utc_now
from src.retraining.protocol import GATE, exclusive_json, inside, load_profile, pinned, read_json
from src.validation.run import _sha256
from src.validation.schema import fingerprint

METRICS = ("mae_minutes", "rmse_minutes", "medae_minutes", "p90_absolute_error_minutes")
CONTROLS = (
    "quality_accepted",
    "integrity_verified",
    "temporal_cuts_verified",
    "no_leakage",
    "smoke_passed",
    "same_population_verified",
)


def gate_metrics(champion, challenger, required_segments, *, controls):
    missing = sorted(set(CONTROLS) - {k for k, value in controls.items() if value is True})
    if missing:
        return {"decision": "CHALLENGER_REJECTED", "reasons": [{"control_failed": missing}]}
    if set(champion) != set(challenger) or set(champion) != {"all", *required_segments}:
        return {"decision": "NOT_EVALUABLE", "reasons": ["MISSING_OR_UNEXPECTED_SEGMENTS"]}
    failures, insufficient = [], []
    for name in sorted(champion):
        left, right = champion[name], challenger[name]
        if (
            type(left.get("rows")) is not int
            or left["rows"] != right.get("rows")
            or left["rows"] < 1
            or any(
                type(m.get(k)) not in (int, float) or not math.isfinite(m[k]) or m[k] < 0
                for m in (left, right)
                for k in METRICS
            )
        ):
            return {"decision": "NOT_EVALUABLE", "reasons": ["INVALID_METRICS_OR_COVERAGE"]}
        if left["rows"] < GATE["minimum_segment_rows"]:
            insufficient.append(name)
        limits = (
            {
                "mae_minutes": 1 - GATE["minimum_mae_improvement"],
                "rmse_minutes": 1,
                "p90_absolute_error_minutes": 1,
            }
            if name == "all"
            else {
                "mae_minutes": 1 + GATE["maximum_segment_mae_increase"],
                "p90_absolute_error_minutes": 1 + GATE["maximum_segment_p90_increase"],
            }
        )
        for metric, multiplier in limits.items():
            if right[metric] > left[metric] * multiplier:
                failures.append(
                    {
                        "segment": name,
                        "metric": metric,
                        "champion": left[metric],
                        "challenger": right[metric],
                        "maximum_ratio": multiplier,
                    }
                )
    # Cada familia exhaustiva se suma al global; rutas frecuentes son un subconjunto.
    for prefix in ("month_", "band_"):
        names = [name for name in required_segments if name.startswith(prefix)]
        if names and sum(champion[name]["rows"] for name in names) != champion["all"]["rows"]:
            return {"decision": "NOT_EVALUABLE", "reasons": ["SEGMENT_COVERAGE_INCOMPLETE"]}
    if insufficient:
        return {"decision": "NOT_EVALUABLE", "reasons": [{"insufficient_segments": insufficient}]}
    return {
        "decision": "CHALLENGER_REJECTED" if failures else "ELIGIBLE_FOR_HUMAN_REVIEW",
        "reasons": failures,
    }


def compare(
    evaluation_entry, *, profile_path=Path("configs/retraining.yaml"), root=None, test_only=False
):
    root = Path(root or Path.cwd()).resolve()
    profile = load_profile(profile_path, test_only=test_only)
    evaluation_path = pinned(root, evaluation_entry)
    evaluation = read_json(evaluation_path)
    if (
        evaluation.get("status")
        != ("PAIRED_EVALUATION_TEST_ONLY" if test_only else "PAIRED_EVALUATION_REAL")
        or evaluation.get("publication_complete") is not True
        or evaluation.get("profile_sha256") != fingerprint(profile)
        or evaluation.get("period") != profile["periods"]["final"]
        or evaluation.get("candidate_frozen_before_final") is not True
    ):
        raise ValueError("Evaluacion no corresponde al gate final aprobado")
    for entry in evaluation["evidence"]:
        pinned(root, entry)
    result = gate_metrics(
        evaluation["metrics"]["champion"],
        evaluation["metrics"]["challenger"],
        evaluation["required_segments"],
        controls=evaluation["controls"],
    )
    destination = inside(root, "reports/retraining/comparisons")
    if test_only:
        destination /= "_test_only"
    path = destination / f"{uuid.uuid4().hex}.json"
    result.update(
        status="COMPARISON_TEST_ONLY" if test_only else "COMPARISON_REAL",
        profile_sha256=fingerprint(profile),
        timestamp_utc=utc_now(),
        evaluation=evaluation_entry,
        champion_changed=False,
        alias_updated=False,
        policy=GATE,
        publication_complete=True,
    )
    exclusive_json(path, result)
    return path, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    entry = {
        "path": str(args.evaluation.resolve().relative_to(root)),
        "sha256": _sha256(args.evaluation),
    }
    path, report = compare(entry, profile_path=args.config, test_only=args.test_only)
    print({"report": str(path), "decision": report["decision"]})


if __name__ == "__main__":
    main()
