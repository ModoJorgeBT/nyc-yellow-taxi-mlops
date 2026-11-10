"""Contrato operativo v2 y diario encadenado; T19/v1 permanece independiente."""

import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from src.ingestion.manifest import utc_now
from src.retraining.compare import gate_metrics
from src.retraining.protocol import exclusive_json, inside, pinned, read_json
from src.training.champion import ApprovedChampion, ChampionUnavailable, artifact_files
from src.validation.schema import fingerprint

PROTECTED_PORTS = {5000, 5001, 8000, 8080}


def local_uri(uri, *, test_only):
    parsed = urlparse(uri)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or not parsed.port
        or parsed.port <= 1024
        or (test_only and parsed.port in PROTECTED_PORTS)
        or (not test_only and parsed.port != 5000)
    ):
        raise ChampionUnavailable("Endpoint fuera del alcance local aprobado")
    return uri.rstrip("/")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pending")
    if temporary.exists():
        raise ChampionUnavailable("Escritura parcial existente; requiere recuperacion")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def event(root, operation, state, **data):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", operation):
        raise ChampionUnavailable("Identificador de operacion invalido")
    directory = inside(root, f"tracking/lifecycle/{operation}")
    previous = events(root, operation)
    value = {
        "operation_id": operation,
        "state": state,
        "timestamp_utc": utc_now(),
        "previous_sha256": fingerprint(previous[-1]) if previous else None,
        **data,
    }
    exclusive_json(directory / f"{len(previous):04}.json", value)
    return value


def events(root, operation):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", operation):
        raise ChampionUnavailable("Identificador de operacion invalido")
    paths = sorted(inside(root, f"tracking/lifecycle/{operation}").glob("*.json"))
    result = []
    for index, path in enumerate(paths):
        value = read_json(path)
        if (
            path.name != f"{index:04}.json"
            or value.get("operation_id") != operation
            or value.get("previous_sha256") != (fingerprint(result[-1]) if result else None)
        ):
            raise ChampionUnavailable("Diario parcial o alterado")
        result.append(value)
    return result


def require_gate(root, entry, target, *, test_only=False, previous=None):
    report = read_json(pinned(root, entry))
    if (
        report.get("status") != ("COMPARISON_TEST_ONLY" if test_only else "COMPARISON_REAL")
        or report.get("decision") != "ELIGIBLE_FOR_HUMAN_REVIEW"
        or report.get("publication_complete") is not True
    ):
        raise ChampionUnavailable("Gate no elegible: no se autoriza promover")
    evaluation = read_json(pinned(root, report["evaluation"]))
    if (
        evaluation.get("status")
        != ("PAIRED_EVALUATION_TEST_ONLY" if test_only else "PAIRED_EVALUATION_REAL")
        or evaluation.get("publication_complete") is not True
        or evaluation.get("candidate_sha256") != target["model_sha256"]
        or (test_only and evaluation.get("fixture_origin") != "synthetic")
    ):
        raise ChampionUnavailable("Evaluacion incompatible con el modelo aprobado")
    if previous is not None and any(
        evaluation.get("champion", {}).get(key) != previous[key]
        for key in ("name", "version", "model_sha256")
    ):
        raise ChampionUnavailable("El champion evaluado no coincide con el estado previo")
    result = gate_metrics(
        evaluation["metrics"]["champion"],
        evaluation["metrics"]["challenger"],
        evaluation["required_segments"],
        controls=evaluation["controls"],
    )
    if result["decision"] != "ELIGIBLE_FOR_HUMAN_REVIEW":
        raise ChampionUnavailable("La evidencia recalculada no pasa el gate")
    return report


