"""Metadatos de ingesta y publicacion local sin reemplazar destinos existentes."""

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


class IngestionError(RuntimeError):
    """Fallo controlado de ingesta; no implica aprobacion de calidad."""


class IngestionConflict(IngestionError):
    """Estado local divergente o incompleto que requiere revision explicita."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def source_url(year: int, month: int) -> str:
    if type(year) is not int or not 2009 <= year <= 9999:
        raise ValueError("year debe ser entero entre 2009 y 9999")
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("month debe ser entero entre 1 y 12")
    return (
        "https://d37ci6vzurychx.cloudfront.net/trip-data/"
        f"yellow_tripdata_{year:04}-{month:02}.parquet"
    )


def describe_parquet(path: Path) -> dict:
    """Hash y footer legible; no escanea paginas ni aplica Quality Gates."""
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    try:
        with path.open("rb") as source, pq.ParquetFile(source) as parquet:
            fields = [
                {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                for field in parquet.schema_arrow
            ]
            row_count = parquet.metadata.num_rows
    except (pa.ArrowException, OSError) as error:
        raise IngestionError(f"Parquet ilegible: {path.name}") from error
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise IngestionConflict("El archivo cambio durante su inspeccion")
    return {
        "sha256": digest.hexdigest(),
        "file_size_bytes": after.st_size,
        "row_count": row_count,
        "schema": fields,
        "schema_fingerprint": hashlib.sha256(
            json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def make_manifest(year: int, month: int, description: dict, *, local: bool) -> dict:
    url = source_url(year, month)
    observed_at = utc_now()
    return {
        "manifest_version": 1,
        "year": year,
        "month": month,
        "file_name": f"yellow_tripdata_{year:04}-{month:02}.parquet",
        "source_url": None if local else url,
        "expected_source_url": url,
        "downloaded_at_utc": None if local else observed_at,
        "recorded_at_utc": observed_at,
        "origin": "local" if local else "download",
        "provenance_status": "UNVERIFIED_LOCAL" if local else "RECORDED_DOWNLOAD",
        "status": "LOCAL_UNVERIFIED" if local else "DOWNLOADED",
        "pipeline_version": version("nyc-yellow-taxi-mlops"),
        **description,
    }


def read_and_verify(path: Path, data: Path, year: int, month: int) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("El manifiesto no es un objeto")
        expected = {
            "manifest_version": 1,
            "year": year,
            "month": month,
            "file_name": data.name,
            "expected_source_url": source_url(year, month),
        }
        for key, value in expected.items():
            if type(manifest.get(key)) is not type(value) or manifest[key] != value:
                raise ValueError(f"Metadato inconsistente: {key}")
        local = manifest.get("origin") == "local"
        if manifest.get("origin") not in ("local", "download"):
            raise ValueError("Origen desconocido")
        if manifest.get("status") != ("LOCAL_UNVERIFIED" if local else "DOWNLOADED"):
            raise ValueError("Estado persistente inconsistente")
        if manifest.get("provenance_status") != (
            "UNVERIFIED_LOCAL" if local else "RECORDED_DOWNLOAD"
        ):
            raise ValueError("Procedencia inconsistente")
        if manifest.get("source_url") != (None if local else source_url(year, month)):
            raise ValueError("URL de origen inconsistente")
        for name in ("recorded_at_utc",) if local else ("recorded_at_utc", "downloaded_at_utc"):
            timestamp = datetime.fromisoformat(manifest[name])
            if timestamp.utcoffset() != UTC.utcoffset(None):
                raise ValueError("Timestamp operativo sin UTC")
        if local and manifest.get("downloaded_at_utc") is not None:
            raise ValueError("Fecha de descarga inventada para origen local")
        if (
            not isinstance(manifest.get("pipeline_version"), str)
            or not manifest["pipeline_version"]
        ):
            raise ValueError("Version del pipeline ausente")
        observed = describe_parquet(data)
        for key, value in observed.items():
            if type(manifest.get(key)) is not type(value) or manifest[key] != value:
                raise ValueError(f"Contenido divergente: {key}")
        return manifest
    except (OSError, ValueError, KeyError, TypeError, IngestionError) as error:
        raise IngestionConflict(f"Manifiesto/archivo inconsistentes: {error}") from error


def publish_file(staged: Path, destination: Path) -> None:
    """Hard link atomico sin clobber; origen y destino estan en el mismo volumen."""
    try:
        os.link(staged, destination)
    except FileExistsError as error:
        raise IngestionConflict(f"El destino ya existe: {destination.name}") from error


def publish_manifest(destination: Path, manifest: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, suffix=".part", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        publish_file(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def append_event(directory: Path, event: dict) -> None:
    path = directory / "ingestion-events.jsonl"
    if path.is_symlink():
        raise IngestionConflict("El log de ingesta no puede ser un enlace simbolico")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"observed_at_utc": utc_now(), **event}, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
