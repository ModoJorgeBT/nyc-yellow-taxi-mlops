"""T31: monitoreo mensual retrospectivo, versionado y sin promociones."""

import argparse
import json
import logging
import os
import uuid
from pathlib import Path

from threadpoolctl import threadpool_limits

from src.monitoring import data_quality
from src.monitoring.drift import build_reference, compare_counts, counts_by_month, load_reference
from src.monitoring.performance import evaluate_predictions, frozen_model, make_predictions
from src.monitoring.protocol import (
    MonitorGuard,
    envelope,
    exclusive_json,
    inside,
    load_config,
    pinned,
    source_manifest,
    verify_tables,
)
from src.validation.run import _sha256

LOGGER = logging.getLogger(__name__)


def quality_observation(config, root, year, month):
    test_only = config["status"] == "TEST_ONLY"
    quality = data_quality.load_monitoring_config(
        pinned(root, config["quality_config"]), test_only=test_only
    )
    reference = data_quality.reference_payload(quality, root)
    entries = [e for e in quality["current_reports"] if (e["year"], e["month"]) == (year, month)]
    if len(entries) != 1:
        raise ValueError("Mes sin evidencia de calidad aprobada")
    current = data_quality.read_profile(entries[0], quality, root)
    result = data_quality.compare(
        next(p for p in reference["profiles"] if p["month"] == month), current
    )
    if not current["dataset_acceptance"]:
        raise ValueError("Lote no aceptado: requiere aprobacion antes de consumir features")
    if current["critical_failures"] and not current["exception_id"]:
        raise ValueError("FAIL sin excepcion exacta aprobada")
    return result


def preliminary(quality, drift, performance):
    if quality["status"] == "ALERT_D04_FAIL" or drift["status"] == "ALERT":
        return "ALERT_REVIEW_REQUIRED"
    if drift["status"] == "NOT_AVAILABLE" or performance["status"] != "OBSERVED":
        return "NOT_AVAILABLE"
    return "OBSERVED"


def monthly(
    config_path,
    root,
    year,
    month,
    *,
    test_only=False,
    labels_available=True,
    prediction_fixture=None,
    render_fixture=None,
):
    root = Path(root).resolve()
    config = load_config(config_path, test_only=test_only)
    if year != 2025 or month not in config["policy"]["current_months"]:
        raise ValueError("Mes fuera del replay aprobado; no usar test/holdout")
    if not test_only and (prediction_fixture is not None or render_fixture is not None):
        raise ValueError("Inyeccion de fixtures prohibida en modo real")
    output = inside(root, "reports/monitoring/monthly")
    if test_only:
        output /= "_test_only"
    output /= f"{year}/{month:02}/{uuid.uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    report = {
        **envelope(config),
        "year": year,
        "month": month,
        "scope": config["status"],
        "publication_complete": False,
        "status": "FAIL",
        "model_changed": False,
        "models_fitted": False,
        "automatic_retraining": False,
        "automatic_promotion": False,
        "test_or_final_holdout_opened": False,
        "output": str(output.relative_to(root)),
    }
    try:
        guard = MonitorGuard(root, test_only=test_only)
        guard.check(start=True)
        quality = quality_observation(config, root, year, month)
        reference = load_reference(pinned(root, config["reference"]), config)
        directory, manifest = source_manifest(config, root)
        verify_tables(directory, manifest, "monitoring_replay", ("features",), test_only=test_only)
        counts, rows = counts_by_month(directory, manifest, "monitoring_replay", guard)
        drift = compare_counts(reference, counts[str(month)], month)
        exclusive_json(output / "drift.json", drift)
        if render_fixture is None:
            from src.monitoring.renderer import render_report

            renderer_resources = render_report(config, root, output, guard)
        else:
            render_fixture(drift, output)
            renderer_resources = {"scope": "SYNTHETIC_FIXTURE"}
        if prediction_fixture is None:
            predict, identity, verify_model = frozen_model(config, root)
        else:
            predict, identity = prediction_fixture

            def verify_model():
                return None

        with threadpool_limits(limits=4):
            prediction = make_predictions(
                config, root, guard, year, month, output / "predictions.parquet", predict, identity
            )
            if prediction["rows"] != drift["features"]["pickup_month"]["current_rows"]:
                raise ValueError("Cohortes de drift y prediccion no coinciden")
            performance = evaluate_predictions(
                config,
                root,
                guard,
                prediction,
                output / "errors",
                labels_available=labels_available,
            )
        verify_model()
        verify_tables(directory, manifest, "monitoring_replay", ("features",), test_only=test_only)
        pinned(root, config["reference"])
        source_manifest(config, root)
        if load_config(config_path, test_only=test_only) != config:
            raise ValueError("Configuracion cambio durante el monitoreo")
        guard.check()
        report.update(
            status="MONITORING_TEST_ONLY" if test_only else "MONITORING_REAL",
            publication_complete=True,
            preliminary_decision=preliminary(quality, drift, performance),
            quality=quality,
            drift={key: value for key, value in drift.items() if key != "bins"},
            prediction=prediction,
            performance=performance,
            resources=guard.evidence(),
            renderer_resources=renderer_resources,
            replay_rows_scanned=rows,
            service={
                "status": "NOT_AVAILABLE",
                "reason": "NO_API_LOGS_FOR_HISTORICAL_2025_WINDOW",
                "current_api_metrics_attributed_to_2025": False,
                "availability": "NOT_INFERRED",
            },
            artifacts={
                name: _sha256(output / name)
                for name in (
                    "drift.json",
                    "evidently.json",
                    "evidently.html",
                    "predictions.parquet",
                )
                if (output / name).is_file()
            },
        )
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, ImportError) as error:
        report.update(status="FAIL", publication_complete=False, error=str(error))
        LOGGER.error("monthly_monitoring_failed: %s", error)
    exclusive_json(output / "monitoring.json", report)
    return report


def main():
    os.environ.setdefault("DO_NOT_TRACK", "1")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/monitoring.yaml"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    parser.add_argument("--build-reference", type=Path)
    parser.add_argument("--without-labels", action="store_true")
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config, test_only=args.test_only)
    if args.build_reference:
        guard = MonitorGuard(args.root, test_only=args.test_only)
        guard.check(start=True)
        path = inside(args.root, args.build_reference)
        result = build_reference(config, args.root, guard, path)
        print(
            json.dumps(
                {
                    "status": "REFERENCE_FROZEN",
                    "reference": str(path),
                    "sha256": result["reference_sha256"],
                }
            )
        )
        return
    if args.year is None or args.month is None:
        parser.error("Se requieren --year y --month")
    report = monthly(
        args.config,
        args.root,
        args.year,
        args.month,
        test_only=args.test_only,
        labels_available=not args.without_labels,
    )
    print(json.dumps({"status": report["status"], "output": report["output"]}))
    if not report["publication_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
