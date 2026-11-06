"""Frontera de artefactos validados reales/TEST_ONLY, sin fit ni permiso de entrenamiento."""

import json
import logging
import os
import re
import tempfile
import uuid
from collections import Counter
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.features.build import feature_values, prepare_historical
from src.features.schema import FEATURE_COLUMNS, FEATURE_VERSION, FeatureError
from src.features.target import TEMPORAL_POLICY, TIMEZONE
from src.features.vectorized import SUPPORTED_REAL_YEARS, real_tables
from src.ingestion.manifest import (
    describe_parquet,
    publish_file,
    publish_manifest,
    source_url,
    utc_now,
)
from src.validation.exceptions import verify_exception
from src.validation.real import authorize_source, validate_policy
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint

LOGGER = logging.getLogger(__name__)


def verify_validated(
    directory: Path, *, test_only: bool, max_rows: int | None = None
) -> tuple[dict, dict]:
    if type(test_only) is not bool:
        raise FeatureError("test_only debe ser booleano")
    if max_rows is None and test_only:
        max_rows = 65_536
    if max_rows is not None and (type(max_rows) is not int or max_rows < 1):
        raise FeatureError("Limite de fixtures debe estar entre 1 y 65536 filas")
    scope = "TEST_ONLY" if test_only else "REAL"
    expected_status = "VALIDATED_TEST_ONLY" if test_only else "VALIDATED_REAL"
    marker = _under(directory, "validation.json")
    data = _under(directory, "data.parquet")
    try:
        report = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise FeatureError("Falta marcador de validacion legible") from error
    exceptional = not test_only and report.get("execution_status") == "VALIDATED_REAL_EXCEPTION"
    if exceptional:
        expected_status = "VALIDATED_REAL_EXCEPTION"
        try:
            verify_exception(report)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise FeatureError("Excepcion de calidad no verificable") from error
    elif report.get("quality_exception") is not None:
        raise FeatureError("Aceptacion excepcional sin estado explicito")
    expected = {
        "report_version": 2,
        "mode": "TEST_ONLY" if test_only else "NORMAL",
        "execution_status": expected_status,
        "quality_passed": not exceptional,
        "approved_for_training": False,
        "lineage_status": "VERIFIED_CONTENT",
        "scan_scope": "FULL_PARQUET",
        "eligibility_complete": True,
    }
    if not test_only:
        expected["data_quality_approved"] = True
    if not isinstance(report, dict) or any(
        type(report.get(key)) is not type(value) or report[key] != value
        for key, value in expected.items()
    ):
        raise FeatureError("D-04: marcador no habilitado para el modo solicitado")
    validation_id = report.get("validation_id")
    checks = report.get("checks")
    if (
        not isinstance(validation_id, str)
        or not re.fullmatch(r"[a-f0-9]{32}", validation_id)
        or directory.name != validation_id
        or report.get("status") not in ("PASS", "WARN")
        or not isinstance(checks, list)
        or not checks
        or any(
            not isinstance(item, dict)
            or item.get("status")
            not in (("PASS", "WARN", "FAIL") if exceptional else ("PASS", "WARN"))
            for item in checks
        )
    ):
        raise FeatureError("Identidad/resultado de validacion incompatible")
    source_url(report.get("year"), report.get("month"))
    output = report.get("output")
    if not isinstance(output, dict) or output.get("status") != expected_status:
        raise FeatureError("Salida de validacion incompleta")
    prefix = "_test_only/" if test_only else ""
    expected_relative = (
        f"{prefix}{report['year']:04}/{report['month']:02}/{validation_id}/data.parquet"
    )
    if output.get("relative_path") != expected_relative:
        raise FeatureError("Ruta declarada de salida inconsistente")
    actual = describe_parquet(data)
    if any(
        type(output.get(key)) is not type(value) or output[key] != value
        for key, value in actual.items()
    ):
        raise FeatureError("Contenido validado divergente")
    with data.open("rb") as stream, pq.ParquetFile(stream) as parquet:
        metadata = parquet.schema_arrow.metadata or {}
    if any(
        metadata.get(key) != value
        for key, value in {
            **({b"fixture_origin": b"synthetic"} if test_only else {}),
            b"validation_scope": scope.encode(),
            b"approved_for_training": b"false",
            b"validation_id": validation_id.encode(),
        }.items()
    ):
        raise FeatureError("Metadata de salida no corresponde al marcador de calidad")
    try:
        raw_rows = report["input"]["manifest"]["row_count"]
        seen, eligible, excluded = (
            report[key] for key in ("rows_scanned", "eligible_rows", "excluded_rows")
        )
        configuration = report["configuration"]
        consistent = (
            all(type(n) is int for n in (raw_rows, seen, eligible, excluded))
            and seen == raw_rows
            and eligible == actual["row_count"]
            and seen == eligible + excluded
            and 0 <= excluded <= seen
            and fingerprint(configuration) == report["config_sha256"]
            and configuration["quality"]["status"]
            == ("TEST_ONLY" if test_only else "APPROVED_REAL")
            and report["input"]["manifest"]["year"] == report["year"]
            and report["input"]["manifest"]["month"] == report["month"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise FeatureError("Linaje de validacion incompleto") from error
    if (
        not consistent
        or actual["row_count"] < 1
        or max_rows is not None
        and actual["row_count"] > max_rows
    ):
        raise FeatureError("Conteos/limite de fixture inconsistentes")
    if not test_only:
        validate_policy(configuration["quality"])
        if (
            report.get("temporal_policy") != TEMPORAL_POLICY
            or report.get("tzdata_version") != version("tzdata")
            or report.get("source_use_approval")
            != authorize_source(report["input"]["manifest"], configuration["quality"])
        ):
            raise FeatureError("Politica temporal o autorizacion de procedencia inconsistente")
    return report, actual


def build_validated_features(
    directory: Path,
    *,
    processed_dir: Path = Path("data/processed"),
    test_only: bool = False,
    batch_size: int = 2_048,
    resource_check=None,
) -> dict:
    """Calidad real autorizada o fixtures; no ajusta encoder ni ejecuta entrenamiento."""
    directory, processed_dir = Path(directory), Path(processed_dir).resolve()
    if directory.is_symlink() or directory.is_junction():
        raise FeatureError("No se admite un directorio de lote enlazado")
    directory = directory.resolve()
    if processed_dir.is_relative_to(directory) or directory.is_relative_to(processed_dir):
        raise FeatureError("La salida debe estar separada del lote de entrada")
    if type(batch_size) is not int or not 1 <= batch_size <= 65_536:
        raise FeatureError("batch_size debe estar entre 1 y 65536")
    marker = _under(directory, "validation.json")
    initial_marker_hash = _sha256(marker) if marker.is_file() else None
    validation, description = verify_validated(directory, test_only=test_only)
    if _sha256(marker) != initial_marker_hash:
        raise FeatureError("El marcador cambio durante su verificacion")
    feature_id = uuid.uuid4().hex
    period = (f"{validation['year']:04}", f"{validation['month']:02}")
    output_parts = (("_test_only",) if test_only else ()) + period
    parent = _under(processed_dir, *output_parts)
    parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        **({b"fixture_origin": b"synthetic"} if test_only else {}),
        b"feature_scope": b"TEST_ONLY" if test_only else b"REAL",
        b"approved_for_training": b"false",
        b"feature_version": FEATURE_VERSION.encode(),
    }
    if not test_only:
        with (directory / "data.parquet").open("rb") as stream, pq.ParquetFile(stream) as source:
            origin = (source.schema_arrow.metadata or {}).get(b"fixture_origin")
            if origin is not None:
                metadata[b"fixture_origin"] = origin
    schemas = {
        "features": pa.schema([(name, pa.int64()) for name in FEATURE_COLUMNS], metadata=metadata),
        "target": pa.schema([("trip_duration_minutes", pa.float64())], metadata=metadata),
        "context": pa.schema(
            [
                ("validated_row_index", pa.int64()),
                ("pickup_datetime_utc", pa.timestamp("us", "UTC")),
                ("label_event_datetime_utc", pa.timestamp("us", "UTC")),
            ],
            metadata=metadata,
        ),
    }
    count, seen, excluded_counts, examples = 0, 0, Counter(), []
    with tempfile.TemporaryDirectory(prefix=".features-", dir=parent) as owned:
        staged = Path(owned)
        with ExitStack() as stack:
            writers = {
                name: stack.enter_context(pq.ParquetWriter(staged / f"{name}.parquet", schema))
                for name, schema in schemas.items()
            }
            source = stack.enter_context((directory / "data.parquet").open("rb"))
            parquet = stack.enter_context(pq.ParquetFile(source))
            for batch in parquet.iter_batches(batch_size=batch_size, use_threads=False):
                if resource_check is not None:
                    resource_check()
                if not test_only and validation["year"] in SUPPORTED_REAL_YEARS:
                    tables = real_tables(
                        batch,
                        year=validation["year"],
                        month=validation["month"],
                        start_index=seen,
                        schemas=schemas,
                    )
                    for name, table in tables.items():
                        writers[name].write_table(table)
                    seen += batch.num_rows
                    count += batch.num_rows
                    LOGGER.info(
                        "Features %04d-%02d: %d filas",
                        validation["year"],
                        validation["month"],
                        seen,
                    )
                    if resource_check is not None:
                        resource_check()
                    continue
                prepared = prepare_historical(pa.Table.from_batches([batch]), start_index=seen)
                seen += prepared.rows_seen
                for excluded in prepared.excluded:
                    excluded_counts[excluded["reason"]] += 1
                    if len(examples) < 10:
                        examples.append(excluded)
                if not prepared.examples:
                    continue
                feature_rows, targets, context = [], [], []
                for item in prepared.examples:
                    values = feature_values(item.request)
                    feature_rows.append(
                        dict(zip(FEATURE_COLUMNS, (int(value) for value in values), strict=True))
                    )
                    targets.append({"trip_duration_minutes": item.target_minutes})
                    context.append(
                        {
                            "validated_row_index": item.source_row_index,
                            "pickup_datetime_utc": item.pickup_utc,
                            "label_event_datetime_utc": item.label_event_at_utc,
                        }
                    )
                for name, rows in (
                    ("features", feature_rows),
                    ("target", targets),
                    ("context", context),
                ):
                    writers[name].write_table(pa.Table.from_pylist(rows, schema=schemas[name]))
                count += len(prepared.examples)
                LOGGER.info(
                    "Features %04d-%02d: %d filas", validation["year"], validation["month"], seen
                )
                if resource_check is not None:
                    resource_check()
        if not count:
            raise FeatureError(f"Sin ejemplos utilizables; motivos: {dict(excluded_counts)}")
        if not test_only and excluded_counts:
            raise FeatureError("Calidad real incoherente: exclusiones adicionales en features")
        if seen != description["row_count"]:
            raise FeatureError("Lectura incompleta")
        after_validation, after_description = verify_validated(directory, test_only=test_only)
        if (
            after_validation != validation
            or after_description != description
            or _sha256(marker) != initial_marker_hash
        ):
            raise FeatureError("El lote validado cambio durante features")
        for name in schemas:
            with (staged / f"{name}.parquet").open("r+b") as stream:
                os.fsync(stream.fileno())
        descriptions = {name: describe_parquet(staged / f"{name}.parquet") for name in schemas}
        if any(item["row_count"] != count for item in descriptions.values()):
            raise FeatureError("Desalineacion de features, target y contexto")
        manifest = {
            "manifest_version": 1,
            "feature_id": feature_id,
            "created_at_utc": utc_now(),
            "status": "FEATURES_TEST_ONLY" if test_only else "FEATURES_REAL",
            "data_quality_approved": not test_only,
            "approved_for_training": False,
            "year": validation["year"],
            "month": validation["month"],
            "feature_version": FEATURE_VERSION,
            "temporal_policy": TEMPORAL_POLICY,
            "timezone": TIMEZONE,
            "tzdata_version": version("tzdata"),
            "sklearn_version": version("scikit-learn"),
            "pipeline_version": version("nyc-yellow-taxi-mlops"),
            "validation_id": validation["validation_id"],
            "validation_manifest_sha256": initial_marker_hash,
            "input_sha256": description["sha256"],
            "rows_seen": seen,
            "rows_emitted": count,
            "excluded_counts": dict(excluded_counts),
            "excluded_examples": examples,
            "row_index_scope": "validated_input",
            "feature_columns": list(FEATURE_COLUMNS),
            "preprocessor_fitted": False,
            "historical_engine": (
                "numpy-hour-offsets-v1"
                if not test_only and validation["year"] in SUPPORTED_REAL_YEARS
                else "reference-python-v1"
            ),
            "artifacts": descriptions,
        }
        if validation.get("quality_exception") is not None:
            manifest["source_quality_exception"] = validation["quality_exception"]
        destination = _under(processed_dir, *output_parts, feature_id)
        destination.mkdir(exist_ok=False)
        for name in schemas:
            publish_file(staged / f"{name}.parquet", _under(destination, f"{name}.parquet"))
        publish_manifest(_under(destination, "features_manifest.json"), manifest)
    return {**manifest, "output_directory": str(destination)}
