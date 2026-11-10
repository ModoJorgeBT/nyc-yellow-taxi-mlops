"""Bootstrap stdlib: esperar supervision RSS antes de importar Evidently/pandas."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "input-sha256", "output", "identity", "ready", "token"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--runtime-lock")
    parser.add_argument("--runtime-lock-sha256")
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    identity, ready = Path(args.identity), Path(args.ready)
    temporary = identity.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"pid": os.getpid(), "parent_pid": os.getppid(), "token": args.token}),
        encoding="utf-8",
    )
    temporary.replace(identity)
    deadline = time.monotonic() + 30
    while True:
        try:
            token = ready.read_text(encoding="utf-8")
        except FileNotFoundError, PermissionError:
            if time.monotonic() >= deadline:
                raise RuntimeError("Renderer sin supervision autorizada") from None
            time.sleep(0.01)
            continue
        if token != args.token:
            raise ValueError("Token de renderer no coincide")
        break
    os.environ["DO_NOT_TRACK"] = "1"
    if not args.test_only:
        if not args.runtime_lock or not args.runtime_lock_sha256:
            raise ValueError("Renderer sin lock aprobado")
        lock = Path(args.runtime_lock).read_bytes()
        if hashlib.sha256(lock).hexdigest() != args.runtime_lock_sha256:
            raise ValueError("Lock del renderer alterado")
        versions = re.findall(
            r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", lock.decode("utf-8"), re.MULTILINE
        )
        if not versions:
            raise ValueError("Lock del renderer vacio")
        for name, expected in versions:
            if importlib.metadata.version(name) != expected:
                raise ValueError(f"Version renderer fuera de lock: {name}")
    if (
        importlib.metadata.version("evidently") != "0.7.23"
        or importlib.metadata.version("pandas") != "2.3.3"
    ):
        raise ValueError("Runtime del renderer distinto del aprobado")
    source = Path(args.input)
    content = source.read_bytes()
    if hashlib.sha256(content).hexdigest() != args.input_sha256:
        raise ValueError("Agregados cambiaron antes del renderer")
    from src.monitoring.evidently_adapter import render

    render(json.loads(content), Path(args.output))
    if hashlib.sha256(source.read_bytes()).hexdigest() != args.input_sha256:
        raise ValueError("Agregados cambiaron durante el renderer")


if __name__ == "__main__":
    main()
