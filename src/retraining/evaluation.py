"""Predicciones iniciales y evaluacion posterior emparejada; reserva final de un solo uso."""

import hashlib
import uuid
from contextlib import ExitStack
from pathlib import Path

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.evaluation.metrics import ErrorStore
from src.features.build import feature_values
from src.ingestion.manifest import utc_now
from src.monitoring.performance import PredictionRows, frozen_model
from src.monitoring.protocol import load_config
from src.retraining.cohorts import ColumnCursor, verify_cohort
from src.retraining.protocol import budget, exclusive_json, inside, load_profile, pinned, read_json
from src.training.candidate_runtime import CandidateGuard, read_batches
from src.training.models import feature_matrix
from src.training.train import source_digest
from src.validation.run import _sha256
from src.validation.schema import fingerprint

PREDICTION_CONTEXT = ["validated_row_index", "pickup_datetime_utc", "source_feature_id"]


def candidate(training_entry, profile, root, *, test_only=False):
    manifest_path = pinned(root, training_entry)
    training = read_json(manifest_path)
    if (
        training.get("status")
        != ("CHALLENGER_TRAINING_TEST_ONLY" if test_only else "CHALLENGER_TRAINING_REAL")
        or training.get("publication_complete") is not True
        or training.get("profile_sha256") != fingerprint(profile)
    ):
        raise ValueError("Candidato no congelado por T33")
    path = manifest_path.parent / "lightgbm.joblib"
    if _sha256(path) != training["model_sha256"]:
        raise ValueError("Pesos del candidato alterados")
    return joblib.load(path), training, path


def initial_predictions(source, stage, output, predict, guard):
    schema = pa.schema(
        [
            ("partition_row_index", pa.int64()),
            ("source_feature_id", pa.string()),
            ("validated_row_index", pa.int64()),
            ("predicted_duration_minutes", pa.float64()),
        ]
    )
    count = clipped = 0
    with ExitStack() as stack:
        X = stack.enter_context(pq.ParquetFile(source / stage / "features.parquet"))
        context = stack.enter_context(pq.ParquetFile(source / stage / "context.parquet"))
        writer = stack.enter_context(pq.ParquetWriter(output, schema, compression="zstd"))
        for features, ctx in zip(
            X.iter_batches(batch_size=4096, use_threads=False),
            context.iter_batches(batch_size=4096, columns=PREDICTION_CONTEXT, use_threads=False),
            strict=True,
        ):
            guard.check()
            values = feature_matrix(features)
            predictions, changed = predict(values)
            predictions = np.asarray(predictions, dtype=np.float64)
            if (
                predictions.shape != (len(values),)
                or len(ctx) != len(values)
                or not np.isfinite(predictions).all()
                or np.any((predictions < 1 / 60) | (predictions > 180))
            ):
                raise ValueError("Predicciones no finitas, fuera de dominio o desalineadas")
            writer.write_table(
                pa.table(
                    {
                        "partition_row_index": np.arange(count, count + len(values)),
                        "source_feature_id": ctx.column(
                            ctx.schema.get_field_index("source_feature_id")
                        ),
                        "validated_row_index": ctx.column(0),
                        "predicted_duration_minutes": predictions,
                    },
                    schema=schema,
                )
            )
            count += len(values)
            clipped += changed
    return {
        "rows": count,
        "clipped_predictions": clipped,
        "sha256": _sha256(output),
        "labels_read_for_prediction": False,
    }


