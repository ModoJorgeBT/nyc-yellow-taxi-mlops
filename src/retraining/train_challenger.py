"""T33: LightGBM nuevo, train-only, supervisado y sin modificar champion."""

import argparse
import hashlib
import os
import tempfile
import uuid
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from src.features.build import CalendarFeatures
from src.features.schema import FEATURE_COLUMNS
from src.ingestion.manifest import publish_file, utc_now
from src.monitoring.performance import frozen_model
from src.monitoring.protocol import load_config
from src.retraining.cohorts import verify_cohort
from src.retraining.protocol import budget, exclusive_json, inside, load_profile, pinned, read_json
from src.training.candidate_runtime import CandidateGuard, read_batches
from src.training.lightgbm_model import BoundedBooster, NativeFeatures
from src.training.lightgbm_train import read_lightgbm
from src.training.native_supervisor import run_worker
from src.training.tracking import _git_state
from src.training.train import source_digest
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def prepare_disk(source, staged, guard, expected_rows):
    """Mismos bytes nativos T16, escribiendo bloques sin mapear todo train en el padre."""
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
    transformer = NativeFeatures(tuple(sorted(origins))).fit()
    hashes = {name: hashlib.sha256() for name in ("feature", "target")}
    position = blocks = 0
    with (
        (staged / "features.f32").open("xb") as features,
        (staged / "target.f64").open("xb") as target,
    ):
        for values, y, _ in read_batches(source, "train", guard):
            X_bytes = transformer.transform(values).astype("<f4", copy=False).tobytes()
            y_bytes = y.astype("<f8", copy=False).tobytes()
            features.write(X_bytes)
            target.write(y_bytes)
            hashes["feature"].update(X_bytes)
            hashes["target"].update(y_bytes)
            position += len(y)
            blocks += 1
        if position != expected_rows:
            raise ValueError("Conversion train incompleta")
        for stream in (features, target):
            stream.flush()
            os.fsync(stream.fileno())
    guard.check()
    return (
        transformer,
        representative,
        {
            "train_rows": count,
            "vocabulary_observation_rows": count,
            "origin_categories": list(transformer.origins),
            "blocks": blocks,
            "feature_sha256": hashes["feature"].hexdigest(),
            "target_sha256": hashes["target"].hexdigest(),
        },
    )


