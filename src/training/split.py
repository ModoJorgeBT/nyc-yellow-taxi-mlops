"""T14: particiones completas por evento, sin fit ni submuestreo."""

import argparse
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import uuid
from collections import Counter
from contextlib import ExitStack
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.features.artifacts import verify_validated
from src.features.schema import FEATURE_COLUMNS, FEATURE_VERSION
from src.features.target import TEMPORAL_POLICY, TIMEZONE, nyc_zone
from src.ingestion.manifest import (
    describe_parquet,
    publish_file,
    publish_manifest,
    utc_now,
)
from src.training.resources import ResourceGuard
from src.validation.real import authorize_source
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint
from src.validation.schema import load_config as load_data_config

PARTITIONS = ("train", "validation", "test", "monitoring_replay")
LOGGER = logging.getLogger(__name__)
TABLES = ("features", "target", "context")
CONTEXT = pa.schema(
    [
        ("validated_row_index", pa.int64()),
        ("pickup_datetime_utc", pa.timestamp("us", "UTC")),
        ("label_event_datetime_utc", pa.timestamp("us", "UTC")),
    ]
)
SCHEMAS = {
    "features": pa.schema([(name, pa.int64()) for name in FEATURE_COLUMNS]),
    "target": pa.schema([("trip_duration_minutes", pa.float64())]),
    "context": CONTEXT,
}


class SplitError(ValueError):
    pass


def quality_rules(policy: dict) -> dict:
    return {
        key: value
        for key, value in policy.items()
        if key not in ("approval", "local_authorizations")
    }


def read_model_config(path: Path) -> dict:
    config = _read_object(path)
    if (
        type(config.get("format_version")) is not int
        or config["format_version"] != 1
        or config.get("approval_status") != "APPROVED"
        or config.get("timezone") != TIMEZONE
        or config.get("temporal_policy") != TEMPORAL_POLICY
        or config.get("feature_version") != FEATURE_VERSION
        or config.get("data_scope") != "ALL_ELIGIBLE_NO_SUBSAMPLING"
        or config.get("label_before_partition_end") is not True
        or config.get("fit_scope") != "train_only"
        or config.get("selection_scope") != "validation_only"
        or config.get("test_usage") != "final_evaluation_only"
        or config.get("protocol_mode")
        != "RETROSPECTIVE_EVENT_TIME_REPLAY_NOT_HISTORICAL_PUBLICATION_SIMULATION"
        or set(config.get("partitions", {})) != set(PARTITIONS)
    ):
        raise SplitError("Contrato D-01/D-02 incompleto o no aprobado")
    end = None
    for part in PARTITIONS:
        start, finish = boundaries(config, part)
        if start >= finish or (end is not None and start != end):
            raise SplitError("Intervalos no contiguos o desordenados")
        end = finish
    expected = required_months(config)
    if len(expected) != 24:
        raise SplitError("Este protocolo requiere los 24 meses aprobados")
    resources = config.get("resources")
    approved = {
        "threads_total": 4,
        "parallel_models": 1,
        "process_rss_limit_gib": 8,
        "candidate_timeout_seconds": 7200,
        "preflight_min_free_ram_gib": 12,
        "preflight_min_free_disk_gib": 50,
        "quality_batch_rows_max": 65536,
        "monthly_quality_concurrency": 1,
    }
    if not isinstance(resources, dict) or any(
        type(resources.get(key)) is not int or resources[key] != value
        for key, value in approved.items()
    ):
        raise SplitError("Presupuesto diferente del aprobado D-02")
    if resources.get("candidates") != ["SGDRegressor", "MLPRegressor_small"]:
        raise SplitError("Candidatos diferentes de los aprobados D-02")
    preparation_budget(config)
    return config


