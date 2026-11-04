"""CLI raw -> calidad real aprobada o TEST_ONLY; no concede permiso de entrenamiento."""

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
import tempfile
import uuid
from importlib.metadata import version
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.ingestion.download import month_lock
from src.ingestion.manifest import (
    IngestionError,
    describe_parquet,
    publish_file,
    publish_manifest,
    read_and_verify,
    source_url,
    utc_now,
)
from src.validation.exceptions import authorize_exception, bind_exception, load_exception
from src.validation.real import authorize_source, validate_policy
from src.validation.rules import evaluate_batches
from src.validation.schema import check, fingerprint, load_config, validate_schema

LOGGER = logging.getLogger(__name__)


class ValidationError(RuntimeError):
    """Fallo de validacion/publicacion; no habilita el consumo del lote."""


def _under(root: Path, *parts: str) -> Path:
    destination = root.joinpath(*parts)
    if not destination.resolve().is_relative_to(root):
        raise ValidationError("La ruta escapa de su directorio configurado")
    cursor = root
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink() or cursor.is_junction():
            raise ValidationError("No se permiten enlaces en las rutas del lote")
    return destination


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write_eligible(writer: pq.ParquetWriter, batch: pa.RecordBatch, mask: list[bool]) -> None:
    """Escribe tramos validos por slice, sin depender de PyArrow Compute."""
    start = None
    pieces = []
    for index, keep in enumerate([*mask, False]):
        if keep and start is None:
            start = index
        elif not keep and start is not None:
            pieces.append(batch.slice(start, index - start))
            start = None
    if pieces:
        # Un grupo por bloque, evitando miles de grupos diminutos por las exclusiones.
        writer.write_table(pa.Table.from_batches(pieces), row_group_size=65_536)


def _scan(
    data: Path,
    staged: Path,
    config: dict,
    scratch: Path,
    year: int,
    month: int,
    batch_size: int,
    validation_id: str,
    resource_check=None,
) -> dict:
    with data.open("rb") as source, pq.ParquetFile(source) as parquet:
        real = config["quality"].get("status") == "APPROVED_REAL"
        metadata = {
            **(parquet.schema_arrow.metadata or {}),
            b"validation_scope": b"REAL" if real else b"TEST_ONLY",
            b"approved_for_training": b"false",
            b"validation_id": validation_id.encode(),
        }
        output_schema = parquet.schema_arrow.with_metadata(metadata)
        if real and "passenger_count" in output_schema.names:
            index = output_schema.get_field_index("passenger_count")
            output_schema = output_schema.set(index, output_schema.field(index).with_nullable(True))
        with staged.open("xb") as stream:
            with pq.ParquetWriter(stream, output_schema, compression="snappy") as writer:

                def checked_write(batch, mask):
                    if resource_check is not None:
                        try:
                            resource_check()
                        except RuntimeError as error:
                            raise ValidationError(str(error)) from error
                    _write_eligible(writer, batch, mask)

                report = evaluate_batches(
                    parquet.schema_arrow,
                    parquet.iter_batches(batch_size=batch_size, use_threads=False),
                    year=year,
                    month=month,
                    config=config,
                    scratch_dir=scratch,
                    on_batch=checked_write,
                )
            stream.flush()
            os.fsync(stream.fileno())
    return report


