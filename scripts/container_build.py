"""Descargas binarias fijadas por hash para T23; no instala en el host."""

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

TRANSFER_LIMIT = 2 * 1024**3


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download_file(info: dict, folder: Path) -> str:
    filename = info["filename"]
    parsed = urlsplit(info["url"])
    if (
        Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
        or parsed.scheme != "https"
        or parsed.hostname not in ("files.pythonhosted.org", "deb.debian.org")
        or parsed.username
        or parsed.password
        or type(info["size_bytes"]) is not int
        or not 0 < info["size_bytes"] <= TRANSFER_LIMIT
    ):
        raise ValueError("Artefacto fuera del perfil de descarga")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    if target.exists():
        if target.stat().st_size != info["size_bytes"] or sha256(target) != info["sha256"]:
            raise ValueError("Artefacto existente divergente")
        return "SKIPPED"
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            received = 0
            with urlopen(info["url"], timeout=30) as response:
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > info["size_bytes"]:
                        raise ValueError("Descarga excede el tamano fijado")
                    stream.write(chunk)
            stream.flush()
            stream.close()
            if received != info["size_bytes"] or sha256(temporary) != info["sha256"]:
                raise ValueError("Tamano o hash de descarga no coincide")
            os.link(temporary, target)  # No reemplazar un destino concurrente.
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)
    return "DOWNLOADED"


def preflight(root: Path, *, profile="local") -> None:
    minimum = {"local": 50, "ci": 10}[profile]
    if shutil.disk_usage(root).free < minimum * 1024**3:
        raise ValueError(f"Se requieren {minimum} GiB de disco libre para {profile}")


def check_ci_limits(cgroup=Path("/sys/fs/cgroup")) -> None:
    memory = (cgroup / "memory.max").read_text().strip()
    quota, period = (cgroup / "cpu.max").read_text().split()
    if memory != str(4 * 1024**3) or quota == "max" or int(quota) / int(period) != 2:
        raise ValueError("CI requiere limites efectivos de build: 4 GiB y 2 CPU")


def fetch(kind: str, folder: Path, *, root=Path(".")) -> dict:
    wheels = json.loads((root / "configs/container-wheels-linux.json").read_text())
    system = json.loads((root / "configs/container-system-packages.json").read_text())
    total = wheels["base_and_wheels_transfer_bytes"] + sum(
        info["size_bytes"] for info in system["packages"]
    )
    if total > TRANSFER_LIMIT or wheels["transfer_limit_bytes"] != TRANSFER_LIMIT:
        raise ValueError("Presupuesto de transferencia excedido")
    entries = list(wheels["wheels"].values()) if kind == "wheels" else system["packages"]
    statuses = [download_file(info, folder) for info in entries]
    return {"files": len(statuses), "skipped": statuses.count("SKIPPED"), "profile_bytes": total}


def fetch_monitoring(folder: Path, *, root=Path(".")) -> dict:
    baseline = json.loads((root / "configs/container-wheels-linux.json").read_text())
    monitoring = json.loads((root / "configs/monitoring-wheels-linux.json").read_text())
    system = json.loads((root / "configs/container-system-packages.json").read_text())
    if any(
        monitoring["wheels"].get(name) != info
        for name, info in baseline["wheels"].items()
        if name != "pandas"
    ):
        raise ValueError("Monitoreo no puede cambiar artefactos compartidos de serving")
    if (
        monitoring.get("scope") != "EVIDENTLY_RENDERER_ONLY_NOT_MODEL_RUNTIME"
        or monitoring["wheels"]["pandas"].get("version") != "2.3.3"
    ):
        raise ValueError("Excepcion pandas limitada al renderer aprobado")
    additional = [
        info
        for name, info in monitoring["wheels"].items()
        if name not in baseline["wheels"] or name == "pandas"
    ]
    total = (
        baseline["base_and_wheels_transfer_bytes"]
        + sum(info["size_bytes"] for info in system["packages"])
        + sum(info["size_bytes"] for info in additional)
        + json.loads((root / "configs/ci-tools-linux.json").read_text())["ruff"]["size_bytes"]
    )
    if total > TRANSFER_LIMIT:
        raise ValueError("Presupuesto de imagen con monitoreo excedido")
    statuses = [download_file(info, folder) for info in monitoring["wheels"].values()]
    return {"files": len(statuses), "skipped": statuses.count("SKIPPED"), "profile_bytes": total}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", choices=("wheels", "system"))
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--fetch-monitoring", action="store_true")
    parser.add_argument("--profile", choices=("local", "ci"), default="local")
    args = parser.parse_args()
    if args.preflight:
        preflight(Path.cwd(), profile=args.profile)
        if args.profile == "ci":
            check_ci_limits()
        print("PREFLIGHT_PASS")
    elif args.fetch and args.destination:
        print(json.dumps(fetch(args.fetch, args.destination)))
    elif args.fetch_monitoring and args.destination:
        print(json.dumps(fetch_monitoring(args.destination)))
    else:
        parser.error("Usar --preflight o --fetch con --destination")


if __name__ == "__main__":
    main()
