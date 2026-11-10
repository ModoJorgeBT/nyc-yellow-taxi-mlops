"""Registro idempotente de un challenger validado, sin asignar alias."""

import os
from pathlib import Path

from src.ingestion.download import month_lock
from src.ingestion.manifest import utc_now
from src.monitoring.performance import frozen_model
from src.monitoring.protocol import load_config
from src.retraining.evaluation import candidate
from src.retraining.protocol import budget, exclusive_json, inside, load_profile, pinned, read_json
from src.training.candidate_runtime import CandidateGuard
from src.training.tracking import _git_state
from src.training.tracking_model import python_model
from src.training.train import source_digest
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def verify_registration(receipt, profile, root):
    from mlflow import MlflowClient

    if (
        receipt.get("status") != "CHALLENGER_REGISTERED_REAL"
        or receipt.get("profile_sha256") != fingerprint(profile)
        or receipt.get("champion_changed") is not False
    ):
        raise ValueError("Registro no corresponde al nuevo ciclo")
    client = MlflowClient(
        tracking_uri="http://127.0.0.1:5000", registry_uri="http://127.0.0.1:5000"
    )
    version = client.get_model_version(receipt["name"], receipt["version"])
    if (
        version.run_id != receipt["run_id"]
        or version.tags.get("model_sha256") != receipt["model_sha256"]
        or dict(client.get_registered_model(receipt["name"]).aliases) != receipt["aliases_before"]
        or str(receipt["version"]) in receipt["aliases_before"].values()
    ):
        raise ValueError("Identidad de challenger/alias divergente")
    for entry in receipt["evidence"]:
        pinned(root, entry)
    return version


