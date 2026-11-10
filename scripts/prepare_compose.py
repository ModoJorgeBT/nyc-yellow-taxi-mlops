"""T24: copia consistente y aislada del Registry local, sin modificar su origen."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def database_snapshot(connection) -> str:
    # SQLite 3.40 y 3.50 formatean doubles de iterdump de modo distinto.
    # Hex conserva exactamente el IEEE-754, sin redondear metricas.
    def value(item):
        if isinstance(item, float):
            return ["float", item.hex()]
        if isinstance(item, bytes):
            return ["blob", item.hex()]
        return [type(item).__name__, item]

    schema = sorted(connection.execute("select type,name,tbl_name,sql from sqlite_master"))
    content = []
    for kind, name, _, _ in schema:
        if kind != "table":
            continue
        quoted = '"' + name.replace('"', '""') + '"'
        rows = [
            json.dumps([value(item) for item in row], separators=(",", ":"), allow_nan=False)
            for row in connection.execute(f"select * from {quoted}")
        ]
        content.append([name, sorted(rows)])
    encoded = json.dumps([schema, content], separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def files(directory: Path) -> dict:
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("No se admiten enlaces en el estado de tracking")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = digest(path)
    return result


def prepare(root: Path, destination: Path) -> dict:
    root, destination = root.resolve(), destination.resolve()
    source = (root / "tracking").resolve()
    if (
        not source.is_relative_to(root)
        or not destination.is_relative_to(root / ".cache")
        or destination == root / ".cache"
        or destination.is_relative_to(source)
    ):
        raise ValueError("La copia debe estar aislada bajo .cache del proyecto")
    if destination.exists():
        raise ValueError("Destino existente: conservarlo, no reinicializar ni sobrescribir")
    approval = json.loads((root / "configs/champion.yaml").read_text(encoding="utf-8"))
    target = approval["target"]
    if approval["approval_status"] != "APPROVED" or target["version"] != "4":
        raise ValueError("No hay champion inicial aprobado")
    approval_sha = hashlib.sha256(
        json.dumps(approval, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    applied = source / "approvals" / f"{approval_sha}.applied.json"
    receipt = json.loads(applied.read_text(encoding="utf-8"))
    if receipt["status"] != "CHAMPION_APPROVED_REAL" or receipt["target"] != target:
        raise ValueError("Recibo aplicado no coincide")
    source_files = {
        **{f"artifacts/{k}": v for k, v in files(source / "artifacts").items()},
        **{f"approvals/{k}": v for k, v in files(source / "approvals").items()},
    }
    if not source_files:
        raise ValueError("No hay artefactos/recibos que copiar")
    database = sqlite3.connect(f"file:{(source / 'mlflow.db').as_posix()}?mode=ro", uri=True)
    try:
        if (
            database.execute("select count(*) from runs").fetchone()[0] != 4
            or database.execute("select count(*) from model_versions").fetchone()[0] != 4
            or database.execute(
                "select name,alias,version from registered_model_aliases"
            ).fetchall()
            != [(target["name"], "champion", 4)]
        ):
            raise ValueError("Registry no coincide con la entrega aprobada")
        before = database_snapshot(database)
        destination.mkdir(parents=True, exist_ok=False)
        # Si falla una copia se conserva el destino incompleto; no publicamos marcador.
        with closing(sqlite3.connect(destination / "mlflow.db")) as copied:
            database.backup(copied)
            if database_snapshot(copied) != before:
                raise ValueError("Backup SQLite divergente")
        shutil.copytree(source / "artifacts", destination / "artifacts")
        shutil.copytree(source / "approvals", destination / "approvals")
        for relative, expected in source_files.items():
            if digest(destination / relative) != expected or digest(source / relative) != expected:
                raise ValueError("Artefacto/recibo modificado durante la copia")
        if database_snapshot(database) != before:
            raise ValueError("Registry cambio durante la copia; revisar antes de usar")
    finally:
        database.close()
    result = {
        "status": "COMPOSE_SEED_VERIFIED",
        "snapshot_format": "typed-python-values-v2",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "original_registry_modified": False,
        "registry_logical_sha256": before,
        "registry_runs": 4,
        "registry_versions": 4,
        "champion_version": "4",
        "approval_sha256": approval_sha,
        "files": files(destination),
    }
    (destination / "compose-seed.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def import_seed(seed: Path, destination: Path) -> dict:
    """Inicializa un volumen Linux vacio; nunca reescribe un Registry existente."""
    seed, destination = seed.resolve(), destination.resolve()
    marker = seed / "compose-seed.json"
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    if metadata.get("status") != "COMPOSE_SEED_VERIFIED":
        raise ValueError("Seed no verificado")
    expected = metadata["files"]
    if files(seed) != {**expected, "compose-seed.json": digest(marker)}:
        raise ValueError("Seed modificado desde su preparacion")
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        previous = destination / "compose-seed.json"
        if previous.is_file() and digest(previous) == digest(marker):
            return {"status": "SKIPPED", "existing_registry_overwritten": False}
        raise ValueError("Volumen no vacio o incompleto: no se sobrescribe")
    for relative, checksum in expected.items():
        target = (destination / relative).resolve()
        if not target.is_relative_to(destination) or target == destination:
            raise ValueError("Ruta de seed fuera del volumen")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed / relative, target)
        if digest(target) != checksum:
            raise ValueError("Copia al volumen divergente")
    shutil.copyfile(marker, destination / "compose-seed.json")  # Publicar al final.
    return {"status": "VOLUME_INITIALIZED", "existing_registry_overwritten": False}


def audit_volume(directory: Path) -> dict:
    metadata = json.loads((directory / "compose-seed.json").read_text(encoding="utf-8"))
    for relative, checksum in metadata["files"].items():
        if relative != "mlflow.db" and digest(directory / relative) != checksum:
            raise ValueError("Artefacto o recibo del volumen divergente")
    with closing(
        sqlite3.connect(f"file:{(directory / 'mlflow.db').as_posix()}?mode=ro", uri=True)
    ) as db:
        if database_snapshot(db) != metadata["registry_logical_sha256"]:
            raise ValueError("Contenido logico del Registry cambio")
    return {"status": "PERSISTENCE_VERIFIED", "registry_runs": 4, "champion_version": "4"}


def upgrade_snapshot(directory: Path, expected: str | None = None) -> dict:
    """Migra solo metadatos de auditoria, exigiendo bytes DB/artefactos intactos."""
    marker = directory / "compose-seed.json"
    old = marker.read_bytes()
    metadata = json.loads(old)
    if metadata.get("snapshot_format") == "typed-python-values-v2":
        audit_volume(directory)
        return {"status": "SKIPPED", "portable_sha256": metadata["registry_logical_sha256"]}
    for relative, checksum in metadata["files"].items():
        if digest(directory / relative) != checksum:
            raise ValueError("No migrar metadatos: bytes originales divergentes")
    with closing(
        sqlite3.connect(f"file:{(directory / 'mlflow.db').as_posix()}?mode=ro", uri=True)
    ) as db:
        portable = database_snapshot(db)
    if expected is not None and portable != expected:
        raise ValueError("Valores tipados diferentes entre Windows y Linux")
    legacy = directory / "compose-seed-v1.json"
    if legacy.exists() and legacy.read_bytes() != old:
        raise ValueError("Evidencia legacy divergente")
    legacy.write_bytes(old)
    metadata["files"][legacy.name] = digest(legacy)
    metadata["legacy_sql_dump_sha256"] = metadata["registry_logical_sha256"]
    metadata["registry_logical_sha256"] = portable
    metadata["snapshot_format"] = "typed-python-values-v2"
    data = json.dumps(metadata, sort_keys=True, indent=2, allow_nan=False).encode()
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    os.replace(temporary, marker)
    return {
        "status": "AUDIT_METADATA_UPGRADED",
        "portable_sha256": portable,
        "database_modified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--destination", type=Path, default=Path(".cache/compose-state/tracking"))
    parser.add_argument("--import-seed", type=Path)
    parser.add_argument("--volume-root", type=Path, default=Path("/app/tracking"))
    parser.add_argument("--audit-volume", type=Path)
    parser.add_argument("--upgrade-snapshot", type=Path)
    parser.add_argument("--expected-portable")
    args = parser.parse_args()
    if args.upgrade_snapshot:
        result = upgrade_snapshot(args.upgrade_snapshot, args.expected_portable)
    elif args.import_seed:
        result = import_seed(args.import_seed, args.volume_root)
    elif args.audit_volume:
        result = audit_volume(args.audit_volume)
    else:
        result = prepare(args.root, args.destination)
        result = {k: result[k] for k in ("status", "registry_runs", "champion_version")}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
