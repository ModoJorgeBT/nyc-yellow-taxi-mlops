"""T19: aprobación inicial explícita y resolución de una versión fija."""

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from src.ingestion.manifest import publish_manifest, utc_now
from src.training.candidate_runtime import CandidateGuard
from src.training.tracking import local_path, read_object, sha256
from src.training.train import source_digest
from src.validation.schema import fingerprint


class ChampionUnavailable(ValueError):
    """No hay una versión aprobada que coincida con el estado del Registry."""


@dataclass(frozen=True)
class ApprovedChampion:
    name: str
    version: str
    run_id: str
    model_uri: str
    model_sha256: str
    approval_id: str
    approval_sha256: str


def read_approval(path: Path, *, test_only: bool = False) -> dict:
    if not path.is_file():
        raise ChampionUnavailable("No existe una elección aprobada de champion")
    decision = read_object(path)
    target = decision.get("target", {})
    if (
        type(test_only) is not bool
        or decision.get("format_version") != 1
        or decision.get("approval_status") != ("TEST_ONLY" if test_only else "APPROVED")
        or decision.get("scope") != "initial_champion_only"
        or decision.get("approved_by") != "USER_EXPLICIT_IN_CONVERSATION"
        or decision.get("automatic_future_promotion_authorized") is not False
        or decision.get("hyperparameter_search_authorized") is not False
        or decision.get("segment_limitations_acknowledged") is not True
        or target.get("family") != "lightgbm"
        or not isinstance(target.get("version"), str)
        or not target["version"].isdigit()
        or int(target["version"]) <= 0
        or decision.get("tracking_uri") != "http://127.0.0.1:5000"
        or not decision.get("approval_id")
        or (test_only and decision.get("fixture_origin") != "synthetic")
        or (test_only and not target.get("name", "").startswith("synthetic-"))
        or (not test_only and target.get("name") != "nyc-yellow-taxi-duration")
    ):
        raise ChampionUnavailable("La elección de champion no está aprobada para este ámbito")
    return decision


def _client():
    os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    from mlflow import MlflowClient

    return MlflowClient(tracking_uri="http://127.0.0.1:5000", registry_uri="http://127.0.0.1:5000")


def _records(root: Path, decision: dict) -> tuple[Path, Path]:
    folder = (root / "tracking/approvals").resolve()
    if not folder.is_relative_to(root.resolve()):
        raise ChampionUnavailable("Directorio de aprobaciones fuera del proyecto")
    key = fingerprint(decision)
    return folder / f"{key}.prepared.json", folder / f"{key}.applied.json"


def verify_evidence(decision: dict, root: Path, *, test_only: bool) -> None:
    documents = {}
    for role, info in decision["evidence"].items():
        path = local_path(root, info["path"])
        if sha256(path) != info["sha256"]:
            raise ChampionUnavailable("La evidencia aprobada fue alterada")
        documents[role] = read_object(path)
    audit, tracking, final = [documents[k] for k in ("tracking_audit", "registration", "final")]
    target = decision["target"]
    expected_mode = "TEST_ONLY" if test_only else "REAL"
    if (
        audit.get("status") != f"VERIFIED_T18_{expected_mode}_SQLITE_ARTIFACTS_AND_LINEAGE"
        or tracking.get("status") != f"TRACKING_{expected_mode}"
        or final.get("status") != f"FINAL_EVALUATION_{expected_mode}"
        or final.get("publication_complete") is not True
        or final["configuration"]["models"]["lightgbm"]["sha256"] != target["model_sha256"]
        or tracking["models"]["lightgbm"]["version"] != target["version"]
        or tracking["models"]["lightgbm"]["run_id"] != target["run_id"]
        or tracking["models"]["lightgbm"]["model_sha256"] != target["model_sha256"]
        or audit["models_verified"]["lightgbm"]["version"] != target["version"]
        or audit["models_verified"]["lightgbm"]["run_id"] != target["run_id"]
        or audit["models_verified"]["lightgbm"]["frozen_model_sha256"] != target["model_sha256"]
    ):
        raise ChampionUnavailable("La elección no corresponde a las evidencias auditadas")


