"""Contrato aprobado T29-T31: fuentes congeladas, lectura acotada y salidas propias."""

import json
import time
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from src.features.schema import FEATURE_COLUMNS
from src.training.resources import ResourceGuard, ResourceLimitError
from src.validation.run import _sha256
from src.validation.schema import fingerprint

POLICY = {
    "reference_year": 2024,
    "current_year": 2025,
    "current_months": [7, 8, 9, 10, 11, 12],
    "psi_threshold": 0.2,
    "smoothing_alpha": 0.5,
    "minimum_rows": 1000,
    "label_maturity_hours": 24,
    "automatic_retraining": False,
    "automatic_promotion": False,
}
RESOURCES = {
    "preflight_min_free_ram_gib": 4,
    "process_rss_limit_gib": 2,
    "preflight_min_free_disk_gib": 50,
    "threads_total": 4,
    "candidate_timeout_seconds": 7200,
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inside(root, name):
    path = (Path(root) / name).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("Fuente/salida fuera del proyecto de monitoreo")
    return path


def pinned(root, entry):
    path = inside(root, entry["path"])
    if not path.is_file() or path.is_symlink() or _sha256(path) != entry["sha256"]:
        raise ValueError("Fuente congelada alterada o ausente")
    return path


def load_config(path, *, test_only=False):
    config = read_json(path)
    if (
        config.get("status") != ("TEST_ONLY" if test_only else "APPROVED")
        or config.get("protocol") != "monthly-full-replay-v1"
        or config.get("policy") != POLICY
        or config.get("resources") != RESOURCES
        or config.get("feature_columns") != list(FEATURE_COLUMNS)
        or (test_only and config.get("fixture_origin") != "synthetic")
    ):
        raise ValueError("Protocolo de monitoreo no aprobado para este ambito")
    return config


class MonitorGuard(ResourceGuard):
    def __init__(self, root, *, test_only=False):
        super().__init__(RESOURCES, root, test_only=test_only)
        self.started = time.monotonic()

    def check(self, *, start=False):
        super().check(start=start)
        if time.monotonic() - self.started > RESOURCES["candidate_timeout_seconds"]:
            raise ResourceLimitError("D-02: timeout de monitoreo; no ampliar presupuesto")

    def evidence(self):
        return {
            "initial": self.initial,
            "final": self.last,
            "elapsed_seconds": time.monotonic() - self.started,
            "policy": self.policy,
        }


def source_manifest(config, root):
    path = pinned(root, config["split"])
    value = read_json(path)
    test_only = config["status"] == "TEST_ONLY"
    if (
        value.get("status") != ("SPLIT_TEST_ONLY" if test_only else "SPLIT_REAL")
        or value.get("publication_complete") is not True
        or (not test_only and value.get("complete_protocol_coverage") is not True)
    ):
        raise ValueError("Particionado no publicado/auditado para este ambito")
    return path.parent, value


def verify_tables(directory, manifest, partition, names, *, test_only=False):
    if partition not in ("train", "monitoring_replay"):
        raise ValueError("Monitoreo no autoriza test, validacion ni holdout final")
    info = manifest["partitions"][partition]
    for name in names:
        path = directory / partition / f"{name}.parquet"
        expected = info["artifacts"][name]
        if (
            path.is_symlink()
            or path.stat().st_size != expected["file_size_bytes"]
            or _sha256(path) != expected["sha256"]
        ):
            raise ValueError("Artefacto T14 alterado")
        with pq.ParquetFile(path) as parquet:
            metadata = parquet.schema_arrow.metadata or {}
            if (
                parquet.metadata.num_rows != info["rows"]
                or expected["row_count"] != info["rows"]
                or metadata.get(b"split_scope") != (b"TEST_ONLY" if test_only else b"REAL")
                or (test_only and metadata.get(b"fixture_origin") != b"synthetic")
            ):
                raise ValueError("Volumen/ambito de artefacto incompatible")
            if name == "features" and tuple(parquet.schema_arrow.names) != FEATURE_COLUMNS:
                raise ValueError("Features fuera de whitelist")


def batches(directory, partition, names, guard, *, batch_size=65536, context_columns=None):
    if partition not in ("train", "monitoring_replay") or not 1 <= batch_size <= 65536:
        raise ValueError("Lectura fuera del alcance aprobado")
    with ExitStack() as stack:
        readers = [
            stack.enter_context(pq.ParquetFile(directory / partition / f"{name}.parquet"))
            for name in names
        ]
        streams = [
            reader.iter_batches(
                batch_size=batch_size,
                use_threads=False,
                columns=context_columns if name == "context" else None,
            )
            for reader, name in zip(readers, names, strict=True)
        ]
        for rows in zip(*streams, strict=True):
            guard.check()
            if len({table.num_rows for table in rows}) != 1:
                raise ValueError("Bloques desalineados")
            yield rows


def month_bounds(year, month):
    if type(year) is not int or type(month) is not int or not 1 <= month <= 12:
        raise ValueError("Mes invalido")
    zone = ZoneInfo("America/New_York")
    start = datetime(year, month, 1, tzinfo=zone)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


def maturity_cutoff(year, month):
    return month_bounds(year, month)[1] + timedelta(hours=POLICY["label_maturity_hours"])


def exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)


def envelope(config):
    # La referencia se sella despues de construirla; no participa en su propio hash.
    policy = {key: value for key, value in config.items() if key != "reference"}
    return {"config_sha256": fingerprint(policy), "split_sha256": config["split"]["sha256"]}