def read_approval(path, *, root=None, test_only=False, check_gate=True):
    root = Path(root or Path.cwd()).resolve()
    path = inside(root, path)
    decision = read_json(path)
    target = decision.get("target", {})
    if (
        decision.get("format_version") != 2
        or decision.get("scope") != "controlled_champion_v2"
        or decision.get("approval_status") != ("TEST_ONLY" if test_only else "APPROVED")
        or decision.get("approved_by")
        != ("USER_APPROVED_SYNTHETIC_DEMO" if test_only else "USER_EXPLICIT_IN_CONVERSATION")
        or decision.get("automatic_future_promotion_authorized") is not False
        or decision.get("action") not in ("PROMOTE", "BOOTSTRAP_FIXTURE")
        or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", decision.get("operation_id", ""))
        or not isinstance(target.get("version"), str)
        or not target["version"].isdigit()
        or int(target["version"]) < 1
        or not target.get("run_id")
        or not target.get("model_sha256")
        or not decision.get("artifact_files")
        or decision["artifact_files"].get(decision.get("frozen_model_artifact"))
        != target["model_sha256"]
    ):
        raise ChampionUnavailable("Aprobacion operativa v2 incompleta o fuera de alcance")
    if any(
        not isinstance(target.get(k), str) or not target[k]
        for k in ("name", "family", "logged_model_uri", "run_params_sha256", "run_metrics_sha256")
    ):
        raise ChampionUnavailable("Identidad registrada incompleta")
    smoke = decision.get("smoke", {})
    if not smoke.get("payloads") or len(smoke["payloads"]) != len(
        smoke.get("expected_minutes", [])
    ):
        raise ChampionUnavailable("Falta smoke aprobado")
    local_uri(decision["tracking_uri"], test_only=test_only)
    if test_only:
        marker = read_json(root / "ISOLATED_DEMO.json")
        if (
            marker.get("status") != "TEST_ONLY"
            or marker.get("scope_id") != decision.get("scope_id")
            or decision.get("fixture_origin") != "synthetic"
            or not target.get("name", "").startswith("synthetic-")
            or not re.fullmatch(r"[a-f0-9]{32}", decision.get("scope_id", ""))
        ):
            raise ChampionUnavailable("Fixture fuera de su aislamiento")
    elif (
        target.get("name") != "nyc-yellow-taxi-duration"
        or target.get("family") != "lightgbm"
        or decision["action"] != "PROMOTE"
    ):
        raise ChampionUnavailable("Destino real fuera del contrato aprobado")
    if decision["action"] == "BOOTSTRAP_FIXTURE" and not test_only:
        raise ChampionUnavailable("Bootstrap sintetico prohibido en modo real")
    if check_gate and decision["action"] == "PROMOTE":
        require_gate(root, decision["gate"], target, test_only=test_only)
    return decision


def client_for(decision):
    from mlflow import MlflowClient

    return MlflowClient(
        tracking_uri=decision["tracking_uri"], registry_uri=decision["tracking_uri"]
    )


def verify_target(client, decision):
    target = decision["target"]
    version = client.get_model_version(target["name"], target["version"])
    run = client.get_run(target["run_id"])
    if (
        version.run_id != target["run_id"]
        or version.status != "READY"
        or run.info.status != "FINISHED"
        or version.tags.get("model_sha256") != target["model_sha256"]
        or version.tags.get("family") != target["family"]
        or version.source != target["logged_model_uri"]
        or fingerprint(run.data.metrics) != target["run_metrics_sha256"]
        or fingerprint(run.data.params) != target["run_params_sha256"]
    ):
        raise ChampionUnavailable("Identidad/parametros/metricas del candidato cambiaron")
    return version


def aliases(client, name):
    return {k: str(v) for k, v in client.get_registered_model(name).aliases.items()}


def resolve_champion(config, *, root=None, client=None, test_only=False):
    root = Path(root or Path.cwd()).resolve()
    decision = read_approval(config, root=root, test_only=test_only)
    journal = events(root, decision["operation_id"])
    ready = [e for e in journal if e["state"] in ("APPLIED", "VERIFIED")]
    if not ready or ready[-1].get("approval_sha256") != fingerprint(decision):
        raise ChampionUnavailable("Aprobacion sin aplicacion registrada")
    if journal[-1]["state"] not in ("APPLIED", "VERIFIED"):
        raise ChampionUnavailable("Operacion pendiente de recuperacion")
    client = client or client_for(decision)
    verify_target(client, decision)
    target = decision["target"]
    if aliases(client, target["name"]).get("champion") != target["version"]:
        raise ChampionUnavailable("Alias y aprobacion operativa no coinciden")
    return ApprovedChampion(
        target["name"],
        target["version"],
        target["run_id"],
        f"models:/{target['name']}/{target['version']}",
        target["model_sha256"],
        decision["operation_id"],
        fingerprint(decision),
    )


def verified_package(decision, directory):
    if artifact_files(directory) != decision["artifact_files"]:
        raise ChampionUnavailable("Paquete distinto de la aprobacion antes de deserializar")


def identity_dict(identity):
    return asdict(identity)
