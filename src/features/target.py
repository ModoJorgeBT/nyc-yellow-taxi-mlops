"""Etiqueta historica en minutos UTC y convencion temporal aprobada en D-06."""

from datetime import UTC, datetime
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo

from src.features.schema import FeatureError

TIMEZONE = "America/New_York"
TEMPORAL_POLICY = "nyc-local-unambiguous-utc-elapsed-v1"


@lru_cache(maxsize=1)
def nyc_zone() -> ZoneInfo:
    # Usa la dependencia fijada, tambien en Linux con otra base IANA del sistema.
    with files("tzdata.zoneinfo").joinpath("America", "New_York").open("rb") as stream:
        return ZoneInfo.from_file(stream, key=TIMEZONE)


def localize_historical(value: datetime) -> datetime:
    if value is None:
        raise FeatureError("Timestamp historico ausente", reason="missing_timestamp")
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise FeatureError(
            "El historico requiere datetime sin zona", reason="invalid_historical_time"
        )
    zone = nyc_zone()
    candidates = {}
    for fold in (0, 1):
        candidate = value.replace(tzinfo=zone, fold=fold)
        instant = candidate.astimezone(UTC)
        restored = instant.astimezone(zone).replace(tzinfo=None)
        if restored == value:
            candidates[instant] = candidate
    if not candidates:
        raise FeatureError("Hora local inexistente", reason="nonexistent_local_time")
    if len(candidates) > 1:
        raise FeatureError("Hora local ambigua sin offset", reason="ambiguous_local_time")
    return next(iter(candidates.values()))


def historical_times(pickup: datetime, dropoff: datetime) -> tuple[datetime, datetime, float]:
    start, end = localize_historical(pickup), localize_historical(dropoff)
    start_utc, end_utc = start.astimezone(UTC), end.astimezone(UTC)
    minutes = (end_utc - start_utc).total_seconds() / 60
    if minutes <= 0:
        raise FeatureError("Duracion historica no positiva", reason="nonpositive_duration")
    return start, end, minutes


def duration_minutes(pickup: datetime, dropoff: datetime) -> float:
    return historical_times(pickup, dropoff)[2]
