"""Registra evidencia T34 en el run candidato; no modifica aliases ni pesos."""

import argparse
import time
from pathlib import Path

from src.retraining.compare import gate_metrics
from src.retraining.protocol import exclusive_json, load_profile, pinned, read_json
from src.retraining.registration import verify_registration
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def log_result(comparison_path, output, *, profile_path=Path("configs/retraining.yaml"), root=None):
    from mlflow import MlflowClient

    root = Path(root or Path.cwd()).resolve()
    comparison_path = Path(comparison_path).resolve()
    if not comparison_path.is_relative_to(root):
        raise ValueError("Comparacion fuera del proyecto")
    profile = load_profile(profile_path)
    report = read_json(comparison_path)
    if (
        report.get("status") != "COMPARISON_REAL"
        or report.get("publication_complete") is not True
        or report.get("profile_sha256") != fingerprint(profile)
        or report.get("champion_changed") is not False
    ):
        raise ValueError("Gate no corresponde al ciclo aprobado")
    evaluation_path = pinned(root, report["evaluation"])
    evaluation = read_json(evaluation_path)
    expected = gate_metrics(
        evaluation["metrics"]["champion"],
        evaluation["metrics"]["challenger"],
        evaluation["required_segments"],
        controls=evaluation["controls"],
    )
    if report["decision"] != expected["decision"] or report["reasons"] != expected["reasons"]:
        raise ValueError("Decision no coincide con reglas/evidencia congeladas")
    entries = [
        e
        for e in evaluation["evidence"]
        if Path(e["path"])
        .as_posix()
        .replace("\\", "/")
        .startswith("reports/retraining/registrations/")
    ]
    if len(entries) != 1:
        raise ValueError("Falta registro candidato unico")
    registration = read_json(pinned(root, entries[0]))
    verify_registration(registration, profile, root)
    if (
        registration["model_sha256"] != evaluation["candidate_sha256"]
        or registration["version"] == "4"
    ):
        raise ValueError("Gate de otro candidato o intento de modificar champion")
    comparison_sha = _sha256(comparison_path)
    output = Path(output)
    if output.exists():
        prior = read_json(output)
        if prior["comparison_sha256"] != comparison_sha:
            raise ValueError("Recibo existente de otra comparacion")
        return prior
    client = MlflowClient(
        tracking_uri="http://127.0.0.1:5000", registry_uri="http://127.0.0.1:5000"
    )
    for name, metrics in evaluation["metrics"].items():
        for key, value in metrics["all"].items():
            client.log_metric(
                registration["run_id"],
                f"t34_final_{name}_{key}",
                float(value),
                int(time.time() * 1000),
            )
    client.log_artifact(registration["run_id"], str(evaluation_path), artifact_path="t34")
    client.log_artifact(registration["run_id"], str(comparison_path), artifact_path="t34")
    tags = {
        "final_evaluation": "COMPLETED_FROZEN_ONCE",
        "t34_decision": report["decision"],
        "t34_evaluation_sha256": report["evaluation"]["sha256"],
        "t34_comparison_sha256": comparison_sha,
    }
    for key, value in tags.items():
        client.set_tag(registration["run_id"], key, value)
        client.set_model_version_tag(registration["name"], registration["version"], key, value)
    verify_registration(registration, profile, root)
    result = {
        "status": "T34_EVIDENCE_LOGGED",
        "name": registration["name"],
        "version": registration["version"],
        "run_id": registration["run_id"],
        "decision": report["decision"],
        "comparison_sha256": comparison_sha,
        "champion_changed": False,
        "aliases": registration["aliases_before"],
    }
    exclusive_json(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    args = parser.parse_args()
    print(log_result(args.comparison, args.output, profile_path=args.config))


if __name__ == "__main__":
    main()
