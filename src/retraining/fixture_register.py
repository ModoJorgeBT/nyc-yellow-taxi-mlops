"""Registro de fixture entrenada en un Registry de prueba, sin aliases."""

from pathlib import Path

from src.retraining.lifecycle import local_uri
from src.retraining.protocol import exclusive_json, read_json
from src.training.tracking_model import python_model
from src.validation.run import _sha256


def register_fixture(root, uri, model_path, training):
    import mlflow
    import pandas as pd
    from mlflow import MlflowClient
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    from src.retraining.demo_fixture import PAYLOAD

    root = Path(root).resolve()
    model_path = Path(model_path).resolve()
    marker = read_json(root / "ISOLATED_DEMO.json")
    local_uri(uri, test_only=True)
    if (
        marker.get("status") != "TEST_ONLY"
        or not model_path.is_relative_to(root)
        or training.get("status") != "CHALLENGER_TRAINING_TEST_ONLY"
        or _sha256(model_path) != training["model_sha256"]
    ):
        raise ValueError("No registrar pesos reales como fixtures")
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    name = "synthetic-workflow-" + marker["scope_id"]
    client = MlflowClient()
    experiment = client.create_experiment(name)
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
    with mlflow.start_run(
        experiment_id=experiment, tags={"fixture_origin": "synthetic", "serving_approved": "false"}
    ) as run:
        logged = mlflow.pyfunc.log_model(
            name="model",
            python_model=python_model("lightgbm", training["model_sha256"]),
            artifacts={"frozen_model": str(model_path)},
            signature=signature,
            input_example=pd.DataFrame([PAYLOAD]),
            pip_requirements=[],
        )
        version = mlflow.register_model(
            logged.model_uri,
            name,
            tags={
                "fixture_origin": "synthetic",
                "model_sha256": training["model_sha256"],
                "serving_approved": "false",
            },
        )
        run_id = run.info.run_id
    model = mlflow.pyfunc.load_model(f"models:/{name}/{version.version}")
    if (
        len(model.predict(pd.DataFrame([PAYLOAD]))) != 1
        or client.get_registered_model(name).aliases
    ):
        raise ValueError("Fixture registrada no verificable o con alias")
    result = {
        "status": "FIXTURE_REGISTERED_TEST_ONLY",
        "fixture_origin": "synthetic",
        "publication_complete": True,
        "name": name,
        "version": str(version.version),
        "run_id": run_id,
        "aliases": {},
        "model_sha256": training["model_sha256"],
    }
    path = root / "fixture-registration.json"
    exclusive_json(path, result)
    return path, result
