"""T32: recomendaciones auditables desde reportes mensuales congelados."""

import argparse
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.features.schema import FEATURE_COLUMNS
from src.ingestion.manifest import utc_now
from src.monitoring.protocol import envelope, load_config, maturity_cutoff
from src.monitoring.run import quality_observation
from src.retraining.protocol import exclusive_json, inside, load_profile, pinned, read_json
from src.validation.schema import fingerprint


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def signals(report, reference_mae, *, minimum_rows=1000):
    """Una senal ausente no se convierte en deterioro ni en una metrica ficticia."""
    performance, prediction = report["performance"], report["prediction"]
    metric = performance.get("metrics", {}).get("all", {})
    mae = None
    if performance.get("status") == "OBSERVED":
        rows = metric.get("rows")
        if (
            type(rows) is not int
            or rows < 0
            or performance.get("coverage_ratio") != 1.0
            or rows != performance.get("expected_rows")
            or rows != prediction["rows"]
            or not finite(metric.get("mae_minutes"))
        ):
            raise ValueError("Desempeno observado con cobertura/metricas incompatibles")
        if rows >= minimum_rows:
            mae = metric["mae_minutes"] > reference_mae * 1.15
    elif performance.get("status") != "NOT_AVAILABLE":
        raise ValueError("Estado de etiquetas desconocido")
    drift = {}
    if set(report["drift"]["features"]) != set(FEATURE_COLUMNS):
        raise ValueError("Features de drift incompatibles")
    for name, value in report["drift"]["features"].items():
        if any(
            type(value.get(k)) is not int or value[k] < 0
            for k in ("current_rows", "reference_rows")
        ):
            raise ValueError("Soporte PSI invalido")
        enough = min(value["current_rows"], value["reference_rows"]) >= minimum_rows
        if enough:
            if not finite(value.get("psi")) or value["current_rows"] != prediction["rows"]:
                raise ValueError("PSI/cobertura incompatible")
            drift[name] = value["psi"] > 0.2
        else:
            drift[name] = None
    return {"mae_deteriorated": mae, "drift": drift}


def decide(windows, *, as_of, last_fit_end):
    if as_of.tzinfo is None or last_fit_end.tzinfo is None or as_of < last_fit_end:
        raise ValueError("Fechas operativas invalidas")
    months = sorted(windows, key=lambda w: (w["year"], w["month"]))
    if len({(w["year"], w["month"]) for w in months}) != len(months):
        raise ValueError("Mes duplicado")
    reasons = []
    for previous, current in zip(months, months[1:], strict=False):
        left, right = (
            previous["year"] * 12 + previous["month"],
            current["year"] * 12 + current["month"],
        )
        if right != left + 1:
            continue
        pair = [[previous["year"], previous["month"]], [current["year"], current["month"]]]
        if previous["mae_deteriorated"] is True and current["mae_deteriorated"] is True:
            reasons.append({"rule": "MAE_TWO_MONTHS", "months": pair})
        for feature in FEATURE_COLUMNS:
            if previous["drift"][feature] is True and current["drift"][feature] is True:
                reasons.append(
                    {"rule": "PSI_SAME_FEATURE_TWO_MONTHS", "feature": feature, "months": pair}
                )
    months_elapsed = (as_of.year - last_fit_end.year) * 12 + as_of.month - last_fit_end.month
    due = months_elapsed >= 3 and (months_elapsed > 3 or as_of.day >= last_fit_end.day)
    return {
        "decision": "RETRAIN_RECOMMENDED" if reasons else "NO_ACTION",
        "reasons": reasons,
        "quarterly_review": "REVIEW_REQUIRED" if due else "NOT_DUE",
        "training_started": False,
        "champion_changed": False,
    }


def evaluate(config_path=Path("configs/retraining.yaml"), *, root=None, test_only=False):
    root = Path(root or Path.cwd()).resolve()
    profile = load_profile(config_path, test_only=test_only)
    output = inside(root, "reports/retraining/triggers")
    if test_only:
        output /= "_test_only"
    path = output / f"{uuid.uuid4().hex}.json"
    report = {
        "status": "FAIL",
        "decision": "BLOCKED_REVIEW",
        "publication_complete": False,
        "profile_sha256": fingerprint(profile),
        "timestamp_utc": utc_now(),
        "training_started": False,
        "champion_changed": False,
    }
    try:
        monitor = load_config(pinned(root, profile["monitoring_config"]), test_only=test_only)
        expected = envelope(monitor)
        windows = []
        as_of = datetime.fromisoformat(profile["trigger_as_of_utc"]).astimezone(UTC)
        for entry in profile["monitoring_reports"]:
            value = read_json(pinned(root, entry))
            if (
                value.get("status") != ("MONITORING_TEST_ONLY" if test_only else "MONITORING_REAL")
                or value.get("scope") != monitor["status"]
                or value.get("publication_complete") is not True
                or any(value.get(k) != v for k, v in expected.items())
                or value["prediction"]["model"]["model_sha256"] != monitor["model"]["sha256"]
                or value.get("models_fitted") is not False
                or value.get("model_changed") is not False
                or value.get("year") != entry["year"]
                or value.get("month") != entry["month"]
                or maturity_cutoff(value["year"], value["month"]) > as_of
            ):
                raise ValueError("Reporte no corresponde al modelo, periodo o linaje aprobados")
            if value["quality"] != quality_observation(
                monitor, root, value["year"], value["month"]
            ):
                raise ValueError("Calidad/excepcion distinta de evidencia aceptada")
            changes = value["quality"]["schema_changes"]
            if changes["removed_columns"] or changes["changed_fields"]:
                raise ValueError("Cambio de esquema incompatible requiere revision")
            signal = signals(value, profile["reference_mae_minutes"])
            windows.append({"year": value["year"], "month": value["month"], **signal})
        result = decide(
            windows, as_of=as_of, last_fit_end=datetime.fromisoformat(profile["champion_train_end"])
        )
        if load_profile(config_path, test_only=test_only) != profile:
            raise ValueError("Configuracion alterada durante trigger")
        report.update(
            result,
            status="TRIGGER_TEST_ONLY" if test_only else "TRIGGER_REAL",
            publication_complete=True,
            windows=windows,
            reports=profile["monitoring_reports"],
            as_of_utc=as_of.isoformat(),
            historical_tlc_publication_claim=False,
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        report["error"] = str(error)
    exclusive_json(path, report)
    return path, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    path, result = evaluate(args.config, root=args.root, test_only=args.test_only)
    print({"report": str(path), "decision": result["decision"], "status": result["status"]})
    if not result["publication_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
