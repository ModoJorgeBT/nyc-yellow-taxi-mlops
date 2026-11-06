"""Extensión LightGBM: solo validation; selección y test originales inmutables."""

import argparse
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
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.evaluation.metrics import ErrorStore
from src.evaluation.run import read_object
from src.evaluation.segments import SegmentRows, group_masks
from src.ingestion.manifest import describe_parquet, publish_file, publish_manifest, utc_now
from src.training.candidate_runtime import CandidateGuard, read_batches, verify_scope
from src.training.lightgbm_train import read_lightgbm, separate_roots
from src.training.split import read_model_config
from src.training.train import source_digest
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint, load_config

LOGGER = logging.getLogger(__name__)


def original_comparison(directory, *, audit_path, split_sha256, test_only):
    marker = _under(directory, "evaluation_manifest.json")
    selection_path = _under(directory, "selection.json")
    report, selection = read_object(marker), read_object(selection_path)
    if (
        report.get("status") != ("EVALUATION_TEST_ONLY" if test_only else "EVALUATION_REAL")
        or report.get("publication_complete") is not True
        or directory.name != report.get("evaluation_id")
        or report.get("source_split_sha256") != split_sha256
        or report.get("selection") != selection
        or _sha256(selection_path) != report.get("selection_sha256")
        or selection.get("test_accessed_at_selection") is not False
        or report.get("recommended_model") != selection.get("recommended_model")
    ):
        raise ValueError("Comparación original alterada o no congelada antes de test")
    if not test_only:
        if audit_path is None:
            raise ValueError("Extensión REAL requiere auditoría de la comparación original")
        audit = read_object(audit_path)
        if (
            audit.get("status") != "VERIFIED_T17_FROZEN_VALIDATION_AND_FINAL_TEST"
            or audit.get("evaluation_id") != report["evaluation_id"]
            or audit.get("evaluation_manifest_sha256") != _sha256(marker)
            or audit.get("selection_sha256") != _sha256(selection_path)
            or audit.get("selection_unchanged_after_test") is not True
            or audit.get("recommended_model") != report["recommended_model"]
        ):
            raise ValueError("La auditoría original no corresponde a esta comparación")
    return report, _sha256(marker), _sha256(selection_path)


