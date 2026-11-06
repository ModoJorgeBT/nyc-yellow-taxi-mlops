"""Prueba T18: registro, reinicio propio, carga y persistencia sin promocion."""

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from src.training.native_supervisor import process_alive, process_peak_rss, worker_identity
from src.training.tracking import read_object, register_candidates, verify_registry


@contextmanager
def owned_server(config, root, *, test_only=False):
    """Solo detener el arbol que identifica nuestro proceso lanzado por token."""
    profile = read_object(config)
    port = urlparse(profile["tracking_uri"]).port
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    cache = root / ".cache/tracking-server"
    cache.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    identity = cache / f"{token}.json"
    log = cache / f"{token}.log"
    command = [
        sys.executable,
        str(Path(__file__).with_name("mlflow_server.py").resolve()),
        "--config",
        str(config.resolve()),
        "--root",
        str(root.resolve()),
        "--identity-file",
        str(identity.resolve()),
        "--identity-token",
        token,
    ]
    if test_only:
        command.append("--test-only")
    environment = {
        **os.environ,
        "MLFLOW_DISABLE_AGENT_HINT": "1",
        "PYTHONUTF8": "1",
        "MLFLOW_HTTP_REQUEST_TIMEOUT": "15",
        "MLFLOW_HTTP_REQUEST_MAX_RETRIES": "0",
        "OMP_NUM_THREADS": "4",
        "OPENBLAS_NUM_THREADS": "4",
        "MKL_NUM_THREADS": "4",
    }
    pid = None
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            command,
            stdout=output,
            stderr=subprocess.STDOUT,
            env=environment,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Servidor no inicio; revisar {log}")
                if identity.exists():
                    pid = worker_identity((identity, None, token), process.pid)
                    try:
                        with urlopen(profile["tracking_uri"] + "/health", timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        pass
                time.sleep(0.1)
            else:
                raise RuntimeError(f"Timeout del servidor; revisar {log}")
            print(json.dumps({"phase": "server_ready", "pid": pid, "log": str(log)}), flush=True)
            server_info = {"pid": pid, "log": str(log), "identity": str(identity)}
            yield server_info
            # El PID proviene exclusivamente del log de nuestro servidor ya identificado.
            workers = re.findall(
                r"Started server process \[(\d+)\]", log.read_text(encoding="utf-8")
            )
            if len(workers) != 1:
                raise ValueError("No se pudo identificar el único worker HTTP propio")
            server_info["http_worker_pid"] = int(workers[0])
            server_info["http_worker_peak_rss_bytes"] = process_peak_rss(int(workers[0]))
        finally:
            if pid is None and identity.exists():
                pid = worker_identity((identity, None, token), process.pid)
            if pid is not None and process_alive(pid):
                assert worker_identity((identity, None, token), process.pid) == pid
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"], check=True, capture_output=True
                    )
                else:
                    os.killpg(pid, signal.SIGTERM)
            process.wait(timeout=15)


def smoke(config, root, *, test_only=False):
    config, root = Path(config).resolve(), Path(root).resolve()
    profile = read_object(config)
    with owned_server(config, root, test_only=test_only) as first:
        receipt = register_candidates(config, root=root, test_only=test_only)
        print(
            json.dumps(
                {
                    "phase": "four_candidates_registered",
                    "versions": {
                        family: row["version"] for family, row in receipt["models"].items()
                    },
                }
            ),
            flush=True,
        )
    database = root / "tracking/mlflow.db"
    if not database.is_file():
        raise ValueError("SQLite persistente no existe")
    with owned_server(config, root, test_only=test_only) as second:
        verify_registry(receipt, profile, root)
        reused = register_candidates(config, root=root, test_only=test_only)
        if reused != receipt:
            raise ValueError("Reinicio duplico o cambio los registros")
        from mlflow import MlflowClient

        client = MlflowClient(tracking_uri=profile["tracking_uri"])
        versions = client.search_model_versions(f"name = '{profile['registered_model_name']}'")
        runs = client.search_runs(
            [client.get_experiment_by_name(profile["experiment_name"]).experiment_id]
        )
        if len(versions) != 4 or len(runs) != 4:
            raise ValueError("Se esperaban cuatro runs y versiones sin duplicados")
    result = {
        "status": "TRACKING_PERSISTENCE_TEST_ONLY" if test_only else "TRACKING_PERSISTENCE_REAL",
        "first_server": first,
        "restarted_server": second,
        "same_runs_and_versions": True,
        "registry_models_verified": len(receipt["models"]),
        "champion_assigned": False,
        "server_stopped_after_smoke": True,
        "receipt": receipt,
    }
    target = (
        root / "reports/tracking" / ("_test_only" if test_only else "real") / "persistence.json"
    )
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/tracking.yaml"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    result = smoke(args.config, args.root, test_only=args.test_only)
    print(json.dumps({"status": result["status"], "verified": result["registry_models_verified"]}))


if __name__ == "__main__":
    main()