def preparation_budget(config: dict) -> dict:
    policy = config.get("preparation_resources", config["resources"])
    if "preparation_resources" in config:
        if policy.get("approval_status") != "APPROVED" or any(
            type(policy.get(key)) is not int or policy[key] != limit
            for key, limit in {
                "preflight_min_free_ram_gib": 4,
                "process_rss_limit_gib": 2,
                "preflight_min_free_disk_gib": 50,
                "threads_total": 4,
            }.items()
        ):
            raise SplitError("Perfil de preparacion distinto del aprobado")
    return policy


def boundaries(config: dict, part: str) -> tuple[datetime, datetime]:
    times = [datetime.fromisoformat(config["partitions"][part][key]) for key in ("start", "end")]
    for instant in times:
        if (
            instant.tzinfo is None
            or instant.utcoffset() != instant.astimezone(nyc_zone()).utcoffset()
        ):
            raise SplitError("Frontera sin offset coherente con Nueva York")
        if instant.astimezone(nyc_zone()).day != 1 or instant.time().isoformat() != "00:00:00":
            raise SplitError("Frontera debe ser inicio de mes local")
    return tuple(instant.astimezone(UTC) for instant in times)


def required_months(config: dict) -> set[tuple[int, int]]:
    result = set()
    for part in PARTITIONS:
        start, end = (t.astimezone(nyc_zone()) for t in boundaries(config, part))
        year, month = start.year, start.month
        while (year, month) < (end.year, end.month):
            result.add((year, month))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def classify(pickup: datetime, label: datetime, config: dict) -> tuple[str | None, str | None]:
    return _classify(pickup, label, [(part, *boundaries(config, part)) for part in PARTITIONS])


def _classify(pickup: datetime, label: datetime, intervals) -> tuple[str | None, str | None]:
    if any(not isinstance(t, datetime) or t.utcoffset() is None for t in (pickup, label)):
        raise SplitError("Eventos deben tener offset")
    pickup, label = pickup.astimezone(UTC), label.astimezone(UTC)
    if label <= pickup:
        raise SplitError("Evento de etiqueta no posterior a recogida")
    for part, start, end in intervals:
        if start <= pickup < end:
            return (part, None) if label < end else (None, "label_not_available_at_cutoff")
    return None, "pickup_outside_protocol"


def _read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SplitError(f"Se requiere objeto JSON: {path.name}")
    return value


