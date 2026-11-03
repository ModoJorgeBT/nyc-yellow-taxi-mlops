"""Contrato raw versionado; no es una whitelist de features."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pyarrow as pa


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def check(rule: str, status: str, observed: object, threshold: object, evidence: object) -> dict:
    return {
        "rule": rule,
        "status": status,
        "severity": "critical" if status == "FAIL" else "warning" if status == "WARN" else "info",
        "observed": observed,
        "threshold": threshold,
        "evidence": evidence,
    }


def load_config(path: Path) -> dict:
    """Lee YAML en sintaxis JSON (subconjunto), sin incorporar un parser adicional."""
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(
            "Configuracion ilegible; se requiere sintaxis JSON en data.yaml"
        ) from error
    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    if not isinstance(config, dict) or type(config.get("format_version")) is not int:
        raise ValueError("format_version ausente o incompatible")
    if config["format_version"] != 1 or not isinstance(config.get("schema_version"), str):
        raise ValueError("Version de configuracion incompatible")
    schema = config.get("schema", {})
    if not isinstance(schema, dict):
        raise ValueError("Contrato de esquema invalido")
    columns, required = schema.get("columns"), schema.get("required")
    if not isinstance(columns, dict) or not columns or not isinstance(required, list):
        raise ValueError("Columnas/obligatorias ausentes")
    essential = {"tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID", "DOLocationID"}
    if any(not isinstance(name, str) for name in required):
        raise ValueError("Nombre de columna obligatoria invalido")
    if not essential.issubset(required) or not set(required).issubset(columns):
        raise ValueError("Contrato sin columnas esenciales")
    for name, types in columns.items():
        if (
            not isinstance(name, str)
            or not isinstance(types, list)
            or not types
            or any(not isinstance(item, str) or not item for item in types)
        ):
            raise ValueError("Tipos permitidos invalidos")
    if not isinstance(config.get("quality"), dict):
        raise ValueError("Politica de calidad ausente")
    fingerprint(config)  # Rechaza NaN/Infinity en la configuracion completa.


def validate_schema(actual: pa.Schema, config: dict) -> dict:
    validate_config(config)
    expected = config["schema"]
    names = set(actual.names)
    missing = sorted(set(expected["required"]) - names)
    repeated = sorted(name for name, count in Counter(actual.names).items() if count > 1)
    incompatible = [
        {
            "column": field.name,
            "actual": str(field.type),
            "allowed": expected["columns"][field.name],
        }
        for field in actual
        if field.name in expected["columns"]
        and str(field.type) not in expected["columns"][field.name]
    ]
    extra = sorted(names - set(expected["columns"]))
    failed = bool(missing or repeated or incompatible)
    fields = [
        {"name": field.name, "type": str(field.type), "nullable": field.nullable}
        for field in actual
    ]
    checks = [
        check(
            "schema.structure",
            "FAIL" if failed else "PASS",
            {"missing": missing, "duplicate_names": repeated, "incompatible_types": incompatible},
            {"missing": 0, "duplicate_names": 0, "incompatible_types": 0},
            {"schema_version": config["schema_version"], "fields": fields},
        ),
        check("schema.additional_columns", "WARN" if extra else "PASS", extra, "report", extra),
    ]
    return {
        "status": "FAIL" if failed else "WARN" if extra else "PASS",
        "schema_version": config["schema_version"],
        "schema_fingerprint": fingerprint(fields),
        "checks": checks,
    }
