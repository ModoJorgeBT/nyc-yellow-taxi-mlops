"""T37: export sin datos/secretos, venv limpio y wheels exactos offline."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import venv
from pathlib import Path


def tool_lock(root):
    content = (root / "requirements-dev.lock").read_text(encoding="utf-8")
    blocks = re.split(r"(?=^[a-zA-Z0-9_.-]+==)", content, flags=re.MULTILINE)
    selected = [b for b in blocks if b.split("==", 1)[0] in {"pip", "ruff", "setuptools", "wheel"}]
    if len(selected) != 4:
        raise ValueError("No se encontraron las cuatro herramientas aprobadas")
    return "# Solo herramientas ya aprobadas; extraidas del lock historico.\n" + "\n".join(selected)


def export(root, destination):
    destination = Path(destination).resolve()
    if destination == root or not destination.is_relative_to(root):
        raise ValueError("Export requiere subdirectorio nuevo")
    destination.mkdir(parents=True, exist_ok=False)
    # Excepcion solo para esta lectura y raiz explicita; no cambia config global.
    git = ["git", "-c", f"safe.directory={root}"]
    tracked = set(
        subprocess.check_output([*git, "ls-files", "-z"], cwd=root).decode("utf-8").split("\0")
    )
    paths = set(
        subprocess.check_output(
            [*git, "ls-files", "-c", "-m", "-o", "--exclude-standard", "-z"], cwd=root
        )
        .decode("utf-8")
        .split("\0")
    )
    manifest = {}
    for name in sorted(paths):
        if not name:
            continue
        path = Path(name)
        allowed_dirs = {
            "src",
            "tests",
            "scripts",
            "configs",
            "docs",
            "reports",
            ".github",
            "notebooks",
        }
        allowed_root = {
            "Dockerfile",
            "docker-compose.yml",
            "Makefile",
            "pyproject.toml",
            ".gitignore",
            ".dockerignore",
            ".gitattributes",
            ".python-version",
            ".env.example",
        }
        if len(path.parts) > 1 and path.parts[0] not in allowed_dirs:
            continue
        if (
            len(path.parts) == 1
            and name not in allowed_root
            and path.suffix not in {".md", ".lock", ".in", ".pdf"}
        ):
            continue
        if any(part.startswith(".env") for part in path.parts) and name != ".env.example":
            continue
        if any(
            part in {".git", ".aws", "secrets", "__pycache__", ".cache"} or part.startswith(".venv")
            for part in path.parts
        ):
            continue
        if (root / path).is_symlink():
            raise ValueError("No exportar enlaces simbolicos")
        if name.startswith(
            (".git/", ".cache/", ".venv", "tracking/", "models/", "data/", ".aws/", "secrets/")
        ):
            continue
        if path.suffix in {
            ".db",
            ".sqlite",
            ".sqlite3",
            ".joblib",
            ".pkl",
            ".pickle",
            ".pem",
            ".key",
            ".onnx",
            ".pt",
            ".pth",
            ".h5",
            ".keras",
            ".bin",
        }:
            continue
        if path.suffix == ".pdf" and name not in tracked:
            continue
        if path.suffix == ".parquet" and (
            not name.startswith("tests/fixtures/") or (root / path).stat().st_size > 2**20
        ):
            continue
        if name.startswith("reports/") and path.suffix != ".md":
            continue
        source = (root / path).resolve()
        if not source.is_relative_to(root) or source.is_symlink():
            raise ValueError("Enlace fuera del export")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    for directory in [
        "data/raw",
        "data/validated",
        "data/processed",
        "tracking",
        "models",
        ".cache",
    ]:
        (destination / directory).mkdir(parents=True, exist_ok=True)
    (destination / "EXPORT_MANIFEST.json").write_text(
        json.dumps(
            {"kind": "UNCOMMITTED_WORKTREE_EXPORT_NOT_REMOTE_CLONE", "files": manifest}, indent=2
        ),
        encoding="utf-8",
    )
    return manifest


def reproduce(directory, *, root=None, run_tests=True):
    root = Path(root or Path.cwd()).resolve()
    directory = (root / directory).resolve()
    if directory == root or not directory.is_relative_to(root):
        raise ValueError("Destino fuera de workspace")
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / "source"
    manifest = export(root, source)
    (source / "requirements-repro-tools.lock").write_text(tool_lock(root), encoding="utf-8")
    environment = directory / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheel_dirs = [
        root / ".cache/t29-t31/wheels-windows",
        root / ".cache/wheels",
        root / ".cache/t18/wheels",
    ]
    links = [x for p in wheel_dirs if p.exists() for x in ("--find-links", str(p))]
    if not links:
        raise ValueError("No hay wheelhouse local; no se autoriza descargar")
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "PYTHONPATH",
            "PYTHONHOME",
            "PYTHONUTF8",
            "VIRTUAL_ENV",
            "CI",
            "MLFLOW_TRACKING_URI",
            "MLFLOW_REGISTRY_URI",
            "NYC_MLFLOW_TRACKING_URI",
        }
    }
    env.update(
        PIP_NO_INDEX="1",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
        MLFLOW_DISABLE_AGENT_HINT="1",
        MLFLOW_DISABLE_TELEMETRY="true",
        DO_NOT_TRACK="1",
        MLFLOW_SERVER_ENABLE_JOB_EXECUTION="false",
        GIT_CEILING_DIRECTORIES=str(directory),
    )

    def run(name, args, *, cwd=source, timeout=1200):
        with (directory / f"{name}.log").open("wb") as stream:
            result = subprocess.run(
                [str(python), *args],
                cwd=cwd,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        if result.returncode:
            raise RuntimeError(f"Reproduccion fallo en {name}; revisar log")

    for name, lock in [
        ("runtime", "requirements-serving.lock"),
        ("tools", "requirements-repro-tools.lock"),
    ]:
        run(
            name,
            [
                "-m",
                "pip",
                "--isolated",
                "install",
                "--no-index",
                "--no-deps",
                "--require-hashes",
                "--only-binary=:all:",
                *links,
                "-r",
                lock,
            ],
        )
    run(
        "wheel",
        [
            "-m",
            "pip",
            "--isolated",
            "wheel",
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(directory / "dist"),
            ".",
        ],
    )
    wheels = list((directory / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("Paquete exportado no es unico")
    run(
        "install", ["-m", "pip", "--isolated", "install", "--no-index", "--no-deps", str(wheels[0])]
    )
    run("dependencies", ["-m", "pip", "check"])
    run("ruff", ["-m", "ruff", "check", "."])
    run("format", ["-m", "ruff", "format", "--check", "."])
    if run_tests:
        run(
            "pytest",
            [
                "-m",
                "pytest",
                "-q",
                "--maxfail=1",
                "--junitxml=.cache/reproduction-junit.xml",
                "--basetemp=.cache/reproduction-tests",
                "-o",
                "cache_dir=.cache/reproduction-pytest-cache",
            ],
        )
    result = {
        "status": "ISOLATED_REPRODUCTION_PASS",
        "scope": "AUTOMATED_NOT_HUMAN_REVIEW",
        "files": len(manifest),
        "new_external_downloads": 0,
        "real_datasets_or_models_exported": False,
        "tests_executed": run_tests,
        "wheel_sha256": hashlib.sha256(wheels[0].read_bytes()).hexdigest(),
        "derived_tools_lock_sha256": hashlib.sha256(
            (source / "requirements-repro-tools.lock").read_bytes()
        ).hexdigest(),
        "human_cross_review": "NOT_VERIFIED",
        "academic_defense": "NOT_VERIFIED",
    }
    (directory / "reproduction-result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--without-tests", action="store_true")
    args = parser.parse_args()
    reproduce(args.output_dir, run_tests=not args.without_tests)


if __name__ == "__main__":
    main()
