"""Errores exactos por grupo, con cuantiles en archivos propios y memoria supervisada."""

import math
import mmap
from pathlib import Path

import numpy as np


def exact_quantiles(path: Path, count: int, *, resource_check=None) -> tuple[float, float]:
    if count < 1 or path.stat().st_size != count * 8:
        raise ValueError("Archivo de errores incompleto o vacio")
    positions = [(count - 1) * q for q in (0.5, 0.9)]
    indexes = sorted({i for pos in positions for i in (math.floor(pos), math.ceil(pos))})
    if resource_check:
        resource_check()
    with path.open("r+b") as stream, mmap.mmap(stream.fileno(), 0) as mapping:
        values = np.ndarray((count,), dtype="<f8", buffer=mapping)
        if not np.isfinite(values).all():
            del values
            raise ValueError("Archivo de errores no finitos")
        values.partition(indexes)
        result = []
        for position in positions:
            low, high = math.floor(position), math.ceil(position)
            result.append(
                float(values[low]) + (float(values[high]) - float(values[low])) * (position - low)
            )
        del values  # Soltar la vista antes de cerrar mmap en Windows.
    if resource_check:
        resource_check()
    return tuple(result)


class ErrorStore:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.groups = {}

    def add(self, target, predicted, groups: dict[str, np.ndarray]):
        target, predicted = np.asarray(target), np.asarray(predicted)
        if target.ndim != 1 or target.shape != predicted.shape or not len(target):
            raise ValueError("Predicciones y etiquetas desalineadas o vacias")
        errors = np.abs(target.astype(np.float64) - predicted.astype(np.float64))
        if not np.isfinite(errors).all():
            raise ValueError("Errores no finitos")
        selections = {"all": np.ones(len(errors), dtype=bool), **groups}
        for key, mask in selections.items():
            if not key or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in key):
                raise ValueError("Identidad de segmento incompatible")
            mask = np.asarray(mask)
            if mask.shape != errors.shape or mask.dtype != np.bool_:
                raise ValueError("Mascara de segmento incompatible")
            values = errors[mask]
            if not len(values):
                continue
            group = self.groups.setdefault(key, {"count": 0, "sums": [], "squares": []})
            group["count"] += len(values)
            group["sums"].append(float(np.sum(values, dtype=np.float64)))
            square = float(np.dot(values, values))
            if not math.isfinite(square):
                raise ValueError("Suma de cuadrados no finita")
            group["squares"].append(square)
            with (self.directory / f"{key}.f64").open("ab") as stream:
                values.astype("<f8", copy=False).tofile(stream)

    def results(self, *, resource_check=None):
        result = {}
        for key, group in sorted(self.groups.items()):
            median, p90 = exact_quantiles(
                self.directory / f"{key}.f64", group["count"], resource_check=resource_check
            )
            count = group["count"]
            result[key] = {
                "rows": count,
                "mae_minutes": math.fsum(group["sums"]) / count,
                "rmse_minutes": math.sqrt(math.fsum(group["squares"]) / count),
                "medae_minutes": median,
                "p90_absolute_error_minutes": p90,
            }
        if "all" not in result:
            raise ValueError("Evaluacion vacia")
        return result
