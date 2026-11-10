"""Particiones nuevas por bloques, con cortes propios y fuentes aceptadas verificadas."""

import hashlib
import uuid
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.ingestion.manifest import describe_parquet, utc_now
from src.retraining.protocol import budget, exclusive_json, inside, load_profile, pinned, read_json
from src.training.candidate_runtime import CandidateGuard
from src.training.models import feature_matrix
from src.training.split import SCHEMAS, verify_features
from src.validation.run import _sha256
from src.validation.schema import fingerprint, load_config

TABLES = ("features", "target", "context", "segments")
CONTEXT = SCHEMAS["context"].append(pa.field("source_feature_id", pa.string()))
SEGMENTS = pa.schema([("destination_location_id", pa.int64())])


def interval(profile, stage):
    if stage not in ("train", "validation", "final"):
        raise ValueError("Particion fuera del protocolo T33-T34")
    return tuple(datetime.fromisoformat(x).astimezone(UTC) for x in profile["periods"][stage])


def expected_months(profile, stage):
    start, end = (datetime.fromisoformat(x) for x in profile["periods"][stage])
    result = set()
    year, month = start.year, start.month
    while (year, month) < (end.year, end.month):
        result.add((year, month))
        year, month = year + (month == 12), month % 12 + 1
    return result


class ColumnCursor:
    def __init__(self, parquet, column):
        self.stream = iter(
            parquet.iter_batches(batch_size=65536, columns=[column], use_threads=False)
        )
        self.buffer = None

    def take(self, count):
        chunks = []
        while count:
            if self.buffer is None or not len(self.buffer):
                self.buffer = next(self.stream).column(0)
            size = min(count, len(self.buffer))
            chunks.append(self.buffer.slice(0, size))
            self.buffer = self.buffer.slice(size)
            count -= size
        return pa.concat_arrays(chunks)

    def exhausted(self):
        return (
            not (self.buffer is not None and len(self.buffer)) and next(self.stream, None) is None
        )


def checked_arrays(features, target, context, *, year, month, seen):
    values = feature_matrix(features)
    labels = target.column(0).to_numpy()
    indices = context.column(0).to_numpy()
    pickup = context.column(1)
    end = context.column(2)
    micros = pc.cast(pickup, pa.int64()).to_numpy()
    label_micros = pc.cast(end, pa.int64()).to_numpy()
    local = pc.cast(pickup, pa.timestamp("us", tz="America/New_York"))
    if (
        len(labels) != len(values)
        or len(indices) != len(values)
        or not np.array_equal(indices, np.arange(seen, seen + len(indices)))
        or np.any(~np.isfinite(labels) | (labels <= 0) | (labels > 180))
        or np.any(np.abs(labels - (label_micros - micros) / 60_000_000) > 1e-9)
        or not np.all(pc.year(local).to_numpy() == year)
        or not np.all(pc.month(local).to_numpy() == month)
        or not np.array_equal(pc.hour(local).to_numpy(), values[:, 1])
        or not np.array_equal(pc.day_of_week(local).to_numpy(), values[:, 2])
        or not np.array_equal(pc.month(local).to_numpy(), values[:, 3])
        or np.any(values[:, 0] <= 0)
        or np.any(values[:, 4] < 0)
        or np.any(values[:, 4] > 6)
        or np.any((values[:, 5] != 0) & (values[:, 5] != 1))
        or np.any((values[:, 5] == 1) & (values[:, 4] != 0))
    ):
        raise ValueError("Identidades, features, etiquetas o contexto temporal divergentes")
    return values, labels, micros, label_micros


