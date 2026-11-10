"""T21: instantanea verificada del champion, sin promover ni recargar alias."""

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from src.training.champion import (
    ApprovedChampion,
    ChampionUnavailable,
    read_approval,
    resolve_champion,
    verify_artifact_files,
)


def tracking_endpoint(approved_uri: str) -> str:
    """Transporte del operador; nunca altera identidad, hashes ni recibo T19."""
    uri = os.environ.get("NYC_MLFLOW_TRACKING_URI", approved_uri)
    if uri not in (approved_uri, "http://mlflow:5000"):
        raise ChampionUnavailable("Transporte MLflow fuera del perfil local aprobado")
    return uri


def restore_generated_metadata(directory: Path, decision: dict) -> None:
    """MLflow genera registered_model_meta con saltos del SO del cliente."""
    path = directory / "registered_model_meta"
    expected = decision["artifact_files"].get(path.name)
    if not expected or not path.is_file() or path.is_symlink():
        return
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() == expected:
        return
    for candidate in (
        data.replace(b"\r\n", b"\n"),
        data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"),
    ):
        if hashlib.sha256(candidate).hexdigest() == expected:
            path.write_bytes(candidate)
            return


@dataclass(frozen=True)
class LoadedChampion:
    identity: ApprovedChampion
    predictor: Any = field(repr=False)
    lock: Lock = field(default_factory=Lock, repr=False)

    def predict(self, payload: dict) -> float:
        import pandas as pd

        # Evita coercion int->float del pasajero ausente y llamadas nativas simultaneas.
        frame = pd.DataFrame([{k: v for k, v in payload.items() if v is not None}])
        with self.lock:
            values = self.predictor.predict(frame)
        if len(values) != 1:
            raise ValueError("Numero de predicciones incompatible")
        value = float(values[0])
        if not math.isfinite(value) or not 1 / 60 <= value <= 180:
            raise ValueError("Prediccion fuera del contrato congelado")
        return value


@contextmanager
def load_champion(
    *, root: Path | None = None, config: Path | None = None, test_only: bool = False
) -> Iterator[LoadedChampion]:
    """Solo configuracion del operador; ninguna URI procede de una peticion HTTP."""
    root = (Path.cwd() if root is None else Path(root)).resolve()
    config = root / "configs/champion.yaml" if config is None else Path(config)
    if (
        config.is_file()
        and json.loads(config.read_text(encoding="utf-8")).get("format_version") == 2
    ):
        from functools import partial

        from src.retraining import lifecycle

        decision = lifecycle.read_approval(config, root=root, test_only=test_only)
        resolver = partial(lifecycle.resolve_champion, test_only=test_only)
    else:
        if test_only:
            raise ChampionUnavailable("Serving TEST_ONLY requiere contrato operativo v2 aislado")
        decision = read_approval(config)
        resolver = resolve_champion
    os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
    import mlflow
    from mlflow.artifacts import download_artifacts
    from mlflow.pyfunc import load_model

    endpoint = tracking_endpoint(decision["tracking_uri"])
    client_options = {}
    if endpoint != decision["tracking_uri"]:
        client_options["client"] = mlflow.MlflowClient(tracking_uri=endpoint, registry_uri=endpoint)
    # MLflow 3.16 consulta tambien el URI global al resolver un logged model anidado.
    mlflow.set_tracking_uri(endpoint)
    mlflow.set_registry_uri(endpoint)
    identity = resolver(config, root=root, **client_options)
    cache = (root / ".cache/serving").resolve()
    if not cache.is_relative_to(root):
        raise ChampionUnavailable("Cache fuera del proyecto")
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as owned:
        directory = Path(owned).resolve()
        downloaded = Path(
            download_artifacts(
                artifact_uri=identity.model_uri,
                dst_path=str(directory),
                tracking_uri=endpoint,
                registry_uri=endpoint,
            )
        ).resolve()
        if not downloaded.is_relative_to(directory):
            raise ChampionUnavailable("Artefactos fuera de la instantanea propia")
        if any(
            path.suffix == ".pyc" or "__pycache__" in path.parts for path in downloaded.rglob("*")
        ):
            raise ChampionUnavailable("Bytecode no aprobado dentro del paquete")
        restore_generated_metadata(downloaded, decision)
        verify_artifact_files(downloaded, decision)  # Antes de pickle y codigo registrado.
        if resolver(config, root=root, **client_options) != identity:
            raise ChampionUnavailable("Champion cambio durante la descarga")
        model = LoadedChampion(identity, load_model(str(downloaded)))
        for payload, expected in zip(
            decision["smoke"]["payloads"], decision["smoke"]["expected_minutes"], strict=True
        ):
            if not math.isclose(model.predict(payload), expected, rel_tol=0, abs_tol=1e-10):
                raise ChampionUnavailable("Smoke no coincide con la version aprobada")
        yield model