def evaluate_lightgbm(
    split_directory,
    training_directory,
    original_directory,
    *,
    audit_path=None,
    original_audit_path=None,
    lightgbm_config_path=Path("configs/lightgbm.yaml"),
    config_path=Path("configs/model.yaml"),
    data_config_path=Path("configs/data.yaml"),
    output_dir=Path("data/processed/lightgbm-evaluations"),
    report_dir=Path("reports/evaluation/lightgbm"),
    test_only=False,
):
    if type(test_only) is not bool:
        raise ValueError("Modo test_only inválido")
    source, training, original, output, reports = separate_roots(
        split_directory, training_directory, original_directory, output_dir, report_dir
    )
    scopes = ("_test_only",) if test_only else ()
    report_root = _under(reports, *scopes)
    report_root.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    report = {
        "evaluation_id": identifier,
        "status": "FAIL",
        "publication_complete": False,
        "mode": "TEST_ONLY" if test_only else "REAL",
        "started_at_utc": utc_now(),
        "test_accessed": False,
        "monitoring_replay_accessed": False,
        "new_independent_final_evaluation": "PENDING",
        "approved_for_serving": False,
        "model_registered": False,
        "human_review_complete": False,
    }
    try:
        protocol = read_lightgbm(lightgbm_config_path)
        config, data = read_model_config(config_path), load_config(data_config_path)
        code_hash, lock_hash = source_digest(), _sha256(Path("requirements-dev.lock"))
        guard = CandidateGuard(protocol["resources"], source, test_only=test_only)
        guard.check(start=True)
        verified = verify_scope(
            source,
            config=config,
            data_config=data,
            test_only=test_only,
            partitions=("validation",),
            audit_path=audit_path,
        )
        original_report, original_sha, selection_sha = original_comparison(
            original,
            audit_path=original_audit_path,
            split_sha256=verified["marker_sha256"],
            test_only=test_only,
        )
        marker = training / "training_manifest.json"
        fitted = read_object(marker)
        marker_sha = _sha256(marker)
        model_path = training / "lightgbm.joblib"
        if (
            fitted.get("status")
            != ("LIGHTGBM_TRAINING_TEST_ONLY" if test_only else "LIGHTGBM_TRAINING_REAL")
            or fitted.get("publication_complete") is not True
            or fitted.get("training_id") != training.name
            or fitted.get("source_split_sha256") != verified["marker_sha256"]
            or fitted.get("source_audit_sha256") != verified.get("audit_sha256")
            or fitted.get("protocol_sha256") != fingerprint(protocol)
            or fitted.get("configuration") != protocol
            or fitted.get("resources", {}).get("worker_pid_verified") is not True
            or _sha256(model_path) != fitted.get("model_sha256")
            or _sha256(training / "booster.txt") != fitted.get("booster_sha256")
        ):
            raise ValueError("Modelo LightGBM no corresponde al ajuste aprobado")
        model = joblib.load(model_path)
        if model.named_steps["estimator"].rows_fitted_ != fitted["learned"]["train_rows"]:
            raise ValueError("Estado aprendido LightGBM incompatible")
        routes = original_report["selection"]["route_catalog"]
        selected = [row["code"] for row in routes["routes"]]
        parent = _under(output, *scopes)
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".lightgbm-eval-", dir=parent) as owned:
            staged = Path(owned)
            store = ErrorStore(staged / "errors")
            count, changed, unknown = 0, 0, 0
            target_hash = hashlib.sha256()
            schema = pa.schema(
                [("row_index", pa.int64()), ("predicted_duration_minutes", pa.float64())]
            )
            with ExitStack() as stack, threadpool_limits(limits=4):
                writer = stack.enter_context(
                    pq.ParquetWriter(staged / "validation.parquet", schema)
                )
                segments = stack.enter_context(SegmentRows(verified["manifest"], "validation"))
                for values, y, context in read_batches(source, "validation", guard):
                    encoded = model.named_steps["native"].transform(values)
                    predicted, clipped = model.named_steps["estimator"].predict_with_diagnostics(
                        encoded
                    )
                    unknown += int(np.count_nonzero(encoded[:, 0] == -1))
                    changed += clipped
                    store.add(
                        y,
                        predicted,
                        group_masks(values, segments.route_codes(values, context), selected),
                    )
                    writer.write_table(
                        pa.Table.from_arrays(
                            [
                                pa.array(np.arange(count, count + len(y), dtype=np.int64)),
                                pa.array(predicted),
                            ],
                            schema=schema,
                        )
                    )
                    count += len(y)
                    target_hash.update(y.astype("<f8", copy=False).tobytes())
                    if count % (4096 * 256) == 0:
                        LOGGER.info("LightGBM validation: %d filas", count)
            if count != verified["manifest"]["partitions"]["validation"]["rows"]:
                raise ValueError("Evaluación LightGBM no exhaustiva")
            metrics = store.results(resource_check=guard.check)
            for prefix in ("month_", "band_", "route_"):
                if sum(v["rows"] for k, v in metrics.items() if k.startswith(prefix)) != count:
                    raise ValueError("Segmentos LightGBM incompletos")
            if (
                target_hash.hexdigest() != original_report["validation"]["target_sha256"]
                or count != original_report["validation"]["rows"]
            ):
                raise ValueError("Validation distinta de la comparación original")
            after = verify_scope(
                source,
                config=config,
                data_config=data,
                test_only=test_only,
                partitions=("validation",),
                audit_path=audit_path,
            )
            if (
                after["marker_sha256"] != verified["marker_sha256"]
                or _sha256(marker) != marker_sha
                or _sha256(model_path) != fitted["model_sha256"]
                or _sha256(training / "booster.txt") != fitted["booster_sha256"]
                or _sha256(original / "selection.json") != selection_sha
                or _sha256(original / "evaluation_manifest.json") != original_sha
                or read_lightgbm(lightgbm_config_path) != protocol
                or source_digest() != code_hash
                or _sha256(Path("requirements-dev.lock")) != lock_hash
                or fingerprint(read_model_config(config_path)) != fingerprint(config)
                or fingerprint(load_config(data_config_path)) != fingerprint(data)
            ):
                raise ValueError("Artefactos o protocolo cambiaron durante la extensión")
            guard.check()
            destination = _under(parent, identifier)
            destination.mkdir(exist_ok=False)
            report.update(
                status="LIGHTGBM_EVALUATION_TEST_ONLY" if test_only else "LIGHTGBM_EVALUATION_REAL",
                output_directory=str(destination),
                publication_complete=True,
                validation_rows=count,
                metrics=metrics,
                clipped_predictions=changed,
                unknown_origin_rows=unknown,
                target_sha256=target_hash.hexdigest(),
                route_catalog=routes,
                predictions=describe_parquet(staged / "validation.parquet"),
                training_id=fitted["training_id"],
                training_manifest_sha256=marker_sha,
                source_split_sha256=verified["marker_sha256"],
                source_audit_sha256=verified.get("audit_sha256"),
                original_evaluation_id=original_report["evaluation_id"],
                original_evaluation_manifest_sha256=original_sha,
                original_selection_sha256=selection_sha,
                original_recommended_model=original_report["recommended_model"],
                frozen_validation_comparators=original_report["validation"]["metrics"],
                original_selection_changed=False,
                configuration=protocol,
                source_tree_sha256=code_hash,
                lock_sha256=lock_hash,
                resources={
                    "initial": guard.initial,
                    "final": guard.last,
                    "elapsed_seconds": guard.elapsed,
                },
                finished_at_utc=utc_now(),
            )
            publish_file(staged / "validation.parquet", destination / "validation.parquet")
            publish_manifest(destination / "evaluation_manifest.json", report)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as error:
        report.update(
            status="FAIL", publication_complete=False, error=str(error), finished_at_utc=utc_now()
        )
    publish_manifest(report_root / f"{identifier}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--original-evaluation", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--original-audit", type=Path)
    parser.add_argument("--lightgbm-config", type=Path, default=Path("configs/lightgbm.yaml"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/lightgbm-evaluations")
    )
    parser.add_argument("--report-dir", type=Path, default=Path("reports/evaluation/lightgbm"))
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    result = evaluate_lightgbm(
        args.split,
        args.training,
        args.original_evaluation,
        audit_path=args.audit,
        original_audit_path=args.original_audit,
        lightgbm_config_path=args.lightgbm_config,
        output_dir=args.output_dir,
        report_dir=args.report_dir,
        test_only=args.test_only,
    )
    print(json.dumps(result))
    if not result["publication_complete"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
