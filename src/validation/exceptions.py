"""Aceptacion humana puntual: conserva FAIL medido y todas las exclusiones."""

import hashlib
import json
from pathlib import Path

from src.validation.schema import fingerprint


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_exception(path: Path) -> dict:
    try:
        return _load_exception(path)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Registro de excepcion incompleto") from error


def _allowed_failures(document: dict) -> list[dict]:
    version = document.get("format_version")
    if type(version) is not int:
        raise ValueError("Version de excepcion incompatible")
    if version == 1:
        failures = [document["allowed_failure"]]
        expected_rules = {"rows.duration_nonpositive"}
        if "allowed_failures" in document:
            raise ValueError("Excepcion v1 con conjuntos de fallos incompatibles")
    elif version == 2:
        failures = document["allowed_failures"]
        expected_rules = {"rows.duration_nonpositive", "rows.union_invalid_rows"}
        if "allowed_failure" in document:
            raise ValueError("Excepcion v2 con autorizaciones contradictorias")
    else:
        raise ValueError("Version de excepcion incompatible")
    if (
        not isinstance(failures, list)
        or not failures
        or any(not isinstance(failure, dict) for failure in failures)
    ):
        raise ValueError("Conjunto de fallos autorizado incompleto")
    rules = [failure.get("rule") for failure in failures]
    if (
        any(not isinstance(rule, str) for rule in rules)
        or len(set(rules)) != len(rules)
        or not set(rules).issubset(expected_rules)
        or "rows.duration_nonpositive" not in rules
        or any(failure.get("status") != "FAIL" for failure in failures)
    ):
        raise ValueError("La excepcion no cubre ese conjunto de fallos")
    return failures


def _load_exception(path: Path) -> dict:
    path = path.resolve()
    document = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "approval_status": "APPROVED",
        "approved_by": "USER_EXPLICIT_IN_CONVERSATION",
        "preserve_invalid_row_exclusions": True,
        "allow_other_failures": False,
        "allow_other_lots": False,
    }
    if not isinstance(document, dict) or any(
        type(document.get(k)) is not type(v) or document[k] != v for k, v in required.items()
    ):
        raise ValueError("Excepcion de calidad sin aprobacion explicita o con alcance ampliado")
    allowed = _allowed_failures(document)
    reference = (path.parent / document["rejected_report"]["relative_path"]).resolve()
    if digest(reference) != document["rejected_report"]["sha256"]:
        raise ValueError("Reporte FAIL original alterado o no verificable")
    rejected = json.loads(reference.read_text(encoding="utf-8"))
    failures = [c for c in rejected["checks"] if c["status"] == "FAIL"]
    if (
        rejected.get("status") != "FAIL"
        or rejected.get("execution_status") != "REJECTED"
        or rejected.get("mode") != "NORMAL"
        or rejected.get("quality_passed") is not False
        or rejected.get("data_quality_approved") is not False
        or rejected.get("output") is not None
        or rejected.get("error") is not None
        or rejected.get("scan_scope") != "FULL_PARQUET"
        or rejected.get("eligibility_complete") is not True
        or failures != allowed
    ):
        raise ValueError(
            "La excepcion solo admite el rechazo completo y el conjunto de fallos autorizados"
        )
    context = {
        "path": path,
        "document": document,
        "reference": rejected,
        "authorization_sha256": digest(path),
    }
    bind_exception(rejected, context)
    return context


def bind_exception(report: dict, context: dict) -> None:
    document = context["document"]
    manifest = report["input"]["manifest"]
    if (
        (report["year"], report["month"]) != (document["year"], document["month"])
        or (manifest["year"], manifest["month"]) != (document["year"], document["month"])
        or manifest["sha256"] != document["raw_sha256"]
        or report["config_sha256"] != document["config_sha256"]
        or report["configuration"]["quality"]["policy_version"] != document["policy_version"]
        or fingerprint(report["configuration"]) != document["config_sha256"]
    ):
        raise ValueError("Excepcion no corresponde al mes/hash/configuracion autorizados")


def authorize_exception(report: dict, path: Path) -> dict:
    context = load_exception(path)
    bind_exception(report, context)
    original = context["reference"]
    failures = [c for c in report["checks"] if c["status"] == "FAIL"]
    if (
        report.get("scan_scope") != "FULL_PARQUET"
        or report.get("eligibility_complete") is not True
        or report.get("lineage_status") != "VERIFIED_CONTENT"
        or failures != _allowed_failures(context["document"])
        or any(
            report.get(k) != original.get(k)
            for k in (
                "rows_scanned",
                "eligible_rows",
                "excluded_rows",
                "normalizations",
            )
        )
        or not any(
            c["rule"] == "input.exhaustive" and c["status"] == "PASS" for c in report["checks"]
        )
    ):
        raise ValueError(
            "La excepcion no cubre otros fallos, mediciones distintas ni escaneos incompletos"
        )
    evidence = {
        "authorization_path": str(context["path"]),
        "authorization_sha256": context["authorization_sha256"],
        "authorization": context["document"],
        "rejected_report_sha256": context["document"]["rejected_report"]["sha256"],
    }
    if context["document"]["format_version"] == 1:
        evidence["waived_rule"] = "rows.duration_nonpositive"
    else:
        evidence["waived_rules"] = [failure["rule"] for failure in failures]
    return evidence


def verify_exception(report: dict) -> None:
    evidence = report["quality_exception"]
    if (
        report.get("raw_quality_status") != "FAIL"
        or report.get("quality_passed") is not False
        or report.get("status") != "WARN"
        or authorize_exception(report, Path(evidence["authorization_path"])) != evidence
    ):
        raise ValueError("Evidencia de aceptacion excepcional no valida")