def verify_features(
    directory: Path, validated: Path, *, test_only: bool, config: dict, data_config: dict
) -> dict:
    marker = _under(directory, "features_manifest.json")
    marker_hash = _sha256(marker)
    feature = _read_object(marker)
    validation, _ = verify_validated(validated, test_only=test_only)
    expected = {
        "manifest_version": 1,
        "status": "FEATURES_TEST_ONLY" if test_only else "FEATURES_REAL",
        "preprocessor_fitted": False,
        "approved_for_training": False,
        "data_quality_approved": not test_only,
        "feature_version": FEATURE_VERSION,
        "temporal_policy": TEMPORAL_POLICY,
        "timezone": TIMEZONE,
        "tzdata_version": version("tzdata"),
        "row_index_scope": "validated_input",
    }
    if any(type(feature.get(k)) is not type(v) or feature[k] != v for k, v in expected.items()):
        raise SplitError("Manifest de features incompatible con el modo solicitado")
    identifier = feature.get("feature_id", "")
    if (
        not isinstance(identifier, str)
        or not re.fullmatch(r"[a-f0-9]{32}", identifier)
        or directory.name != identifier
    ):
        raise SplitError("Identidad de features incompatible")
    if (
        feature.get("validation_id") != validation["validation_id"]
        or feature.get("validation_manifest_sha256") != _sha256(validated / "validation.json")
        or feature.get("input_sha256") != validation["output"]["sha256"]
        or (feature.get("year"), feature.get("month")) != (validation["year"], validation["month"])
        or feature.get("feature_columns") != list(FEATURE_COLUMNS)
        or feature.get("source_quality_exception") != validation.get("quality_exception")
    ):
        raise SplitError("Linaje features/validacion divergente")
    emitted = feature.get("rows_emitted")
    excluded = feature.get("excluded_counts")
    if (
        type(emitted) is not int
        or emitted < 1
        or feature.get("rows_seen") != validation["eligible_rows"]
        or not isinstance(excluded, dict)
        or any(type(n) is not int or n < 0 for n in excluded.values())
        or emitted + sum(excluded.values()) != feature["rows_seen"]
        or (not test_only and excluded)
    ):
        raise SplitError("Cobertura de features incompleta")
    if test_only and emitted > 65536:
        raise SplitError("Fixture excede limite de prueba")
    if not test_only:
        if (
            fingerprint(quality_rules(validation["configuration"]["quality"]))
            != config["quality_rules_sha256"]
        ):
            raise SplitError("Perfil de calidad distinto del congelado")
        authorize_source(validation["input"]["manifest"], data_config["quality"])
    for name in TABLES:
        data = _under(directory, f"{name}.parquet")
        actual = describe_parquet(data)
        if actual != feature.get("artifacts", {}).get(name) or actual["row_count"] != emitted:
            raise SplitError("Hash/esquema/conteo de features divergente")
        with pq.ParquetFile(data) as parquet:
            schema = parquet.schema_arrow
        metadata = schema.metadata or {}
        if (
            not schema.equals(SCHEMAS[name], check_metadata=False)
            or metadata.get(b"feature_scope") != (b"TEST_ONLY" if test_only else b"REAL")
            or metadata.get(b"approved_for_training") != b"false"
            or metadata.get(b"feature_version") != FEATURE_VERSION.encode()
            or (test_only and metadata.get(b"fixture_origin") != b"synthetic")
            or (not test_only and b"fixture_origin" in metadata)
        ):
            raise SplitError("Esquema/metadata no aptos para particionar")
    if _sha256(marker) != marker_hash:
        raise SplitError("Manifest de features cambio durante verificacion")
    return {
        "feature": feature,
        "marker_sha256": marker_hash,
        "raw_sha256": validation["input"]["manifest"]["sha256"],
    }


def _catalog(
    path: Path,
    config: dict,
    *,
    test_only: bool,
    required: set[tuple[int, int]] | None = None,
) -> list[dict]:
    expected = required_months(config) if required is None else required
    catalog = _read_object(path)
    if (
        catalog.get("format_version") != 1
        or not isinstance(catalog.get("batches"), list)
        or not catalog["batches"]
    ):
        raise SplitError("Catalogo de entradas vacio o incompatible")
    result, seen = [], set()
    for entry in catalog["batches"]:
        year, month = entry["year"], entry["month"]
        if (
            type(year) is not int
            or type(month) is not int
            or (year, month) not in expected
            or (year, month) in seen
        ):
            raise SplitError("Mes repetido o fuera del protocolo")
        seen.add((year, month))
        paths = {}
        for name in ("features_directory", "validated_directory"):
            candidate = path.parent / entry[name]
            if candidate.is_symlink() or candidate.is_junction():
                raise SplitError("No se aceptan directorios de entrada enlazados")
            paths[name] = candidate.resolve()
        result.append({"year": year, "month": month, **paths})
    if not test_only and seen != expected:
        raise SplitError(
            "Faltan meses: REAL exige los 24 lotes explicitos, sin elegir versiones por glob"
            if required is None
            else "Faltan meses: ajuste REAL exige todos los meses de train explicitos"
        )
    return sorted(result, key=lambda item: (item["year"], item["month"]))