def validate(
    year: int,
    month: int,
    *,
    raw_dir: Path = Path("data/raw"),
    validated_dir: Path = Path("data/validated"),
    report_dir: Path = Path("reports/quality"),
    config_path: Path = Path("configs/data.yaml"),
    scratch_dir: Path = Path(".cache/validation"),
    batch_size: int = 65_536,
    test_only: bool = False,
    resource_check=None,
    exception_path: Path | None = None,
) -> dict:
    """Valida un lote sin red ni incorporacion automatica de archivos locales.

    Cada intento conserva reporte propio. REAL aprobado publica calidad real;
    TEST_ONLY usa _test_only. Ninguno obtiene approved_for_training. Un validation.json publicado
    al final es el marcador de un resultado completo; un Parquet aislado no lo es.
    """
    source_url(year, month)
    if type(batch_size) is not int or not 1 <= batch_size <= 65_536:
        raise ValueError("batch_size debe ser entero entre 1 y 65536")
    if type(test_only) is not bool:
        raise ValueError("test_only debe ser booleano")
    roots = [Path(path).resolve() for path in (raw_dir, validated_dir, report_dir, scratch_dir)]
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError(
                    "raw, validated, reports y scratch deben ser directorios separados"
                )
    raw, validated, reports, scratch = roots
    validation_id = uuid.uuid4().hex
    period = (f"{year:04}", f"{month:02}")
    report_parts = (("_test_only",) if test_only else ()) + period
    report_parent = _under(reports, *report_parts)
    report_parent.mkdir(parents=True, exist_ok=True)
    report_path = _under(reports, *report_parts, f"{validation_id}.json")
    report = {
        "report_version": 2,
        "validation_id": validation_id,
        "started_at_utc": utc_now(),
        "pipeline_version": version("nyc-yellow-taxi-mlops"),
        "year": year,
        "month": month,
        "mode": "TEST_ONLY" if test_only else "NORMAL",
        "status": "FAIL",
        "execution_status": "REJECTED",
        "quality_passed": False,
        "approved_for_training": False,
        "data_quality_approved": False,
        "lineage_status": "NOT_VERIFIED",
        "scan_scope": "NOT_STARTED",
        "input": None,
        "output": None,
        "checks": [],
        "report_path": str(report_path),
    }
    try:
        config = load_config(Path(config_path))
        report.update(config_sha256=fingerprint(config), configuration=config)
        data = _under(raw, *period, f"yellow_tripdata_{year:04}-{month:02}.parquet")
        manifest_path = _under(raw, *period, "manifest.json")
        if not data.is_file() or not manifest_path.is_file():
            raise ValidationError(
                "Se requieren Parquet y manifiesto de ingesta; no se registran aqui"
            )
        with month_lock(data.parent):
            manifest_hash = _sha256(manifest_path)
            manifest = read_and_verify(manifest_path, data, year, month)
            if _sha256(manifest_path) != manifest_hash:
                raise ValidationError("El manifiesto cambio durante su verificacion")
            report["input"] = {
                "raw_relative_path": "/".join((*period, data.name)),
                "manifest_relative_path": "/".join((*period, manifest_path.name)),
                "manifest_sha256": manifest_hash,
                "manifest": manifest,
            }
            report["lineage_status"] = "VERIFIED_CONTENT"
            with data.open("rb") as stream, pq.ParquetFile(stream) as parquet:
                schema = parquet.schema_arrow
            structural = validate_schema(schema, config)
            report.update(
                schema_version=structural["schema_version"],
                schema_fingerprint=structural["schema_fingerprint"],
            )
            report["checks"] = structural["checks"]
            real = not test_only and config["quality"].get("status") == "APPROVED_REAL"
            if real:
                validate_policy(config["quality"])
                report["source_use_approval"] = authorize_source(manifest, config["quality"])
                if exception_path is not None:
                    bind_exception(report, load_exception(Path(exception_path)))
                report["checks"].append(
                    check(
                        "provenance.authorized",
                        "PASS",
                        report["source_use_approval"],
                        "Recorded download or explicit local authorization",
                        manifest["provenance_status"],
                    )
                )
                if manifest["origin"] == "local":
                    report["checks"].append(
                        check(
                            "provenance.unverified",
                            "WARN",
                            manifest["provenance_status"],
                            "Accepted for academic pilot only",
                            {"source_url": None, "downloaded_at_utc": None},
                        )
                    )
            if exception_path is not None and not real:
                raise ValidationError("Las excepciones exigen calidad REAL, nunca TEST_ONLY")
            if not test_only and not real:
                report["checks"].append(
                    check(
                        "policy.ready",
                        "FAIL",
                        config["quality"].get("status"),
                        "Politica real aprobada (pendiente D-04/D-06)",
                        "No se leen filas ni se publican datasets en el modo normal actual",
                    )
                )
                report["scan_scope"] = "PREFLIGHT_ONLY"
            elif test_only and (
                config["quality"].get("status") != "TEST_ONLY"
                or (schema.metadata or {}).get(b"fixture_origin") != b"synthetic"
            ):
                raise ValidationError(
                    "--test-only exige politica TEST_ONLY y fixture sintetica marcada"
                )
            elif structural["status"] == "FAIL":
                report["scan_scope"] = "PREFLIGHT_ONLY"
            elif real and manifest["row_count"] < config["quality"]["volume"]["min_rows"]:
                report["checks"].append(
                    check(
                        "volume.min_rows",
                        "FAIL",
                        manifest["row_count"],
                        {"minimum": config["quality"]["volume"]["min_rows"]},
                        "Footer preflight",
                    )
                )
                report["scan_scope"] = "PREFLIGHT_ONLY"
            else:
                output_parts = (() if real else ("_test_only",)) + period
                output_parent = _under(validated, *output_parts)
                output_parent.mkdir(parents=True, exist_ok=True)
                destination = _under(validated, *output_parts, validation_id)
                # Staging en el mismo volumen que el destino, sin reemplazos.
                with tempfile.TemporaryDirectory(prefix=".validation-", dir=output_parent) as owned:
                    staged = Path(owned) / "data.parquet"
                    report["scan_scope"] = "FULL_PARQUET_ATTEMPT"
                    quality = _scan(
                        data,
                        staged,
                        config,
                        scratch,
                        year,
                        month,
                        batch_size,
                        validation_id,
                        resource_check=resource_check,
                    )
                    initial_checks = report["checks"]
                    report.update(quality)
                    provenance = [
                        entry for entry in initial_checks if entry["rule"].startswith("provenance.")
                    ]
                    report["checks"].extend(provenance)
                    if (
                        real
                        and quality["status"] == "PASS"
                        and any(entry["status"] == "WARN" for entry in provenance)
                    ):
                        report["status"] = "WARN"
                    report["report_version"] = 2
                    report["scan_scope"] = "FULL_PARQUET"
                    report["lineage_status"] = "VERIFIED_CONTENT"
                    exhaustive = quality["rows_scanned"] == manifest["row_count"]
                    report["checks"].append(
                        check(
                            "input.exhaustive",
                            "PASS" if exhaustive else "FAIL",
                            quality["rows_scanned"],
                            manifest["row_count"],
                            "Filas del footer raw",
                        )
                    )
                    after = read_and_verify(manifest_path, data, year, month)
                    if after != manifest or _sha256(manifest_path) != manifest_hash:
                        raise ValidationError("El lote/manifiesto cambio durante el escaneo")
                    accepted = quality["quality_passed"]
                    if exception_path is not None:
                        report["quality_exception"] = authorize_exception(
                            report, Path(exception_path)
                        )
                        report.update(
                            status="WARN", raw_quality_status="FAIL", quality_passed=False
                        )
                        accepted = True
                    if not accepted or not exhaustive:
                        report.update(status="FAIL", quality_passed=False)
                    else:
                        description = describe_parquet(staged)
                        if description["row_count"] != quality["eligible_rows"]:
                            raise ValidationError("La salida no coincide con las filas elegibles")
                        destination.mkdir(exist_ok=False)
                        final_data = _under(destination, "data.parquet")
                        execution = (
                            "VALIDATED_REAL_EXCEPTION"
                            if exception_path is not None
                            else "VALIDATED_REAL"
                            if real
                            else "VALIDATED_TEST_ONLY"
                        )
                        report["output"] = {
                            "status": execution,
                            "relative_path": "/".join(
                                (*output_parts, validation_id, "data.parquet")
                            ),
                            **description,
                        }
                        report["execution_status"] = execution
                        report["data_quality_approved"] = real
                        report["finished_at_utc"] = utc_now()
                        publish_file(staged, final_data)
                        # Marcador ultimo: un Parquet huerfano nunca es resultado completo.
                        publish_manifest(_under(destination, "validation.json"), report)
    except (
        ValidationError,
        IngestionError,
        OSError,
        ValueError,
        sqlite3.Error,
        pa.ArrowException,
    ) as error:
        report.update(
            status="FAIL",
            execution_status="REJECTED",
            quality_passed=False,
            data_quality_approved=False,
            error=str(error),
        )
        report["lineage_status"] = "FAILED_OR_INCOMPLETE"
        if report["output"] is not None:
            report["output"]["status"] = "INCOMPLETE"
        report["checks"].append(
            check("execution", "FAIL", str(error), "Sin errores", type(error).__name__)
        )
    report.setdefault("finished_at_utc", utc_now())
    # Si falla el almacenamiento de evidencia, se propaga y el CLI devuelve error.
    publish_manifest(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--month", required=True, type=int)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--validated-dir", type=Path, default=Path("data/validated"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/quality"))
    parser.add_argument("--config", type=Path, default=Path("configs/data.yaml"))
    parser.add_argument("--scratch-dir", type=Path, default=Path(".cache/validation"))
    parser.add_argument("--batch-size", type=int, default=65_536)
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--quality-exception", type=Path)
    args = parser.parse_args()
    try:
        report = validate(
            args.year,
            args.month,
            raw_dir=args.raw_dir,
            validated_dir=args.validated_dir,
            report_dir=args.report_dir,
            config_path=args.config,
            scratch_dir=args.scratch_dir,
            batch_size=args.batch_size,
            test_only=args.test_only,
            exception_path=args.quality_exception,
        )
        print(json.dumps(report, allow_nan=False))
        if report["status"] == "FAIL":
            LOGGER.error("Validacion rechazada; reporte: %s", report["report_path"])
            sys.exit(1)
    except (
        ValidationError,
        IngestionError,
        OSError,
        ValueError,
        sqlite3.Error,
        pa.ArrowException,
    ) as error:
        LOGGER.error("Validacion fallida: %s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
