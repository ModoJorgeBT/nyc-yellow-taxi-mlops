"""Transformaciones compartidas y preprocesador serializable, sin ajustar datos reales."""

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pyarrow as pa
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder
from sklearn.utils.validation import check_is_fitted

from src.features.schema import FEATURE_COLUMNS, FeatureError, PredictionInput, parse_input
from src.features.target import historical_times, nyc_zone


def feature_values(payload: dict | PredictionInput) -> tuple:
    request = parse_input(payload)
    pickup = request.pickup_datetime.astimezone(nyc_zone())
    return (
        str(request.pickup_location_id),
        pickup.hour,
        pickup.weekday(),
        pickup.month,
        0 if request.passenger_count is None else request.passenger_count,
        int(request.passenger_count is None),
    )


class CalendarFeatures(TransformerMixin, BaseEstimator):
    def fit(self, X, y=None):
        # Sin vocabularios, imputaciones aprendidas ni estadisticas historicas aqui.
        self.transform_inputs(X)
        self.is_fitted_ = True
        return self

    @staticmethod
    def transform_inputs(X) -> np.ndarray:
        rows = [feature_values(payload) for payload in X]
        if not rows:
            raise FeatureError("No hay entradas para transformar")
        return np.asarray(rows, dtype=object)

    def transform(self, X):
        check_is_fitted(self, "is_fitted_")
        return self.transform_inputs(X)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(FEATURE_COLUMNS, dtype=object)


def _numeric_float32(values):
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = np.asarray(values, dtype=np.float32)
    except (OverflowError, ValueError, FloatingPointError) as error:
        raise FeatureError("Features numericas no representables") from error
    if not np.isfinite(result).all():
        raise FeatureError("Features numericas no finitas")
    return result


def make_preprocessor() -> Pipeline:
    """Vocabulario de origen se ajusta solo con train; desconocidos no cambian columnas.

    Matriz densa float32 para los estimadores propuestos. T14 debera aprobar un
    presupuesto antes de ajustar/transformar historicos grandes; aqui solo fixtures.
    """
    encoder = ColumnTransformer(
        [
            (
                "origin",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float32),
                [0],
            ),
            (
                "numeric",
                FunctionTransformer(_numeric_float32, feature_names_out="one-to-one"),
                list(range(1, len(FEATURE_COLUMNS))),
            ),
        ],
        sparse_threshold=0,
        verbose_feature_names_out=False,
    )
    return Pipeline([("calendar", CalendarFeatures()), ("encoding", encoder)])


def make_model_pipeline(estimator: BaseEstimator) -> Pipeline:
    """Une transformacion e instancia clonada; no ajusta ni elige un modelo."""
    return Pipeline([("features", make_preprocessor()), ("estimator", clone(estimator))])


@dataclass(frozen=True)
class HistoricalExample:
    request: PredictionInput
    target_minutes: float
    source_row_index: int
    pickup_utc: datetime
    label_event_at_utc: datetime


@dataclass(frozen=True)
class PreparedBatch:
    examples: tuple[HistoricalExample, ...]
    excluded: tuple[dict, ...]
    rows_seen: int


def prepare_historical(table: pa.Table, *, start_index: int = 0) -> PreparedBatch:
    """Adaptador puro historico -> entrada compartida + target/contexto separados.

    No acredita calidad ni autoriza consumir raw: el lector de artefactos comprueba
    esa frontera. No usa DOLocationID aunque exista y nunca devuelve tarifas en X.
    """
    if type(start_index) is not int or start_index < 0:
        raise FeatureError("start_index debe ser entero no negativo")
    required = {"tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID"}
    if not required.issubset(table.column_names) or len(set(table.column_names)) != len(
        table.column_names
    ):
        raise FeatureError("Esquema historico incompleto o con nombres duplicados")
    selected = [*sorted(required)]
    if "passenger_count" in table.column_names:
        selected.append("passenger_count")
    examples, excluded = [], []
    for index, row in enumerate(table.select(selected).to_pylist(), start=start_index):
        try:
            pickup, dropoff, target = historical_times(
                row["tpep_pickup_datetime"], row["tpep_dropoff_datetime"]
            )
            request = PredictionInput(pickup, row["PULocationID"], row.get("passenger_count"))
            examples.append(
                HistoricalExample(
                    request, target, index, pickup.astimezone(UTC), dropoff.astimezone(UTC)
                )
            )
        except FeatureError as error:
            excluded.append({"source_row_index": index, "reason": error.reason})
    return PreparedBatch(tuple(examples), tuple(excluded), table.num_rows)


def main() -> None:
    import argparse
    import json
    import logging
    import sys
    from pathlib import Path

    from src.features.artifacts import build_validated_features
    from src.ingestion.manifest import IngestionError
    from src.validation.run import ValidationError

    parser = argparse.ArgumentParser(
        description="Features sin fit desde un lote validado explicito"
    )
    parser.add_argument("--validated-batch", type=Path, required=True)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--batch-size", type=int, default=2_048)
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    try:
        result = build_validated_features(
            args.validated_batch,
            processed_dir=args.processed_dir,
            test_only=args.test_only,
            batch_size=args.batch_size,
        )
        print(json.dumps(result, allow_nan=False))
    except (
        FeatureError,
        IngestionError,
        ValidationError,
        OSError,
        ValueError,
        pa.ArrowException,
    ) as error:
        logging.error("Features rechazadas: %s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