def _source_rows(
    entry, config, counters, digests, ranges, guard, exclusions, *, batch_size, test_only
):
    """Lector causal compartido; emitir bloques no publica ni aprueba particiones."""
    feature = entry["verified"]["feature"]
    intervals = [(part, *boundaries(config, part)) for part in PARTITIONS]
    previous = -1
    seen = 0
    with ExitStack() as stack:
        readers = {
            name: stack.enter_context(
                pq.ParquetFile(entry["features_directory"] / f"{name}.parquet")
            )
            for name in TABLES
        }
        iterators = [
            readers[name].iter_batches(batch_size=batch_size, use_threads=False) for name in TABLES
        ]
        for group in zip(*iterators, strict=True):
            guard.check()
            if len({batch.num_rows for batch in group}) != 1:
                raise SplitError("Bloques de features/target/contexto desalineados")
            values = [batch.to_pylist() for batch in group]
            rows_by_partition = {part: {name: [] for name in TABLES} for part in PARTITIONS}
            for X, y, context in zip(*values, strict=True):
                pickup, label = context["pickup_datetime_utc"], context["label_event_datetime_utc"]
                index = context["validated_row_index"]
                if type(index) is not int or not previous < index < feature["rows_seen"]:
                    raise SplitError("Identidad de fila repetida, fuera de rango o desordenada")
                previous = index
                if not test_only and index != seen:
                    raise SplitError("REAL requiere cobertura contigua del validado")
                seen += 1
                counters["rows_seen"] += 1
                part, reason = _classify(pickup, label, intervals)
                duration = y["trip_duration_minutes"]
                if (
                    not isinstance(duration, float)
                    or not math.isfinite(duration)
                    or abs(duration - (label - pickup).total_seconds() / 60) > 1e-9
                    or (not test_only and duration > 180)
                ):
                    raise SplitError("Target divergente de los eventos UTC")
                local = pickup.astimezone(nyc_zone())
                if (local.year, local.month) != (entry["year"], entry["month"]):
                    raise SplitError("Recogida fuera del mes de origen")
                if (
                    tuple(X[k] for k in ("pickup_hour", "pickup_weekday", "pickup_month"))
                    != (local.hour, local.weekday(), local.month)
                    or X["pickup_location_id"] <= 0
                    or X["passenger_count"] < 0
                    or X["passenger_count_missing"] not in (0, 1)
                    or (X["passenger_count_missing"] == 1 and X["passenger_count"] != 0)
                ):
                    raise SplitError("Features incompatibles con contexto/contrato")
                if reason:
                    counters[reason] += 1
                    if len(exclusions) < 10:
                        exclusions.append(
                            {
                                "source_feature_id": feature["feature_id"],
                                "validated_row_index": index,
                                "reason": reason,
                                "pickup_utc": pickup.isoformat(),
                                "label_event_utc": label.isoformat(),
                            }
                        )
                    continue
                counters[part] += 1
                context = {**context, "source_feature_id": feature["feature_id"]}
                for name, row in zip(TABLES, (X, y, context), strict=True):
                    rows_by_partition[part][name].append(row)
                key = [
                    list(X.values()),
                    duration,
                    index,
                    pickup.isoformat(),
                    label.isoformat(),
                    feature["feature_id"],
                ]
                digests[part].update(
                    json.dumps(key, separators=(",", ":"), allow_nan=False).encode() + b"\n"
                )
                for field in ("min", "max"):
                    old = ranges[part].get(field)
                    ranges[part][field] = (
                        pickup
                        if old is None
                        else (min(old, pickup) if field == "min" else max(old, pickup))
                    )
            yield rows_by_partition
            guard.check()
    if seen != feature["rows_emitted"]:
        raise SplitError("Escaneo de features no exhaustivo")


def _scan_source(
    entry, config, writers, counters, digests, ranges, guard, exclusions, *, batch_size, test_only
):
    schemas = {name: writer.schema for name, writer in writers["train"].items()}
    for grouped in _source_rows(
        entry,
        config,
        counters,
        digests,
        ranges,
        guard,
        exclusions,
        batch_size=batch_size,
        test_only=test_only,
    ):
        for part, tables in grouped.items():
            for name, rows in tables.items():
                if rows:
                    writers[part][name].write_table(
                        pa.Table.from_pylist(rows, schema=schemas[name])
                    )


