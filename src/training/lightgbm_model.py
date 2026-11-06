"""Representación causal compacta y predictor LightGBM serializable."""

import numpy as np
from lightgbm import Booster
from sklearn.base import BaseEstimator, RegressorMixin, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from src.features.schema import FEATURE_COLUMNS, FeatureError


class NativeFeatures(TransformerMixin, BaseEstimator):
    """Vocabulario exhaustivo de train; desconocidos -1, sin escalado aprendido."""

    def __init__(self, origins):
        self.origins = origins

    def fit(self, X=None, y=None):
        categories = np.asarray(self.origins, dtype=np.int64)
        if (
            categories.ndim != 1
            or not len(categories)
            or np.any(categories <= 0)
            or np.any(np.diff(categories) <= 0)
        ):
            raise FeatureError("Vocabulario de origen no ordenado, único y positivo")
        self.categories_ = categories
        self.n_features_in_ = len(FEATURE_COLUMNS)
        return self

    def transform(self, X):
        check_is_fitted(self, "categories_")
        values = np.asarray(X, dtype=np.float32)
        if values.ndim != 2 or values.shape[1] != len(FEATURE_COLUMNS):
            raise FeatureError("Features nativas fuera de whitelist")
        if not np.isfinite(values).all():
            raise FeatureError("Features nativas no finitas")
        result = values.copy()
        origin = values[:, 0]
        if np.any(origin <= 0) or np.any(origin != np.floor(origin)):
            raise FeatureError("Origen no entero positivo")
        positions = np.searchsorted(self.categories_, origin)
        matches = (positions < len(self.categories_)) & (
            self.categories_[np.minimum(positions, len(self.categories_) - 1)] == origin
        )
        result[:, 0] = np.where(matches, positions, -1)
        return result

    def get_feature_names_out(self, input_features=None):
        return np.asarray(FEATURE_COLUMNS, dtype=object)


class BoundedBooster(RegressorMixin, BaseEstimator):
    def __init__(self, model_text=None, lower=1 / 60, upper=180.0):
        self.model_text, self.lower, self.upper = model_text, lower, upper

    def fit(self, X=None, y=None):
        raise ValueError("LightGBM debe ajustarse en el proceso nativo supervisado")

    def load_fitted(self, *, rows):
        self.booster_ = Booster(model_str=self.model_text)
        if self.booster_.num_feature() != len(FEATURE_COLUMNS) or rows <= 0:
            raise FeatureError("Modelo LightGBM incompatible")
        self.rows_fitted_, self.n_features_in_ = rows, len(FEATURE_COLUMNS)
        return self

    def predict_with_diagnostics(self, X):
        check_is_fitted(self, "booster_")
        values = np.asarray(self.booster_.predict(X, num_threads=4), dtype=np.float64)
        if not np.isfinite(values).all():
            raise FeatureError("Predicciones LightGBM no finitas")
        changed = int(np.count_nonzero((values < self.lower) | (values > self.upper)))
        return np.clip(values, self.lower, self.upper), changed

    def predict(self, X):
        return self.predict_with_diagnostics(X)[0]
