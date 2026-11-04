"""Whitelist v1 de informacion disponible al inicio; destino deshabilitado."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

FEATURE_VERSION = "pickup-calendar-passengers-v1"
FEATURE_COLUMNS = (
    "pickup_location_id",
    "pickup_hour",
    "pickup_weekday",
    "pickup_month",
    "passenger_count",
    "passenger_count_missing",
)
INPUT_COLUMNS = frozenset({"pickup_datetime", "pickup_location_id", "passenger_count"})


class FeatureError(ValueError):
    def __init__(self, message: str, *, reason: str = "invalid_feature_input"):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class PredictionInput:
    pickup_datetime: datetime
    pickup_location_id: int
    passenger_count: int | None = None

    def __post_init__(self) -> None:
        timestamp = self.pickup_datetime
        if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
            raise FeatureError("pickup_datetime requiere offset", reason="offset_required")
        if type(self.pickup_location_id) is not int or self.pickup_location_id <= 0:
            raise FeatureError(
                "pickup_location_id debe ser entero positivo", reason="invalid_origin"
            )
        if self.passenger_count is not None and (
            type(self.passenger_count) is not int or self.passenger_count < 0
        ):
            raise FeatureError(
                "passenger_count debe ser entero >=0 o null", reason="invalid_passengers"
            )

    def as_dict(self) -> dict:
        return {
            "pickup_datetime": self.pickup_datetime.isoformat(),
            "pickup_location_id": self.pickup_location_id,
            "passenger_count": self.passenger_count,
        }


def parse_input(payload: Mapping | PredictionInput) -> PredictionInput:
    if isinstance(payload, PredictionInput):
        return payload
    if not isinstance(payload, Mapping):
        raise FeatureError("Se requiere un objeto de entrada")
    if set(payload) - INPUT_COLUMNS:
        raise FeatureError("Entrada con columnas fuera de whitelist", reason="forbidden_columns")
    if not {"pickup_datetime", "pickup_location_id"}.issubset(payload):
        raise FeatureError("Faltan pickup_datetime/pickup_location_id")
    timestamp = payload["pickup_datetime"]
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except ValueError as error:
            raise FeatureError("pickup_datetime no es ISO 8601 valido") from error
    return PredictionInput(timestamp, payload["pickup_location_id"], payload.get("passenger_count"))