def register(
    training_entry, validation_entry, *, profile_path=Path("configs/retraining.yaml"), root=None
):
    import mlflow
    import numpy as np
    import pandas as pd
    from mlflow import MlflowClient
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    os.environ.setdefault("MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT", "true")
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    root = Path(root or Path.cwd()).resolve()
    profile = load_profile(profile_path)
    guard = CandidateGuard(budget("preparation"), root, test_only=False)
    guard.check(start=True)
    validation_path = pinned(root, validation_entry)
    validation = read_json(validation_path)
    model, training, model_path = candidate(training_entry, profile, root)
    if (
        validation.get("status") != "PAIRED_EVALUATION_REAL"
        or validation.get("publication_complete") is not True
        or validation.get("stage") != "validation"
        or validation.get("profile_sha256") != fingerprint(profile)
        or validation.get("candidate_sha256") != training["model_sha256"]
    ):
        raise ValueError("Validacion del candidato no verificable")
    monitor = load_config(pinned(root, profile["monitoring_config"]))
    _, champion, check_champion = frozen_model(monitor, root)
    mlflow.set_tracking_uri("http://127.0.0.1:5000")
    mlflow.set_registry_uri("http://127.0.0.1:5000")
    client = MlflowClient()
    name = champion["name"]
    aliases = dict(client.get_registered_model(name).aliases)
    if aliases.get("champion") != "4":
        raise ValueError("Champion distinto del aprobado para este ciclo")
    key = fingerprint(
        {
            "profile": fingerprint(profile),
            "training": training_entry,
            "validation": validation_entry,
        }
    )
    receipts = inside(root, "reports/retraining/registrations")
    receipts.mkdir(parents=True, exist_ok=True)
    path = receipts / f"{key}.json"
    with month_lock(receipts):
        if path.exists():
            receipt = read_json(path)
            verify_registration(receipt, profile, root)
            return path, receipt
        experiment = client.get_experiment_by_name("nyc-yellow-taxi-retraining")
        experiment_id = (
            experiment.experiment_id
            if experiment
            else client.create_experiment("nyc-yellow-taxi-retraining")
        )
        if client.search_runs(
            [experiment_id], filter_string=f"tags.retraining_registration = '{key}'"
        ):
            raise ValueError("Registro parcial existente; revisar sin duplicar candidatos")
        code_hash = source_digest()
        git_commit, git_dirty = _git_state(root)
        tags = {
            "retraining_registration": key,
            "model_sha256": training["model_sha256"],
            "family": "lightgbm",
            "serving_approved": "false",
            "profile_sha256": fingerprint(profile),
            "source_tree_sha256": code_hash,
            "final_evaluation": "NOT_YET_OPENED",
            "git_commit": git_commit or "UNKNOWN",
            "git_dirty": str(git_dirty),
        }
        sample = pd.DataFrame(
            [
                {
                    "pickup_datetime": "2026-02-15T08:30:00-05:00",
                    "pickup_location_id": 161,
                    "passenger_count": 1,
                }
            ]
        )
        expected = model.predict(sample.to_dict(orient="records"))
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
        evidence = [
            training_entry,
            validation_entry,
            profile["runtime_lock"],
            {"path": str(model_path.relative_to(root)), "sha256": training["model_sha256"]},
        ]
        with mlflow.start_run(
            experiment_id=experiment_id, run_name="lightgbm-2025-challenger", tags=tags
        ) as run:
            mlflow.log_params(
                {
                    "train_period": "2025-full",
                    "validation_period": "2026-Q1-known",
                    "final_period": "2026-Q2-reserved",
                    "train_rows": training["rows"],
                    **read_json(pinned(root, profile["lightgbm_config"]))["parameters"],
                }
            )
            mlflow.log_metrics(
                {
                    f"validation_{k}": v
                    for k, v in validation["metrics"]["challenger"]["all"].items()
                }
            )
            for entry in evidence[:-1]:
                mlflow.log_artifact(str(pinned(root, entry)), artifact_path="lineage")
            mlflow.log_dict(profile, "retraining_profile.json")
            logged = mlflow.pyfunc.log_model(
                name="model",
                python_model=python_model("lightgbm", training["model_sha256"]),
                artifacts={"frozen_model": str(model_path)},
                code_paths=[str(Path(__file__).resolve().parents[1])],
                signature=signature,
                input_example=sample,
                pip_requirements=str(pinned(root, profile["runtime_lock"])),
                metadata={
                    "family": "lightgbm",
                    "serving_approved": False,
                    "model_sha256": training["model_sha256"],
                },
            )
            version = mlflow.register_model(logged.model_uri, name, tags=tags)
            reloaded = mlflow.pyfunc.load_model(f"models:/{name}/{version.version}")
            if not np.allclose(reloaded.predict(sample), expected, rtol=0, atol=1e-10):
                raise ValueError("Predicciones del Registry distintas del candidato congelado")
            run_id = run.info.run_id
        check_champion()
        guard.check()
        if source_digest() != code_hash:
            raise ValueError("Codigo alterado durante empaquetado")
        receipt = {
            "status": "CHALLENGER_REGISTERED_REAL",
            "profile_sha256": fingerprint(profile),
            "name": name,
            "version": str(version.version),
            "run_id": run_id,
            "model_sha256": training["model_sha256"],
            "aliases_before": aliases,
            "champion_changed": False,
            "serving_approved": False,
            "evidence": evidence,
            "registered_at_utc": utc_now(),
            "registration_key": key,
            "source_tree_sha256": code_hash,
            "registered_predictions_smoke": "PASS",
            "git_commit": git_commit,
            "git_dirty": git_dirty,
        }
        verify_registration(receipt, profile, root)
        exclusive_json(path, receipt)
    return path, receipt


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    args = parser.parse_args()

    def entry(path):
        return {"path": str(path.resolve().relative_to(Path.cwd())), "sha256": _sha256(path)}

    path, result = register(entry(args.training), entry(args.validation), profile_path=args.config)
    print({"receipt": str(path), "status": result["status"], "version": result["version"]})


if __name__ == "__main__":
    main()
