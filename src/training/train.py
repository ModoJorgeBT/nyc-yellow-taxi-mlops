"""T16: dos candidatos incrementales sobre todo train, sin abrir validation/test."""

import argparse
import copy
import hashlib
import json
import logging
import tempfile
import uuid
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_info, threadpool_limits

from src.features.build import make_preprocessor
from src.ingestion.manifest import publish_file, publish_manifest, utc_now
from src.training.candidate_runtime import (
    CandidateGuard,
    read_batches,
    read_candidates,
    verify_scope,
)
from src.training.models import encode_matrix, estimator
from src.training.split import read_model_config
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint, load_config

LOGGER = logging.getLogger(__name__)


def fit_preprocessing(source, guard, expected_rows):
    representatives = {}
    seen = 0
    for values, _, context in read_batches(source, "train", guard):
        _, indices = np.unique(values[:, 0], return_index=True)
        for index in indices:
            index = int(index)
            origin = int(values[index, 0])
            if origin not in representatives:
                representatives[origin] = {
                    "pickup_location_id": origin,
                    "pickup_datetime": context.column(1)[index].as_py(),
                    "passenger_count": None if values[index, 5] else int(values[index, 4]),
                }
        seen += len(values)
        if seen % (4096 * 256) == 0:
            LOGGER.info("Vocabulario train: %d filas", seen)
    if seen != expected_rows:
        raise ValueError("Cobertura incompleta al obtener vocabulario train")
    preprocessor = make_preprocessor().fit(list(representatives.values()))
    scaler = StandardScaler(with_mean=False)
    scaled_rows = 0
    for values, _, _ in read_batches(source, "train", guard):
        scaler.partial_fit(encode_matrix(preprocessor, values))
        scaled_rows += len(values)
        if scaled_rows % (4096 * 256) == 0:
            LOGGER.info("Escalado train: %d filas", scaled_rows)
    if scaled_rows != expected_rows or int(scaler.n_samples_seen_) != expected_rows:
        raise ValueError("Escalado no cubre todo train")
    guard.check()
    return (
        preprocessor,
        scaler,
        {
            "vocabulary_observation_rows": seen,
            "vocabulary_fit_representatives": len(representatives),
            "scaler_fit_rows": scaled_rows,
            "feature_dimension": len(scaler.mean_),
            "origin_categories": preprocessor.named_steps["encoding"]
            .named_transformers_["origin"]
            .categories_[0]
            .tolist(),
            "fit_scope": "train_only",
        },
        list(representatives.values()),
    )


