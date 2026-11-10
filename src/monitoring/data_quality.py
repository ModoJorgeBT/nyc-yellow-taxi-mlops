"""T28: calidad/schema retrospectivos desde evidencia congelada, sin nuevos gates."""

import argparse
import hashlib
import json
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.validation.schema import fingerprint


def policy_identity(configuration: dict) -> str:
    quality = {
        key: value
        for key, value in configuration["quality"].items()
        if key not in ("local_authorizations", "approval", "status")
    }
    return fingerprint({"schema": configuration["schema"], "quality": quality})


def read_profile(entry: dict, config: dict, root: Path) -> dict:
    path = (root / entry["path"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Evidencia fuera del proyecto")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != entry["sha256"]:
        raise ValueError("Reporte congelado modificado")
    report = json.loads(content)
    test_only = config["status"] == "TEST_ONLY"
    if (
        report.get("mode") != ("TEST_ONLY" if test_only else "NORMAL")
        or test_only
        and report.get("fixture_origin") != "synthetic"
        or report.get("lineage_status") != "VERIFIED_CONTENT"
        or report.get("year") != entry["year"]
        or report.get("month") != entry["month"]
        or policy_identity(report["configuration"]) != config["policy_identity_sha256"]
    ):
        raise ValueError("Ambito, periodo, linaje o reglas de calidad no coinciden")
    source = report["input"]["manifest"]
    if (
        source["sha256"] != entry["raw_sha256"]
        or source["year"] != entry["year"]
        or source["month"] != entry["month"]
        or type(source["row_count"]) is not int
        or source["row_count"] <= 0
    ):
        raise ValueError("Fuente del reporte no coincide")
    complete = report.get("scan_scope") == "FULL_PARQUET"
    if complete and (
        report.get("eligibility_complete") is not True
        or report.get("rows_scanned") != source["row_count"]
    ):
        raise ValueError("Escaneo incompleto presentado como completo")
    metrics = {}
    for item in report["checks"]:
        if item["rule"].startswith("rows."):
            observed = item["observed"]
            if not complete or observed.get("count") is None:
                continue
            count, rate = observed["count"], observed["rate"]
            if (
                type(count) is not int
                or not 0 <= count <= source["row_count"]
                or not math.isclose(rate, count / source["row_count"], rel_tol=0, abs_tol=1e-15)
            ):
                raise ValueError("Conteo/tasa de calidad inconsistente")
            metrics[item["rule"]] = {"count": count, "rate": rate, "status": item["status"]}
    failures = [item["rule"] for item in report["checks"] if item["status"] == "FAIL"]
    exception = report.get("quality_exception", {}).get("authorization", {})
    return {
        "year": report["year"],
        "month": report["month"],
        "evidence": entry,
        "raw_rows": source["row_count"],
        "raw_schema": source["schema"],
        "raw_quality_status": "FAIL" if failures else report["status"],
        "critical_failures": failures,
        "dataset_acceptance": report.get("data_quality_approved") is True,
        "exception_id": exception.get("exception_id"),
        "invalid_rows_excluded": report.get("excluded_rows"),
        "complete_row_statistics": complete,
        "metrics": metrics,
        "granularity": "D04_ROW_RULE_AGGREGATES_NOT_PER_COLUMN_DISTRIBUTIONS",
        "evidence_mode": "FROZEN_T10_REPORT_NO_RAW_RESCAN",
    }


def load_monitoring_config(path: Path, *, test_only=False) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("status") != ("TEST_ONLY" if test_only else "APPROVED")
        or config.get("scope") != "quality_schema_only"
        or config.get("new_thresholds_authorized") is not False
        or config.get("training_authorized") is not False
        or config.get("reference_year") != 2024
        or sorted(e["month"] for e in config["reference_reports"]) != list(range(1, 13))
        or any(e["year"] != 2024 for e in config["reference_reports"])
        or any(
            e["year"] != 2025 or e["month"] not in range(7, 13) for e in config["current_reports"]
        )
    ):
        raise ValueError("Referencia o alcance de monitoreo no aprobados")
    return config


def reference_payload(config: dict, root: Path) -> dict:
    profiles = [read_profile(entry, config, root) for entry in config["reference_reports"]]
    if any(
        not p["complete_row_statistics"] or not p["dataset_acceptance"] or p["critical_failures"]
        for p in profiles
    ):
        raise ValueError("La referencia exige train completo y calidad sin FAIL")
    return {"config_sha256": fingerprint(config), "profiles": profiles, "use": "QUALITY_ONLY"}


def compare(reference: dict, current: dict) -> dict:
    old = {item["name"]: item for item in reference["raw_schema"]}
    new = {item["name"]: item for item in current["raw_schema"]}
    changes = {
        "added_columns": sorted(new.keys() - old.keys()),
        "removed_columns": sorted(old.keys() - new.keys()),
        "changed_fields": {
            name: {"reference": old[name], "current": new[name]}
            for name in old.keys() & new.keys()
            if old[name] != new[name]
        },
    }
    rates = {
        name: {
            "reference_rate": value["rate"],
            "current_rate": current["metrics"][name]["rate"],
            "delta_percentage_points": (current["metrics"][name]["rate"] - value["rate"]) * 100,
        }
        for name, value in reference["metrics"].items()
        if name in current["metrics"]
    }
    return {
        "status": "ALERT_D04_FAIL"
        if current["critical_failures"]
        else "SCHEMA_CHANGE"
        if any(changes.values())
        else "OBSERVED",
        "year": current["year"],
        "month": current["month"],
        "schema_changes": changes,
        "volume_ratio_same_calendar_month": current["raw_rows"] / reference["raw_rows"],
        "rate_changes_descriptive": rates,
        "reference": reference,
        "current": current,
        "monitoring_grants_dataset_approval": False,
        "new_quality_exception_granted": False,
        "drift_or_retraining_decision": "NOT_EVALUATED",
    }


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/monitoring-quality.yaml"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--build-reference", action="store_true")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    config = load_monitoring_config(args.config, test_only=args.test_only)
    expected = reference_payload(config, args.root.resolve())
    if args.build_reference:
        payload = {"reference": expected, "reference_sha256": fingerprint(expected)}
    else:
        if not args.reference or not args.year or not args.month:
            parser.error("Se requieren --reference, --year y --month")
        stored = json.loads(args.reference.read_text(encoding="utf-8"))
        if stored.get("reference") != expected or stored.get("reference_sha256") != fingerprint(
            expected
        ):
            raise ValueError("Referencia diferente de la evidencia aprobada")
        entries = [
            e
            for e in config["current_reports"]
            if (e["year"], e["month"]) == (args.year, args.month)
        ]
        if len(entries) != 1:
            raise ValueError("Lote fuera del replay de calidad aprobado")
        current = read_profile(entries[0], config, args.root.resolve())
        reference = next(p for p in expected["profiles"] if p["month"] == args.month)
        payload = compare(reference, current)
        payload["reference_sha256"] = fingerprint(expected)
    payload["recorded_at_utc"] = datetime.now(UTC).isoformat()
    output = args.output or Path("reports/monitoring/quality") / f"{uuid.uuid4().hex}.json"
    write_report(output, payload)
    print(
        json.dumps(
            {"status": payload.get("status", "REFERENCE_FROZEN"), "report": output.as_posix()}
        )
    )


if __name__ == "__main__":
    main()
