"""Proceso independiente: solo recibe matrices train aprobadas en disco."""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path


def handshake(request):
    path = Path(request["pid_path"])
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "parent_pid": os.getppid(),
                "token": request["identity_token"],
            }
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
    started = time.monotonic()
    ready = Path(request["ready_path"])
    while not ready.exists():
        if time.monotonic() - started > 30:
            raise RuntimeError("No se autorizó la supervisión del proceso nativo")
        time.sleep(0.01)
    if ready.read_text(encoding="utf-8") != request["identity_token"]:
        raise RuntimeError("Autorización de supervisión no verificable")


if __name__ == "__main__":
    bootstrap = argparse.ArgumentParser(description=__doc__)
    bootstrap.add_argument("--request", type=Path, required=True)
    bootstrap_request = json.loads(bootstrap.parse_args().request.read_text(encoding="utf-8"))
    # Antes de importar librerías nativas o abrir matrices, el coordinador debe
    # identificar y empezar a medir este PID, no el redirector del venv Windows.
    handshake(bootstrap_request)

import lightgbm as lgb  # noqa: E402 — handshake anterior a cualquier biblioteca nativa.
import numpy as np  # noqa: E402


class DiskSequence(lgb.Sequence):
    def __init__(self, path, rows, columns, *, batch_size=4096):
        self.data = np.memmap(path, mode="r", dtype="<f4", shape=(rows, columns))
        self.batch_size = batch_size
        self.range_rows, self.sample_rows = 0, 0
        self.digest = hashlib.sha256()

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        if isinstance(index, slice):
            if index.step not in (None, 1) or index.start != self.range_rows:
                raise ValueError("Construcción del Dataset no secuencial")
            block = np.asarray(self.data[index], dtype=np.float32)
            self.range_rows += len(block)
            self.digest.update(block.astype("<f4", copy=False).tobytes())
            return block
        self.sample_rows += 1
        return np.asarray(self.data[index], dtype=np.float64)


def main(request):
    rows = request["rows"]
    if (
        Path(request["features"]).stat().st_size != rows * len(request["feature_names"]) * 4
        or Path(request["target"]).stat().st_size != rows * 8
    ):
        raise ValueError("Matrices train incompletas o con filas adicionales")
    source = DiskSequence(request["features"], rows, len(request["feature_names"]))
    labels = np.memmap(request["target"], mode="r", dtype="<f8", shape=(rows,))
    target_hash = hashlib.sha256()
    for start in range(0, rows, 65536):
        target_hash.update(labels[start : start + 65536].tobytes())
    if target_hash.hexdigest() != request["target_sha256"]:
        raise ValueError("Etiquetas train alteradas antes del ajuste nativo")
    dataset = lgb.Dataset(
        source,
        label=labels,
        feature_name=request["feature_names"],
        categorical_feature=[0],
        params=request["parameters"],
        free_raw_data=True,
    ).construct()
    if dataset.num_data() != rows or source.range_rows != rows:
        raise ValueError("Dataset LightGBM incompleto")
    if source.digest.hexdigest() != request["feature_sha256"]:
        raise ValueError("Matriz train alterada durante lectura nativa")
    # El Dataset ya posee bins y etiquetas nativos; liberar los mapas evita
    # retener páginas de las matrices compactas durante las cien iteraciones.
    source.data._mmap.close()
    labels._mmap.close()
    print(
        json.dumps(
            {"phase": "dataset_complete", "rows": rows, "bin_sample_rows": source.sample_rows}
        ),
        flush=True,
    )

    def progress(env):
        if (env.iteration + 1) % 10 == 0:
            print(json.dumps({"phase": "boosting", "iteration": env.iteration + 1}), flush=True)

    booster = lgb.train(
        request["parameters"],
        dataset,
        num_boost_round=request["num_boost_round"],
        callbacks=[progress],
    )
    # La API nativa save_model falla con rutas Unicode en Windows; Python abre
    # el archivo y conserva exactamente el modelo generado en memoria.
    Path(request["model"]).write_text(booster.model_to_string(), encoding="utf-8")
    result = {
        "dataset_rows": dataset.num_data(),
        "range_rows": source.range_rows,
        "bin_sample_rows": source.sample_rows,
        "feature_sha256": source.digest.hexdigest(),
        "target_sha256": target_hash.hexdigest(),
        "iterations": booster.current_iteration(),
        "trees": booster.num_trees(),
        "feature_names": booster.feature_name(),
        "lightgbm_version": lgb.__version__,
    }
    Path(request["result"]).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main(bootstrap_request)