def source_entries(catalog, profile, root, stage, *, test_only):
    entries = read_json(catalog)["batches"]
    wanted = expected_months(profile, stage)
    if len(entries) != len(wanted) or {(e["year"], e["month"]) for e in entries} != wanted:
        raise ValueError("Catalogo no cubre exactamente los meses de la particion")
    data = load_config(pinned(root, profile["data_config"]))
    old = read_json(pinned(root, profile["original_split"]))["configuration"]
    verified = []
    for entry in sorted(entries, key=lambda e: (e["year"], e["month"])):
        feature_dir = inside(root, entry["features_directory"])
        valid_dir = inside(root, entry["validated_directory"])
        result = verify_features(
            feature_dir, valid_dir, test_only=test_only, config=old, data_config=data
        )
        if (result["feature"]["year"], result["feature"]["month"]) != (
            entry["year"],
            entry["month"],
        ):
            raise ValueError("Mes de catalogo distinto de fuente verificada")
        verified.append(
            {
                "year": entry["year"],
                "month": entry["month"],
                "features_directory": str(feature_dir.relative_to(root)),
                "validated_directory": str(valid_dir.relative_to(root)),
                "feature_id": result["feature"]["feature_id"],
                "rows": result["feature"]["rows_emitted"],
                "feature_marker_sha256": result["marker_sha256"],
                "validation_marker_sha256": _sha256(valid_dir / "validation.json"),
                "raw_sha256": result["raw_sha256"],
                "quality_exception": result["feature"].get("source_quality_exception"),
            }
        )
    return verified


def prepare(
    catalog, stage, *, profile_path=Path("configs/retraining.yaml"), root=None, test_only=False
):
    root = Path(root or Path.cwd()).resolve()
    profile = load_profile(profile_path, test_only=test_only)
    guard = CandidateGuard(budget("preparation"), root, test_only=test_only)
    guard.check(start=True)
    entries = source_entries(catalog, profile, root, stage, test_only=test_only)
    destination = inside(root, "data/processed/retraining/cohorts")
    if test_only:
        destination /= "_test_only"
    destination /= uuid.uuid4().hex
    directory = destination / stage
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {
        b"retraining_scope": b"TEST_ONLY" if test_only else b"REAL",
        b"profile_sha256": fingerprint(profile).encode(),
        b"partition": stage.encode(),
    }
    schemas = {**SCHEMAS, "context": CONTEXT, "segments": SEGMENTS}
    start, end = interval(profile, stage)
    start_us, end_us = int(start.timestamp() * 1e6), int(end.timestamp() * 1e6)
    rows = seen_total = excluded = 0
    hashes = {key: hashlib.sha256() for key in ("features", "target", "identities")}
    try:
        with ExitStack() as writers_stack:
            writers = {
                name: writers_stack.enter_context(
                    pq.ParquetWriter(
                        directory / f"{name}.parquet",
                        schemas[name].with_metadata(metadata),
                        compression="zstd",
                    )
                )
                for name in TABLES
            }
            for entry in entries:
                seen = 0
                feature_dir = inside(root, entry["features_directory"])
                with ExitStack() as readers_stack:
                    readers = [
                        readers_stack.enter_context(pq.ParquetFile(feature_dir / f"{n}.parquet"))
                        for n in ("features", "target", "context")
                    ]
                    valid = readers_stack.enter_context(
                        pq.ParquetFile(inside(root, entry["validated_directory"]) / "data.parquet")
                    )
                    destinations = ColumnCursor(valid, "DOLocationID")
                    for X, y, context in zip(
                        *(p.iter_batches(batch_size=65536, use_threads=False) for p in readers),
                        strict=True,
                    ):
                        guard.check()
                        values, labels, pickup, label = checked_arrays(
                            X, y, context, year=entry["year"], month=entry["month"], seen=seen
                        )
                        destination_array = destinations.take(len(values))
                        if destination_array.null_count or np.any(
                            destination_array.to_numpy() <= 0
                        ):
                            raise ValueError("Destino para segmentos ausente o no aprobado")
                        mask = (pickup >= start_us) & (pickup < end_us) & (label < end_us)
                        select = pa.array(np.flatnonzero(mask))
                        ids = np.asarray(context.column(0).to_numpy()[mask], dtype="<i8")
                        hashes["features"].update(values[mask].astype("<i8").tobytes())
                        hashes["target"].update(labels[mask].astype("<f8").tobytes())
                        identity = np.empty((len(ids), 3), dtype="<i8")
                        feature_words = np.frombuffer(
                            bytes.fromhex(entry["feature_id"]), dtype="<i8"
                        )
                        identity[:, :2], identity[:, 2] = feature_words, ids
                        hashes["identities"].update(identity.tobytes())
                        selected_context = (
                            pa.Table.from_batches([context])
                            .take(select)
                            .append_column(
                                "source_feature_id", pa.array([entry["feature_id"]] * len(ids))
                            )
                        )
                        tables = {
                            "features": pa.Table.from_batches([X]).take(select),
                            "target": pa.Table.from_batches([y]).take(select),
                            "context": selected_context,
                            "segments": pa.table(
                                {"destination_location_id": destination_array.take(select)}
                            ),
                        }
                        for name, table in tables.items():
                            if len(table):
                                writers[name].write_table(
                                    table.cast(schemas[name].with_metadata(metadata))
                                )
                        rows += len(ids)
                        excluded += len(values) - len(ids)
                        seen += len(values)
                    if seen != entry["rows"] or not destinations.exhausted():
                        raise ValueError("Cobertura de fuente/contexto/segmentos incompleta")
                if (
                    _sha256(feature_dir / "features_manifest.json")
                    != entry["feature_marker_sha256"]
                ):
                    raise ValueError("Fuente cambio durante particionado")
                seen_total += seen
        if rows < 1 or rows + excluded != seen_total:
            raise ValueError("Particion vacia o no exhaustiva")
        after = source_entries(catalog, profile, root, stage, test_only=test_only)
        if after != entries or load_profile(profile_path, test_only=test_only) != profile:
            raise ValueError("Fuentes/configuracion cambiaron durante preparacion")
        guard.check()
        manifest = {
            "status": "RETRAINING_COHORT_TEST_ONLY" if test_only else "RETRAINING_COHORT_REAL",
            "publication_complete": True,
            "profile_sha256": fingerprint(profile),
            "stage": stage,
            "period": profile["periods"][stage],
            "rows": rows,
            "source_rows": seen_total,
            "label_cutoff_exclusions": excluded,
            "sources": entries,
            "value_sha256": {k: v.hexdigest() for k, v in hashes.items()},
            "artifacts": {n: describe_parquet(directory / f"{n}.parquet") for n in TABLES},
            "timestamp_utc": utc_now(),
            "resources": {"initial": guard.initial, "final": guard.last},
        }
        exclusive_json(destination / "cohort.json", manifest)
        return destination, manifest
    except BaseException as error:
        exclusive_json(
            destination / "failure.json",
            {"status": "FAIL", "error": str(error), "publication_complete": False},
        )
        raise


