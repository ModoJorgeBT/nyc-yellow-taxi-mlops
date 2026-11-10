"""Subproceso identificado para Evidently, separado del runtime del champion."""

import os
import sys
import uuid
from pathlib import Path

from src.monitoring.protocol import RESOURCES, inside, pinned
from src.training.native_supervisor import supervise
from src.validation.run import _sha256


def render_report(config, root, output, guard):
    test_only = config["status"] == "TEST_ONLY"
    if test_only:
        interpreter = Path(sys.executable)
    else:
        key = "windows" if os.name == "nt" else "linux"
        interpreter = inside(root, config["renderer_python"][key])
        if interpreter.resolve() == Path(sys.executable).resolve():
            raise ValueError("Renderer real debe usar el entorno aislado aprobado")
    if not interpreter.is_file():
        raise ValueError("Falta el entorno del renderer")
    token = uuid.uuid4().hex
    identity, ready = output / "renderer.pid.json", output / "renderer.ready"
    source = output / "drift.json"
    command = [
        str(interpreter),
        "-I",
        "-B",
        "-m",
        "src.monitoring.render_worker",
        "--input",
        str(source),
        "--input-sha256",
        _sha256(source),
        "--output",
        str(output),
        "--identity",
        str(identity),
        "--ready",
        str(ready),
        "--token",
        token,
    ]
    if test_only:
        command.append("--test-only")
    else:
        runtime = pinned(root, config["renderer_locks"][key])
        command.extend(["--runtime-lock", str(runtime), "--runtime-lock-sha256", _sha256(runtime)])
    return supervise(
        command,
        policy={**RESOURCES, "native_process_poll_seconds": 0.1},
        guard=guard,
        log_path=output / "renderer.log",
        env={**os.environ, "DO_NOT_TRACK": "1", "PYTHONUTF8": "1"},
        identity=(identity, ready, token),
        aggregate_parent_rss=True,
    )