def train(
    train_directory,
    trigger_entry,
    *,
    profile_path=Path("configs/retraining.yaml"),
    root=None,
    test_only=False,
    audit_entry=None,
):
    root = Path(root or Path.cwd()).resolve()
    profile = load_profile(profile_path, test_only=test_only)
    trigger = read_json(pinned(root, trigger_entry))
    if (
        trigger.get("status") != ("TRIGGER_TEST_ONLY" if test_only else "TRIGGER_REAL")
        or trigger.get("profile_sha256") != fingerprint(profile)
        or trigger.get("publication_complete") is not True
        or trigger.get("decision") != "RETRAIN_RECOMMENDED"
    ):
        raise ValueError("Sin trigger aprobado no se entrena challenger")
    source = Path(train_directory).resolve()
    if not source.is_relative_to(root):
        raise ValueError("Train fuera del proyecto")
    output = inside(root, "models/retraining")
    if test_only:
        output /= "_test_only"
    output /= uuid.uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "FAIL",
        "publication_complete": False,
        "profile_sha256": fingerprint(profile),
        "trigger": trigger_entry,
        "started_at_utc": utc_now(),
        "validation_accessed": False,
        "final_accessed": False,
        "champion_changed": False,
        "approved_for_serving": False,
    }
    report["git_commit"], report["git_dirty"] = _git_state(root)
    try:
        guard = CandidateGuard(budget("training"), root, test_only=test_only)
        guard.check(start=True)
        if not test_only:
            from src.retraining.audit import require_audit

            require_audit(audit_entry, source, "train", profile, root)
        marker = verify_cohort(source, "train", profile, test_only=test_only)
        cohort_hash = _sha256(source / "cohort.json")
        protocol = read_lightgbm(pinned(root, profile["lightgbm_config"]))
        monitor = load_config(pinned(root, profile["monitoring_config"]), test_only=test_only)
        if not test_only:
            _, champion_identity, check_champion = frozen_model(monitor, root)
        else:
            champion_identity = {"scope": "SYNTHETIC_FIXTURE"}

            def check_champion():
                return None

        code_hash = source_digest()
        with tempfile.TemporaryDirectory(prefix=".fit-", dir=output) as temporary:
            staged = Path(temporary)
            with threadpool_limits(limits=4):
                transformer, representative, learned = prepare_disk(
                    source, staged, guard, marker["rows"]
                )
            if learned["target_sha256"] != marker["value_sha256"]["target"]:
                raise ValueError("Etiquetas de train distintas de la cohorte auditada")
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
            exclusive_json(request_path, request)
            native_resources = run_worker(
                request_path,
                policy=budget("training"),
                guard=guard,
                log_path=output / "fit.log",
                aggregate_parent_rss=True,
            )
            native = read_json(staged / "native-result.json")
            if (
                native_resources["worker_pid_verified"] is not True
                or native["dataset_rows"] != marker["rows"]
                or native["range_rows"] != marker["rows"]
                or native["feature_sha256"] != learned["feature_sha256"]
                or native["target_sha256"] != learned["target_sha256"]
                or native["feature_names"] != list(FEATURE_COLUMNS)
                or native["lightgbm_version"] != "4.7.0"
                or not 1 <= native["iterations"] <= protocol["num_boost_round"]
            ):
                raise ValueError("Fit nativo incompleto o incompatible")
            booster = BoundedBooster(
                (staged / "booster.txt").read_text(encoding="utf-8")
            ).load_fitted(rows=marker["rows"])
            model = Pipeline(
                [
                    ("calendar", CalendarFeatures().fit([representative])),
                    ("native", transformer),
                    ("estimator", booster),
                ]
            )
            smoke = np.asarray(model.predict([representative]), dtype=float)
            if (
                smoke.shape != (1,)
                or not np.isfinite(smoke).all()
                or np.any((smoke < 1 / 60) | (smoke > 180))
            ):
                raise ValueError("Smoke del candidato invalido")
            joblib.dump(model, staged / "lightgbm.joblib")
            if not np.array_equal(
                joblib.load(staged / "lightgbm.joblib").predict([representative]), smoke
            ):
                raise ValueError("Serializacion divergente")
            check_champion()
            if (
                verify_cohort(source, "train", profile, test_only=test_only) != marker
                or _sha256(source / "cohort.json") != cohort_hash
                or source_digest() != code_hash
                or load_profile(profile_path, test_only=test_only) != profile
            ):
                raise ValueError("Train/codigo/perfil cambio durante ajuste")
            pinned(root, trigger_entry)
            pinned(root, profile["runtime_lock"])
            guard.check()
            for name in ("lightgbm.joblib", "booster.txt"):
                publish_file(staged / name, output / name)
            report.update(
                status="CHALLENGER_TRAINING_TEST_ONLY" if test_only else "CHALLENGER_TRAINING_REAL",
                publication_complete=True,
                cohort={
                    "path": str((source / "cohort.json").relative_to(root)),
                    "sha256": cohort_hash,
                },
                rows=marker["rows"],
                cohort_audit=audit_entry,
                learned=learned,
                native=native,
                champion=champion_identity,
                model_sha256=_sha256(output / "lightgbm.joblib"),
                source_tree_sha256=code_hash,
                lightgbm_config_sha256=profile["lightgbm_config"]["sha256"],
                resources={
                    "initial": guard.initial,
                    "final": guard.last,
                    "elapsed_seconds": guard.elapsed,
                    **native_resources,
                },
            )
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        report["error"] = str(error)
    report["finished_at_utc"] = utc_now()
    exclusive_json(output / "training_manifest.json", report)
    return output, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--trigger", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    entry = {
        "path": str(args.trigger.resolve().relative_to(Path.cwd())),
        "sha256": _sha256(args.trigger),
    }
    audit = (
        {"path": str(args.audit.resolve().relative_to(Path.cwd())), "sha256": _sha256(args.audit)}
        if args.audit
        else None
    )
    output, result = train(
        args.train, entry, profile_path=args.config, test_only=args.test_only, audit_entry=audit
    )
    print({"output": str(output), "status": result["status"], "error": result.get("error")})
    if not result["publication_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