def verify_cohort(directory, stage, profile, *, test_only=False, names=TABLES):
    directory = Path(directory)
    manifest = read_json(directory / "cohort.json")
    if (
        manifest.get("status")
        != ("RETRAINING_COHORT_TEST_ONLY" if test_only else "RETRAINING_COHORT_REAL")
        or manifest.get("publication_complete") is not True
        or manifest.get("stage") != stage
        or manifest.get("profile_sha256") != fingerprint(profile)
        or manifest.get("period") != profile["periods"][stage]
        or manifest.get("rows", 0) < 1
    ):
        raise ValueError("Particion no publicada para este protocolo")
    if not names or any(n not in TABLES for n in names):
        raise ValueError("Artefactos fuera del contrato de cohorte")
    for name in names:
        path = directory / stage / f"{name}.parquet"
        if (
            describe_parquet(path) != manifest["artifacts"][name]
            or manifest["artifacts"][name]["row_count"] != manifest["rows"]
        ):
            raise ValueError("Integridad/conteo de particion divergente")
        with pq.ParquetFile(path) as parquet:
            metadata = parquet.schema_arrow.metadata or {}
            if (
                metadata.get(b"retraining_scope") != (b"TEST_ONLY" if test_only else b"REAL")
                or metadata.get(b"profile_sha256") != fingerprint(profile).encode()
            ):
                raise ValueError("Ambito de particion no autorizado")
    return manifest


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--stage", choices=["train", "validation", "final"], required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    output, report = prepare(
        args.catalog, args.stage, profile_path=args.config, test_only=args.test_only
    )
    print({"output": str(output), "rows": report["rows"], "status": report["status"]})


if __name__ == "__main__":
    main()
