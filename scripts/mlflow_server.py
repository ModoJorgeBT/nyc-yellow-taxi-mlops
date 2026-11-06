"""Servidor T18 local; ejecutar desde la raiz con el entorno MLflow aprobado."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from src.training.tracking import read_object, verify_bundle, verify_runtime

# Configuracion local: no enviar telemetria de uso del SDK y logs UTF-8 en Windows.
os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
os.environ.setdefault("PYTHONUTF8", "1")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/tracking.yaml"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--identity-file", type=Path)
    parser.add_argument("--identity-token")
    args = parser.parse_args()
    profile = read_object(args.config)
    verify_bundle(profile, args.root, test_only=args.test_only)
    verify_runtime(profile)
    if bool(args.identity_file) != bool(args.identity_token):
        parser.error("La identidad requiere ruta y token")
    if args.identity_file:
        args.identity_file.write_text(
            json.dumps(
                {"pid": os.getpid(), "parent_pid": os.getppid(), "token": args.identity_token}
            ),
            encoding="utf-8",
        )
    (args.root / "tracking/artifacts").mkdir(parents=True, exist_ok=True)
    # SQLite explicito evita heredar un FileStore existente por defecto.
    from urllib.parse import urlparse

    port = urlparse(profile["tracking_uri"]).port
    command = [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--workers",
        "1",
        "--backend-store-uri",
        "sqlite:///tracking/mlflow.db",
        "--registry-store-uri",
        "sqlite:///tracking/mlflow.db",
        "--serve-artifacts",
        "--artifacts-destination",
        "tracking/artifacts",
        "--allowed-hosts",
        f"127.0.0.1:{port},localhost:{port}",
    ]
    subprocess.run(command, cwd=args.root, check=True)


if __name__ == "__main__":
    main()
