"""T17: seleccion con validation congelada antes de evaluar test; sin promocion."""

import argparse
import hashlib
import json
import logging
import math
import tempfile
import uuid
from contextlib import ExitStack
from pathlib import Path

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.evaluation.metrics import ErrorStore
from src.evaluation.segments import SegmentRows, group_masks, route_catalog
from src.ingestion.manifest import describe_parquet, publish_file, publish_manifest, utc_now
from src.training.candidate_runtime import (
    CandidateGuard,
    read_batches,
    read_candidates,
    verify_scope,
)
from src.training.models import predict_matrix
from src.training.split import read_model_config
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint, load_config

LOGGER = logging.getLogger(__name__)
NAMES = ("baseline", "sgd", "mlp")


def read_object(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Se requiere objeto JSON")
    return value


def load_models(directory, *, candidates, split, audit_sha256, test_only):
    marker = _under(directory, "training_manifest.json")
    report = read_object(marker)
    if (
        report.get("status") != ("TRAINING_TEST_ONLY" if test_only else "TRAINING_REAL")
        or report.get("publication_complete") is not True
        or directory.name != report.get("training_id")
        or report.get("source_split_sha256") != split["marker_sha256"]
        or report.get("source_audit_sha256") != audit_sha256
        or report.get("candidate_config_sha256") != fingerprint(candidates)
        or set(report.get("models", {})) != {"sgd", "mlp"}
    ):
        raise ValueError("T16 incompleta, alterada o de otro ambito/configuracion")
    models = {}
    for name in ("sgd", "mlp"):
        info = report["models"][name]
        path = _under(directory, f"{name}.joblib")
        if (
            info.get("file_name") != path.name
            or _sha256(path) != info["sha256"]
            or info["train_rows"] != split["manifest"]["partitions"]["train"]["rows"]
            or info["epochs"] != 1
        ):
            raise ValueError("Candidato distinto de la version congelada")
        model = joblib.load(path)  # Solo artefactos locales T16 verificados, no payloads de API.
        if (
            model.named_steps["estimator"].rows_fitted_ != info["train_rows"]
            or model.named_steps["estimator"].lower != 1 / 60
            or model.named_steps["estimator"].upper != 180
        ):
            raise ValueError("Estado aprendido del candidato incompatible")
        models[name] = model
    return report, models, _sha256(marker)


def load_baseline(directory, *, split, audit_path, test_only):
    marker = _under(directory, "baseline_manifest.json")
    report = read_object(marker)
    model = read_object(_under(directory, "model.json"))
    if (
        report.get("status") != ("BASELINE_TEST_ONLY" if test_only else "BASELINE_REAL")
        or report.get("publication_complete") is not True
        or directory.name != report.get("baseline_id")
        or report.get("model") != model
        or report.get("model_sha256") != _sha256(directory / "model.json")
        or model.get("kind") != "exact_global_train_median"
        or model.get("train_rows") != split["manifest"]["partitions"]["train"]["rows"]
        or report.get("validation_rows") != split["manifest"]["partitions"]["validation"]["rows"]
    ):
        raise ValueError("Baseline no corresponde al train/validation congelado")
    value = model["prediction_minutes"]
    if type(value) is not float or not math.isfinite(value) or not 0 < value <= 180:
        raise ValueError("Baseline no positivo/finito")
    if test_only:
        if report.get("source_split_manifest_sha256") != split["marker_sha256"]:
            raise ValueError("Baseline fixture de otras particiones")
    else:
        audit = read_object(audit_path)
        if (
            report.get("t15_complete") is not True
            or model.get("train_target_logical_sha256") != audit["target_sha256"]["train"]
            or report.get("validation_logical_sha256")
            != split["manifest"]["partitions"]["validation"]["logical_sha256"]
        ):
            raise ValueError("Baseline REAL no coincide con T15 verificada")
    return value, report, _sha256(marker)


def evaluate_partition(source, partition, manifest, models, median, routes, guard, staged, scratch):
    selected = [row["code"] for row in routes["routes"]]
    stores = {name: ErrorStore(scratch / partition / name) for name in NAMES}
    clipped = dict.fromkeys(NAMES, 0)
    count = 0
    target_hash = hashlib.sha256()
    schema = pa.schema([("row_index", pa.int64()), ("predicted_duration_minutes", pa.float64())])
    with ExitStack() as stack:
        writers = {
            name: stack.enter_context(
                pq.ParquetWriter(staged / f"{partition}_{name}.parquet", schema)
            )
            for name in NAMES
        }
        segments = stack.enter_context(SegmentRows(manifest, partition))
        for X, y, context in read_batches(source, partition, guard):
            masks = group_masks(X, segments.route_codes(X, context), selected)
            for name in NAMES:
                predictions, changed = (
                    (np.full(len(y), median, dtype=np.float64), 0)
                    if name == "baseline"
                    else predict_matrix(models[name], X)
                )
                clipped[name] += changed
                stores[name].add(y, predictions, masks)
                writers[name].write_table(
                    pa.Table.from_arrays(
                        [
                            pa.array(np.arange(count, count + len(y), dtype=np.int64)),
                            pa.array(predictions),
                        ],
                        schema=schema,
                    )
                )
                guard.check()
            target_hash.update(y.astype("<f8", copy=False).tobytes())
            count += len(y)
            if count % (4096 * 256) == 0:
                LOGGER.info("Evaluacion %s: %d filas", partition, count)
    if count != manifest["partitions"][partition]["rows"]:
        raise ValueError("Evaluacion no cubre toda la particion")
    results = {name: stores[name].results(resource_check=guard.check) for name in NAMES}
    for result in results.values():
        for prefix in ("month_", "band_", "route_"):
            if (
                sum(value["rows"] for key, value in result.items() if key.startswith(prefix))
                != count
            ):
                raise ValueError("Segmentos no cubren todas las filas")
    return {
        "rows": count,
        "metrics": results,
        "clipped_predictions": clipped,
        "target_sha256": target_hash.hexdigest(),
        "predictions": {
            name: describe_parquet(staged / f"{partition}_{name}.parquet") for name in NAMES
        },
    }


def select_validation(result):
    return min(
        NAMES, key=lambda name: (result["metrics"][name]["all"]["mae_minutes"], NAMES.index(name))
    )


def evaluate_models(
    split_directory,
    training_directory,
    baseline_directory,
    *,
    audit_path=None,
    candidate_config_path=Path("configs/candidates.yaml"),
    config_path=Path("configs/model.yaml"),
    data_config_path=Path("configs/data.yaml"),
    output_dir=Path("data/processed/evaluations"),
    report_dir=Path("reports/evaluation"),
    scratch_dir=Path(".cache/evaluation"),
    test_only=False,
):
    if type(test_only) is not bool:
        raise ValueError("Modo de evaluacion invalido")
    source, training, baseline, output, reports, scratch = [
        Path(p).resolve()
        for p in (
            split_directory,
            training_directory,
            baseline_directory,
            output_dir,
            report_dir,
            scratch_dir,
        )
    ]
    roots = (source, training, baseline, output, reports, scratch)
    if any(
        a.is_relative_to(b) or b.is_relative_to(a)
        for i, a in enumerate(roots)
        for b in roots[i + 1 :]
    ):
        raise ValueError("Artefactos y salidas de evaluacion deben estar separados")
    identifier = uuid.uuid4().hex
    scopes = ("_test_only",) if test_only else ()
    reports = _under(reports, *scopes)
    reports.mkdir(parents=True, exist_ok=True)
    report = {
        "evaluation_id": identifier,
        "status": "FAIL",
        "mode": "TEST_ONLY" if test_only else "REAL",
        "publication_complete": False,
        "test_accessed": False,
        "monitoring_replay_accessed": False,
        "approved_for_serving": False,
        "model_registered": False,
        "started_at_utc": utc_now(),
    }
    try:
        candidates = read_candidates(Path(candidate_config_path))
        config, data = read_model_config(Path(config_path)), load_config(Path(data_config_path))
        guard = CandidateGuard(candidates["resources"], source, test_only=test_only)
        guard.check(start=True)
        verified = verify_scope(
            source,
            config=config,
            data_config=data,
            test_only=test_only,
            partitions=("validation",),
            audit_path=audit_path,
        )
        fitted, models, training_sha = load_models(
            training,
            candidates=candidates,
            split=verified,
            audit_sha256=verified.get("audit_sha256"),
            test_only=test_only,
        )
        median, frozen_baseline, baseline_sha = load_baseline(
            baseline, split=verified, audit_path=audit_path, test_only=test_only
        )
        parent = _under(output, *scopes)
        parent.mkdir(parents=True, exist_ok=True)
        scratch.mkdir(parents=True, exist_ok=True)
        with (
            tempfile.TemporaryDirectory(prefix=".evaluate-", dir=parent) as owned,
            tempfile.TemporaryDirectory(prefix="errors-", dir=scratch) as errors,
            threadpool_limits(limits=4),
        ):
            staged = Path(owned)
            manifest = verified["manifest"]
            routes = route_catalog(source, manifest, guard)
            validation = evaluate_partition(
                source, "validation", manifest, models, median, routes, guard, staged, Path(errors)
            )
            if (
                verify_scope(
                    source,
                    config=config,
                    data_config=data,
                    test_only=test_only,
                    partitions=("validation",),
                    audit_path=audit_path,
                )
                != verified
            ):
                raise ValueError("Validation cambio durante la evaluacion")
            if (
                not test_only
                and validation["target_sha256"]
                != read_object(audit_path)["target_sha256"]["validation"]
            ):
                raise ValueError("Etiquetas validation distintas de T14")
            for metric in ("mae_minutes", "rmse_minutes"):
                if not math.isclose(
                    validation["metrics"]["baseline"]["all"][metric],
                    frozen_baseline["validation_metrics"][metric],
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ):
                    raise ValueError("Baseline no reproduce las metricas T15 congeladas")
            winner = select_validation(validation)
            destination = _under(parent, identifier)
            destination.mkdir(exist_ok=False)
            selection = {
                "status": "VALIDATION_SELECTION_FROZEN",
                "evaluation_id": identifier,
                "source_split_sha256": verified["marker_sha256"],
                "training_manifest_sha256": training_sha,
                "baseline_manifest_sha256": baseline_sha,
                "route_catalog": routes,
                "validation_metrics": {n: validation["metrics"][n]["all"] for n in NAMES},
                "recommended_model": winner,
                "criterion": "validation_mae_then_baseline_sgd_mlp",
                "test_accessed_at_selection": False,
                "approved_for_serving": False,
                "model_registered": False,
            }
            publish_manifest(destination / "selection.json", selection)
            selection_sha = _sha256(destination / "selection.json")
            report.update(
                selection=selection,
                selection_sha256=selection_sha,
                validation=validation,
                output_directory=str(destination),
            )
            report["test_accessed"] = True
            test_verified = verify_scope(
                source,
                config=config,
                data_config=data,
                test_only=test_only,
                partitions=("test",),
                audit_path=audit_path,
            )
            test = evaluate_partition(
                source, "test", manifest, models, median, routes, guard, staged, Path(errors)
            )
            if (
                verify_scope(
                    source,
                    config=config,
                    data_config=data,
                    test_only=test_only,
                    partitions=("test",),
                    audit_path=audit_path,
                )
                != test_verified
            ):
                raise ValueError("Test cambio durante la evaluacion")
            if (
                not test_only
                and test["target_sha256"] != read_object(audit_path)["target_sha256"]["test"]
            ):
                raise ValueError("Etiquetas test distintas de T14")
            if (
                _sha256(destination / "selection.json") != selection_sha
                or _sha256(training / "training_manifest.json") != training_sha
                or _sha256(baseline / "baseline_manifest.json") != baseline_sha
                or read_candidates(Path(candidate_config_path)) != candidates
            ):
                raise ValueError("Seleccion, modelos o parametros cambiaron despues de congelar")
            for name, info in fitted["models"].items():
                if _sha256(training / f"{name}.joblib") != info["sha256"]:
                    raise ValueError("Modelo alterado durante evaluacion")
            guard.check()
            for partition in ("validation", "test"):
                for name in NAMES:
                    publish_file(
                        staged / f"{partition}_{name}.parquet",
                        destination / f"{partition}_{name}.parquet",
                    )
            report.update(
                status="EVALUATION_TEST_ONLY" if test_only else "EVALUATION_REAL",
                publication_complete=True,
                test=test,
                recommended_model=winner,
                source_split_id=manifest["split_id"],
                source_split_sha256=verified["marker_sha256"],
                source_audit_sha256=verified.get("audit_sha256"),
                candidate_configuration=candidates,
                resources={
                    "initial": guard.initial,
                    "final": guard.last,
                    "elapsed_seconds": guard.elapsed,
                },
                human_review_complete=False,
                finished_at_utc=utc_now(),
            )
            publish_manifest(destination / "evaluation_manifest.json", report)
    except (ValueError, RuntimeError, OSError, TypeError, KeyError) as error:
        report.update(
            status="FAIL", publication_complete=False, error=str(error), finished_at_utc=utc_now()
        )
    publish_manifest(reports / f"{identifier}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--candidates", type=Path, default=Path("configs/candidates.yaml"))
    parser.add_argument("--config", type=Path, default=Path("configs/model.yaml"))
    parser.add_argument("--data-config", type=Path, default=Path("configs/data.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/evaluations"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/evaluation"))
    parser.add_argument("--scratch-dir", type=Path, default=Path(".cache/evaluation"))
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        result = evaluate_models(
            args.split,
            args.training,
            args.baseline,
            audit_path=args.audit,
            candidate_config_path=args.candidates,
            config_path=args.config,
            data_config_path=args.data_config,
            output_dir=args.output_dir,
            report_dir=args.report_dir,
            scratch_dir=args.scratch_dir,
            test_only=args.test_only,
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Evaluacion fallida: {error}\n")
    print(json.dumps(result))
    if result["status"] == "FAIL":
        parser.exit(1)


if __name__ == "__main__":
    main()
