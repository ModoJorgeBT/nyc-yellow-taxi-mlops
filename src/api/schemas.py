"""D-06 REST v1 aprobado: whitelist estricta e instante con offset."""

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from src.features.target import nyc_zone
from src.validation.schema import fingerprint


def read_zone_catalog(root: Path) -> frozenset[int]:
    data = json.loads((root / "configs/data.yaml").read_text(encoding="utf-8"))
    catalog = data["quality"]["zone_catalog"]
    ids = catalog["ids"]
    if (
        data["quality"]["status"] != "APPROVED_REAL"
        or not ids
        or any(type(value) is not int or value <= 0 for value in ids)
        or len(ids) != len(set(ids))
        or fingerprint(ids) != catalog["ids_sha256"]
        or catalog["ids_sha256"]
        != "7a5743d154afed21f5eddd75f5d8cf10a52d51936e835c0474da3a9580d930c1"
    ):
        raise ValueError("Catalogo operativo no coincide con D-04 aprobado")
    return frozenset(ids)


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pickup_datetime: AwareDatetime
    pickup_location_id: Annotated[int, Field(strict=True, gt=0)]
    passenger_count: Annotated[int, Field(strict=True, ge=0, le=6)] | None = None

    @field_validator("pickup_datetime", mode="before")
    @classmethod
    def iso_instant(cls, value):
        # Pydantic admite epoch numerico por defecto; REST solo permite ISO con offset.
        if not isinstance(value, (str, datetime)):
            raise ValueError("Se requiere timestamp ISO 8601 con offset")
        if isinstance(value, str):
            if "T" not in value:
                raise ValueError("Se requiere fecha y hora ISO 8601")
            try:
                value = datetime.fromisoformat(value)
            except ValueError as error:
                raise ValueError("Timestamp ISO 8601 invalido") from error
        if value.utcoffset() is None:
            raise ValueError("Timestamp sin offset")
        try:
            value.astimezone(nyc_zone())
        except (OverflowError, ValueError) as error:
            raise ValueError("Timestamp fuera del calendario representable") from error
        return value


class PredictResponse(BaseModel):
    predicted_duration_minutes: Annotated[float, Field(ge=1 / 60, le=180, allow_inf_nan=False)]
    unit: Literal["minutes"] = "minutes"
    model_version: str
    predicted_at_utc: AwareDatetime


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    model_loaded: Literal[True] = True


class ModelInfoResponse(BaseModel):
    name: str
    version: str
    status: Literal["ready"] = "ready"
    loaded_at_utc: AwareDatetime
    training_period: Literal["2024"] = "2024"
