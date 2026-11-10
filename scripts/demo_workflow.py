"""T36: flujo completo con fixtures; no downloads ni promocion automatica."""

import argparse
import json
import os
import uuid
from pathlib import Path

import numpy as np

from src.retraining.cohorts import prepare
from src.retraining.compare import compare
from src.retraining.evaluate import ACTIONS, execute
from src.retraining.evaluation import evaluate_pair
from src.retraining.fixture_register import register_fixture
from src.retraining.protocol import exclusive_json
from src.retraining.services import DemoGuard, ManagedProcess, free_port
from src.retraining.train_challenger import train
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def demo(directory, *, project=None):
    from src.retraining.demo_fixture import PAYLOAD
    from tests.integration.test_retraining_cohorts import prepared
    from tests.integration.test_retraining_evaluation import final_catalog

    os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
    root = Path(directory).resolve()
    project = Path(project or Path.cwd()).resolve()
    if root == project or not root.is_relative_to(project):
        raise ValueError("Demo requiere raiz aislada nueva")
    root.mkdir(parents=True, exist_ok=False)
    exclusive_json(
        root / "ISOLATED_DEMO.json", {"status": "TEST_ONLY", "scope_id": uuid.uuid4().hex}
    )
    guard = DemoGuard(root)
    registry = ManagedProcess(root, "mlflow", free_port(), guard)
    state = {}
    trigger = {"publication_complete": True, "decision": "RETRAIN_RECOMMENDED"}
    approval = {
        "status": "TEST_ONLY",
        "allowed_actions": list(ACTIONS),
        "automatic_promotion": False,
        "trigger_sha256": fingerprint(trigger),
    }

    def entry(path, base):
        return {"path": str(path.relative_to(base)), "sha256": _sha256(path)}

    def completed(path):
        guard.check()
        return {
            "mode": "TEST_ONLY",
            "publication_complete": True,
            "evidence": str(path.relative_to(root)),
        }

    def prepare_step():
        inputs = root / "inputs"
        config, catalog, profile = prepared(inputs)
        state.update(inputs=inputs, config=config, profile=profile)
        for name, cat in [
            ("train", catalog),
            ("validation", final_catalog(inputs, months=(1, 2, 3))),
            ("final", None),
        ]:
            if cat is None:
                cat = final_catalog(inputs)
            folder, _ = prepare(cat, name, profile_path=config, root=inputs, test_only=True)
            state[name + "_cohort"] = folder
        return completed(state["train_cohort"] / "cohort.json")

    def train_step():
        packet = {
            "status": "TRIGGER_TEST_ONLY",
            "publication_complete": True,
            "decision": "RETRAIN_RECOMMENDED",
            "profile_sha256": fingerprint(state["profile"]),
        }
        file = state["inputs"] / "workflow-trigger.json"
        exclusive_json(file, packet)
        output, result = train(
            state["train_cohort"],
            entry(file, state["inputs"]),
            profile_path=state["config"],
            root=state["inputs"],
            test_only=True,
        )
        if not result["publication_complete"]:
            raise ValueError(result.get("error"))
        state["training"] = entry(output / "training_manifest.json", state["inputs"])
        state["training_result"] = result
        state["model"] = output / "lightgbm.joblib"
        return completed(output / "training_manifest.json")

    fixture = {
        "champion": (lambda X: (np.full(len(X), 12.0), 0), {"scope": "synthetic"}, lambda: None),
        "smoke_payloads": [PAYLOAD],
    }

    def evaluation(stage):
        output, result = evaluate_pair(
            state[stage + "_cohort"],
            stage,
            state["training"],
            profile_path=state["config"],
            root=state["inputs"],
            test_only=True,
            prediction_fixture=fixture,
        )
        if not result["publication_complete"]:
            raise ValueError(result.get("error"))
        state[stage + "_evaluation"] = entry(output / "evaluation.json", state["inputs"])
        return completed(output / "evaluation.json")

    def register_step():
        registry.start()
        path, result = register_fixture(
            root, f"http://127.0.0.1:{registry.port}", state["model"], state["training_result"]
        )
        state["registration"] = result
        return {**completed(path), "candidate_registered": True}

    def compare_step():
        path, result = compare(
            state["final_evaluation"],
            profile_path=state["config"],
            root=state["inputs"],
            test_only=True,
        )
        state["gate"] = result["decision"]
        return completed(path)

    actions = {
        "prepare": prepare_step,
        "train": train_step,
        "validation": lambda: evaluation("validation"),
        "register": register_step,
        "final": lambda: evaluation("final"),
        "compare": compare_step,
    }
    no_action = execute({**trigger, "decision": "NO_ACTION"}, actions, approval=approval)
    assert no_action["steps"] == [] and not state
    result = {"status": "FAIL", "scope": "TEST_ONLY"}
    try:
        result = execute(trigger, actions, approval=approval)
        result.update(
            no_action_no_calls_verified=True,
            candidate_registered=state["registration"],
            gate_decision=state["gate"],
            fixture_rows=48,
            resources={"combined_peak_rss_bytes": guard.peak},
            real_models_fitted=False,
        )
    finally:
        registry.stop()
        result["owned_services_stopped"] = True
        exclusive_json(root / "workflow-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(demo(args.output_dir)))


if __name__ == "__main__":
    main()
