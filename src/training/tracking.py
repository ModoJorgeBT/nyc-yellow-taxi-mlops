"""Registro posterior al fit: candidatos congelados, trazabilidad y cero promoción."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from src.ingestion.manifest import publish_manifest, utc_now
from src.training.candidate_runtime import CandidateGuard
from src.training.tracking_model import FrozenPredictor, python_model
from src.training.train import source_digest
from src.validation.schema import fingerprint

FAMILIES = ("baseline", "sgd", "mlp", "lightgbm")
EXAMPLE = [
    {"pickup_datetime": "2026-01-12T08:30:00-05:00", "pickup_location_id": 161},
    {
        "pickup_datetime": "2026-03-12T18:30:00-04:00",
        "pickup_location_id": 237,
        "passenger_count": 2,
    },
]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_object(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def local_path(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("Artefacto de tracking fuera del proyecto o inexistente")
    return target


def verify_bundle(profile, root, *, test_only=False):
    if type(test_only) is not bool:
        raise ValueError("Modo de tracking inválido")
    expected = "TEST_ONLY" if test_only else "APPROVED"
    uri = urlparse(profile["tracking_uri"])
    if (
        profile.get("approval_status") != expected
        or profile.get("scope") != "register_frozen_candidates_without_promotion"
        or profile.get("champion_assignment_authorized") is not False
        or set(profile["models"]) != set(FAMILIES)
        or uri.scheme != "http"
        or uri.hostname != "127.0.0.1"
        or uri.username
        or uri.password
        or uri.path not in ("", "/")
        or uri.query
        or uri.fragment
        or not uri.port
        or (not test_only and uri.port != 5000)
        or (test_only and profile.get("fixture_origin") != "synthetic")
        or (not test_only and profile.get("approved_by") != "USER_EXPLICIT_IN_CONVERSATION")
        or profile.get("backend_store_uri") != "sqlite:///tracking/mlflow.db"
    ):
        raise ValueError("Contrato de tracking no aprobado o fuera del alcance local")
    for name, digest in profile["lineage_files"].items():
        if sha256(local_path(root, name)) != digest:
            raise ValueError("Linaje de tracking alterado")
    for family, info in profile["models"].items():
        path = local_path(root, info["path"])
        marker_path = local_path(root, info["training_manifest_path"])
        marker = read_object(marker_path)
        if (
            sha256(path) != info["sha256"]
            or sha256(marker_path) != info["training_manifest_sha256"]
        ):
            raise ValueError("Modelo o manifiesto alterado")
        prefix = (
            "BASELINE"
            if family == "baseline"
            else ("LIGHTGBM_TRAINING" if family == "lightgbm" else "TRAINING")
        )
        if marker.get("status") != prefix + ("_TEST_ONLY" if test_only else "_REAL"):
            raise ValueError("Modelo de otro ámbito")
        marker_sha = (
            marker.get("model_sha256")
            if family in ("baseline", "lightgbm")
            else (marker.get("models", {}).get(family, {}).get("sha256"))
        )
        if marker_sha != info["sha256"]:
            raise ValueError("Modelo distinto del ajuste trazado")
    for info in profile["evaluations"].values():
        path = local_path(root, info["path"])
        report = read_object(path)
        if (
            sha256(path) != info["sha256"]
            or report.get("status") != info["status"]
            or report.get("publication_complete") is not True
            or report.get("mode") != ("TEST_ONLY" if test_only else "REAL")
        ):
            raise ValueError("Evaluación de otro ámbito, incompleta o alterada")
    reports = {
        k: read_object(local_path(root, v["path"])) for k, v in profile["evaluations"].items()
    }
    models = profile["models"]
    original = reports["original_2025"]["selection"]
    if (
        original["training_manifest_sha256"] != models["sgd"]["training_manifest_sha256"]
        or original["baseline_manifest_sha256"] != models["baseline"]["training_manifest_sha256"]
        or reports["lightgbm_validation_2025"]["training_manifest_sha256"]
        != models["lightgbm"]["training_manifest_sha256"]
        or models["mlp"]["training_manifest_sha256"] != models["sgd"]["training_manifest_sha256"]
    ):
        raise ValueError("Evaluaciones no enlazadas a los mismos ajustes")
    for family in ("baseline", "sgd", "lightgbm"):
        if (
            reports["final_2026"]["configuration"]["models"][family]["sha256"]
            != models[family]["sha256"]
        ):
            raise ValueError("Holdout final de otro modelo")


def verify_runtime(profile):
    if importlib.metadata.version("mlflow") != profile["mlflow_version"]:
        raise ValueError("Versión MLflow distinta del perfil")
    for name in ("crewai", "trulens", "trulens-providers-litellm"):
        try:
            importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        raise ValueError("Integración fuera del perfil revisado de seguridad")


def metrics_for(profile, root, family):
    result = {}
    for key, info in profile["evaluations"].items():
        report = read_object(local_path(root, info["path"]))
        if key == "original_2025" and family != "lightgbm":
            windows = {
                f"{window}_2025": report[window]["metrics"][family]
                for window in ("validation", "test")
            }
        elif key == "lightgbm_validation_2025" and family == "lightgbm":
            windows = {"validation_2025": report["metrics"]}
        elif key == "final_2026" and family != "mlp":
            if (
                report["configuration"]["models"][family]["sha256"]
                != profile["models"][family]["sha256"]
            ):
                raise ValueError("Métricas finales de otro modelo")
            windows = {"final_2026": report["results"][family]["metrics"]}
        else:
            continue
        for window, groups in windows.items():
            for group, values in groups.items():
                for metric, value in values.items():
                    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                        raise ValueError("Métrica inválida")
                    result[f"{window}.{group}.{metric}"] = value
    if not result:
        raise ValueError("Modelo sin evaluación trazada")
    return result


def parameters_for(profile, root, family):
    info = profile["models"][family]
    marker = read_object(local_path(root, info["training_manifest_path"]))
    result = {
        "family": family,
        "training_scope": profile["training_scope"],
        "model_sha256": info["sha256"],
        "fit_during_registration": False,
        "train_period": "2024-01/2024-12",
    }
    if "source_split_sha256" in marker:
        result["source_split_manifest_sha256"] = marker["source_split_sha256"]
    if family == "baseline":
        result.update(marker["model"])
    elif family == "lightgbm":
        result.update(marker["configuration"]["parameters"])
        result["num_boost_round"] = marker["configuration"]["num_boost_round"]
        if "learned" in marker:
            result["train_rows"] = marker["learned"]["train_rows"]
    else:
        result.update(marker["candidate_configuration"]["candidates"][family])
        result["epochs"] = marker["candidate_configuration"]["epochs"]
        result["train_rows"] = marker["models"][family]["train_rows"]
    return result


def register_candidates(profile_path=Path("configs/tracking.yaml"), *, root=None, test_only=False):
    # Los enlaces con emoji del SDK fallan en consolas Windows cp1252.
    os.environ.setdefault("MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT", "true")
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    import mlflow
    import pandas as pd
    from mlflow import MlflowClient
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    root = Path.cwd() if root is None else Path(root).resolve()
    profile = read_object(profile_path)
    verify_bundle(profile, root, test_only=test_only)
    verify_runtime(profile)
    guard = CandidateGuard(profile["resources"], root, test_only=test_only)
    guard.check(start=True)
    key = fingerprint(profile)
    mlflow.set_tracking_uri(profile["tracking_uri"])
    mlflow.set_registry_uri(profile["tracking_uri"])
    client = MlflowClient()
    names = [x.name for x in client.search_registered_models()]
    name = profile["registered_model_name"]
    aliases_before = dict(client.get_registered_model(name).aliases) if name in names else {}
    if name not in names:
        client.create_registered_model(name, tags={"promotion": "requires_explicit_T19_approval"})
    experiment = client.get_experiment_by_name(profile["experiment_name"])
    experiment_id = (
        experiment.experiment_id
        if experiment
        else client.create_experiment(profile["experiment_name"])
    )
    receipt_root = root / "reports/tracking" / ("_test_only" if test_only else "real")
    receipt_root.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_root / f"{key}.json"
    if receipt_path.exists():
        receipt = read_object(receipt_path)
        verify_registry(receipt, profile, root)
        return receipt
    if client.search_runs([experiment_id], filter_string=f"tags.registration_profile = '{key}'"):
        raise ValueError("Registro parcial existente; revisar antes de crear otro intento")
    code_hash = source_digest()
    lock = local_path(root, "requirements-mlflow.lock")
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
    # Input example sintético; ninguna fila del holdout se usa para empaquetar.
    example = pd.DataFrame([EXAMPLE[0]])
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False
    )
    receipt = {
        "status": "TRACKING_TEST_ONLY" if test_only else "TRACKING_REAL",
        "registered_at_utc": utc_now(),
        "registration_profile_sha256": key,
        "tracking_uri": profile["tracking_uri"],
        "registered_model_name": name,
        "source_tree_sha256": code_hash,
        "tracking_lock_sha256": sha256(lock),
        "git_commit": git.stdout.strip() if git.returncode == 0 else None,
        "git_dirty": bool(dirty.stdout) if dirty.returncode == 0 else None,
        "models_fitted": False,
        "aliases_before": aliases_before,
        "champion_assigned": False,
        "registration_is_posthoc": True,
        "models": {},
    }
    for family in FAMILIES:
        guard.check()
        info = profile["models"][family]
        tags = {
            "family": family,
            "registration_profile": key,
            "model_sha256": info["sha256"],
            "training_manifest_sha256": info["training_manifest_sha256"],
            "registration_is_posthoc": "true",
            "serving_approved": "false",
            "code_sha256_at_registration": code_hash,
            "git_commit": receipt["git_commit"] or "UNKNOWN",
            "git_dirty": str(receipt["git_dirty"]),
            "final_2026_available": str(family != "mlp").lower(),
            "fixture_origin": "synthetic" if test_only else "NONE",
        }
        with mlflow.start_run(
            experiment_id=experiment_id, run_name=f"{family}-frozen-registration", tags=tags
        ) as run:
            mlflow.log_params(parameters_for(profile, root, family), synchronous=True)
            mlflow.log_metrics(metrics_for(profile, root, family), synchronous=True)
            for relative in profile["lineage_files"]:
                mlflow.log_artifact(
                    str(local_path(root, relative)),
                    artifact_path=(Path("lineage") / Path(relative).parent).as_posix(),
                )
            mlflow.log_artifact(str(lock), artifact_path="environment")
            mlflow.log_dict(profile, "registration_profile.json")
            logged = mlflow.pyfunc.log_model(
                name="model",
                python_model=python_model(family, info["sha256"]),
                artifacts={"frozen_model": str(local_path(root, info["path"]))},
                code_paths=[str(Path(__file__).resolve().parents[1])],
                signature=signature,
                input_example=example,
                pip_requirements=str(lock),
                metadata={
                    "family": family,
                    "model_sha256": info["sha256"],
                    "serving_approved": False,
                },
            )
            version = mlflow.register_model(logged.model_uri, name, tags=tags)
            receipt["models"][family] = {
                "version": version.version,
                "run_id": run.info.run_id,
                "model_uri": f"models:/{name}/{version.version}",
                "model_sha256": info["sha256"],
                "logged_model_uri": logged.model_uri,
            }
    if source_digest() != code_hash:
        raise ValueError("Código cambió durante el registro")
    verify_bundle(profile, root, test_only=test_only)
    verify_registry(receipt, profile, root)
    guard.check()
    receipt["resources"] = {
        "initial": guard.initial,
        "final": guard.last,
        "elapsed_seconds": guard.elapsed,
    }
    publish_manifest(receipt_path, receipt)
    return receipt


def verify_registry(receipt, profile, root):
    import mlflow
    import pandas as pd
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(profile["tracking_uri"])
    mlflow.set_registry_uri(profile["tracking_uri"])
    if (
        set(receipt["models"]) != set(FAMILIES)
        or receipt["registration_profile_sha256"] != fingerprint(profile)
        or receipt["tracking_uri"] != profile["tracking_uri"]
        or receipt["registered_model_name"] != profile["registered_model_name"]
        or receipt["models_fitted"] is not False
        or receipt["champion_assigned"] is not False
    ):
        raise ValueError("Recibo de tracking incompleto o de otro perfil")
    client = MlflowClient()
    if (
        dict(client.get_registered_model(profile["registered_model_name"]).aliases)
        != receipt["aliases_before"]
    ):
        raise ValueError("Los alias del Registry cambiaron")
    for family, item in receipt["models"].items():
        if item["model_uri"] != f"models:/{profile['registered_model_name']}/{item['version']}":
            raise ValueError("URI de otra versión registrada")
        version = client.get_model_version(profile["registered_model_name"], item["version"])
        if (
            version.run_id != item["run_id"]
            or version.tags.get("model_sha256") != item["model_sha256"]
            or item["model_sha256"] != profile["models"][family]["sha256"]
        ):
            raise ValueError("Registry no coincide con el modelo congelado")
        run = client.get_run(item["run_id"])
        if run.info.status != "FINISHED":
            raise ValueError("Run incompleto")
        expected_metrics = metrics_for(profile, root, family)
        if run.data.metrics != expected_metrics:
            raise ValueError("Métricas del run no coinciden")
        for key, value in parameters_for(profile, root, family).items():
            if run.data.params.get(key) != str(value):
                raise ValueError("Parámetros del run no coinciden")
        model = mlflow.pyfunc.load_model(item["model_uri"])
        info = profile["models"][family]
        native = FrozenPredictor(family, local_path(root, info["path"]), info["sha256"])
        for records in (EXAMPLE[:1], EXAMPLE[1:]):
            actual = model.predict(pd.DataFrame(records))
            import numpy as np

            np.testing.assert_allclose(actual, native.predict(records), rtol=0, atol=1e-10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/tracking.yaml"))
    args = parser.parse_args()
    result = register_candidates(args.config)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
