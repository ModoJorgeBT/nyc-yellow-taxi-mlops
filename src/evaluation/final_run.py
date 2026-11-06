"""Evaluación final reservada: modelos congelados, todas las filas, sin selección."""

import argparse
import gc
import hashlib
import json
import logging
import tempfile
import uuid
from contextlib import ExitStack
from pathlib import Path

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.evaluation.final_data import read_final_profile, verify_final
from src.evaluation.metrics import ErrorStore
from src.ingestion.manifest import describe_parquet, publish_file, publish_manifest, utc_now
from src.training.candidate_runtime import CandidateGuard, read_batches
from src.training.models import predict_matrix
from src.training.resources import ResourceGuard
from src.training.split import read_model_config
from src.training.train import source_digest
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint, load_config

NAMES = ("baseline", "sgd", "lightgbm")
LOGGER = logging.getLogger(__name__)


def read_object(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def frozen_models(profile, *, test_only):
    result = {}
    for name in NAMES:
        info = profile["models"][name]
        path = Path(info["path"]).resolve()
        if _sha256(path) != info["sha256"]:
            raise ValueError("Modelo final distinto de sus bytes aprobados")
        if name == "baseline":
            model = read_object(path)
            marker = read_object(path.parent / "baseline_manifest.json")
            expected_status = "BASELINE_TEST_ONLY" if test_only else "BASELINE_REAL"
            if (
                marker.get("status") != expected_status
                or marker.get("model_sha256") != info["sha256"]
            ):
                raise ValueError("Baseline final de otro ámbito")
            value = model.get("prediction_minutes")
            if (
                model.get("kind") != "exact_global_train_median"
                or not isinstance(value, float)
                or not 0 < value <= 180
            ):
                raise ValueError("Baseline no congelado o no positivo")
            result[name] = value
        else:
            marker = read_object(path.parent / "training_manifest.json")
            expected = ("LIGHTGBM_TRAINING_" if name == "lightgbm" else "TRAINING_") + (
                "TEST_ONLY" if test_only else "REAL"
            )
            if marker.get("status") != expected or marker.get("publication_complete") is not True:
                raise ValueError("Candidato final de otro ámbito")
            if name == "lightgbm":
                if marker.get("model_sha256") != info["sha256"] or not marker["resources"].get(
                    "worker_pid_verified"
                ):
                    raise ValueError("LightGBM no auditado por proceso real")
            elif marker.get("models", {}).get(name, {}).get("sha256") != info["sha256"]:
                raise ValueError("SGD no corresponde al ajuste congelado")
            model = joblib.load(path)
            if model.named_steps["estimator"].rows_fitted_ <= 0:
                raise ValueError("Modelo sin ajuste previo verificable")
            result[name] = model
    return result


class Destinations:
    """Join por identidad, admitiendo destino desconocido solo en grupo otras."""

    def __init__(self, entries, catalog):
        self.entries = {e["verified"]["feature"]["feature_id"]: e for e in entries}
        self.catalog = catalog
        self.stack = ExitStack()
        self.readers, self.buffers, self.offsets, self.previous = {}, {}, {}, {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def codes(self, X, context):
        ids = np.asarray(context.column(3).to_pylist(), dtype="U32")
        indices = context.column(0).to_numpy()
        destinations = np.empty(len(X), dtype=np.int64)
        for identity in np.unique(ids):
            if identity not in self.entries:
                raise ValueError("Identidad de segmento fuera del holdout")
            selected = ids == identity
            requested = indices[selected]
            if requested[0] <= self.previous.get(identity, -1) or np.any(np.diff(requested) <= 0):
                raise ValueError("Identidades de segmento repetidas o desordenadas")
            if identity not in self.readers:
                file = self.stack.enter_context(
                    pq.ParquetFile(
                        Path(self.entries[identity]["validated_directory"]) / "data.parquet"
                    )
                )
                self.readers[identity] = iter(
                    file.iter_batches(columns=["DOLocationID"], batch_size=65536, use_threads=False)
                )
                self.offsets[identity] = 0
                self.buffers[identity] = None
            taken = np.empty(len(requested), dtype=np.int64)
            position = 0
            while position < len(requested):
                buffer = self.buffers[identity]
                if buffer is None or requested[position] >= self.offsets[identity] + len(buffer):
                    if buffer is not None:
                        self.offsets[identity] += len(buffer)
                    batch = next(self.readers[identity], None)
                    if batch is None:
                        raise ValueError("Fuente de destino incompleta")
                    self.buffers[identity] = pc.fill_null(batch.column(0), -1).to_numpy()
                    continue
                if requested[position] < self.offsets[identity]:
                    raise ValueError("Destino fuera de orden de origen")
                end = int(np.searchsorted(requested, self.offsets[identity] + len(buffer)))
                taken[position:end] = buffer[requested[position:end] - self.offsets[identity]]
                position = end
            self.previous[identity] = int(requested[-1])
            destinations[selected] = np.where(np.isin(taken, self.catalog), taken, -1)
        unknown = int(np.count_nonzero(destinations == -1))
        return X[:, 0] * 1000 + destinations, unknown


def segment_masks(values, routes, selected, *, year):
    masks = {
        f"month_{year}_{int(month):02}": values[:, 3] == month for month in np.unique(values[:, 3])
    }
    masks.update(
        {f"band_{int(band)}": values[:, 1] // 6 == band for band in np.unique(values[:, 1] // 6)}
    )
    for code in selected:
        mask = routes == code
        if mask.any():
            masks[f"route_{code // 1000}_{code % 1000}"] = mask
    masks["route_other"] = ~np.isin(routes, selected)
    return masks


def evaluate_candidate(
    name, model, *, source, holdout, profile, data, staged, test_only, shared_seconds, resources
):
    selected = [row["code"] for row in profile["route_catalog"]["routes"]]
    guard = CandidateGuard(
        resources,
        source,
        test_only=test_only,
        charged_seconds=shared_seconds,
    )
    guard.check(start=True)
    store = ErrorStore(staged / "errors" / name)
    rows = clipped = unknown_origin = unknown_destination = 0
    target_hash = hashlib.sha256()
    schema = pa.schema([("row_index", pa.int64()), ("predicted_duration_minutes", pa.float64())])
    with (
        pq.ParquetWriter(staged / f"{name}.parquet", schema) as writer,
        Destinations(holdout["inputs"], data["quality"]["zone_catalog"]["ids"]) as destinations,
        threadpool_limits(limits=4),
    ):
        # read_batches obtiene tablas homólogas; el directorio raíz es el holdout final.
        for X, y, context in read_batches(source.parent, source.name, guard):
            routes, missing_dest = destinations.codes(X, context)
            unknown_destination += missing_dest
            if name == "baseline":
                predicted, changed = np.full(len(y), model), 0
            elif name == "sgd":
                predicted, changed = predict_matrix(model, X)
            else:
                encoded = model.named_steps["native"].transform(X)
                unknown_origin += int(np.count_nonzero(encoded[:, 0] == -1))
                predicted, changed = model.named_steps["estimator"].predict_with_diagnostics(
                    encoded
                )
            clipped += changed
            store.add(
                y,
                predicted,
                segment_masks(X, routes, selected, year=profile["period"]["year"]),
            )
            writer.write_table(
                pa.Table.from_arrays(
                    [
                        pa.array(np.arange(rows, rows + len(y), dtype=np.int64)),
                        pa.array(predicted),
                    ],
                    schema=schema,
                )
            )
            rows += len(y)
            target_hash.update(y.astype("<f8", copy=False).tobytes())
            if rows % 1048576 == 0:
                LOGGER.info("Final %s: %d filas", name, rows)
    if rows != holdout["rows"] or target_hash.hexdigest() != holdout["target_sha256"]:
        raise ValueError("Evaluación final no cubre todas las etiquetas congeladas")
    metrics = store.results(resource_check=guard.check)
    for prefix in ("month_", "band_", "route_"):
        if sum(v["rows"] for k, v in metrics.items() if k.startswith(prefix)) != rows:
            raise ValueError("Segmentos finales incompletos")
    guard.check()
    return {
        "rows": rows,
        "metrics": metrics,
        "clipped_predictions": clipped,
        "unknown_origin_rows": unknown_origin if name == "lightgbm" else None,
        "unknown_destination_rows": unknown_destination,
        "target_sha256": target_hash.hexdigest(),
        "predictions": describe_parquet(staged / f"{name}.parquet"),
        "resources": {
            "initial": guard.initial,
            "final": guard.last,
            "elapsed_seconds": guard.elapsed,
        },
    }


def resource_review(path, *, profile, holdout_sha, retry_of, test_only):
    if path is None:
        return profile["evaluation_resources"], None
    review = read_object(path)
    expected_resources = {
        "approval_status": "APPROVED",
        "profile_id": "d02-final-inference-6-2-2026-11-05",
        "threads_total": 4,
        "parallel_models": 1,
        "process_rss_limit_gib": 2,
        "preflight_min_free_ram_gib": 6,
        "preflight_min_free_disk_gib": 50,
        "candidate_timeout_seconds": 7200,
    }
    if (
        review.get("approval_status") != ("TEST_ONLY" if test_only else "APPROVED")
        or (test_only and review.get("fixture_origin") != "synthetic")
        or (not test_only and review.get("approved_by") != "USER_EXPLICIT_IN_CONVERSATION")
        or review.get("scope") != "frozen_independent_final_inference_only"
        or review.get("base_profile_sha256") != fingerprint(profile)
        or review.get("holdout_manifest_sha256") != holdout_sha
        or review.get("resources") != expected_resources
        or retry_of is None
        or review.get("failed_report_sha256") != _sha256(Path(retry_of))
    ):
        raise ValueError("Revisión de recursos final no aprobada o de otro experimento")
    return review["resources"], {"configuration": review, "sha256": _sha256(Path(path))}


def reserve_attempt(report_root, *, report, profile, holdout_sha, code_hash, retry_of):
    reservation_root = report_root / "reservations"
    reservation_root.mkdir(exist_ok=True)
    base = reservation_root / f"{fingerprint(profile)}.json"
    reservation, previous = base, None
    if retry_of is not None:
        failed = read_object(retry_of)
        original = read_object(base)
        if (
            failed.get("status") != "FAIL"
            or failed.get("publication_complete") is not False
            or failed.get("mode") != report["mode"]
            or not str(failed.get("error", "")).startswith("D-02:")
            or failed.get("evaluation_id") != original.get("evaluation_id")
            or failed.get("reservation_sha256") != _sha256(base)
            or original.get("profile_sha256") != fingerprint(profile)
            or original.get("holdout_manifest_sha256") != holdout_sha
            or original.get("models") != profile["models"]
            or failed.get("models_fitted") is not False
            or failed.get("selection_changed") is not False
        ):
            raise ValueError("El reinicio exige FAIL de recursos y el mismo experimento congelado")
        previous = {
            "evaluation_id": failed["evaluation_id"],
            "report_sha256": _sha256(Path(retry_of)),
            "reservation_sha256": _sha256(base),
            "reason": failed["error"],
        }
        reservation = (
            reservation_root / f"{fingerprint(profile)}-retry-{failed['evaluation_id']}.json"
        )
    publish_manifest(
        reservation,
        {
            "status": "FINAL_EVALUATION_RESERVED",
            "evaluation_id": report["evaluation_id"],
            "profile_sha256": fingerprint(profile),
            "holdout_manifest_sha256": holdout_sha,
            "models": profile["models"],
            "source_tree_sha256": code_hash,
            "metrics_opened": False,
            "reserved_at_utc": utc_now(),
            "retry_of": previous,
        },
    )
    return reservation, previous


def evaluate_final(
    holdout_directory,
    *,
    profile_path=Path("configs/lightgbm-final-evaluation.yaml"),
    config_path=Path("configs/model.yaml"),
    data_config_path=Path("configs/data.yaml"),
    output_dir=Path("data/processed/independent-final-evaluations"),
    report_dir=Path("reports/independent-final-evaluations"),
    test_only=False,
    resource_review_path=None,
    retry_of=None,
):
    if type(test_only) is not bool:
        raise ValueError("Modo de evaluación inválido")
    source, output, reports = [
        Path(p).resolve() for p in (holdout_directory, output_dir, report_dir)
    ]
    if any(
        a.is_relative_to(b) or b.is_relative_to(a)
        for i, a in enumerate((source, output, reports))
        for b in (source, output, reports)[i + 1 :]
    ):
        raise ValueError("Entradas y salidas de evaluación deben estar separadas")
    profile = read_final_profile(profile_path, test_only=test_only)
    config, data = read_model_config(config_path), load_config(data_config_path)
    if not test_only and fingerprint(data) != profile["quality_config_sha256"]:
        raise ValueError("D-04 no coincide con el protocolo final congelado")
    scopes = ("_test_only",) if test_only else ()
    parent, report_root = _under(output, *scopes), _under(reports, *scopes)
    parent.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    identifier, code_hash = uuid.uuid4().hex, source_digest()
    lock_hash = _sha256(Path("requirements-dev.lock"))
    report = {
        "evaluation_id": identifier,
        "status": "FAIL",
        "publication_complete": False,
        "mode": "TEST_ONLY" if test_only else "REAL",
        "started_at_utc": utc_now(),
        "models_fitted": False,
        "selection_changed": False,
        "model_registered": False,
        "approved_for_serving": False,
        "original_test_reused": False,
        "replay_reused": False,
    }
    try:
        known_holdout_sha = _sha256(source / "holdout_manifest.json")
        effective_resources, review = resource_review(
            resource_review_path,
            profile=profile,
            holdout_sha=known_holdout_sha,
            retry_of=retry_of,
            test_only=test_only,
        )
        report["effective_evaluation_resources"] = effective_resources
        report["resource_review"] = review
        verifier_guard = CandidateGuard(effective_resources, source, test_only=test_only)
        verifier_guard.check(start=True)
        holdout, holdout_sha = verify_final(
            source, profile=profile, config=config, data=data, test_only=test_only
        )
        models = frozen_models(profile, test_only=test_only)
        if not test_only:
            original = Path(profile["original_evaluation_directory"])
            if (
                _sha256(original / "selection.json") != profile["original_selection_sha256"]
                or _sha256(original / "evaluation_manifest.json")
                != profile["original_evaluation_manifest_sha256"]
            ):
                raise ValueError("La comparación original fue alterada")
        reservation, previous = reserve_attempt(
            report_root,
            report=report,
            profile=profile,
            holdout_sha=holdout_sha,
            code_hash=code_hash,
            retry_of=retry_of,
        )
        report["reservation_sha256"] = _sha256(reservation)
        report["retry_of"] = previous
        results = {}
        shared_seconds = verifier_guard.elapsed
        with tempfile.TemporaryDirectory(prefix=".independent-final-", dir=parent) as owned:
            staged = Path(owned)
            for name in NAMES:
                gc.collect()
                pa.default_memory_pool().release_unused()
                results[name] = evaluate_candidate(
                    name,
                    models[name],
                    source=source,
                    holdout=holdout,
                    profile=profile,
                    data=data,
                    staged=staged,
                    test_only=test_only,
                    shared_seconds=shared_seconds,
                    resources=effective_resources,
                )
                report["completed_candidates"] = list(results)
            after, after_sha = verify_final(
                source, profile=profile, config=config, data=data, test_only=test_only
            )
            if after != holdout or after_sha != holdout_sha or source_digest() != code_hash:
                raise ValueError("Datos o código cambiaron durante la evaluación final")
            if read_final_profile(profile_path, test_only=test_only) != profile:
                raise ValueError("El protocolo final cambió")
            if (
                resource_review_path is not None
                and _sha256(Path(resource_review_path)) != review["sha256"]
            ):
                raise ValueError("La aprobación de recursos cambió durante evaluación")
            if (
                fingerprint(read_model_config(config_path)) != fingerprint(config)
                or fingerprint(load_config(data_config_path)) != fingerprint(data)
                or _sha256(Path("requirements-dev.lock")) != lock_hash
            ):
                raise ValueError("Configuración o dependencias cambiaron durante evaluación")
            for info in profile["models"].values():
                if _sha256(Path(info["path"])) != info["sha256"]:
                    raise ValueError("Un modelo congelado cambió durante evaluación")
            if (
                not test_only
                and _sha256(Path(profile["original_evaluation_directory"]) / "selection.json")
                != profile["original_selection_sha256"]
            ):
                raise ValueError("La selección original cambió")
            if _sha256(reservation) != report["reservation_sha256"]:
                raise ValueError("La reserva de evaluación fue alterada")
            ResourceGuard(effective_resources, source, test_only=test_only).check()
            destination = _under(parent, identifier)
            destination.mkdir(exist_ok=False)
            report.update(
                status="FINAL_EVALUATION_TEST_ONLY" if test_only else "FINAL_EVALUATION_REAL",
                output_directory=str(destination),
                publication_complete=True,
                holdout_id=holdout["holdout_id"],
                holdout_manifest_sha256=holdout_sha,
                configuration=profile,
                profile_sha256=fingerprint(profile),
                results=results,
                source_tree_sha256=code_hash,
                lock_sha256=lock_hash,
                finished_at_utc=utc_now(),
                human_review_complete=False,
            )
            for name in NAMES:
                publish_file(staged / f"{name}.parquet", destination / f"{name}.parquet")
            publish_manifest(destination / "evaluation_manifest.json", report)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as error:
        report.update(status="FAIL", publication_complete=False, error=str(error))
    publish_manifest(report_root / f"{identifier}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument(
        "--profile", type=Path, default=Path("configs/lightgbm-final-evaluation.yaml")
    )
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--resource-review", type=Path)
    parser.add_argument("--retry-of", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = evaluate_final(
        args.holdout,
        profile_path=args.profile,
        test_only=args.test_only,
        resource_review_path=args.resource_review,
        retry_of=args.retry_of,
    )
    print(json.dumps(result))
    if not result["publication_complete"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