def prepare_splits(
    catalog_path: Path,
    *,
    config_path: Path = Path("configs/model.yaml"),
    data_config_path: Path = Path("configs/data.yaml"),
    output_dir: Path = Path("data/processed/splits"),
    report_dir: Path = Path("reports/splits"),
    batch_size: int = 65536,
    test_only: bool = False,
) -> dict:
    if type(test_only) is not bool or type(batch_size) is not int or not 1 <= batch_size <= 65536:
        raise SplitError("Modo o batch_size incompatible")
    root, reports = Path(output_dir).resolve(), Path(report_dir).resolve()
    if root.is_relative_to(reports) or reports.is_relative_to(root):
        raise SplitError("Salidas y reportes deben estar separados")
    split_id = uuid.uuid4().hex
    scope_parts = ("_test_only",) if test_only else ()
    reports = _under(reports, *scope_parts)
    reports.mkdir(parents=True, exist_ok=True)
    report_path = _under(reports, f"{split_id}.json")
    report = {
        "report_version": 1,
        "split_id": split_id,
        "status": "FAIL",
        "mode": "TEST_ONLY" if test_only else "REAL",
        "approved_for_training": False,
        "preprocessor_fitted": False,
        "started_at_utc": utc_now(),
        "output_directory": None,
        "publication_complete": False,
    }
    try:
        config = read_model_config(Path(config_path))
        data_config = load_data_config(Path(data_config_path))
        if fingerprint(quality_rules(data_config["quality"])) != config["quality_rules_sha256"]:
            raise SplitError("data.yaml distinto de D-04 congelada")
        entries = _catalog(Path(catalog_path).resolve(), config, test_only=test_only)
        for entry in entries:
            for field in ("features_directory", "validated_directory"):
                source = entry[field]
                if (
                    root.is_relative_to(source)
                    or source.is_relative_to(root)
                    or reports.is_relative_to(source)
                    or source.is_relative_to(reports)
                ):
                    raise SplitError("Salida/reporte se solapa con entradas")
        root.mkdir(parents=True, exist_ok=True)
        guard = ResourceGuard(preparation_budget(config), root, test_only=test_only)
        guard.check(start=True)
        seen_ids = set()
        for entry in entries:
            verified = verify_features(
                entry["features_directory"],
                entry["validated_directory"],
                test_only=test_only,
                config=config,
                data_config=data_config,
            )
            if (verified["feature"]["year"], verified["feature"]["month"]) != (
                entry["year"],
                entry["month"],
            ):
                raise SplitError("Mes declarado distinto de features")
            identity = verified["feature"]["validation_id"]
            if identity in seen_ids:
                raise SplitError("Validacion de origen repetida")
            seen_ids.add(identity)
            entry["verified"] = verified
        if test_only and sum(e["verified"]["feature"]["rows_emitted"] for e in entries) > 65536:
            raise SplitError("Protocolo TEST_ONLY excede 65536 filas")
        metadata = {
            b"split_scope": report["mode"].encode(),
            b"approved_for_training": b"false",
            b"temporal_policy": TEMPORAL_POLICY.encode(),
        }
        if test_only:
            metadata[b"fixture_origin"] = b"synthetic"
        schemas = {name: schema.with_metadata(metadata) for name, schema in SCHEMAS.items()}
        schemas["context"] = schemas["context"].append(pa.field("source_feature_id", pa.string()))
        parent = _under(root, *scope_parts)
        parent.mkdir(parents=True, exist_ok=True)
        counters, ranges = Counter(), {part: {} for part in PARTITIONS}
        exclusions = []
        digests = {part: hashlib.sha256() for part in PARTITIONS}
        with tempfile.TemporaryDirectory(prefix=".split-", dir=parent) as owned:
            staged = Path(owned)
            with (
                ExitStack() as stack,
                threadpool_limits(limits=config["resources"]["threads_total"]),
            ):
                writers = {}
                for part in PARTITIONS:
                    (staged / part).mkdir()
                    writers[part] = {
                        name: stack.enter_context(
                            pq.ParquetWriter(staged / part / f"{name}.parquet", schema)
                        )
                        for name, schema in schemas.items()
                    }
                for entry in entries:
                    _scan_source(
                        entry,
                        config,
                        writers,
                        counters,
                        digests,
                        ranges,
                        guard,
                        exclusions,
                        batch_size=batch_size,
                        test_only=test_only,
                    )
                    LOGGER.info(
                        "Particionado %04d-%02d: %d filas acumuladas",
                        entry["year"],
                        entry["month"],
                        counters["rows_seen"],
                    )
            for entry in entries:
                after = verify_features(
                    entry["features_directory"],
                    entry["validated_directory"],
                    test_only=test_only,
                    config=config,
                    data_config=data_config,
                )
                if after != entry["verified"]:
                    raise SplitError("Entrada cambio durante particionado")
            expected = sum(e["verified"]["feature"]["rows_emitted"] for e in entries)
            kept = sum(counters[p] for p in PARTITIONS)
            if (
                counters["rows_seen"] != expected
                or kept + counters["label_not_available_at_cutoff"] != expected
            ):
                raise SplitError("Contabilidad de cobertura no exhaustiva")
            if not test_only and any(counters[p] == 0 for p in PARTITIONS):
                raise SplitError("Particion real vacia")
            outputs = {}
            for part in PARTITIONS:
                outputs[part] = {}
                for name in TABLES:
                    path = staged / part / f"{name}.parquet"
                    with path.open("r+b") as stream:
                        os.fsync(stream.fileno())
                    description = describe_parquet(path)
                    if description["row_count"] != counters[part]:
                        raise SplitError("Salida desalineada")
                    outputs[part][name] = description
            guard.check()
            report.update(
                status="SPLIT_TEST_ONLY" if test_only else "SPLIT_REAL",
                configuration=config,
                config_sha256=fingerprint(config),
                inputs=[
                    {
                        **e,
                        "features_directory": str(e["features_directory"]),
                        "validated_directory": str(e["validated_directory"]),
                    }
                    for e in entries
                ],
                counts=dict(counters),
                exclusion_examples=exclusions,
                partitions={
                    part: {
                        "rows": counters[part],
                        "logical_sha256": digests[part].hexdigest(),
                        "pickup_range_utc": {k: v.isoformat() for k, v in ranges[part].items()},
                        "artifacts": outputs[part],
                    }
                    for part in PARTITIONS
                },
                complete_protocol_coverage={(e["year"], e["month"]) for e in entries}
                == required_months(config),
                resources={
                    "preflight": guard.initial,
                    "final": guard.last,
                    "supervision": "between_blocks",
                    "candidate_timeout_enforced": False,
                },
                finished_at_utc=utc_now(),
            )
            destination = _under(parent, split_id)
            destination.mkdir(exist_ok=False)
            report["output_directory"] = str(destination)
            for part in PARTITIONS:
                (destination / part).mkdir()
                for name in TABLES:
                    publish_file(
                        staged / part / f"{name}.parquet",
                        _under(destination, part, f"{name}.parquet"),
                    )
            report["publication_complete"] = True
            publish_manifest(_under(destination, "split_manifest.json"), report)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, pa.ArrowException) as error:
        report.update(
            status="FAIL", error=str(error), finished_at_utc=utc_now(), publication_complete=False
        )
    publish_manifest(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/model.yaml"))
    parser.add_argument("--data-config", type=Path, default=Path("configs/data.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/splits"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/splits"))
    parser.add_argument("--batch-size", type=int, default=65536)
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    try:
        report = prepare_splits(
            args.inputs,
            config_path=args.config,
            data_config_path=args.data_config,
            output_dir=args.output_dir,
            report_dir=args.report_dir,
            batch_size=args.batch_size,
            test_only=args.test_only,
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Particionado fallido: {error}\n")
    print(json.dumps(report))
    if report["status"] == "FAIL":
        parser.exit(1)


if __name__ == "__main__":
    main()
