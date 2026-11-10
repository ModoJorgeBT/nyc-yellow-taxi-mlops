"""T26: checks reproducibles con fixtures, sin datos ni Registry reales."""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def main():
    os.environ["MLFLOW_DISABLE_TELEMETRY"] = "true"
    os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
    os.environ["MLFLOW_SERVER_ENABLE_JOB_EXECUTION"] = "false"
    root = Path.cwd()
    if list((root / "data/raw").rglob("*.parquet")) or (root / "tracking/mlflow.db").exists():
        raise ValueError("CI exige checkout aislado sin datasets/Registry reales")
    (root / ".cache").mkdir(exist_ok=True)
    for command in (
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "pip", "check"],
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--maxfail=1",
            "--basetemp=.cache/ci-pytest",
            "-o",
            "cache_dir=.cache/ci-pytest-cache",
        ],
    ):
        subprocess.run(command, check=True, timeout=900)
    import uvicorn

    # El checkout no tiene recibo aplicado: HTTP real debe dar 503, nunca prediccion ficticia.
    from smoke_api import smoke

    from src.api.main import create_app

    server = uvicorn.Server(
        uvicorn.Config(
            create_app(root=root), host="127.0.0.1", port=0, access_log=False, log_level="error"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 30
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Smoke API no inicio")
            time.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        approval = json.loads((root / "configs/champion.yaml").read_text(encoding="utf-8"))
        result = smoke(f"http://127.0.0.1:{port}", approval, unavailable=True)
        assert result["status"] == "PASS"
    finally:
        server.should_exit = True
        thread.join(10)
        if thread.is_alive():
            raise RuntimeError("Smoke API no cerro su servidor propio")
    print(
        json.dumps(
            {
                "status": "CI_LOCAL_PASS",
                "datasets_downloaded": False,
                "real_models_fitted": False,
                "api_503_smoke": "PASS",
            }
        )
    )


if __name__ == "__main__":
    main()
