"""Descarga mensual TLC y registro local explicito, sin sobrescrituras."""

import argparse
import json
import logging
import math
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.client import HTTPException
from pathlib import Path

from src.ingestion.manifest import (
    IngestionConflict,
    IngestionError,
    append_event,
    describe_parquet,
    make_manifest,
    publish_file,
    publish_manifest,
    read_and_verify,
    source_url,
)

LOGGER = logging.getLogger(__name__)


@contextmanager
def month_lock(directory: Path):
    path = directory / ".ingestion.lock"
    try:
        stream = path.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise IngestionConflict("El lote esta bloqueado; revisar .ingestion.lock") from error
    try:
        with stream:
            stream.write(str(os.getpid()))
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        path.unlink(missing_ok=True)


def fetch(url: str, directory: Path, *, timeout: float) -> Path:
    """Un intento, en bloques de 1 MiB y con temporal propio limpiado ante fallo."""
    temporary = None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "nyc-yellow-taxi-mlops/0.1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise IngestionError(f"HTTP inesperado: {response.status}")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or int(length) < 0):
                raise IngestionError("Content-Length invalido")
            with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as stream:
                temporary = Path(stream.name)
                received = 0
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
                    received += len(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if length is not None and received != int(length):
                raise HTTPException("Descarga truncada: Content-Length no coincide")
        return temporary
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _download_new(url: str, directory: Path, *, timeout: float, retries: int) -> Path:
    for attempt in range(retries + 1):
        try:
            return fetch(url, directory, timeout=timeout)
        except urllib.error.HTTPError as error:
            error.close()
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == retries:
                raise IngestionError(f"Descarga fallida: HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError, HTTPException) as error:
            if attempt == retries:
                raise IngestionError("Descarga fallida: agotados los reintentos de red") from error
        LOGGER.warning("Reintento de descarga %s/%s", attempt + 1, retries)
        time.sleep(0.25 * 2**attempt)
    raise AssertionError("Bucle de reintentos inalcanzable")


def ingest(
    year: int,
    month: int,
    *,
    raw_dir: Path = Path("data/raw"),
    timeout: float = 30,
    retries: int = 2,
    expected_sha256: str | None = None,
    register_local: bool = False,
) -> dict:
    """Ingiere un lote o verifica el existente; la calidad se evalua en T08/T09."""
    url = source_url(year, month)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout debe ser positivo y finito")
    if type(retries) is not int or not 0 <= retries <= 5:
        raise ValueError("retries debe ser entero entre 0 y 5")
    if expected_sha256 is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
        raise ValueError("expected_sha256 debe tener 64 digitos hexadecimales")
    root = raw_dir.resolve()
    directory = root / f"{year:04}" / f"{month:02}"
    if not directory.resolve().is_relative_to(root):
        raise IngestionConflict("El destino resuelto esta fuera de raw")
    directory.mkdir(parents=True, exist_ok=True)
    data = directory / f"yellow_tripdata_{year:04}-{month:02}.parquet"
    manifest_path = directory / "manifest.json"
    staged = None
    with month_lock(directory):
        try:
            if data.is_symlink() or manifest_path.is_symlink():
                raise IngestionConflict("Datos y manifiestos no pueden ser enlaces simbolicos")
            if manifest_path.exists():
                if not data.is_file():
                    raise IngestionConflict("Manifiesto sin archivo de datos")
                manifest = read_and_verify(manifest_path, data, year, month)
                status = "SKIPPED"
            elif data.exists():
                if not register_local:
                    raise IngestionConflict(
                        "Archivo sin manifiesto; usar --register-local para procedencia pendiente"
                    )
                description = describe_parquet(data)
                if expected_sha256 and description["sha256"] != expected_sha256.lower():
                    raise IngestionConflict("SHA-256 local distinto del esperado")
                manifest = make_manifest(year, month, description, local=True)
                publish_manifest(manifest_path, manifest)
                status = "REGISTERED_LOCAL_UNVERIFIED"
            else:
                if register_local:
                    raise IngestionConflict("--register-local requiere un Parquet local existente")
                staged = _download_new(url, directory, timeout=timeout, retries=retries)
                description = describe_parquet(staged)
                if expected_sha256 and description["sha256"] != expected_sha256.lower():
                    raise IngestionConflict("SHA-256 descargado distinto del esperado")
                manifest = make_manifest(year, month, description, local=False)
                publish_file(staged, data)
                publish_manifest(manifest_path, manifest)
                status = "DOWNLOADED"
            if expected_sha256 and manifest["sha256"] != expected_sha256.lower():
                raise IngestionConflict("SHA-256 del lote existente distinto del esperado")
            result = {
                "status": status,
                "manifest_status": manifest["status"],
                "provenance_status": manifest["provenance_status"],
                "year": year,
                "month": month,
                "sha256": manifest["sha256"],
                "data_path": data.as_posix(),
                "manifest_path": manifest_path.as_posix(),
            }
            append_event(directory, {"status": status, "sha256": manifest["sha256"]})
            return result
        except (IngestionError, OSError, ValueError) as error:
            append_event(directory, {"status": "FAILED", "reason": str(error)})
            raise
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--register-local", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = ingest(
            args.year,
            args.month,
            raw_dir=args.raw_dir,
            timeout=args.timeout,
            retries=args.retries,
            expected_sha256=args.expected_sha256,
            register_local=args.register_local,
        )
    except (IngestionError, OSError, ValueError) as error:
        parser.exit(1, f"Ingesta fallida: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
