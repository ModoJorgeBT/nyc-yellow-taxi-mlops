"""Preparación exclusiva del holdout aprobado; sin fit ni acceso al test anterior."""

import argparse
import hashlib
import json
import logging
import tempfile
import uuid
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from src.features.target import nyc_zone
from src.ingestion.manifest import (
    describe_parquet,
    publish_file,
    publish_manifest,
    read_and_verify,
    utc_now,
)
from src.training.resources import ResourceGuard
from src.training.split import SCHEMAS, TABLES, _catalog, read_model_config, verify_features
from src.training.train import source_digest
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint, load_config

APPROVED_PROFILE_SHA256 = "740eabe6aebbad1608dde981e022c57051c7617691039c64a599ab61ae59268a"
HOUR_US = 3_600_000_000
LOGGER = logging.getLogger(__name__)
FINAL_SCHEMAS = {
    **SCHEMAS,
    "context": SCHEMAS["context"].append(pa.field("source_feature_id", pa.string())),
}


def read_final_profile(path, *, test_only=False):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not test_only:
        if fingerprint(value) != APPROVED_PROFILE_SHA256:
            raise ValueError("Evaluación final distinta del protocolo aprobado")
    elif value.get("approval_status") != "TEST_ONLY" or value.get("fixture_origin") != "synthetic":
        raise ValueError("El protocolo de pruebas exige marca sintética")
    if (
        value["period"]["year"] != 2026
        or value["period"]["months"] != [1, 2, 3]
        or value["period"]["pickup_start"] != "2026-01-01T00:00:00-05:00"
        or value["period"]["pickup_end"] != "2026-04-01T00:00:00-04:00"
        or value["period"]["label_cutoff_utc"] != "2026-04-01T04:00:00+00:00"
        or value.get("evaluation_only") is not True
        or value.get("fit_forbidden") is not True
        or set(value["models"]) != {"baseline", "sgd", "lightgbm"}
    ):
        raise ValueError("Periodo, modelos o corte final no permitido")
    return value


