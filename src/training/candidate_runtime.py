"""Contrato aprobado, lectura por bloques y presupuesto de candidatos T16/T17."""

import json
import time
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from src.training.baseline import verify_split
from src.training.models import PARAMETERS, feature_matrix
from src.training.resources import ResourceGuard, ResourceLimitError
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def read_candidates(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "format_version": 1,
        "approval_status": "APPROVED",
        "fit_scope": "train_only",
        "selection_scope": "validation_only",
        "epochs": 1,
        "batch_size": 4096,
        "random_state": 42,
        "prediction_bounds_minutes": [1 / 60, 180.0],
        "preprocessing": "train_vocabulary_then_streaming_standard_scaler_no_centering",
        "candidates": PARAMETERS,
    }
    if any(type(config.get(k)) is not type(v) or config[k] != v for k, v in required.items()):
        raise ValueError("Perfil de candidatos distinto del aprobado")
    policy = config["resources"]
    approved = {
        "approval_status": "APPROVED",
        "threads_total": 4,
        "parallel_models": 1,
        "candidate_timeout_seconds": 7200,
        "preflight_min_free_disk_gib": 50,
        "profile_id": "d02-incremental-8-4-2026-11-05",
        "preflight_min_free_ram_gib": 8,
        "process_rss_limit_gib": 4,
    }
    if any(type(policy.get(k)) is not type(v) or policy[k] != v for k, v in approved.items()):
        raise ValueError("Perfil D-02 de candidatos no aprobado")
    evaluation = config.get("evaluation", {})
    if evaluation != {
        "quantile_method": "linear_exact",
        "hour_band_width": 6,
        "route_count": 20,
        "route_min_validation_rows": 1000,
        "route_scope": "validation_frequency_only",
        "destination_usage": "segmentation_only_not_predictor",
        "tie_preference": ["baseline", "sgd", "mlp"],
        "test_usage": "once_after_frozen_validation_selection",
        "monitoring_replay_usage": "not_accessed",
    }:
        raise ValueError("Protocolo T17 distinto del aprobado")
    return config


class CandidateGuard(ResourceGuard):
    def __init__(self, policy, directory, *, test_only, charged_seconds=0.0):
        super().__init__(policy, directory, test_only=test_only)
        self.started = time.monotonic()
        self.charged_seconds = charged_seconds

    @property
    def elapsed(self):
        return time.monotonic() - self.started + self.charged_seconds

    def check(self, *, start=False):
        super().check(start=start)
        if self.elapsed > self.policy["candidate_timeout_seconds"]:
            raise ResourceLimitError("D-02: tiempo por candidato excedido, sin ampliar presupuesto")


def verify_scope(directory, *, config, data_config, test_only, partitions, audit_path=None):
    verified = verify_split(
        directory,
        config=config,
        data_config=data_config,
        test_only=test_only,
        partitions=partitions,
    )
    if not test_only:
        if audit_path is None:
            raise ValueError("T16/T17 REAL requiere recibo de cierre auditado T14")
        audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
        marker = verified["manifest"]
        if (
            audit.get("status") != "VERIFIED_T14_FULL_24_MONTH_PROTOCOL"
            or audit.get("t14_technical_complete") is not True
            or audit.get("split_id") != marker["split_id"]
            or audit.get("split_manifest_sha256") != verified["marker_sha256"]
            or audit.get("data_config_sha256") != fingerprint(data_config)
            or audit.get("model_config_sha256") != fingerprint(config)
            or audit.get("train_validation_match_frozen_t15") is not True
            or audit.get("counts") != {p: v["rows"] for p, v in marker["partitions"].items()}
        ):
            raise ValueError("Recibo T14 no corresponde a las particiones/configuracion actuales")
        verified["audit_sha256"] = _sha256(Path(audit_path))
    elif audit_path is not None:
        raise ValueError("Fixtures y recibos REAL no se mezclan")
    if test_only and sum(verified["manifest"]["partitions"][p]["rows"] for p in partitions) > 65536:
        raise ValueError("Fixture demasiado grande")
    return verified


def read_batches(directory, partition, guard, *, batch_size=4096):
    count = 0
    with ExitStack() as stack:
        readers = [
            stack.enter_context(pq.ParquetFile(Path(directory) / partition / f"{n}.parquet"))
            for n in ("features", "target", "context")
        ]
        for Xb, yb, context in zip(
            *(reader.iter_batches(batch_size=batch_size, use_threads=False) for reader in readers),
            strict=True,
        ):
            guard.check()
            if Xb.num_rows != yb.num_rows or context.num_rows != Xb.num_rows:
                raise ValueError("Bloques desalineados")
            values = feature_matrix(Xb)
            y = yb.column(0).to_numpy()
            if not np.all(np.isfinite(y) & (y > 0) & (y <= 180)):
                raise ValueError("Etiquetas incompatibles con el dominio aprobado")
            count += len(y)
            yield values, y, context
            guard.check()
    return count
