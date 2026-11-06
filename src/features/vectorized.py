"""Conversión por bloques para años autorizados y datos ya validados D-04."""

from datetime import datetime, timedelta
from functools import lru_cache

import numpy as np
import pyarrow as pa

from src.features.schema import FeatureError
from src.features.target import localize_historical

EPOCH = datetime(1970, 1, 1)
HOUR_US = 3_600_000_000
DAY_US = 24 * HOUR_US
SUPPORTED_REAL_YEARS = frozenset((2024, 2025, 2026))


@lru_cache(maxsize=8192)
def _hour_offset(hour: int) -> int:
    # En los años admitidos de Nueva York los cambios son en fronteras de hora.
    # Las horas ambiguas/inexistentes ya se apartaron en D-04; no se adivinan.
    try:
        wall = EPOCH + timedelta(hours=hour, minutes=30)
        return int(localize_historical(wall).utcoffset().total_seconds()) * 1_000_000
    except (OverflowError, ValueError) as error:
        raise FeatureError("Evento fuera del dominio temporal validado") from error


def _utc(values):
    hours, inverse = np.unique(values // HOUR_US, return_inverse=True)
    offsets = np.array([_hour_offset(int(hour)) for hour in hours], dtype=np.int64)
    return values - offsets[inverse]


def real_tables(
    batch: pa.RecordBatch, *, year: int, month: int, start_index: int, schemas: dict
) -> dict[str, pa.Table]:
    if year not in SUPPORTED_REAL_YEARS:
        raise FeatureError("Año fuera del dominio temporal verificado")
    names = batch.schema.names
    arrays = {}
    for name in ("tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID"):
        array = batch.column(names.index(name))
        if array.null_count:
            raise FeatureError("Calidad REAL incoherente: esencial nulo")
        if pa.types.is_timestamp(array.type):
            array = array.view(pa.int64())
        arrays[name] = array.to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
    pickup, dropoff = arrays["tpep_pickup_datetime"], arrays["tpep_dropoff_datetime"]
    start = (datetime(year, month, 1) - EPOCH).days * DAY_US
    end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    end = (end_date - EPOCH).days * DAY_US
    if np.any((pickup < start) | (pickup >= end)) or np.any(arrays["PULocationID"] <= 0):
        raise FeatureError("Calidad REAL incoherente: mes/origen")
    pickup_utc, dropoff_utc = _utc(pickup), _utc(dropoff)
    delta = dropoff_utc - pickup_utc
    if np.any(delta <= 0):
        raise FeatureError("Calidad REAL incoherente: duracion no positiva")
    count = batch.num_rows
    if "passenger_count" in names:
        raw = batch.column(names.index("passenger_count")).to_numpy(zero_copy_only=False)
        missing = np.isnan(raw)
        passengers = np.where(missing, 0, raw).astype(np.int64)
    else:
        missing, passengers = np.ones(count, dtype=bool), np.zeros(count, dtype=np.int64)
    if np.any(passengers < 0):
        raise FeatureError("Calidad REAL incoherente: pasajeros negativos")
    values = [
        arrays["PULocationID"],
        (pickup // HOUR_US) % 24,
        (pickup // DAY_US + 3) % 7,
        np.full(count, month, dtype=np.int64),
        passengers,
        missing.astype(np.int64),
    ]
    return {
        "features": pa.Table.from_arrays([pa.array(v) for v in values], schema=schemas["features"]),
        # Mismas dos divisiones que timedelta.total_seconds()/60 de la referencia.
        "target": pa.Table.from_arrays(
            [pa.array(delta.astype(np.float64) / 1_000_000 / 60)], schema=schemas["target"]
        ),
        "context": pa.Table.from_arrays(
            [
                pa.array(np.arange(start_index, start_index + count, dtype=np.int64)),
                pa.array(pickup_utc).view(pa.timestamp("us", "UTC")),
                pa.array(dropoff_utc).view(pa.timestamp("us", "UTC")),
            ],
            schema=schemas["context"],
        ),
    }
