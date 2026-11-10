"""Wrapper identificado de servicios de prueba/serving gestionado, sin ventanas GUI."""

import argparse
import os
import subprocess
import sys
from functools import partial
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--kind", choices=["mlflow", "api"], required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--active", type=Path)
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    from src.retraining.lifecycle import local_uri
    from src.retraining.protocol import exclusive_json, read_json

    local_uri(f"http://127.0.0.1:{args.port}", test_only=True)
    if not args.identity.resolve().is_relative_to(args.root.resolve()):
        raise ValueError("Identidad fuera de raiz")
    if args.test_only and read_json(args.root / "ISOLATED_DEMO.json").get("status") != "TEST_ONLY":
        raise ValueError("Falta aislamiento")
    exclusive_json(
        args.identity, {"pid": os.getpid(), "parent_pid": os.getppid(), "token": args.token}
    )
    if args.kind == "mlflow":
        if not args.test_only:
            raise ValueError("No arrancar otro Registry real desde el demo")
        uri = "sqlite:///" + (args.root / "tracking/mlflow.db").as_posix()
        (args.root / "tracking/artifacts").mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "mlflow",
                "server",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.port),
                "--workers",
                "1",
                "--backend-store-uri",
                uri,
                "--registry-store-uri",
                uri,
                "--serve-artifacts",
                "--artifacts-destination",
                str(args.root / "tracking/artifacts"),
                "--allowed-hosts",
                f"127.0.0.1:{args.port},localhost:{args.port}",
            ],
            check=True,
            cwd=args.root,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    else:
        import uvicorn

        from src.api.main import create_app
        from src.api.model_loader import load_champion

        loader = partial(load_champion, config=args.active, test_only=args.test_only)
        uvicorn.run(
            create_app(root=args.root, loader=loader),
            host="127.0.0.1",
            port=args.port,
            workers=1,
            access_log=False,
            log_level="error",
        )


if __name__ == "__main__":
    main()