def score_predictions(source, stage, prediction_path, output, guard, routes):
    store = ErrorStore(output)
    total = 0
    digest = hashlib.sha256()
    with (
        pq.ParquetFile(prediction_path) as predictions,
        pq.ParquetFile(source / stage / "segments.parquet") as segments,
    ):
        cursor = PredictionRows(predictions)
        destinations = ColumnCursor(segments, "destination_location_id")
        for values, y, context in read_batches(source, stage, guard):
            predicted = cursor.take(len(y))
            ids = context.column(0).to_numpy()
            feature_ids = context.column(context.schema.get_field_index("source_feature_id"))
            if (
                not np.array_equal(
                    predicted["partition_row_index"].to_numpy(), np.arange(total, total + len(y))
                )
                or not np.array_equal(predicted["validated_row_index"].to_numpy(), ids)
                or predicted["source_feature_id"].to_pylist() != feature_ids.to_pylist()
            ):
                raise ValueError("Union prediccion/etiqueta con identidad incorrecta")
            route_codes = values[:, 0] * 1000 + destinations.take(len(y)).to_numpy()
            masks = {
                f"month_2026_{int(month):02}": values[:, 3] == month
                for month in np.unique(values[:, 3])
            }
            masks.update({f"band_{band}": values[:, 1] // 6 == band for band in range(4)})
            masks.update(
                {f"route_{code // 1000}_{code % 1000}": route_codes == code for code in routes}
            )
            store.add(y, predicted["predicted_duration_minutes"].to_numpy(), masks)
            digest.update(ids.astype("<i8").tobytes())
            total += len(y)
        if cursor.has_remaining() or not destinations.exhausted():
            raise ValueError("Predicciones/segmentos sobrantes")
    return store.results(resource_check=guard.check), {
        "rows": total,
        "joined_row_indices_sha256": digest.hexdigest(),
    }


def evaluate_pair(
    cohort_directory,
    stage,
    training_entry,
    *,
    profile_path=Path("configs/retraining.yaml"),
    root=None,
    test_only=False,
    prediction_fixture=None,
    registration_entry=None,
    audit_entry=None,
):
    if stage not in ("validation", "final"):
        raise ValueError("Solo validacion de desarrollo o final independiente")
    if stage != "final" and registration_entry is not None:
        raise ValueError("El recibo de registro se exige solo para la comparacion final")
    root = Path(root or Path.cwd()).resolve()
    source = Path(cohort_directory).resolve()
    if not source.is_relative_to(root):
        raise ValueError("Cohorte fuera del proyecto")
    profile = load_profile(profile_path, test_only=test_only)
    guard = CandidateGuard(budget("evaluation"), root, test_only=test_only)
    guard.check(start=True)
    if not test_only:
        from src.retraining.audit import require_audit

        require_audit(audit_entry, source, stage, profile, root)
    candidate_model, training, model_path = candidate(
        training_entry, profile, root, test_only=test_only
    )
    monitor = load_config(pinned(root, profile["monitoring_config"]), test_only=test_only)
    if not test_only and prediction_fixture is not None:
        raise ValueError("Fixture prohibida en evaluacion real")
    if test_only:
        if prediction_fixture is None:
            raise ValueError("Fixture sintetica explicita requerida")
        champion_predict, champion_identity, check_champion = prediction_fixture["champion"]
    else:
        champion_predict, champion_identity, check_champion = frozen_model(monitor, root)
    if stage == "final" and not test_only:
        from src.retraining.registration import verify_registration

        if registration_entry is None:
            raise ValueError("Comparacion final requiere candidato registrado sin alias")
        registered = read_json(pinned(root, registration_entry))
        verify_registration(registered, profile, root)
        if registered["model_sha256"] != training["model_sha256"]:
            raise ValueError("Registro de otro candidato")
    marker = verify_cohort(
        source, stage, profile, test_only=test_only, names=("features", "context")
    )
    marker_sha = _sha256(source / "cohort.json")
    routes = [
        r["code"]
        for r in read_json(pinned(root, profile["original_validation"]))["route_catalog"]["routes"]
    ]
    months = range(1, 4) if stage == "validation" else range(4, 7)
    required = [
        *(f"month_2026_{m:02}" for m in months),
        *(f"band_{h}" for h in range(4)),
        *(f"route_{r // 1000}_{r % 1000}" for r in routes),
    ]
    output = inside(root, "reports/retraining/evaluations")
    if test_only:
        output /= "_test_only"
    output = output / stage / uuid.uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    code_hash = source_digest()
    reserve = {
        "profile_sha256": fingerprint(profile),
        "candidate_sha256": training["model_sha256"],
        "cohort_sha256": marker_sha,
        "stage": stage,
        "champion": champion_identity,
        "timestamp_utc": utc_now(),
        "source_tree_sha256": code_hash,
        "output": str(output.relative_to(root)),
        "gate_frozen_before_predictions": profile["gate"],
    }
    if stage == "final":
        key = fingerprint(
            {"profile_sha256": reserve["profile_sha256"], "period": profile["periods"]["final"]}
        )
        exclusive_json(inside(root, "reports/retraining/reservations") / f"{key}.json", reserve)
    exclusive_json(output / "frozen-before-predictions.json", reserve)
    report = {
        "status": "FAIL",
        "publication_complete": False,
        "candidate_frozen_before_final": True,
        "profile_sha256": fingerprint(profile),
        "period": profile["periods"][stage],
        "stage": stage,
        "required_segments": required,
        "champion": champion_identity,
        "candidate_sha256": training["model_sha256"],
        "cohort": {"path": str((source / "cohort.json").relative_to(root)), "sha256": marker_sha},
        "champion_changed": False,
        "models_fitted": False,
        "metrics": {},
        "predictions": {},
        "joins": {},
    }
    try:
        from src.training.champion import read_approval

        smoke_payloads = (
            prediction_fixture["smoke_payloads"]
            if test_only
            else read_approval(pinned(root, profile["champion_approval"]))["smoke"]["payloads"]
        )
        smoke = candidate_model.predict(smoke_payloads)
        matrix = np.asarray([feature_values(p) for p in smoke_payloads])
        direct = candidate_model.named_steps["estimator"].predict(
            candidate_model.named_steps["native"].transform(matrix)
        )
        if not np.allclose(smoke, direct, rtol=0, atol=1e-10) or not np.isfinite(smoke).all():
            raise ValueError("Smoke de interfaz del candidato divergente")

        def challenger_predict(values):
            return candidate_model.named_steps["estimator"].predict_with_diagnostics(
                candidate_model.named_steps["native"].transform(values)
            )

        for name, predict in [("champion", champion_predict), ("challenger", challenger_predict)]:
            guard = CandidateGuard(budget("evaluation"), root, test_only=test_only)
            guard.check(start=True)
            with threadpool_limits(limits=4):
                predictions = initial_predictions(
                    source, stage, output / f"{name}-predictions.parquet", predict, guard
                )
                if predictions["rows"] != marker["rows"]:
                    raise ValueError("Prediccion no exhaustiva")
                verify_cohort(source, stage, profile, test_only=test_only)
                metrics, joined = score_predictions(
                    source,
                    stage,
                    output / f"{name}-predictions.parquet",
                    output / f"{name}-errors",
                    guard,
                    routes,
                )
            if joined["rows"] != marker["rows"]:
                raise ValueError("Evaluacion no exhaustiva")
            report["metrics"][name] = metrics
            report["predictions"][name] = predictions
            report["joins"][name] = joined
            report.setdefault("resources", {})[name] = {
                "initial": guard.initial,
                "final": guard.last,
                "elapsed_seconds": guard.elapsed,
            }
        check_champion()
        if (
            source_digest() != code_hash
            or _sha256(model_path) != training["model_sha256"]
            or _sha256(source / "cohort.json") != marker_sha
            or verify_cohort(source, stage, profile, test_only=test_only) != marker
            or load_profile(profile_path, test_only=test_only) != profile
        ):
            raise ValueError("Codigo/modelos/datos/configuracion cambiaron durante comparacion")
        report.update(
            status="PAIRED_EVALUATION_TEST_ONLY" if test_only else "PAIRED_EVALUATION_REAL",
            publication_complete=True,
            controls={
                "quality_accepted": True,
                "integrity_verified": True,
                "temporal_cuts_verified": True,
                "no_leakage": True,
                "smoke_passed": True,
                "same_population_verified": report["joins"]["champion"]
                == report["joins"]["challenger"],
            },
            evidence=[
                training_entry,
                report["cohort"],
                profile["champion_approval"],
                {"path": str(model_path.relative_to(root)), "sha256": training["model_sha256"]},
                {
                    "path": str((output / "frozen-before-predictions.json").relative_to(root)),
                    "sha256": _sha256(output / "frozen-before-predictions.json"),
                },
            ],
        )
        if registration_entry is not None:
            report["evidence"].append(registration_entry)
            verify_registration(read_json(pinned(root, registration_entry)), profile, root)
        if audit_entry is not None:
            report["evidence"].append(audit_entry)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        report["error"] = str(error)
    report["finished_at_utc"] = utc_now()
    exclusive_json(output / "evaluation.json", report)
    return output, report


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--stage", choices=["validation", "final"], required=True)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    args = parser.parse_args()

    def entry(path):
        return {"path": str(path.resolve().relative_to(Path.cwd())), "sha256": _sha256(path)}

    output, result = evaluate_pair(
        args.cohort,
        args.stage,
        entry(args.training),
        profile_path=args.config,
        registration_entry=entry(args.registration) if args.registration else None,
        audit_entry=entry(args.audit) if args.audit else None,
    )
    print({"output": str(output), "status": result["status"], "error": result.get("error")})
    if not result["publication_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
