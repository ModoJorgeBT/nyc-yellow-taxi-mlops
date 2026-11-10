"""Workflow manual: plan/resume real y ejecucion explicitamente autorizada, sin promover."""

import argparse
import uuid
from pathlib import Path

from src.retraining.protocol import exclusive_json, inside, load_profile, pinned, read_json
from src.retraining.registration import verify_registration
from src.validation.schema import fingerprint

ACTIONS = ("prepare", "train", "validation", "register", "final", "compare")


def execute(trigger, actions, *, approval=None, test_only=True):
    if trigger.get("publication_complete") is not True:
        raise ValueError("Trigger incompleto")
    if trigger.get("decision") == "NO_ACTION":
        return {
            "status": "NO_ACTION",
            "steps": [],
            "models_fitted": False,
            "champion_changed": False,
        }
    if trigger.get("decision") != "RETRAIN_RECOMMENDED":
        return {
            "status": "BLOCKED_REVIEW",
            "steps": [],
            "models_fitted": False,
            "champion_changed": False,
        }
    expected = "TEST_ONLY" if test_only else "APPROVED"
    if (
        not approval
        or approval.get("status") != expected
        or approval.get("trigger_sha256") != fingerprint(trigger)
        or approval.get("allowed_actions") != list(ACTIONS)
        or approval.get("automatic_promotion") is not False
    ):
        return {
            "status": "EXECUTION_APPROVAL_REQUIRED",
            "steps": [],
            "models_fitted": False,
            "champion_changed": False,
        }
    if set(actions) != set(ACTIONS):
        raise ValueError("Workflow fuera del grafo aprobado; promocion separada")
    completed = []
    for name in ACTIONS:
        result = actions[name]()
        if result.get("publication_complete") is not True or result.get("mode") != (
            "TEST_ONLY" if test_only else "REAL"
        ):
            raise ValueError(f"Etapa {name} incompleta o de otro alcance")
        completed.append({"stage": name, **result})
    return {
        "status": "WORKFLOW_TEST_ONLY_COMPLETE" if test_only else "WORKFLOW_REAL_COMPLETE",
        "steps": completed,
        "models_fitted": True,
        "champion_changed": False,
        "automatic_promotion": False,
    }


def resume(campaign, *, profile_path=Path("configs/retraining.yaml"), root=None, plan=False):
    root = Path(root or Path.cwd()).resolve()
    profile = load_profile(profile_path)
    state = read_json(campaign)
    required = {
        "trigger": "TRIGGER_REAL",
        "train": "CHALLENGER_TRAINING_REAL",
        "validation": "PAIRED_EVALUATION_REAL",
        "register": "CHALLENGER_REGISTERED_REAL",
        "final": "PAIRED_EVALUATION_REAL",
        "compare": "COMPARISON_REAL",
    }
    reports = {}
    for name, status in required.items():
        value = read_json(pinned(root, state[name]))
        if value.get("status") != status or value.get("profile_sha256") != fingerprint(profile):
            raise ValueError("Campana/alcance de evidencia incompatible")
        reports[name] = value
    if reports["trigger"]["decision"] != "RETRAIN_RECOMMENDED":
        raise ValueError("Campana ejecutada sin recomendacion")
    model = reports["train"]["model_sha256"]
    if (
        reports["register"]["model_sha256"] != model
        or any(reports[k]["candidate_sha256"] != model for k in ("validation", "final"))
        or reports["compare"]["evaluation"] != state["final"]
        or reports["validation"]["stage"] != "validation"
        or reports["final"]["stage"] != "final"
    ):
        raise ValueError("Etapas de modelos/periodos distintos")
    if not plan:
        verify_registration(reports["register"], profile, root)
    output = inside(root, "reports/retraining/workflows") / f"{uuid.uuid4().hex}.json"
    result = {
        "status": "WORKFLOW_PLAN_VERIFIED" if plan else "WORKFLOW_RESUME_VERIFIED",
        "profile_sha256": fingerprint(profile),
        "reused_evidence": {k: state[k] for k in required},
        "new_fits": 0,
        "new_evaluations": 0,
        "new_downloads": 0,
        "aliases_changed": False,
        "candidate_version": reports["register"]["version"],
        "gate_decision": reports["compare"]["decision"],
        "new_scientific_campaign": "REQUIRES_SEPARATE_APPROVAL",
    }
    exclusive_json(output, result)
    return output, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    path, result = resume(args.campaign, profile_path=args.config, plan=args.plan)
    print({"report": str(path), **result})


if __name__ == "__main__":
    main()
