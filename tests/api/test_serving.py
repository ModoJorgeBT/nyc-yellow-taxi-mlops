"""REST offline: contratos, errores sin secretos y version estable del proceso."""

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi", reason="API en entorno serving separado")
pytest.importorskip("httpx", reason="TestClient en entorno serving separado")
from fastapi.testclient import TestClient

from src.api.main import create_app

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = {"pickup_datetime": "2026-03-12T08:30:00-04:00", "pickup_location_id": 161}


@pytest.fixture
def service():
    model = SimpleNamespace(identity=SimpleNamespace(name="synthetic-duration", version="4"))
    calls = []

    def predict(payload):
        calls.append(payload)
        return 12.5

    model.predict = predict

    @contextmanager
    def loader(**kwargs):
        yield model

    with TestClient(create_app(root=ROOT, loader=loader)) as client:
        yield client, model, calls


@pytest.mark.parametrize("passengers", [None, 0, 1, 6])
def test_predict_version_unit_and_utc(service, passengers):
    client, _, calls = service
    response = client.post("/predict", json={**PAYLOAD, "passenger_count": passengers})
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_duration_minutes"] == 12.5
    assert data["unit"] == "minutes" and data["model_version"] == "4"
    assert datetime.fromisoformat(data["predicted_at_utc"]).utcoffset() == UTC.utcoffset(None)
    assert calls[-1]["passenger_count"] == passengers
    assert "dropoff_location_id" not in calls[-1]


@pytest.mark.parametrize("zone", [1, 264, 265])
def test_approved_special_zones(service, zone):
    assert (
        service[0].post("/predict", json={**PAYLOAD, "pickup_location_id": zone}).status_code == 200
    )


@pytest.mark.parametrize(
    "change",
    [
        {"pickup_datetime": "2026-03-12T08:30:00"},
        {"pickup_datetime": "2026-03-12"},
        {"pickup_datetime": "invalid"},
        {"pickup_datetime": 1773304200},
        {"pickup_datetime": None},
        {"pickup_datetime": "0001-01-01T00:00:00+00:00"},
        {"pickup_location_id": 0},
        {"pickup_location_id": -1},
        {"pickup_location_id": 266},
        {"pickup_location_id": "161"},
        {"pickup_location_id": 161.0},
        {"pickup_location_id": True},
        {"passenger_count": -1},
        {"passenger_count": 7},
        {"passenger_count": "1"},
        {"passenger_count": 1.0},
        {"passenger_count": False},
        {"DOLocationID": 161},
        {"trip_distance": 4},
        {"trip_duration_minutes": 12},
        {"model_uri": "file:///untrusted-pickle"},
    ],
)
def test_invalid_inputs_never_reach_model(service, change):
    client, _, calls = service
    response = client.post("/predict", json={**PAYLOAD, **change})
    assert response.status_code == 422
    assert calls == []
    assert response.json() == {"detail": "invalid_request"}


@pytest.mark.parametrize("payload", [{}, [], None, {"pickup_location_id": 161}])
def test_missing_or_wrong_shape(service, payload):
    assert service[0].post("/predict", json=payload).status_code == 422


def test_health_info_and_no_per_request_reload(service):
    client, model, _ = service
    assert client.get("/health").json() == {"status": "ok", "model_loaded": True}
    info = client.get("/model-info").json()
    assert info["version"] == model.identity.version == "4"
    assert info["training_period"] == "2024" and info["status"] == "ready"
    assert set(info) == {"name", "version", "status", "loaded_at_utc", "training_period"}
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/predict", "/health", "/model-info"}


def test_unavailable_model_all_endpoints_503_no_internal_errors(caplog):
    @contextmanager
    def unavailable(**kwargs):
        raise RuntimeError("secret-token C:/private/path")
        yield

    with TestClient(create_app(root=ROOT, loader=unavailable)) as client:
        for path in ("/health", "/model-info"):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json() == {"detail": "model_unavailable"}
        assert client.post("/predict", json=PAYLOAD).status_code == 503
    assert "secret-token" not in caplog.text and "C:/private" not in caplog.text


def test_prediction_failure_does_not_leak_or_replace_model(service, caplog):
    client, model, _ = service

    def broken(payload):
        raise RuntimeError("password:secret-private-input")

    model.predict = broken
    response = client.post("/predict", json=PAYLOAD)
    assert response.status_code == 500
    assert response.json() == {"detail": "prediction_failed"}
    assert "secret-private-input" not in caplog.text
    assert client.get("/model-info").json()["version"] == "4"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, 181])
def test_invalid_model_output_never_200(service, value):
    client, model, _ = service
    model.predict = lambda payload: value
    assert client.post("/predict", json=PAYLOAD).status_code == 500


def test_catalog_corruption_keeps_service_unready(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/data.yaml").write_text("{}")
    with TestClient(create_app(root=tmp_path)) as client:
        assert client.get("/health").status_code == 503


def test_logs_do_not_include_extra_fields_or_query(service, caplog):
    caplog.set_level("INFO", logger="nyc_taxi.api")
    client, _, _ = service
    response = client.post(
        "/predict?password=private-query",
        json={**PAYLOAD, "secret": "private-input"},
        headers={"Authorization": "Bearer private-header"},
    )
    assert response.status_code == 422
    messages = [r.getMessage() for r in caplog.records if r.name == "nyc_taxi.api"]
    assert any("route=/predict status=422" in message for message in messages)
    assert all("private-" not in message for message in messages)


def test_loader_context_released_after_api_shutdown():
    events = []

    @contextmanager
    def loader(**kwargs):
        events.append("loaded")
        yield SimpleNamespace()
        events.append("closed")

    app = create_app(root=ROOT, loader=loader)
    with TestClient(app):
        assert app.state.model is not None and events == ["loaded"]
    assert app.state.model is None and events == ["loaded", "closed"]
