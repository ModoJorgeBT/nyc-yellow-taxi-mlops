"""Auditoria independiente de cobertura, predicciones y cuantiles por CDF completa."""

import argparse
import json
import math
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.features.schema import FEATURE_COLUMNS
from src.monitoring.drift import feature_array, load_reference
from src.monitoring.performance import PredictionRows, frozen_model
from src.monitoring.protocol import (
    MonitorGuard,
    batches,
    envelope,
    exclusive_json,
    load_config,
    maturity_cutoff,
    pinned,
    read_json,
    source_manifest,
    verify_tables,
)
from src.validation.run import _sha256


def quantile_verified(count, probability, value, below, equal, lower, upper):
    """Validar R7 sin ordenar ni materializar los errores de la particion."""
    position = (count - 1) * probability
    if equal:
        return below <= math.floor(position) and math.ceil(position) < below + equal
    if not math.isfinite(lower) or not math.isfinite(upper):
        return False
    expected = lower + (position - math.floor(position)) * (upper - lower)
    return below == math.floor(position) + 1 and math.isclose(
        value, expected, rel_tol=0, abs_tol=1e-12
    )


def update_cdf(accumulator, errors):
    value = accumulator["value"]
    accumulator["below"] += int(np.count_nonzero(errors < value))
    accumulator["equal"] += int(np.count_nonzero(errors == value))
    lower, upper = errors[errors <= value], errors[errors >= value]
    if len(lower):
        accumulator["lower"] = max(accumulator["lower"], float(lower.max()))
    if len(upper):
        accumulator["upper"] = min(accumulator["upper"], float(upper.min()))


