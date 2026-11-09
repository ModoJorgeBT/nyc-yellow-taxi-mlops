"""T24: no iniciar un Registry vacio silenciosamente en el volumen Docker."""

import os
import sys
from pathlib import Path

from prepare_compose import audit_volume


def main():
    audit_volume(Path("tracking"))
    port = int(os.environ.get("DOCKER_MLFLOW_PORT", "5001"))
    if not 1 <= port <= 65535:
        raise ValueError("Puerto publico no valido")
    hosts = f"mlflow:5000,127.0.0.1:5000,localhost:5000,127.0.0.1:{port},localhost:{port}"
    args = [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--host",
        "0.0.0.0",
        "--port",
        "5000",
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
        hosts,
    ]
    os.execv(sys.executable, args)


if __name__ == "__main__":
    main()
