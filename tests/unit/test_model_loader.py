"""La deserializacion solo ocurre tras integridad e identidad aprobadas."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.api import model_loader as module
from src.training.champion import ApprovedChampion, ChampionUnavailable, artifact_files


@pytest.fixture
def loading(tmp_path, monkeypatch):
    pytest.importorskip("mlflow", reason="Loader en entorno MLflow separado")
    import mlflow.artifacts
    import mlflow.pyfunc

    artifact = tmp_path / "not-downloaded-yet"
    identity = ApprovedChampion("synthetic", "4", "run", "models:/synthetic/4", "hash", "id", "sha")
    decision = {
        "tracking_uri": "http://127.0.0.1:5000",
        "smoke": {"payloads": [], "expected_minutes": []},
    }
    monkeypatch.setattr(module, "read_approval", lambda path: decision)
    resolve = Mock(return_value=identity)
    monkeypatch.setattr(module, "resolve_champion", resolve)

    def download(**kwargs):
        nonlocal artifact
        artifact = Path(kwargs["dst_path"]) / "package"
        artifact.mkdir()
        (artifact / "model.joblib").write_bytes(b"synthetic-not-pickle")
        decision["artifact_files"] = artifact_files(artifact)
        decision["frozen_model_artifact"] = "model.joblib"
        decision["target"] = {"model_sha256": decision["artifact_files"]["model.joblib"]}
        return str(artifact)

    monkeypatch.setattr(mlflow.artifacts, "download_artifacts", download)
    deserializer = Mock(return_value=SimpleNamespace(predict=lambda frame: [12.5]))
    monkeypatch.setattr(mlflow.pyfunc, "load_model", deserializer)
    return tmp_path, decision, deserializer, resolve


def test_verified_snapshot_lifetime_and_identity(loading):
    root, _, deserialize, _ = loading
    with module.load_champion(root=root) as loaded:
        directory = Path(deserialize.call_args.args[0])
        assert directory.is_dir()
        assert loaded.identity.version == "4"
        assert loaded.predict({"pickup_location_id": 161, "passenger_count": None}) == 12.5
    assert not directory.exists()


def test_modified_artifact_blocks_deserialization(loading, monkeypatch):
    root, _, deserialize, _ = loading
    original = module.verify_artifact_files

    def corrupt(path, decision):
        (path / "model.joblib").write_bytes(b"changed")
        original(path, decision)

    monkeypatch.setattr(module, "verify_artifact_files", corrupt)
    with pytest.raises(ChampionUnavailable):
        with module.load_champion(root=root):
            pytest.fail("No debe cargar")
    deserialize.assert_not_called()


def test_alias_change_during_download_blocks_deserialization(loading):
    root, _, deserialize, resolve = loading
    resolve.side_effect = [resolve.return_value, None]
    with pytest.raises(ChampionUnavailable):
        with module.load_champion(root=root):
            pytest.fail("No debe cargar")
    deserialize.assert_not_called()


def test_unapproved_or_absent_champion_never_downloads(loading):
    root, _, deserialize, resolve = loading
    resolve.side_effect = ChampionUnavailable("absent")
    with pytest.raises(ChampionUnavailable):
        with module.load_champion(root=root):
            pytest.fail("No debe cargar")
    deserialize.assert_not_called()


def test_smoke_mismatch_fails_readiness(loading):
    root, decision, _, _ = loading
    decision["smoke"] = {"payloads": [{"pickup_location_id": 161}], "expected_minutes": [99]}
    with pytest.raises(ChampionUnavailable):
        with module.load_champion(root=root):
            pytest.fail("No debe cargar")


def test_outside_download_rejected_before_deserialization(loading, monkeypatch):
    import mlflow.artifacts

    root, _, deserialize, _ = loading
    monkeypatch.setattr(mlflow.artifacts, "download_artifacts", lambda **kwargs: str(root))
    with pytest.raises(ChampionUnavailable):
        with module.load_champion(root=root):
            pytest.fail("No debe cargar")
    deserialize.assert_not_called()


def test_unverified_bytecode_rejected_before_deserialization(loading, monkeypatch):
    import mlflow.artifacts

    root, _, deserialize, _ = loading
    original = mlflow.artifacts.download_artifacts

    def inject(**kwargs):
        path = Path(original(**kwargs))
        (path / "malicious.pyc").write_bytes(b"not-approved")
        return str(path)

    monkeypatch.setattr(mlflow.artifacts, "download_artifacts", inject)
    with pytest.raises(ChampionUnavailable):
        with module.load_champion(root=root):
            pytest.fail("No debe cargar")
    deserialize.assert_not_called()


def test_compose_transport_keeps_approved_identity_and_uses_explicit_client(loading, monkeypatch):
    import mlflow
    import mlflow.artifacts

    root, _, _, resolve = loading
    client = object()
    factory = Mock(return_value=client)
    monkeypatch.setattr(mlflow, "MlflowClient", factory)
    monkeypatch.setenv("NYC_MLFLOW_TRACKING_URI", "http://mlflow:5000")
    original = mlflow.artifacts.download_artifacts

    def checked_download(**kwargs):
        assert kwargs["tracking_uri"] == kwargs["registry_uri"] == "http://mlflow:5000"
        assert kwargs["artifact_uri"] == "models:/synthetic/4"
        return original(**kwargs)

    monkeypatch.setattr(mlflow.artifacts, "download_artifacts", checked_download)
    with module.load_champion(root=root) as model:
        assert model.identity.version == "4"
    assert all(call.kwargs["client"] is client for call in resolve.call_args_list)
    factory.assert_called_once_with(
        tracking_uri="http://mlflow:5000", registry_uri="http://mlflow:5000"
    )


def test_generated_registry_metadata_is_restored_only_to_exact_approved_hash(tmp_path):
    import hashlib

    approved = b"name: synthetic\r\nversion: 4\r\n"
    decision = {"artifact_files": {"registered_model_meta": hashlib.sha256(approved).hexdigest()}}
    path = tmp_path / "registered_model_meta"
    path.write_bytes(approved.replace(b"\r\n", b"\n"))
    module.restore_generated_metadata(tmp_path, decision)
    assert path.read_bytes() == approved
    path.write_bytes(b"name: unapproved\nversion: 99\n")
    module.restore_generated_metadata(tmp_path, decision)
    assert path.read_bytes() == b"name: unapproved\nversion: 99\n"