def _micros(timestamp):
    instant = datetime.fromisoformat(timestamp).astimezone(UTC)
    return int((instant - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() * 1_000_000)


def calendar_at_pickup(pickup_us):
    hours, inverse = np.unique(pickup_us // HOUR_US, return_inverse=True)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    offsets = np.asarray(
        [
            int(
                (epoch + timedelta(hours=int(h), minutes=30))
                .astimezone(nyc_zone())
                .utcoffset()
                .total_seconds()
            )
            * 1_000_000
            for h in hours
        ],
        dtype=np.int64,
    )
    wall = pickup_us + offsets[inverse]
    month_index = wall.view("datetime64[us]").astype("datetime64[M]").astype(np.int64)
    return {
        "year": month_index // 12 + 1970,
        "month": month_index % 12 + 1,
        "hour": wall // HOUR_US % 24,
        "weekday": (wall // (24 * HOUR_US) + 3) % 7,
    }


def checked_block(group, *, entry, previous, seen, real):
    if len({b.num_rows for b in group}) != 1:
        raise ValueError("Features, etiquetas y contexto desalineados")
    xb, yb, cb = group
    X = np.column_stack([c.to_numpy() for c in xb.columns])
    y = yb.column(0).to_numpy()
    indices = cb.column(0).to_numpy()
    pickup, label = (cb.column(i).cast(pa.int64()).to_numpy() for i in (1, 2))
    if (
        not len(y)
        or indices[0] <= previous
        or np.any(np.diff(indices) <= 0)
        or (real and not np.array_equal(indices, np.arange(seen, seen + len(y))))
        or not np.all(np.isfinite(y) & (y > 0) & (y <= 180))
        or not np.allclose(
            y, (label - pickup).astype(np.float64) / 1_000_000 / 60, rtol=0, atol=1e-9
        )
    ):
        raise ValueError("Identidades o etiquetas finales incoherentes")
    calendar = calendar_at_pickup(pickup)
    if (
        np.any(calendar["year"] != entry["year"])
        or np.any(calendar["month"] != entry["month"])
        or np.any(X[:, 1] != calendar["hour"])
        or np.any(X[:, 2] != calendar["weekday"])
        or np.any(X[:, 3] != calendar["month"])
        or np.any(X[:, 0] <= 0)
        or np.any(X[:, 4] < 0)
        or np.any(~np.isin(X[:, 5], (0, 1)))
        or np.any((X[:, 5] == 1) & (X[:, 4] != 0))
    ):
        raise ValueError("Calendario/mes/features finales divergentes")
    return X, y, pickup, label, int(indices[-1])


def verify_sources(entries, *, config, data, test_only):
    for entry in entries:
        current = verify_features(
            Path(entry["features_directory"]),
            Path(entry["validated_directory"]),
            config=config,
            data_config=data,
            test_only=test_only,
        )
        if current != entry["verified"]:
            raise ValueError("Linaje de fuente final divergente")
        if not test_only:
            raw = Path("data/raw") / str(entry["year"]) / f"{entry['month']:02}"
            manifest = read_and_verify(
                raw / "manifest.json",
                raw / f"yellow_tripdata_{entry['year']}-{entry['month']:02}.parquet",
                entry["year"],
                entry["month"],
            )
            if manifest["sha256"] != current["raw_sha256"]:
                raise ValueError("Raw final distinto de su validación congelada")


def verify_final(directory, *, profile, config, data, test_only):
    directory = Path(directory).resolve()
    marker = directory / "holdout_manifest.json"
    marker_sha = _sha256(marker)
    value = json.loads(marker.read_text(encoding="utf-8"))
    if (
        value.get("status") != ("FINAL_HOLDOUT_TEST_ONLY" if test_only else "FINAL_HOLDOUT_REAL")
        or value.get("publication_complete") is not True
        or value.get("approved_for_training") is not False
        or value.get("models_fitted") is not False
        or value.get("holdout_id") != directory.name
        or value.get("configuration") != profile
        or value.get("profile_sha256") != fingerprint(profile)
        or {(e["year"], e["month"]) for e in value["inputs"]} != {(2026, m) for m in (1, 2, 3)}
        or len(value["inputs"]) != 3
    ):
        raise ValueError("Holdout final incompleto o de otro protocolo")
    verify_sources(value["inputs"], config=config, data=data, test_only=test_only)
    for name in TABLES:
        actual = describe_parquet(directory / f"{name}.parquet")
        if actual != value["artifacts"][name] or actual["row_count"] != value["rows"]:
            raise ValueError("Artefacto final alterado")
        with pq.ParquetFile(directory / f"{name}.parquet") as reader:
            schema = reader.schema_arrow
        if not schema.equals(FINAL_SCHEMAS[name], check_metadata=False) or (
            schema.metadata or {}
        ).get(b"heldout_scope") != (b"TEST_ONLY" if test_only else b"INDEPENDENT_FINAL"):
            raise ValueError("Esquema o ámbito final incompatible")
    if _sha256(marker) != marker_sha:
        raise ValueError("Marcador final cambió durante verificación")
    return value, marker_sha


def prepare_final(
    catalog_path,
    *,
    profile_path=Path("configs/lightgbm-final-evaluation.yaml"),
    config_path=Path("configs/model.yaml"),
    data_config_path=Path("configs/data.yaml"),
    output_dir=Path("data/processed/final-holdouts"),
    report_dir=Path("reports/final-preparation"),
    test_only=False,
    batch_size=65536,
):
    if type(test_only) is not bool or type(batch_size) is not int or not 1 <= batch_size <= 65536:
        raise ValueError("Modo o tamaño de bloque inválido")
    profile = read_final_profile(profile_path, test_only=test_only)
    config, data = read_model_config(config_path), load_config(data_config_path)
    if not test_only and fingerprint(data) != profile["quality_config_sha256"]:
        raise ValueError("D-04 cambió respecto al protocolo final")
    entries = _catalog(
        Path(catalog_path).resolve(),
        config,
        test_only=test_only,
        required={(2026, month) for month in (1, 2, 3)},
    )
    if {(e["year"], e["month"]) for e in entries} != {(2026, m) for m in (1, 2, 3)}:
        raise ValueError("Holdout exige los tres meses, sin selección parcial")
    output, reports = Path(output_dir).resolve(), Path(report_dir).resolve()
    roots = [output, reports]
    roots.extend(
        entry[key] for entry in entries for key in ("features_directory", "validated_directory")
    )
    for i, root in enumerate(roots[:2]):
        if any(
            root.is_relative_to(other) or other.is_relative_to(root) for other in roots[i + 1 :]
        ):
            raise ValueError("Entradas y salidas finales deben estar separadas")
    scopes = ("_test_only",) if test_only else ()
    parent, report_root = _under(output, *scopes), _under(reports, *scopes)
    parent.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    identifier, code_hash = uuid.uuid4().hex, source_digest()
    report = {
        "holdout_id": identifier,
        "status": "FAIL",
        "publication_complete": False,
        "mode": "TEST_ONLY" if test_only else "REAL",
        "approved_for_training": False,
        "started_at_utc": utc_now(),
        "models_fitted": False,
    }
    try:
        guard = ResourceGuard(profile["preparation_resources"], output, test_only=test_only)
        guard.check(start=True)
        for entry in entries:
            entry["verified"] = verify_features(
                entry["features_directory"],
                entry["validated_directory"],
                config=config,
                data_config=data,
                test_only=test_only,
            )
        verify_sources(entries, config=config, data=data, test_only=test_only)
        expected = sum(e["verified"]["feature"]["rows_emitted"] for e in entries)
        if test_only and expected > 65536:
            raise ValueError("Fixture de holdout demasiado grande")
        start, end, cutoff = (
            _micros(profile["period"][key])
            for key in ("pickup_start", "pickup_end", "label_cutoff_utc")
        )
        monthly, target_hash = [], hashlib.sha256()
        with tempfile.TemporaryDirectory(prefix=".final-holdout-", dir=parent) as owned:
            staged = Path(owned)
            metadata = {
                b"heldout_scope": b"TEST_ONLY" if test_only else b"INDEPENDENT_FINAL",
                b"approved_for_training": b"false",
            }
            with ExitStack() as stack:
                writers = {
                    name: stack.enter_context(
                        pq.ParquetWriter(
                            staged / f"{name}.parquet", FINAL_SCHEMAS[name].with_metadata(metadata)
                        )
                    )
                    for name in TABLES
                }
                for entry in entries:
                    seen = kept = crossed = 0
                    previous = -1
                    with ExitStack() as readers:
                        files = [
                            readers.enter_context(
                                pq.ParquetFile(entry["features_directory"] / f"{n}.parquet")
                            )
                            for n in TABLES
                        ]
                        for group in zip(
                            *(
                                p.iter_batches(batch_size=batch_size, use_threads=False)
                                for p in files
                            ),
                            strict=True,
                        ):
                            guard.check()
                            X, y, pickup, label, previous = checked_block(
                                group, entry=entry, previous=previous, seen=seen, real=not test_only
                            )
                            if np.any((pickup < start) | (pickup >= end)):
                                raise ValueError("Recogida fuera del periodo final aprobado")
                            eligible = label < cutoff
                            seen += len(y)
                            crossed += int(np.count_nonzero(~eligible))
                            kept += int(np.count_nonzero(eligible))
                            tables = {
                                name: pa.Table.from_batches([batch]).filter(pa.array(eligible))
                                for name, batch in zip(TABLES, group, strict=True)
                            }
                            tables["context"] = tables["context"].append_column(
                                "source_feature_id",
                                pa.array(
                                    [entry["verified"]["feature"]["feature_id"]]
                                    * int(eligible.sum())
                                ),
                            )
                            for name, table in tables.items():
                                writers[name].write_table(table.cast(FINAL_SCHEMAS[name]))
                            target_hash.update(y[eligible].astype("<f8", copy=False).tobytes())
                    if seen != entry["verified"]["feature"]["rows_emitted"]:
                        raise ValueError("Fuente final no exhaustiva")
                    monthly.append(
                        {
                            "year": entry["year"],
                            "month": entry["month"],
                            "feature_rows": seen,
                            "cutoff_excluded": crossed,
                            "rows": kept,
                        }
                    )
                    LOGGER.info(
                        "Holdout final %d-%02d: %d filas, %d cruzan corte",
                        entry["year"],
                        entry["month"],
                        kept,
                        crossed,
                    )
            rows = sum(m["rows"] for m in monthly)
            if rows < 1 or sum(m["feature_rows"] for m in monthly) != expected:
                raise ValueError("Holdout vacío o incompleto")
            artifacts = {n: describe_parquet(staged / f"{n}.parquet") for n in TABLES}
            if any(a["row_count"] != rows for a in artifacts.values()):
                raise ValueError("Salidas finales desalineadas")
            for entry in entries:
                after = verify_features(
                    entry["features_directory"],
                    entry["validated_directory"],
                    config=config,
                    data_config=data,
                    test_only=test_only,
                )
                if after != entry["verified"]:
                    raise ValueError("Fuente final cambió durante preparación")
            if (
                read_final_profile(profile_path, test_only=test_only) != profile
                or source_digest() != code_hash
            ):
                raise ValueError("Protocolo o código cambió durante preparación")
            guard.check()
            destination = _under(parent, identifier)
            destination.mkdir(exist_ok=False)
            report.update(
                status="FINAL_HOLDOUT_TEST_ONLY" if test_only else "FINAL_HOLDOUT_REAL",
                publication_complete=True,
                output_directory=str(destination),
                rows=rows,
                monthly=monthly,
                target_sha256=target_hash.hexdigest(),
                artifacts=artifacts,
                inputs=[
                    {
                        **e,
                        "features_directory": str(e["features_directory"]),
                        "validated_directory": str(e["validated_directory"]),
                    }
                    for e in entries
                ],
                configuration=profile,
                profile_sha256=fingerprint(profile),
                source_tree_sha256=code_hash,
                resources={"initial": guard.initial, "final": guard.last},
                finished_at_utc=utc_now(),
            )
            for name in TABLES:
                publish_file(staged / f"{name}.parquet", destination / f"{name}.parquet")
            publish_manifest(destination / "holdout_manifest.json", report)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as error:
        report.update(status="FAIL", publication_complete=False, error=str(error))
    publish_manifest(report_root / f"{identifier}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument(
        "--profile", type=Path, default=Path("configs/lightgbm-final-evaluation.yaml")
    )
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    result = prepare_final(args.catalog, profile_path=args.profile, test_only=args.test_only)
    print(json.dumps(result))
    if not result["publication_complete"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
