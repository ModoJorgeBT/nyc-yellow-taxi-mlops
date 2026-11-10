"""Modelos/metricas sinteticos declarados; nunca candidatos cientificos reales."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np

from src.retraining.compare import CONTROLS, gate_metrics
from src.retraining.lifecycle import atomic_json, event
from src.retraining.protocol import exclusive_json
from src.training.champion import artifact_files
from src.validation.run import _sha256
from src.validation.schema import fingerprint

PAYLOAD = {
    "pickup_datetime": "2026-04-15T08:30:00-04:00",
    "pickup_location_id": 161,
    "passenger_count": 1,
}


def fixture_model(digest):
    from mlflow.pyfunc import PythonModel

    class ConstantDuration(PythonModel):
        def load_context(self, context):
            path = Path(context.artifacts["frozen_model"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("Fixture alterada")
            value = json.loads(path.read_text())
            if value["scope"] != "TEST_ONLY":
                raise ValueError("No es fixture sintetica")
            self.value = float(value["minutes"])

        def predict(self, context, model_input, params=None):
            return np.full(len(model_input), self.value, dtype=float)

    return ConstantDuration()


def models(root, uri):
    import mlflow
    import pandas as pd
    from mlflow import MlflowClient
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    root = Path(root)
    scope = json.loads((root / "ISOLATED_DEMO.json").read_text())["scope_id"]
    name = f"synthetic-lifecycle-{scope}"
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    client = MlflowClient()
    experiment = client.create_experiment(name)
    code = root / "package/src"
    code.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1]
    for path in source.rglob("*.py"):
        target = code / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    signature = ModelSignature(
        inputs=Schema(
            [
                ColSpec("string", "pickup_datetime"),
                ColSpec("long", "pickup_location_id"),
                ColSpec("long", "passenger_count", required=False),
            ]
        ),
        outputs=Schema([ColSpec("double")]),
    )
    decisions = []
    for minutes in [10.0, 12.0]:
        data = root / f"fixture-{int(minutes)}.json"
        exclusive_json(data, {"scope": "TEST_ONLY", "minutes": minutes})
        digest = _sha256(data)
        tags = {"family": "fixture_constant", "model_sha256": digest, "fixture_origin": "synthetic"}
        with mlflow.start_run(experiment_id=experiment, tags=tags) as run:
            mlflow.log_params({"fixture_origin": "synthetic", "minutes": minutes})
            logged = mlflow.pyfunc.log_model(
                name="model",
                python_model=fixture_model(digest),
                artifacts={"frozen_model": str(data)},
                code_paths=[str(code)],
                signature=signature,
                input_example=pd.DataFrame([PAYLOAD]),
                pip_requirements=[],
            )
            version = mlflow.register_model(logged.model_uri, name, tags=tags)
            run_id = run.info.run_id
        snapshot = client.get_run(run_id)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            package = Path(
                mlflow.artifacts.download_artifacts(
                    artifact_uri=f"models:/{name}/{version.version}", dst_path=directory
                )
            )
            files = artifact_files(package)
            frozen = [n for n, h in files.items() if h == digest]
            if len(frozen) != 1:
                raise ValueError("Artefacto congelado de fixture no es unico")
        decisions.append(
            {
                "format_version": 2,
                "scope": "controlled_champion_v2",
                "approval_status": "TEST_ONLY",
                "approved_by": "USER_APPROVED_SYNTHETIC_DEMO",
                "automatic_future_promotion_authorized": False,
                "fixture_origin": "synthetic",
                "scope_id": scope,
                "action": "BOOTSTRAP_FIXTURE",
                "operation_id": "bootstrap",
                "tracking_uri": uri,
                "artifact_files": files,
                "frozen_model_artifact": frozen[0],
                "target": {
                    "family": "fixture_constant",
                    "name": name,
                    "version": str(version.version),
                    "run_id": run_id,
                    "model_sha256": digest,
                    "logged_model_uri": logged.model_uri,
                    "run_metrics_sha256": fingerprint(snapshot.data.metrics),
                    "run_params_sha256": fingerprint(snapshot.data.params),
                },
                "smoke": {"payloads": [PAYLOAD], "expected_minutes": [minutes]},
            }
        )
    return decisions


def gate(root, candidate, *, positive):
    count = 24000
    index = np.arange(count)
    y = np.full(count, 12.0 if positive else 10.0)
    masks = {f"month_2026_{m + 4:02}": index % 3 == m for m in range(3)}
    masks.update({f"band_{b}": index % 4 == b for b in range(4)})
    masks.update({f"route_161_{r + 1}": index % 20 == r for r in range(20)})
    groups = {"all": np.ones(count, dtype=bool), **masks}
    metrics = {}
    for name, prediction in [("champion", 10.0), ("challenger", 12.0)]:
        errors = np.abs(y - prediction)
        metrics[name] = {
            key: {
                "rows": int(mask.sum()),
                "mae_minutes": float(errors[mask].mean()),
                "rmse_minutes": float(np.sqrt(np.mean(errors[mask] ** 2))),
                "medae_minutes": float(np.quantile(errors[mask], 0.5)),
                "p90_absolute_error_minutes": float(np.quantile(errors[mask], 0.9)),
            }
            for key, mask in groups.items()
        }
    controls = dict.fromkeys(CONTROLS, True)
    evaluation = {
        "status": "PAIRED_EVALUATION_TEST_ONLY",
        "fixture_origin": "synthetic",
        "publication_complete": True,
        "candidate_sha256": candidate["target"]["model_sha256"],
        "metrics": metrics,
        "required_segments": list(masks),
        "controls": controls,
    }
    scenario = "positive" if positive else "negative"
    path = Path(root) / f"{scenario}-evaluation.json"
    exclusive_json(path, evaluation)
    result = gate_metrics(
        metrics["champion"], metrics["challenger"], list(masks), controls=controls
    )
    report = {
        "status": "COMPARISON_TEST_ONLY",
        "fixture_origin": "synthetic",
        "publication_complete": True,
        "evaluation": {"path": path.name, "sha256": _sha256(path)},
        **result,
    }
    output = Path(root) / f"{scenario}-gate.json"
    exclusive_json(output, report)
    return {"path": output.name, "sha256": _sha256(output)}


def bootstrap(root, decision, active):
    from src.retraining.lifecycle import client_for

    client = client_for(decision)
    client.set_registered_model_alias(
        decision["target"]["name"], "champion", decision["target"]["version"]
    )
    atomic_json(active, decision)
    event(root, "bootstrap", "APPLIED", approval_sha256=fingerprint(decision))
