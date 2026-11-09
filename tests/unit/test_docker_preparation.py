"""Preparacion Docker offline: hashes, transporte, copia SQLite y smoke HTTP."""

import copy
import hashlib
import io
import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import container_build, prepare_compose, smoke_api
from src.api.model_loader import tracking_endpoint
from src.training.champion import ChampionUnavailable
from src.validation.schema import fingerprint

ROOT = Path(__file__).resolve().parents[2]


def test_linux_lock_and_wheel_manifest_are_complete_and_bounded():
    manifest = json.loads((ROOT / "configs/container-wheels-linux.json").read_text())
    lock = (ROOT / "requirements-serving-linux.lock").read_text()
    assert len(manifest["wheels"]) == 99
    assert "pywin32" not in manifest["wheels"] and "colorama" not in manifest["wheels"]
    assert "gunicorn" in manifest["wheels"]
    for name, item in manifest["wheels"].items():
        assert f"{name}=={item['version']}" in lock
        assert f"--hash=sha256:{item['sha256']}" in lock
        assert item["url"].startswith("https://files.pythonhosted.org/")
    assert manifest["base_and_wheels_transfer_bytes"] < 2 * 1024**3
    assert manifest["base_image"]["reference"] in (ROOT / "Dockerfile").read_text()


def test_compose_is_local_persistent_bounded_and_unprivileged():
    compose = json.loads((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]
    for name in ("api", "mlflow"):
        service = services[name]
        assert all(port.startswith("127.0.0.1:") for port in service["ports"])
        assert service["mem_limit"] == "2g" and service["cpus"] == 2
        assert service["cap_drop"] == ["ALL"] and service["read_only"]
    assert services["api"]["depends_on"]["mlflow"]["condition"] == "service_healthy"
    assert services["api"]["volumes"][0]["read_only"]
    assert services["mlflow"]["volumes"][0]["source"] == "tracking-state"
    assert "compose-state" in services["bootstrap"]["volumes"][0]["source"]
    assert services["bootstrap"]["volumes"][0]["read_only"]
    assert services["mlflow"]["environment"]["MLFLOW_SERVER_ENABLE_JOB_EXECUTION"] == "false"
    assert services["pipeline"]["profiles"] == ["pipeline"]
    assert services["api-unavailable"]["profiles"] == ["smoke"]
    assert not services["api-unavailable"].get("volumes")
    assert "USER 10001:10001" in (ROOT / "Dockerfile").read_text()


def test_transports_only_allow_native_or_compose_service(monkeypatch):
    monkeypatch.delenv("NYC_MLFLOW_TRACKING_URI", raising=False)
    assert tracking_endpoint("http://127.0.0.1:5000") == "http://127.0.0.1:5000"
    monkeypatch.setenv("NYC_MLFLOW_TRACKING_URI", "http://mlflow:5000")
    assert tracking_endpoint("http://127.0.0.1:5000") == "http://mlflow:5000"
    monkeypatch.setenv("NYC_MLFLOW_TRACKING_URI", "https://untrusted.example")
    with pytest.raises(ChampionUnavailable):
        tracking_endpoint("http://127.0.0.1:5000")


@pytest.fixture
def download(tmp_path, monkeypatch):
    content = b"synthetic-wheel-content"
    info = {
        "filename": "synthetic.whl",
        "url": "https://files.pythonhosted.org/synthetic.whl",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    monkeypatch.setattr(container_build, "urlopen", lambda *a, **kw: io.BytesIO(content))
    return info, tmp_path


def test_download_verifies_hash_and_is_idempotent(download, monkeypatch):
    info, folder = download
    assert container_build.download_file(info, folder) == "DOWNLOADED"
    monkeypatch.setattr(container_build, "urlopen", Mock(side_effect=AssertionError("no network")))
    assert container_build.download_file(info, folder) == "SKIPPED"
    (folder / info["filename"]).write_bytes(b"changed")
    with pytest.raises(ValueError):
        container_build.download_file(info, folder)


@pytest.mark.parametrize("fault", ["hash", "size", "traversal", "untrusted_url"])
def test_bad_download_never_publishes_file(download, fault):
    info, folder = download
    info = copy.deepcopy(info)
    if fault == "hash":
        info["sha256"] = "0" * 64
    elif fault == "size":
        info["size_bytes"] -= 1
    elif fault == "traversal":
        info["filename"] = "../outside.whl"
    else:
        info["url"] = "https://untrusted.example/file"
    with pytest.raises(ValueError):
        container_build.download_file(info, folder)
    assert list(folder.iterdir()) == []


@pytest.fixture
def seed(tmp_path):
    source = tmp_path / "tracking"
    (source / "artifacts").mkdir(parents=True)
    (source / "artifacts/model.txt").write_text("synthetic artifact")
    (source / "approvals").mkdir()
    (tmp_path / "configs").mkdir()
    approval = {"approval_status": "APPROVED", "target": {"name": "synthetic", "version": "4"}}
    (tmp_path / "configs/champion.yaml").write_text(json.dumps(approval))
    receipt = {"status": "CHAMPION_APPROVED_REAL", "target": approval["target"]}
    (source / "approvals" / f"{fingerprint(approval)}.applied.json").write_text(json.dumps(receipt))
    with sqlite3.connect(source / "mlflow.db") as db:
        db.execute("create table runs(id integer)")
        db.execute("create table model_versions(version integer)")
        db.execute("create table registered_model_aliases(name text,alias text,version integer)")
        db.executemany("insert into runs values (?)", [(i,) for i in range(4)])
        db.executemany("insert into model_versions values (?)", [(i,) for i in range(1, 5)])
        db.execute("insert into registered_model_aliases values ('synthetic','champion',4)")
    return tmp_path, tmp_path / ".cache/compose-state/tracking"


def test_sqlite_copy_preserves_original_and_refuses_overwrite(seed):
    root, destination = seed
    before = prepare_compose.files(root / "tracking")
    result = prepare_compose.prepare(root, destination)
    assert result["status"] == "COMPOSE_SEED_VERIFIED"
    assert {k: v for k, v in result["files"].items() if k != "mlflow.db"} == {
        k: v for k, v in before.items() if k != "mlflow.db"
    }
    with sqlite3.connect(root / "tracking/mlflow.db") as db:
        assert result["registry_logical_sha256"] == prepare_compose.database_snapshot(db)
    assert prepare_compose.files(root / "tracking") == before
    with pytest.raises(ValueError, match="existente"):
        prepare_compose.prepare(root, destination)


def test_seed_rejects_in_place_or_unapproved_registry(seed):
    root, destination = seed
    with pytest.raises(ValueError):
        prepare_compose.prepare(root, root / "tracking")
    with sqlite3.connect(root / "tracking/mlflow.db") as db:
        db.execute("delete from registered_model_aliases")
    with pytest.raises(ValueError, match="Registry"):
        prepare_compose.prepare(root, destination)
    assert not destination.exists()


def test_volume_import_does_not_reset_existing_registry(seed):
    root, staging = seed
    prepare_compose.prepare(root, staging)
    volume = root / ".cache/linux-volume"
    assert prepare_compose.import_seed(staging, volume)["status"] == "VOLUME_INITIALIZED"
    assert prepare_compose.audit_volume(volume)["status"] == "PERSISTENCE_VERIFIED"
    with sqlite3.connect(volume / "mlflow.db") as db:
        db.execute("insert into runs values (99)")
    assert prepare_compose.import_seed(staging, volume)["status"] == "SKIPPED"
    with pytest.raises(ValueError, match="logico"):
        prepare_compose.audit_volume(volume)
    assert prepare_compose.audit_volume(staging)["status"] == "PERSISTENCE_VERIFIED"


def test_volume_import_rejects_tampered_seed_and_nonempty_target(seed):
    root, staging = seed
    prepare_compose.prepare(root, staging)
    volume = root / ".cache/linux-volume"
    volume.mkdir()
    (volume / "keep.txt").write_text("do not overwrite")
    with pytest.raises(ValueError, match="vacio"):
        prepare_compose.import_seed(staging, volume)
    (staging / "artifacts/model.txt").write_text("tampered")
    with pytest.raises(ValueError, match="modificado"):
        prepare_compose.import_seed(staging, root / ".cache/other")


def test_backup_with_live_wal_closes_destination_before_recording_files(seed):
    root, destination = seed
    writer = sqlite3.connect(root / "tracking/mlflow.db")
    try:
        writer.execute("pragma journal_mode=WAL")
        writer.execute("create table marker(value text)")
        writer.execute("insert into marker values ('committed')")
        writer.commit()
        result = prepare_compose.prepare(root, destination)
        assert all((destination / relative).is_file() for relative in result["files"])
        assert "mlflow.db-wal" not in result["files"]
        assert prepare_compose.audit_volume(destination)["status"] == "PERSISTENCE_VERIFIED"
    finally:
        writer.close()


def test_snapshot_preserves_exact_float_values_but_ignores_row_order(tmp_path):
    import math

    first, second = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    try:
        for db in (first, second):
            db.execute("create table metrics(value real)")
        first.executemany("insert into metrics values (?)", [(1.0,), (2.0,)])
        second.executemany("insert into metrics values (?)", [(2.0,), (1.0,)])
        assert prepare_compose.database_snapshot(first) == prepare_compose.database_snapshot(second)
        second.execute("update metrics set value=? where value=1", (math.nextafter(1.0, 2.0),))
        assert prepare_compose.database_snapshot(first) != prepare_compose.database_snapshot(second)
    finally:
        first.close()
        second.close()


def test_legacy_upgrade_requires_exact_database_bytes_and_expected_values(seed):
    root, staging = seed
    prepare_compose.prepare(root, staging)
    marker = staging / "compose-seed.json"
    metadata = json.loads(marker.read_text())
    portable = metadata["registry_logical_sha256"]
    metadata.pop("snapshot_format")
    metadata["registry_logical_sha256"] = "legacy-sql-text-hash"
    marker.write_text(json.dumps(metadata))
    before = prepare_compose.digest(staging / "mlflow.db")
    with pytest.raises(ValueError, match="tipados"):
        prepare_compose.upgrade_snapshot(staging, "0" * 64)
    assert not (staging / "compose-seed-v1.json").exists()
    result = prepare_compose.upgrade_snapshot(staging, portable)
    assert result["database_modified"] is False
    assert prepare_compose.digest(staging / "mlflow.db") == before
    assert prepare_compose.audit_volume(staging)["status"] == "PERSISTENCE_VERIFIED"
    assert prepare_compose.upgrade_snapshot(staging)["status"] == "SKIPPED"


@pytest.fixture
def expected():
    return json.loads((ROOT / "configs/champion.yaml").read_text(encoding="utf-8"))


def responder(approval, *, unavailable=False, version="4"):
    def request(url, payload=None):
        if unavailable:
            return 503, {"detail": "model_unavailable"}
        if url.endswith("/health"):
            return 200, {"status": "ok", "model_loaded": True}
        if url.endswith("/model-info"):
            return 200, {"name": approval["target"]["name"], "version": version}
        if "trip_duration_minutes" in payload or payload["pickup_location_id"] > 265:
            return 422, {"detail": "invalid_request"}
        position = approval["smoke"]["payloads"].index(payload)
        return 200, {
            "predicted_duration_minutes": approval["smoke"]["expected_minutes"][position],
            "unit": "minutes",
            "model_version": version,
            "predicted_at_utc": "2026-11-09T18:00:00Z",
        }

    return request


def test_smoke_checks_version_predictions_and_422_without_registry_writes(expected):
    result = smoke_api.smoke("http://127.0.0.1:8000", expected, request=responder(expected))
    assert result["status"] == "PASS"
    assert len(result["observations"]) == 9 and not result["registry_mutated"]
    with pytest.raises(smoke_api.SmokeError):
        smoke_api.smoke(
            "http://127.0.0.1:8000", expected, request=responder(expected, version="99")
        )


def test_smoke_unavailable_uses_503_and_rejects_fake_200(expected):
    result = smoke_api.smoke(
        "http://127.0.0.1:8001",
        expected,
        unavailable=True,
        request=responder(expected, unavailable=True),
    )
    assert result["mode"] == "UNAVAILABLE"
    with pytest.raises(smoke_api.SmokeError):
        smoke_api.smoke(
            "http://127.0.0.1:8001", expected, unavailable=True, request=responder(expected)
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example:443",
        "http://localhost:8000/path",
        "http://user:secret@localhost:8000",
        "http://localhost:8000?secret=x",
        "http://localhost",
    ],
)
def test_smoke_rejects_non_loopback_or_credential_urls(url):
    with pytest.raises(smoke_api.SmokeError):
        smoke_api.check_url(url)


def test_unavailable_container_healthcheck_exits_success_on_503(monkeypatch):
    import urllib.error
    import urllib.request

    code = json.loads((ROOT / "docker-compose.yml").read_text())["services"]["api-unavailable"][
        "healthcheck"
    ]["test"][-1]
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        Mock(side_effect=urllib.error.HTTPError("http://localhost", 503, "unavailable", {}, None)),
    )
    with pytest.raises(SystemExit) as stopped:
        exec(code)
    assert stopped.value.code == 0
