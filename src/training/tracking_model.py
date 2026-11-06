"""Adaptador opcional MLflow que conserva el contrato del Pipeline congelado."""

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path

import joblib
import numpy as np

from src.features.schema import INPUT_COLUMNS, FeatureError, parse_input


def canonical_records(records):
    """Normaliza representaciones tabulares sin admitir columnas posteriores."""
    result = []
    for record in records:
        if not isinstance(record, Mapping) or set(record) - INPUT_COLUMNS:
            raise FeatureError("Entrada fuera de whitelist")
        item = dict(record)
        for name in ("pickup_location_id", "passenger_count"):
            if name not in item:
                continue
            value = item[name]
            if name == "passenger_count" and (
                value is None or isinstance(value, (float, np.floating)) and math.isnan(value)
            ):
                item[name] = None
            elif isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
                item[name] = int(value)
            elif (
                name == "passenger_count"
                and isinstance(value, (float, np.floating))
                and math.isfinite(value)
                and value.is_integer()
            ):
                item[name] = int(value)
        result.append(parse_input(item).as_dict())
    if not result:
        raise FeatureError("No hay entradas para predecir")
    return result


class FrozenPredictor:
    def __init__(self, family, model_path, expected_sha256):
        self.family = family
        path = Path(model_path)
        with path.open("rb") as stream:
            observed = hashlib.file_digest(stream, "sha256").hexdigest()
        if observed != expected_sha256:
            raise ValueError("Modelo registrado alterado")
        if family == "baseline":
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("kind") != "exact_global_train_median":
                raise ValueError("Baseline no reconocido")
            self.model = obj["prediction_minutes"]
            if not isinstance(self.model, float) or not 0 < self.model <= 180:
                raise ValueError("Constante baseline inválida")
        elif family in ("sgd", "mlp", "lightgbm"):
            self.model = joblib.load(path)
        else:
            raise ValueError("Familia de modelo desconocida")

    def predict(self, records):
        records = canonical_records(records)
        if self.family == "baseline":
            return np.full(len(records), self.model, dtype=np.float64)
        values = np.asarray(self.model.predict(records), dtype=np.float64)
        if values.shape != (len(records),) or not np.isfinite(values).all() or np.any(values <= 0):
            raise ValueError("Predicciones registradas inválidas")
        return values


def python_model(family, expected_sha256):
    # Importación diferida: el entorno histórico no necesita instalar MLflow.
    from mlflow.pyfunc import PythonModel

    class FrozenModel(PythonModel):
        def load_context(self, context):
            self.predictor = FrozenPredictor(
                family, context.artifacts["frozen_model"], expected_sha256
            )

        def predict(self, context, model_input, params=None):
            frame = model_input.astype(object).where(model_input.notna(), None)
            return self.predictor.predict(frame.to_dict(orient="records"))

    return FrozenModel()