def audit(config_path, catalog_path, root):
    config = load_config(config_path)
    guard = MonitorGuard(root)
    guard.check(start=True)
    reports = {}
    catalog = read_json(catalog_path)
    for entry in catalog["reports"]:
        path = pinned(root, entry)
        report = read_json(path)
        month = report["month"]
        if (
            report["year"] != 2025
            or month not in range(7, 13)
            or month in reports
            or report["status"] != "MONITORING_REAL"
            or report["publication_complete"] is not True
            or any(report.get(k) != v for k, v in envelope(config).items())
            or report["performance"]["status"] != "OBSERVED"
        ):
            raise ValueError("Reporte mensual incompleto o de otro ambito")
        for name, digest in report["artifacts"].items():
            if _sha256(path.parent / name) != digest:
                raise ValueError("Artefacto mensual modificado")
        reports[month] = (path, report)
    if set(reports) != set(range(7, 13)):
        raise ValueError("Faltan meses del replay")
    directory, manifest = source_manifest(config, root)
    verify_tables(directory, manifest, "monitoring_replay", ("features", "target", "context"))
    reference = load_reference(pinned(root, config["reference"]), config)["reference"]
    predict, identity, verify_model = frozen_model(config, root)
    totals = {}
    for month, (_, report) in reports.items():
        metric = report["performance"]["metrics"]["all"]
        totals[month] = {
            "rows": 0,
            "sums": [],
            "squares": [],
            "features": {name: Counter() for name in FEATURE_COLUMNS},
            "quantiles": {
                probability: {
                    "value": metric[field],
                    "below": 0,
                    "equal": 0,
                    "lower": -math.inf,
                    "upper": math.inf,
                }
                for probability, field in [
                    (0.5, "medae_minutes"),
                    (0.9, "p90_absolute_error_minutes"),
                ]
            },
        }
    offset = 0
    with ExitStack() as stack, threadpool_limits(limits=4):
        streams = {}
        for month, (_, report) in reports.items():
            parquet = stack.enter_context(pq.ParquetFile(pinned(root, report["prediction"])))
            metadata = parquet.schema_arrow.metadata or {}
            if metadata.get(b"model_sha256") != identity["model_sha256"].encode():
                raise ValueError("Predicciones de otro modelo")
            streams[month] = PredictionRows(parquet)
        for features, target, context in batches(
            directory,
            "monitoring_replay",
            ("features", "target", "context"),
            guard,
            batch_size=4096,
        ):
            values = feature_array(features)
            for month in np.unique(values[:, 3]):
                month = int(month)
                mask = values[:, 3] == month
                current = streams[month].take(int(mask.sum()))
                expected_context = context.filter(mask)
                expected_values = values[mask]
                y = target.filter(mask).column(0).to_numpy()
                if not np.array_equal(
                    current.column("partition_row_index").to_numpy(), np.flatnonzero(mask) + offset
                ):
                    raise ValueError("Cobertura de identidades no exacta")
                for name in ("validated_row_index", "source_feature_id", "pickup_datetime_utc"):
                    if (
                        not current.column(name)
                        .combine_chunks()
                        .equals(expected_context.column(name))
                    ):
                        raise ValueError("Identidad/tiempo no corresponde a T14")
                for index, name in enumerate(FEATURE_COLUMNS):
                    if not np.array_equal(
                        current.column(name).to_numpy(), expected_values[:, index]
                    ):
                        raise ValueError("Predictor almacenado no corresponde a T14")
                events = expected_context.column("label_event_datetime_utc").to_numpy()
                cutoff = np.datetime64(maturity_cutoff(2025, month).replace(tzinfo=None), "us")
                if not np.all(
                    np.isfinite(y) & (y > 0) & (y <= 180) & ~np.isnat(events) & (events <= cutoff)
                ):
                    raise ValueError("Etiquetas no maduras en replay auditado")
                stored = current.column("predicted_duration_minutes").to_numpy()
                repeated, _ = predict(expected_values)
                if not np.allclose(stored, repeated, rtol=0, atol=1e-10):
                    raise ValueError("Predicciones no coinciden con champion congelado")
                errors = np.abs(y - stored)
                state = totals[month]
                state["rows"] += len(errors)
                state["sums"].append(float(errors.sum()))
                state["squares"].append(float(np.dot(errors, errors)))
                for accumulator in state["quantiles"].values():
                    update_cdf(accumulator, errors)
                for index, name in enumerate(FEATURE_COLUMNS):
                    keys, numbers = np.unique(expected_values[:, index], return_counts=True)
                    state["features"][name].update(
                        {str(int(k)): int(n) for k, n in zip(keys, numbers, strict=True)}
                    )
            offset += len(values)
        if any(stream.has_remaining() for stream in streams.values()):
            raise ValueError("Predicciones adicionales fuera de T14")
    result = {}
    for month, state in totals.items():
        path, report = reports[month]
        count = state["rows"]
        metrics = report["performance"]["metrics"]
        if count != report["prediction"]["rows"] or count != metrics["all"]["rows"]:
            raise ValueError("Denominador mensual no coincide")
        if not math.isclose(
            math.fsum(state["sums"]) / count,
            metrics["all"]["mae_minutes"],
            rel_tol=0,
            abs_tol=1e-10,
        ):
            raise ValueError("MAE no reproducible")
        if not math.isclose(
            math.sqrt(math.fsum(state["squares"]) / count),
            metrics["all"]["rmse_minutes"],
            rel_tol=0,
            abs_tol=1e-10,
        ):
            raise ValueError("RMSE no reproducible")
        for probability, value in state["quantiles"].items():
            if not quantile_verified(count, probability, **value):
                raise ValueError("Cuantil no coincide con CDF exhaustiva")
        for prefix in ("band_", "route_", "month_"):
            groups = [row for name, row in metrics.items() if name.startswith(prefix)]
            if sum(row["rows"] for row in groups) != count:
                raise ValueError("Segmentos no exhaustivos")
            if not math.isclose(
                sum(row["rows"] * row["mae_minutes"] for row in groups) / count,
                metrics["all"]["mae_minutes"],
                rel_tol=0,
                abs_tol=1e-10,
            ):
                raise ValueError("MAE de segmentos no consistente")
        drift = read_json(path.parent / "drift.json")
        evidence = read_json(path.parent / "evidently.json")
        evident_values = {
            item["config"]["feature"]: item["value"]
            for item in evidence["metrics"]
            if item["config"]["type"].endswith("HistogramPSI")
        }
        for name in FEATURE_COLUMNS:
            bins = reference["domains"][name]
            old = reference["counts"][str(month)][name]
            current = state["features"][name]
            left = [old.get(key, 0) for key in bins]
            right = [current.get(key, 0) for key in bins]
            right[-1] = sum(n for key, n in current.items() if key not in bins)
            a = [(number + 0.5) / (sum(left) + 0.5 * len(bins)) for number in left]
            b = [(number + 0.5) / (sum(right) + 0.5 * len(bins)) for number in right]
            score = math.fsum((q - p) * math.log(q / p) for p, q in zip(a, b, strict=True))
            if not math.isclose(
                score, drift["features"][name]["psi"], rel_tol=0, abs_tol=1e-12
            ) or not math.isclose(score, evident_values[name], rel_tol=0, abs_tol=1e-12):
                raise ValueError("PSI/Evidently no representan la poblacion completa")
        result[str(month)] = {
            "rows": count,
            "metrics": metrics["all"],
            "report_sha256": _sha256(path),
        }
    if (
        offset != manifest["partitions"]["monitoring_replay"]["rows"]
        or sum(row["rows"] for row in result.values()) != offset
    ):
        raise ValueError("Cobertura de replay incompleta")
    verify_tables(directory, manifest, "monitoring_replay", ("features", "target", "context"))
    verify_model()
    guard.check()
    return {
        "status": "VERIFIED_FULL_MONTHLY_REPLAY",
        "rows": offset,
        "months": result,
        "resources": guard.evidence(),
        "all_predictions_recomputed": True,
        "quantiles_verified_by_full_cdf": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/monitoring.yaml"))
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.config, args.catalog, Path.cwd())
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        exclusive_json(args.output, {"status": "FAIL", "error": str(error)})
        raise
    exclusive_json(args.output, result)
    print(json.dumps({"status": result["status"], "rows": result["rows"]}))


if __name__ == "__main__":
    main()
