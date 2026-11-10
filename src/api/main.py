"""T22: FastAPI local, modelo aprobado al inicio y fallos sin datos internos."""

import json
import logging
from collections.abc import Callable
from contextlib import ExitStack, asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.metrics import MetricsMiddleware, WindowMetrics
from src.api.model_loader import load_champion
from src.api.schemas import (
    HealthResponse,
    ModelInfoResponse,
    PredictRequest,
    PredictResponse,
    read_zone_catalog,
)

logger = logging.getLogger("nyc_taxi.api")


def create_app(*, root: Path | None = None, loader: Callable = load_champion) -> FastAPI:
    root = (Path.cwd() if root is None else Path(root)).resolve()
    metrics = WindowMetrics(lambda report: logger.info("metrics_window %s", json.dumps(report)))

    @asynccontextmanager
    async def lifespan(app):
        with ExitStack() as stack:
            app.state.model = None
            app.state.zones = frozenset()
            try:
                zones = read_zone_catalog(root)
                model = stack.enter_context(loader(root=root))
                app.state.zones = zones
                app.state.loaded_at = datetime.now(UTC)
                app.state.model = model
            except Exception:
                # Ni excepciones, payloads, credenciales ni rutas en logs publicos.
                logger.error("model_startup_failed")
            yield
            app.state.model = None
            metrics.close()

    app = FastAPI(title="NYC Yellow Taxi duration", version="1.0.0", lifespan=lifespan)
    app.state.model = None
    app.state.metrics = metrics
    app.add_middleware(MetricsMiddleware, collector=metrics, logger=logger)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # El error por defecto incluye input/context; puede contener secretos del cliente.
        return JSONResponse(status_code=422, content={"detail": "invalid_request"})

    def ready():
        if app.state.model is None:
            raise HTTPException(status_code=503, detail="model_unavailable")
        return app.state.model

    @app.get("/health", response_model=HealthResponse)
    def health():
        ready()
        return HealthResponse()

    @app.get("/model-info", response_model=ModelInfoResponse)
    def model_info():
        model = ready()
        return ModelInfoResponse(
            name=model.identity.name,
            version=model.identity.version,
            loaded_at_utc=app.state.loaded_at,
        )

    @app.post("/predict", response_model=PredictResponse)
    def predict(payload: PredictRequest):
        model = ready()
        if payload.pickup_location_id not in app.state.zones:
            raise HTTPException(status_code=422, detail="invalid_request")
        try:
            minutes = model.predict(payload.model_dump(mode="json"))
            return PredictResponse(
                predicted_duration_minutes=minutes,
                model_version=model.identity.version,
                predicted_at_utc=datetime.now(UTC),
            )
        except Exception:
            logger.error("prediction_failed")
            raise HTTPException(status_code=500, detail="prediction_failed") from None

    return app


app = create_app()
