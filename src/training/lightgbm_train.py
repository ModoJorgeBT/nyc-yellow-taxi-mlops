"""Extensión aprobada: LightGBM sobre todo train, sin abrir validation/test/replay."""

import argparse
import hashlib
import json
import logging
import tempfile
import uuid
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from src.features.build import CalendarFeatures
from src.features.schema import FEATURE_COLUMNS
from src.ingestion.manifest import publish_file, publish_manifest, utc_now
from src.training.candidate_runtime import CandidateGuard, read_batches, verify_scope
from src.training.lightgbm_model import BoundedBooster, NativeFeatures
from src.training.native_supervisor import run_worker
from src.training.split import read_model_config
from src.training.train import source_digest
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint, load_config

APPROVED_CONFIG_SHA256 = "98f59416cd0138faf764db0b02464d446b8273691d960f57ccc4c7e8f217af0e"
LOGGER = logging.getLogger(__name__)


def read_lightgbm(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if fingerprint(value) != APPROVED_CONFIG_SHA256:
        raise ValueError(
            "Protocolo LightGBM distinto del aprobado, incluida evaluación solo validation"
        )
    return value


def separate_roots(*paths):
    roots = tuple(Path(p).resolve() for p in paths)
    if any(
        a.is_relative_to(b) or b.is_relative_to(a)
        for i, a in enumerate(roots)
        for b in roots[i + 1 :]
    ):
        raise ValueError("Entradas y salidas deben estar separadas")
    return roots


def prepare_disk(source, staged, guard, expected_rows):
    origins, count, representative = set(), 0, None
    for values, y, context in read_batches(source, "train", guard):
        origins.update(int(v) for v in np.unique(values[:, 0]))
        count += len(y)
        if representative is None:
            representative = {
                "pickup_location_id": int(values[0, 0]),
                "pickup_datetime": context.column(1)[0].as_py(),
                "passenger_count": None if values[0, 5] else int(values[0, 4]),
            }
    if count != expected_rows or representative is None:
        raise ValueError("Vocabulario no cubre todo train")
    LOGGER.info("LightGBM: vocabulario de %d zonas observado en %d filas", len(origins), count)
    transformer = NativeFeatures(tuple(sorted(origins))).fit()
    feature_hash, target_hash = hashlib.sha256(), hashlib.sha256()
    X = np.memmap(staged / "features.f32", mode="w+", dtype="<f4", shape=(count, 6))
    y_disk = None
    position, blocks = 0, 0
    try:
        y_disk = np.memmap(staged / "target.f64", mode="w+", dtype="<f8", shape=(count,))
        for values, y, _ in read_batches(source, "train", guard):
            end = position + len(y)
            if end > count:
                raise ValueError("Train creció durante conversión")
            native = transformer.transform(values)
            X[position:end], y_disk[position:end] = native, y
            feature_hash.update(native.astype("<f4", copy=False).tobytes())
            target_hash.update(y.astype("<f8", copy=False).tobytes())
            position, blocks = end, blocks + 1
            if blocks % 256 == 0:
                LOGGER.info("LightGBM: %d filas convertidas a disco", position)
        if position != count:
            raise ValueError("Conversión train incompleta")
        X.flush()
        y_disk.flush()
        guard.check()
    finally:
        X._mmap.close()
        if y_disk is not None:
            y_disk._mmap.close()
    return (
        transformer,
        representative,
        {
            "train_rows": count,
            "vocabulary_observation_rows": count,
            "origin_categories": list(transformer.origins),
            "blocks": blocks,
            "feature_sha256": feature_hash.hexdigest(),
            "target_sha256": target_hash.hexdigest(),
        },
    )


def train_lightgbm(
    split_directory,
    *,
    audit_path=None,
    lightgbm_config_path=Path("configs/lightgbm.yaml"),
    config_path=Path("configs/model.yaml"),
    data_config_path=Path("configs/data.yaml"),
    output_dir=Path("models/lightgbm"),
    report_dir=Path("reports/training/lightgbm"),
    test_only=False,
):
    if type(test_only) is not bool:
        raise ValueError("Modo test_only inválido")
    source, output, reports = separate_roots(split_directory, output_dir, report_dir)
    scopes = ("_test_only",) if test_only else ()
    report_root = _under(reports, *scopes)
    report_root.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    report = {
        "training_id": identifier,
        "status": "FAIL",
        "publication_complete": False,
        "mode": "TEST_ONLY" if test_only else "REAL",
        "started_at_utc": utc_now(),
        "validation_accessed": False,
        "test_accessed": False,
        "monitoring_replay_accessed": False,
        "approved_for_serving": False,
        "model_registered": False,
        "human_review_complete": False,
    }
    try:
        protocol = read_lightgbm(lightgbm_config_path)
        code_hash, lock_hash = source_digest(), _sha256(Path("requirements-dev.lock"))
        config, data = read_model_config(config_path), load_config(data_config_path)
        guard = CandidateGuard(protocol["resources"], source, test_only=test_only)
        guard.check(start=True)
        verified = verify_scope(
            source,
            config=config,
            data_config=data,
            test_only=test_only,
            partitions=("train",),
            audit_path=audit_path,
        )
        parent = _under(output, *scopes)
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".lightgbm-", dir=parent) as owned:
            staged = Path(owned)
            with threadpool_limits(limits=4):
                transformer, representative, learned = prepare_disk(
                    source, staged, guard, verified["manifest"]["partitions"]["train"]["rows"]
                )
            if not test_only:
                audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
                if learned["target_sha256"] != audit["target_sha256"]["train"]:
                    raise ValueError("Etiquetas distintas de T14 auditada")
            request = {
                "features": str(staged / "features.f32"),
                "target": str(staged / "target.f64"),
                "rows": learned["train_rows"],
                "feature_names": list(FEATURE_COLUMNS),
                "feature_sha256": learned["feature_sha256"],
                "target_sha256": learned["target_sha256"],
                "parameters": protocol["parameters"],
                "num_boost_round": protocol["num_boost_round"],
                "model": str(staged / "booster.txt"),
                "result": str(staged / "native-result.json"),
            }
            request_path = staged / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            native_resources = run_worker(
                request_path,
                policy=protocol["resources"],
                guard=guard,
                log_path=report_root / f"{identifier}.log",
            )
            native = json.loads((staged / "native-result.json").read_text(encoding="utf-8"))
            if (
                native_resources.get("worker_pid_verified") is not True
                or native_resources["native_peak_rss_bytes"] <= 0
                or native["dataset_rows"] != learned["train_rows"]
                or native["range_rows"] != learned["train_rows"]
                or native["feature_sha256"] != learned["feature_sha256"]
                or native["target_sha256"] != learned["target_sha256"]
                or native["feature_names"] != list(FEATURE_COLUMNS)
                or not 1 <= native["iterations"] <= protocol["num_boost_round"]
                or native["lightgbm_version"] != "4.7.0"
            ):
                raise ValueError("Resultado nativo incompleto o incompatible")
            predictor = BoundedBooster(
                (staged / "booster.txt").read_text(encoding="utf-8")
            ).load_fitted(rows=learned["train_rows"])
            model = Pipeline(
                [
                    ("calendar", CalendarFeatures().fit([representative])),
                    ("native", transformer),
                    ("estimator", predictor),
                ]
            )
            predictions = model.predict([representative])
            if not np.isfinite(predictions).all():
                raise ValueError("Pipeline serializado incompatible")
            joblib.dump(model, staged / "lightgbm.joblib")
            after = verify_scope(
                source,
                config=config,
                data_config=data,
                test_only=test_only,
                partitions=("train",),
                audit_path=audit_path,
            )
            if (
                after["marker_sha256"] != verified["marker_sha256"]
                or read_lightgbm(lightgbm_config_path) != protocol
                or source_digest() != code_hash
                or _sha256(Path("requirements-dev.lock")) != lock_hash
                or fingerprint(read_model_config(config_path)) != fingerprint(config)
                or fingerprint(load_config(data_config_path)) != fingerprint(data)
            ):
                raise ValueError("Entradas/código/configuración cambiaron durante ajuste")
            guard.check()
            destination = _under(parent, identifier)
            destination.mkdir(exist_ok=False)
            report.update(
                status="LIGHTGBM_TRAINING_TEST_ONLY" if test_only else "LIGHTGBM_TRAINING_REAL",
                output_directory=str(destination),
                source_split_id=verified["manifest"]["split_id"],
                source_split_sha256=verified["marker_sha256"],
                source_audit_sha256=verified.get("audit_sha256"),
                configuration=protocol,
                protocol_sha256=fingerprint(protocol),
                learned=learned,
                native=native,
                source_tree_sha256=code_hash,
                lock_sha256=lock_hash,
                model_sha256=_sha256(staged / "lightgbm.joblib"),
                booster_sha256=_sha256(staged / "booster.txt"),
                resources={
                    "initial": guard.initial,
                    "final": guard.last,
                    "elapsed_seconds": guard.elapsed,
                    **native_resources,
                },
                finished_at_utc=utc_now(),
                publication_complete=True,
            )
            for name in ("lightgbm.joblib", "booster.txt"):
                publish_file(staged / name, destination / name)
            publish_manifest(destination / "training_manifest.json", report)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as error:
        report.update(
            status="FAIL", publication_complete=False, error=str(error), finished_at_utc=utc_now()
        )
    publish_manifest(report_root / f"{identifier}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--lightgbm-config", type=Path, default=Path("configs/lightgbm.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/lightgbm"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/training/lightgbm"))
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = train_lightgbm(
        args.split,
        audit_path=args.audit,
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
