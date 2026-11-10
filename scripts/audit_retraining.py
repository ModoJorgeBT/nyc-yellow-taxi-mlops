"""Audita la comparacion congelada completa; no ajusta ni selecciona otro modelo."""

import argparse
import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from scripts.audit_monitoring import quantile_verified, update_cdf
from src.monitoring.performance import PredictionRows, frozen_model
from src.monitoring.protocol import load_config
from src.retraining.cohorts import ColumnCursor, verify_cohort
from src.retraining.evaluation import candidate
from src.retraining.protocol import budget, exclusive_json, load_profile, pinned, read_json
from src.training.candidate_runtime import CandidateGuard, read_batches
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def accumulator(metrics):
    return {
        "rows": 0,
        "sums": [],
        "squares": [],
        "quantiles": {
            probability: {
                "value": metrics[key],
                "below": 0,
                "equal": 0,
                "lower": -math.inf,
                "upper": math.inf,
            }
            for probability, key in [(0.5, "medae_minutes"), (0.9, "p90_absolute_error_minutes")]
        },
    }


def verify_metrics(state, reported):
    count = state["rows"]
    if count != reported["rows"] or count < 1:
        raise ValueError("Soporte de segmento no coincide")
    for observed, expected in [
        (math.fsum(state["sums"]) / count, reported["mae_minutes"]),
        (math.sqrt(math.fsum(state["squares"]) / count), reported["rmse_minutes"]),
    ]:
        if not math.isclose(observed, expected, rel_tol=0, abs_tol=1e-10):
            raise ValueError("MAE/RMSE no reproducible")
    for probability, stats in state["quantiles"].items():
        if not quantile_verified(count, probability, **stats):
            raise ValueError("MedAE/P90 no corresponde a CDF completa")


def audit(evaluation_path, *, profile_path=Path("configs/retraining.yaml"), root=None):
    root = Path(root or Path.cwd()).resolve()
    path = Path(evaluation_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Evaluacion fuera del proyecto")
    original_sha = _sha256(path)
    report = read_json(path)
    profile = load_profile(profile_path)
    if (
        report.get("status") != "PAIRED_EVALUATION_REAL"
        or not report.get("publication_complete")
        or report.get("profile_sha256") != fingerprint(profile)
    ):
        raise ValueError("Comparacion no congelada/publicada")
    for evidence in report["evidence"]:
        pinned(root, evidence)
    stage = report["stage"]
    source = pinned(root, report["cohort"]).parent
    manifest = verify_cohort(source, stage, profile)
    model, training, model_path = candidate(report["evidence"][0], profile, root)
    config = load_config(pinned(root, profile["monitoring_config"]))
    champion, identity, verify_champion = frozen_model(config, root)
    if identity != report["champion"]:
        raise ValueError("Champion distinto del comparado")
    routes = [
        r["code"]
        for r in read_json(pinned(root, profile["original_validation"]))["route_catalog"]["routes"]
    ]

    def challenger(values):
        return model.named_steps["estimator"].predict_with_diagnostics(
            model.named_steps["native"].transform(values)
        )

    summaries = {}
    for name, predict in [("champion", champion), ("challenger", challenger)]:
        guard = CandidateGuard(budget("evaluation"), root, test_only=False)
        guard.check(start=True)
        prediction_path = path.parent / f"{name}-predictions.parquet"
        if _sha256(prediction_path) != report["predictions"][name]["sha256"]:
            raise ValueError("Predicciones alteradas")
        expected = report["metrics"][name]
        states = {key: accumulator(value) for key, value in expected.items()}
        total = clipped = 0
        with (
            threadpool_limits(limits=4),
            pq.ParquetFile(prediction_path) as parquet,
            pq.ParquetFile(source / stage / "segments.parquet") as segments,
        ):
            predicted = PredictionRows(parquet)
            destinations = ColumnCursor(segments, "destination_location_id")
            for values, y, context in read_batches(source, stage, guard):
                saved = predicted.take(len(y))
                feature_ids = context.column(context.schema.get_field_index("source_feature_id"))
                if (
                    not np.array_equal(
                        saved["partition_row_index"].to_numpy(), np.arange(total, total + len(y))
                    )
                    or not np.array_equal(
                        saved["validated_row_index"].to_numpy(), context.column(0).to_numpy()
                    )
                    or saved["source_feature_id"].to_pylist() != feature_ids.to_pylist()
                ):
                    raise ValueError("Identidades/orden de predicciones incorrectos")
                stored = saved["predicted_duration_minutes"].to_numpy()
                recomputed, changes = predict(values)
                if not np.allclose(stored, recomputed, rtol=0, atol=1e-10):
                    raise ValueError("Predicciones diferentes del modelo congelado")
                clipped += changes
                errors = np.abs(y - stored)
                route = values[:, 0] * 1000 + destinations.take(len(y)).to_numpy()
                masks = {"all": np.ones(len(y), dtype=bool)}
                masks.update(
                    {f"month_2026_{int(m):02}": values[:, 3] == m for m in np.unique(values[:, 3])}
                )
                masks.update({f"band_{b}": values[:, 1] // 6 == b for b in range(4)})
                masks.update({f"route_{r // 1000}_{r % 1000}": route == r for r in routes})
                for key, mask in masks.items():
                    subset = errors[mask]
                    if not len(subset):
                        continue
                    if key not in states:
                        raise ValueError("Segmento observado omitido del reporte")
                    state = states[key]
                    state["rows"] += len(subset)
                    state["sums"].append(float(subset.sum()))
                    state["squares"].append(float(np.dot(subset, subset)))
                    for q in state["quantiles"].values():
                        update_cdf(q, subset)
                total += len(y)
            if predicted.has_remaining() or not destinations.exhausted():
                raise ValueError("Cobertura no exhaustiva")
        if (
            total != manifest["rows"]
            or clipped != report["predictions"][name]["clipped_predictions"]
        ):
            raise ValueError("Denominadores/recortes divergentes")
        for key, state in states.items():
            verify_metrics(state, expected[key])
        for prefix in ("month_", "band_"):
            if sum(v["rows"] for k, v in expected.items() if k.startswith(prefix)) != total:
                raise ValueError("Segmentos no cubren la cohorte")
        guard.check()
        summaries[name] = {
            "rows": total,
            "all_metrics": expected["all"],
            "segments_verified": len(states),
            "resources": {
                "initial": guard.initial,
                "final": guard.last,
                "elapsed_seconds": guard.elapsed,
            },
        }
    verify_champion()
    if (
        _sha256(model_path) != training["model_sha256"]
        or _sha256(path) != original_sha
        or verify_cohort(source, stage, profile) != manifest
    ):
        raise ValueError("Fuentes cambiaron durante auditoria")
    return {
        "status": "VERIFIED_FULL_PAIRED_EVALUATION",
        "stage": stage,
        "unique_rows": manifest["rows"],
        "all_predictions_recomputed": True,
        "all_segment_metrics_verified": True,
        "evaluation_sha256": original_sha,
        "models": summaries,
        "model_fitted": False,
        "champion_changed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.evaluation, profile_path=args.config)
    exclusive_json(args.output, result)
    print({"status": result["status"], "rows": result["unique_rows"]})


if __name__ == "__main__":
    main()