def _identity(client, decision: dict):
    target = decision["target"]
    version = client.get_model_version(target["name"], target["version"])
    run = client.get_run(target["run_id"])
    expected_tags = {
        "family": "lightgbm",
        "model_sha256": target["model_sha256"],
        "training_manifest_sha256": target["training_manifest_sha256"],
        "code_sha256_at_registration": target["registered_code_sha256"],
    }
    if (
        str(version.version) != target["version"]
        or version.run_id != target["run_id"]
        or version.source != target["logged_model_uri"]
        or version.status != "READY"
        or run.info.status != "FINISHED"
        or any(version.tags.get(k) != v for k, v in expected_tags.items())
        or fingerprint(run.data.metrics) != target["run_metrics_sha256"]
        or fingerprint(run.data.params) != target["run_params_sha256"]
    ):
        raise ChampionUnavailable("La versión, ajuste o evaluación del Registry no coincide")
    return version


def _aliases(client, name: str) -> dict:
    # SQLite y REST pueden devolver números o strings para la misma versión.
    return {key: str(value) for key, value in client.get_registered_model(name).aliases.items()}


def artifact_files(directory: Path) -> dict:
    result = {}
    for path in sorted(directory.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ChampionUnavailable("Un artefacto registrado es un enlace simbólico")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = sha256(path)
    return result


def verify_artifact_files(directory: Path, decision: dict) -> None:
    expected = decision["artifact_files"]
    if artifact_files(directory) != expected:
        raise ChampionUnavailable("El paquete registrado no coincide con sus hashes aprobados")
    if expected.get(decision["frozen_model_artifact"]) != decision["target"]["model_sha256"]:
        raise ChampionUnavailable("El modelo del paquete no es el aprobado")


def _artifact_smoke(decision: dict, root: Path) -> dict:
    import mlflow
    import numpy as np
    import pandas as pd

    target = decision["target"]
    mlflow.set_tracking_uri(decision["tracking_uri"])
    mlflow.set_registry_uri(decision["tracking_uri"])
    cache = (root / ".cache/champion-verification").resolve()
    if not cache.is_relative_to(root.resolve()):
        raise ChampionUnavailable("Cache de verificación fuera del proyecto")
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as owned:
        directory = Path(owned).resolve()
        if not directory.is_relative_to(cache):
            raise ChampionUnavailable("Temporal fuera de la cache propia")
        downloaded = Path(
            mlflow.artifacts.download_artifacts(
                artifact_uri=f"models:/{target['name']}/{target['version']}",
                dst_path=str(directory),
            )
        )
        if not downloaded.resolve().is_relative_to(directory):
            raise ChampionUnavailable("Descarga fuera del temporal propio")
        verify_artifact_files(downloaded, decision)  # Antes de ejecutar pickle o código.
        model = mlflow.pyfunc.load_model(str(downloaded))
        values = []
        for record in decision["smoke"]["payloads"]:
            frame = pd.DataFrame([{k: v for k, v in record.items() if v is not None}])
            values.append(float(model.predict(frame)[0]))
        expected = decision["smoke"]["expected_minutes"]
        np.testing.assert_allclose(values, expected, rtol=0, atol=1e-10)
    return {
        "artifact_manifest_sha256": fingerprint(decision["artifact_files"]),
        "model_sha256": target["model_sha256"],
        "synthetic_payloads": len(values),
        "maximum_difference_minutes": float(np.max(np.abs(np.asarray(values) - expected))),
    }


def resolve_champion(
    config=Path("configs/champion.yaml"), *, root=None, client=None, test_only=False
) -> ApprovedChampion:
    root = Path.cwd() if root is None else Path(root).resolve()
    decision = read_approval(Path(config), test_only=test_only)
    _, applied = _records(root, decision)
    if not applied.is_file():
        raise ChampionUnavailable("No existe una aprobación aplicada de champion")
    receipt = read_object(applied)
    target = decision["target"]
    if (
        receipt.get("status")
        != ("CHAMPION_APPROVED_TEST_ONLY" if test_only else "CHAMPION_APPROVED_REAL")
        or receipt.get("approval_sha256") != fingerprint(decision)
        or receipt.get("target") != target
        or receipt.get("approval_id") != decision["approval_id"]
        or receipt.get("approved_by") != decision["approved_by"]
        or receipt.get("models_fitted") is not False
        or receipt.get("previous_champion_version") is not None
        or receipt.get("artifact_verification", {}).get("model_sha256") != target["model_sha256"]
        or receipt.get("artifact_verification", {}).get("artifact_manifest_sha256")
        != fingerprint(decision["artifact_files"])
    ):
        raise ChampionUnavailable("Recibo de aprobación incompleto o de otro modelo")
    client = _client() if client is None else client
    aliases = _aliases(client, target["name"])
    if str(aliases.get("champion")) != target["version"]:
        raise ChampionUnavailable("El alias champion está ausente o apunta a otra versión")
    version = _identity(client, decision)
    if any(
        version.tags.get(k) != v
        for k, v in {
            "serving_approved": "true",
            "approval_id": decision["approval_id"],
            "approval_sha256": fingerprint(decision),
            "approval_scope": "initial_champion_only",
        }.items()
    ):
        raise ChampionUnavailable("La versión no tiene la aprobación explícita esperada")
    return ApprovedChampion(
        target["name"],
        target["version"],
        target["run_id"],
        f"models:/{target['name']}/{target['version']}",
        target["model_sha256"],
        decision["approval_id"],
        fingerprint(decision),
    )


def approve_initial_champion(
    config=Path("configs/champion.yaml"), *, root=None, client=None, test_only=False
) -> dict:
    root = Path.cwd() if root is None else Path(root).resolve()
    decision = read_approval(Path(config), test_only=test_only)
    verify_evidence(decision, root, test_only=test_only)
    prepared, applied = _records(root, decision)
    prepared.parent.mkdir(parents=True, exist_ok=True)
    client = _client() if client is None else client
    if applied.exists():
        resolve_champion(config, root=root, client=client, test_only=test_only)
        return read_object(applied)
    lock = prepared.with_suffix(".lock")
    with lock.open("x", encoding="utf-8") as exclusive:
        exclusive.close()  # Mantener el marcador; Windows no permite borrarlo abierto.
        try:
            guard = CandidateGuard(decision["resources"], root, test_only=test_only)
            guard.check(start=True)
            target = decision["target"]
            version = _identity(client, decision)
            before = _aliases(client, target["name"])
            previous = before.get("champion")
            if previous is not None and not (
                str(previous) == target["version"]
                and prepared.exists()
                and version.tags.get("approval_sha256") == fingerprint(decision)
            ):
                raise ChampionUnavailable(
                    "Ya existe un champion; T19 solo autoriza la elección inicial"
                )
            if not prepared.exists():
                publish_manifest(
                    prepared,
                    {
                        "status": "INITIAL_CHAMPION_PREPARED",
                        "approval_sha256": fingerprint(decision),
                        "target": target,
                        "previous_aliases": before,
                        "prepared_at_utc": utc_now(),
                    },
                )
            pending = read_object(prepared)
            if (
                pending["approval_sha256"] != fingerprint(decision)
                or pending["target"] != target
                or pending["previous_aliases"].get("champion") is not None
            ):
                raise ChampionUnavailable("Preparación de otra aprobación o cambio de champion")
            artifact = _artifact_smoke(decision, root)
            guard.check()
            if _aliases(client, target["name"]) != before:
                raise ChampionUnavailable("Los alias cambiaron durante la verificación")
            _identity(client, decision)
            for key, value in {
                "approval_id": decision["approval_id"],
                "approval_sha256": fingerprint(decision),
                "approval_scope": "initial_champion_only",
                "serving_approved": "true",
            }.items():
                client.set_model_version_tag(target["name"], target["version"], key, value)
            if previous is None:
                client.set_registered_model_alias(target["name"], "champion", target["version"])
            after = _aliases(client, target["name"])
            if after != {**pending["previous_aliases"], "champion": target["version"]}:
                raise ChampionUnavailable("Estado de alias inesperado después de la aprobación")
            guard.check()
            result = {
                "status": "CHAMPION_APPROVED_TEST_ONLY" if test_only else "CHAMPION_APPROVED_REAL",
                "approval_id": decision["approval_id"],
                "approval_sha256": fingerprint(decision),
                "approved_by": decision["approved_by"],
                "user_instruction": decision["user_instruction"],
                "approved_at_utc": utc_now(),
                "target": target,
                "previous_champion_version": None,
                "aliases_before": pending["previous_aliases"],
                "aliases_after": after,
                "prepared_record_sha256": sha256(prepared),
                "artifact_verification": artifact,
                "models_fitted": False,
                "runner_source_sha256": source_digest(),
                "resources": {
                    "initial": guard.initial,
                    "final": guard.last,
                    "elapsed_seconds": guard.elapsed,
                },
            }
            publish_manifest(applied, result)
            resolve_champion(config, root=root, client=client, test_only=test_only)
            return result
        finally:
            lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/champion.yaml"))
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--approve-initial", action="store_true")
    action.add_argument("--resolve", action="store_true")
    args = parser.parse_args()
    if args.approve_initial:
        result = approve_initial_champion(args.config)
    else:
        result = asdict(resolve_champion(args.config))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