def source_digest():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def train_candidates(
    split_directory: Path,
    *,
    audit_path: Path | None = None,
    candidate_config_path: Path = Path("configs/candidates.yaml"),
    config_path: Path = Path("configs/model.yaml"),
    data_config_path: Path = Path("configs/data.yaml"),
    output_dir: Path = Path("models/candidates"),
    report_dir: Path = Path("reports/training"),
    test_only: bool = False,
) -> dict:
    if type(test_only) is not bool:
        raise ValueError("Modo test_only invalido")
    source, output, reports = [Path(p).resolve() for p in (split_directory, output_dir, report_dir)]
    roots = (source, output, reports)
    if any(
        a.is_relative_to(b) or b.is_relative_to(a)
        for i, a in enumerate(roots)
        for b in roots[i + 1 :]
    ):
        raise ValueError("Entradas, modelos y reportes deben estar separados")
    run_id = uuid.uuid4().hex
    scopes = ("_test_only",) if test_only else ()
    report_root = _under(reports, *scopes)
    report_root.mkdir(parents=True, exist_ok=True)
    report = {
        "manifest_version": 1,
        "training_id": run_id,
        "status": "FAIL",
        "mode": "TEST_ONLY" if test_only else "REAL",
        "publication_complete": False,
        "approved_for_serving": False,
        "model_registered": False,
        "validation_accessed": False,
        "test_accessed": False,
        "monitoring_replay_accessed": False,
        "started_at_utc": utc_now(),
        "output_directory": None,
        "models": {},
    }
    try:
        candidates = read_candidates(Path(candidate_config_path))
        code_sha256 = source_digest()
        config, data = read_model_config(Path(config_path)), load_config(Path(data_config_path))
        guard = CandidateGuard(candidates["resources"], source, test_only=test_only)
        guard.check(start=True)
        verified = verify_scope(
            source,
            config=config,
            data_config=data,
            test_only=test_only,
            partitions=("train",),
            audit_path=audit_path,
        )
        expected_rows = verified["manifest"]["partitions"]["train"]["rows"]
        parent = _under(output, *scopes)
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".train-", dir=parent) as owned:
            staged = Path(owned)
            with threadpool_limits(limits=4):
                preprocessor, scaler, learned, representatives = fit_preprocessing(
                    source, guard, expected_rows
                )
                joblib.dump(
                    {"features": preprocessor, "scaling": scaler}, staged / "preprocessor.joblib"
                )
                preprocessor_sha = _sha256(staged / "preprocessor.joblib")
                guard.check()
                shared_seconds = guard.elapsed
                for name in ("sgd", "mlp"):
                    budget = CandidateGuard(
                        candidates["resources"],
                        source,
                        test_only=test_only,
                        charged_seconds=shared_seconds,
                    )
                    budget.check(start=True)
                    model = estimator(name)
                    pipeline = Pipeline(
                        [
                            ("features", copy.deepcopy(preprocessor)),
                            ("scaling", copy.deepcopy(scaler)),
                            ("estimator", model),
                        ]
                    )
                    count, blocks = 0, 0
                    target_hash = hashlib.sha256()
                    for values, y, _ in read_batches(source, "train", budget):
                        encoded = encode_matrix(pipeline.named_steps["features"], values)
                        scaled = pipeline.named_steps["scaling"].transform(encoded)
                        model.partial_fit(scaled, y)
                        target_hash.update(y.astype("<f8", copy=False).tobytes())
                        count += len(y)
                        blocks += 1
                        if blocks % 256 == 0:
                            LOGGER.info("Candidato %s: %d filas, %d bloques", name, count, blocks)
                        budget.check()
                    if count != expected_rows or model.rows_fitted_ != expected_rows:
                        raise ValueError("Entrenamiento no cubre todas las filas")
                    if not test_only:
                        audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
                        if target_hash.hexdigest() != audit["target_sha256"]["train"]:
                            raise ValueError("Etiquetas train distintas del T14 auditado")
                    pipeline.predict(representatives)  # Prueba del adaptador de inferencia real.
                    model_file = staged / f"{name}.joblib"
                    joblib.dump(pipeline, model_file)
                    reloaded = joblib.load(model_file)
                    if not np.array_equal(
                        pipeline.predict(representatives), reloaded.predict(representatives)
                    ):
                        raise ValueError("Predicciones distintas despues de serializar")
                    budget.check()
                    report["models"][name] = {
                        "file_name": model_file.name,
                        "sha256": _sha256(model_file),
                        "train_rows": count,
                        "blocks": blocks,
                        "epochs": 1,
                        "target_sha256": target_hash.hexdigest(),
                        "elapsed_seconds_including_shared_preprocessing": budget.elapsed,
                        "resources": {"initial": budget.initial, "final": budget.last},
                        "prediction_bounds_minutes": [1 / 60, 180.0],
                    }
                after = verify_scope(
                    source,
                    config=config,
                    data_config=data,
                    test_only=test_only,
                    partitions=("train",),
                    audit_path=audit_path,
                )
                if after != verified:
                    raise ValueError("Entradas cambiaron durante el entrenamiento")
                if (
                    read_candidates(Path(candidate_config_path)) != candidates
                    or read_model_config(Path(config_path)) != config
                    or load_config(Path(data_config_path)) != data
                    or source_digest() != code_sha256
                ):
                    raise ValueError("Codigo o configuracion cambio durante el entrenamiento")
                budget.check()
                report.update(
                    status="TRAINING_TEST_ONLY" if test_only else "TRAINING_REAL",
                    candidate_configuration=candidates,
                    candidate_config_sha256=fingerprint(candidates),
                    source_split_id=verified["manifest"]["split_id"],
                    source_split_sha256=verified["marker_sha256"],
                    source_audit_sha256=verified.get("audit_sha256"),
                    model_config_sha256=fingerprint(config),
                    data_config_sha256=fingerprint(data),
                    preprocessing=learned,
                    preprocessing_elapsed_seconds=shared_seconds,
                    preprocessing_sha256=preprocessor_sha,
                    source_tree_sha256=code_sha256,
                    dependency_versions={
                        name: version(name)
                        for name in ("scikit-learn", "numpy", "scipy", "joblib", "pyarrow")
                    },
                    threadpools=threadpool_info(),
                    resources_policy=candidates["resources"],
                    human_review_complete=False,
                    finished_at_utc=utc_now(),
                )
            destination = _under(parent, run_id)
            destination.mkdir(exist_ok=False)
            report["output_directory"] = str(destination)
            for name in ("preprocessor.joblib", "sgd.joblib", "mlp.joblib"):
                publish_file(staged / name, _under(destination, name))
            report["publication_complete"] = True
            publish_manifest(destination / "training_manifest.json", report)
    except (ValueError, RuntimeError, OSError, TypeError, KeyError) as error:
        report.update(
            status="FAIL", error=str(error), publication_complete=False, finished_at_utc=utc_now()
        )
    publish_manifest(report_root / f"{run_id}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--candidates", type=Path, default=Path("configs/candidates.yaml"))
    parser.add_argument("--config", type=Path, default=Path("configs/model.yaml"))
    parser.add_argument("--data-config", type=Path, default=Path("configs/data.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/candidates"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/training"))
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        result = train_candidates(
            args.split,
            audit_path=args.audit,
            candidate_config_path=args.candidates,
            config_path=args.config,
            data_config_path=args.data_config,
            output_dir=args.output_dir,
            report_dir=args.report_dir,
            test_only=args.test_only,
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Entrenamiento fallido: {error}\n")
    print(json.dumps(result))
    if result["status"] == "FAIL":
        parser.exit(1)


if __name__ == "__main__":
    main()
