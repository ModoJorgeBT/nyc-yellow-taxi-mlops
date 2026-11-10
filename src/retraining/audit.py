"""Auditoria exhaustiva de valores y cobertura contra fuentes originales aceptadas."""

import argparse
import uuid
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.ingestion.manifest import utc_now
from src.monitoring.performance import PredictionRows
from src.retraining.cohorts import TABLES, ColumnCursor, interval, verify_cohort
from src.retraining.protocol import budget, exclusive_json, inside, load_profile, pinned, read_json
from src.training.candidate_runtime import CandidateGuard
from src.training.split import verify_features
from src.validation.run import _sha256
from src.validation.schema import fingerprint, load_config


def audit_cohort(
    directory, stage, *, profile_path=Path("configs/retraining.yaml"), root=None, test_only=False
):
    root = Path(root or Path.cwd()).resolve()
    directory = Path(directory).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("Cohorte fuera del proyecto")
    profile = load_profile(profile_path, test_only=test_only)
    guard = CandidateGuard(budget("preparation"), root, test_only=test_only)
    guard.check(start=True)
    manifest = verify_cohort(directory, stage, profile, test_only=test_only)
    marker_sha = _sha256(directory / "cohort.json")
    config = read_json(pinned(root, profile["original_split"]))["configuration"]
    data = load_config(pinned(root, profile["data_config"]))
    start, end = (int(t.timestamp() * 1e6) for t in interval(profile, stage))
    seen = matched = excluded = 0
    with ExitStack() as stack:
        outputs = {
            n: PredictionRows(
                stack.enter_context(pq.ParquetFile(directory / stage / f"{n}.parquet"))
            )
            for n in TABLES
        }
        for entry in manifest["sources"]:
            folder = inside(root, entry["features_directory"])
            valid = inside(root, entry["validated_directory"])
            verified = verify_features(
                folder, valid, test_only=test_only, config=config, data_config=data
            )
            if (
                verified["marker_sha256"] != entry["feature_marker_sha256"]
                or _sha256(valid / "validation.json") != entry["validation_marker_sha256"]
                or verified["raw_sha256"] != entry["raw_sha256"]
            ):
                raise ValueError("Fuente original o su aprobacion cambiaron")
            month_seen = 0
            with ExitStack() as source_stack:
                readers = [
                    source_stack.enter_context(pq.ParquetFile(folder / f"{n}.parquet"))
                    for n in ("features", "target", "context")
                ]
                raw = source_stack.enter_context(pq.ParquetFile(valid / "data.parquet"))
                destinations = ColumnCursor(raw, "DOLocationID")
                for X, y, context in zip(
                    *(p.iter_batches(batch_size=65536, use_threads=False) for p in readers),
                    strict=True,
                ):
                    guard.check()
                    count = len(context)
                    if (
                        len(X) != count
                        or len(y) != count
                        or not np.array_equal(
                            context.column(0).to_numpy(), np.arange(month_seen, month_seen + count)
                        )
                    ):
                        raise ValueError("Identidades de fuente incompletas")
                    pickup = pc.cast(context.column(1), pa.int64()).to_numpy()
                    dropoff = pc.cast(context.column(2), pa.int64()).to_numpy()
                    if not np.allclose(
                        y.column(0).to_numpy(), (dropoff - pickup) / 60_000_000, rtol=0, atol=1e-9
                    ):
                        raise ValueError("Etiqueta no corresponde a eventos UTC")
                    chosen = np.flatnonzero((pickup >= start) & (pickup < end) & (dropoff < end))
                    destination = destinations.take(count)
                    selected = pa.array(chosen)
                    month_seen += count
                    seen += count
                    excluded += count - len(chosen)
                    if not len(chosen):
                        continue
                    expected = {
                        "features": pa.Table.from_batches([X]).take(selected),
                        "target": pa.Table.from_batches([y]).take(selected),
                        "context": pa.Table.from_batches([context])
                        .take(selected)
                        .append_column(
                            "source_feature_id", pa.array([entry["feature_id"]] * len(chosen))
                        ),
                        "segments": pa.table(
                            {
                                "destination_location_id": pc.cast(
                                    destination.take(selected), pa.int64()
                                )
                            }
                        ),
                    }
                    for name, table in expected.items():
                        if not outputs[name].take(len(chosen)).equals(table, check_metadata=False):
                            raise ValueError(f"Valores/identidades de {name} difieren de la fuente")
                    matched += len(chosen)
                if month_seen != entry["rows"] or not destinations.exhausted():
                    raise ValueError("Fuente no recorrida completamente")
        if any(c.has_remaining() for c in outputs.values()):
            raise ValueError("Particion contiene filas adicionales")
    if (
        matched != manifest["rows"]
        or seen != manifest["source_rows"]
        or excluded != manifest["label_cutoff_exclusions"]
        or _sha256(directory / "cohort.json") != marker_sha
    ):
        raise ValueError("Auditoria no coincide con cobertura/cortes declarados")
    guard.check()
    result = {
        "status": "COHORT_AUDIT_TEST_ONLY" if test_only else "COHORT_AUDIT_REAL",
        "profile_sha256": fingerprint(profile),
        "stage": stage,
        "all_values_verified": True,
        "cohort": {
            "path": str((directory / "cohort.json").relative_to(root)),
            "sha256": marker_sha,
        },
        "source_rows": seen,
        "matched_rows": matched,
        "label_cutoff_exclusions": excluded,
        "timestamp_utc": utc_now(),
        "resources": {
            "initial": guard.initial,
            "final": guard.last,
            "elapsed_seconds": guard.elapsed,
        },
    }
    output = inside(root, "reports/retraining/audits")
    if test_only:
        output /= "_test_only"
    path = output / f"{uuid.uuid4().hex}.json"
    exclusive_json(path, result)
    return path, result


def require_audit(entry, directory, stage, profile, root):
    if entry is None:
        raise ValueError("Ejecucion real requiere auditoria completa de la cohorte")
    audit = read_json(pinned(root, entry))
    if (
        audit.get("status") != "COHORT_AUDIT_REAL"
        or audit.get("stage") != stage
        or audit.get("all_values_verified") is not True
        or audit.get("profile_sha256") != fingerprint(profile)
        or audit["cohort"]["sha256"] != _sha256(Path(directory) / "cohort.json")
        or pinned(root, audit["cohort"]) != Path(directory).resolve() / "cohort.json"
    ):
        raise ValueError("Auditoria no corresponde a la cohorte aprobada")
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--stage", choices=["train", "validation", "final"], required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    args = parser.parse_args()
    output, result = audit_cohort(args.cohort, args.stage, profile_path=args.config)
    print({"report": str(output), "rows": result["matched_rows"], "status": result["status"]})


if __name__ == "__main__":
    main()
