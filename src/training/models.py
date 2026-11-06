"""Pipeline causal congelado y estimadores incrementales aprobados en T16."""

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.linear_model import SGDRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.utils.validation import check_is_fitted

from src.features.schema import FEATURE_COLUMNS, FeatureError

PARAMETERS = {
    "sgd": {
        "loss": "huber",
        "epsilon": 1.35,
        "penalty": "l2",
        "alpha": 0.0001,
        "learning_rate": "invscaling",
        "eta0": 0.001,
        "power_t": 0.25,
        "average": True,
        "shuffle": True,
        "random_state": 42,
    },
    "mlp": {
        "hidden_layer_sizes": [16],
        "activation": "relu",
        "solver": "adam",
        "loss": "squared_error",
        "alpha": 0.0001,
        "learning_rate_init": 0.001,
        "batch_size": 256,
        "shuffle": True,
        "random_state": 42,
        "early_stopping": False,
    },
}


class BoundedRegressor(RegressorMixin, BaseEstimator):
    """No oculta no finitos; las cotas forman parte del artefacto de inferencia."""

    def __init__(self, estimator, lower=1 / 60, upper=180.0):
        self.estimator, self.lower, self.upper = estimator, lower, upper

    def partial_fit(self, X, y):
        if not hasattr(self, "estimator_"):
            self.estimator_ = clone(self.estimator)
            self.rows_fitted_ = 0
        self.estimator_.partial_fit(X, y)
        self.rows_fitted_ += len(y)
        self.n_features_in_ = X.shape[1]
        return self

    def fit(self, X, y):
        raise ValueError("T16 requiere partial_fit por bloques; no fit de una matriz completa")

    def predict_with_diagnostics(self, X):
        check_is_fitted(self, "estimator_")
        values = np.asarray(self.estimator_.predict(X), dtype=np.float64)
        if not np.isfinite(values).all():
            raise FeatureError("Predicciones no finitas")
        clipped = int(np.count_nonzero((values < self.lower) | (values > self.upper)))
        return np.clip(values, self.lower, self.upper), clipped

    def predict(self, X):
        return self.predict_with_diagnostics(X)[0]


def estimator(name: str) -> BoundedRegressor:
    if name == "sgd":
        model = SGDRegressor(**PARAMETERS[name])
    elif name == "mlp":
        params = {**PARAMETERS[name], "hidden_layer_sizes": (16,)}
        model = MLPRegressor(**params)
    else:
        raise ValueError("Candidato no aprobado")
    return BoundedRegressor(model)


def feature_matrix(batch) -> np.ndarray:
    if batch.schema.names != list(FEATURE_COLUMNS):
        raise FeatureError("Columnas de entrenamiento fuera de whitelist")
    if any(column.null_count for column in batch.columns):
        raise FeatureError("Feature nula en artefacto aprobado")
    return np.column_stack([column.to_numpy() for column in batch.columns])


def encode_matrix(preprocessor, values: np.ndarray) -> np.ndarray:
    if values.ndim != 2 or values.shape[1] != len(FEATURE_COLUMNS):
        raise FeatureError("Matriz de features incompatible")
    encoded_input = values.astype(object)
    encoded_input[:, 0] = values[:, 0].astype(str)
    output = preprocessor.named_steps["encoding"].transform(encoded_input)
    if not np.isfinite(output).all():
        raise FeatureError("Features codificadas no finitas")
    return output


def predict_matrix(pipeline, values: np.ndarray) -> tuple[np.ndarray, int]:
    encoded = encode_matrix(pipeline.named_steps["features"], values)
    scaled = pipeline.named_steps["scaling"].transform(encoded)
    return pipeline.named_steps["estimator"].predict_with_diagnostics(scaled)
