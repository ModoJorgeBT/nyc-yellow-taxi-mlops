"""T19: aprobación humana, versión exacta e integridad antes de deserializar."""

import copy
import importlib.util
import json
from types import SimpleNamespace

import pytest

from src.training import champion as module
from src.training.tracking import sha256
from src.validation.schema import fingerprint


class Registry:
    def __init__(self, decision):
        target = decision["target"]
        self.aliases = {}
        self.mutations = 0
        self.version = SimpleNamespace(
            version=target["version"],
            run_id=target["run_id"],
            source=target["logged_model_uri"],
            status="READY",
            tags={
                "family": "lightgbm",
                "model_sha256": target["model_sha256"],
                "training_manifest_sha256": target["training_manifest_sha256"],
                "code_sha256_at_registration": target["registered_code_sha256"],
                "serving_approved": "false",
            },
        )
        self.run = SimpleNamespace(
            info=SimpleNamespace(status="FINISHED"),
            data=SimpleNamespace(metrics={"mae": 1.0}, params={"train_rows": "2"}),
        )

    def get_model_version(self, name, version):
        return self.version

    def get_registered_model(self, name):
        return SimpleNamespace(aliases=dict(self.aliases))

    def get_run(self, run_id):
        return self.run

    def set_model_version_tag(self, name, version, key, value):
        self.version.tags[key] = value
        self.mutations += 1

    def set_registered_model_alias(self, name, alias, version):
        self.aliases[alias] = version
        self.mutations += 1


@pytest.fixture
def setup(tmp_path, monkeypatch):
    artifact = tmp_path / "package"
    artifact.mkdir()
    (artifact / "fixture.joblib").write_bytes(b"synthetic-not-pickle")
    model_sha = sha256(artifact / "fixture.joblib")
    target = {
        "family": "lightgbm",
        "name": "synthetic-t19",
        "version": "4",
        "run_id": "fixture-run",
        "logged_model_uri": "models:/m-fixture",
        "model_sha256": model_sha,
        "training_manifest_sha256": "a" * 64,
        "registered_code_sha256": "b" * 64,
        "run_metrics_sha256": fingerprint({"mae": 1.0}),
        "run_params_sha256": fingerprint({"train_rows": "2"}),
    }
    row = {"version": "4", "run_id": "fixture-run", "model_sha256": model_sha}
    documents = {
        "tracking_audit": {
            "status": "VERIFIED_T18_TEST_ONLY_SQLITE_ARTIFACTS_AND_LINEAGE",
            "models_verified": {"lightgbm": {**row, "frozen_model_sha256": model_sha}},
        },
        "registration": {"status": "TRACKING_TEST_ONLY", "models": {"lightgbm": row}},
        "final": {
            "status": "FINAL_EVALUATION_TEST_ONLY",
            "publication_complete": True,
            "configuration": {"models": {"lightgbm": {"sha256": model_sha}}},
        },
    }
    evidence = {}
    for role, document in documents.items():
        path = tmp_path / f"{role}.json"
        path.write_text(json.dumps(document))
        evidence[role] = {"path": path.name, "sha256": sha256(path)}
    decision = {
        "format_version": 1,
        "approval_status": "TEST_ONLY",
        "fixture_origin": "synthetic",
        "scope": "initial_champion_only",
        "approved_by": "USER_EXPLICIT_IN_CONVERSATION",
        "approval_id": "synthetic-initial",
        "user_instruction": "synthetic approval fixture",
        "segment_limitations_acknowledged": True,
        "automatic_future_promotion_authorized": False,
        "hyperparameter_search_authorized": False,
        "tracking_uri": "http://127.0.0.1:5000",
        "target": target,
        "evidence": evidence,
        "artifact_files": module.artifact_files(artifact),
        "frozen_model_artifact": "fixture.joblib",
        "resources": {"candidate_timeout_seconds": 7200},
    }
    config = tmp_path / "champion.json"
    config.write_text(json.dumps(decision))

    def verified(decision, root):
        module.verify_artifact_files(artifact, decision)
        return {
            "artifact_manifest_sha256": fingerprint(decision["artifact_files"]),
            "model_sha256": model_sha,
            "synthetic_payloads": 1,
            "maximum_difference_minutes": 0,
        }

    monkeypatch.setattr(module, "_artifact_smoke", verified)
    return config, decision, Registry(decision), artifact


def test_initial_approval_exact_resolution_and_idempotence(setup, tmp_path):
    config, decision, client, _ = setup
    with pytest.raises(module.ChampionUnavailable):
        module.resolve_champion(config, root=tmp_path, client=client, test_only=True)
    receipt = module.approve_initial_champion(config, root=tmp_path, client=client, test_only=True)
    result = module.resolve_champion(config, root=tmp_path, client=client, test_only=True)
    assert result.model_uri == "models:/synthetic-t19/4"
    assert result.model_sha256 == decision["target"]["model_sha256"]
    mutations = client.mutations
    assert (
        module.approve_initial_champion(config, root=tmp_path, client=client, test_only=True)
        == receipt
    )
    assert client.mutations == mutations and receipt["previous_champion_version"] is None


@pytest.mark.parametrize(
    "fault", ["alias_absent", "alias_changed", "tag_changed", "metric_changed"]
)
def test_resolver_rejects_unapproved_registry_changes(setup, tmp_path, fault):
    config, _, client, _ = setup
    module.approve_initial_champion(config, root=tmp_path, client=client, test_only=True)
    if fault == "alias_absent":
        client.aliases.clear()
    elif fault == "alias_changed":
        client.aliases["champion"] = "99"
    elif fault == "tag_changed":
        client.version.tags["approval_sha256"] = "0" * 64
    else:
        client.run.data.metrics["mae"] = 99
    with pytest.raises(module.ChampionUnavailable):
        module.resolve_champion(config, root=tmp_path, client=client, test_only=True)


@pytest.mark.parametrize(
    "fault", ["unapproved", "foreign_run", "foreign_hash", "altered_package", "existing_champion"]
)
def test_approval_fails_before_alias_mutation(setup, tmp_path, fault):
    config, decision, client, artifact = setup
    if fault == "unapproved":
        decision["approval_status"] = "PENDING"
        config.write_text(json.dumps(decision))
    elif fault == "foreign_run":
        client.version.run_id = "another-run"
    elif fault == "foreign_hash":
        client.version.tags["model_sha256"] = "0" * 64
    elif fault == "existing_champion":
        client.aliases["champion"] = "2"
    else:
        (artifact / "fixture.joblib").write_bytes(b"changed")
    with pytest.raises(module.ChampionUnavailable):
        module.approve_initial_champion(config, root=tmp_path, client=client, test_only=True)
    assert client.mutations == 0


def test_fixture_cannot_be_promoted_as_real(setup):
    config, _, _, _ = setup
    with pytest.raises(module.ChampionUnavailable):
        module.read_approval(config)


def test_mixed_model_inside_artifact_is_rejected(setup):
    _, decision, _, artifact = setup
    changed = copy.deepcopy(decision)
    changed["target"]["model_sha256"] = "0" * 64
    with pytest.raises(module.ChampionUnavailable):
        module.verify_artifact_files(artifact, changed)


def test_interrupted_alias_update_requires_recovery_before_resolution(setup, tmp_path, monkeypatch):
    config, _, client, _ = setup
    original = client.set_registered_model_alias

    def uncertain_response(*args):
        original(*args)
        raise OSError("simulated lost HTTP response after applying alias")

    monkeypatch.setattr(client, "set_registered_model_alias", uncertain_response)
    with pytest.raises(OSError):
        module.approve_initial_champion(config, root=tmp_path, client=client, test_only=True)
    with pytest.raises(module.ChampionUnavailable):
        module.resolve_champion(config, root=tmp_path, client=client, test_only=True)
    monkeypatch.setattr(client, "set_registered_model_alias", original)
    result = module.approve_initial_champion(config, root=tmp_path, client=client, test_only=True)
    assert result["previous_champion_version"] is None
    assert (
        module.resolve_champion(config, root=tmp_path, client=client, test_only=True).version == "4"
    )


@pytest.mark.skipif(importlib.util.find_spec("mlflow") is None, reason="Entorno MLflow separado")
def test_alias_in_isolated_real_registry_never_touches_project_registry(
    setup, tmp_path, monkeypatch
):
    monkeypatch.setenv("MLFLOW_DISABLE_TELEMETRY", "true")
    monkeypatch.setenv("MLFLOW_DISABLE_AGENT_HINT", "1")
    from mlflow import MlflowClient

    config, decision, _, artifact = setup
    uri = "sqlite:///" + (tmp_path / "synthetic.db").as_posix()
    client = MlflowClient(tracking_uri=uri, registry_uri=uri)
    experiment = client.create_experiment("synthetic-t19")
    run = client.create_run(experiment)
    client.log_metric(run.info.run_id, "mae", 1.0)
    client.log_param(run.info.run_id, "train_rows", "2")
    client.set_terminated(run.info.run_id)
    client.create_registered_model("synthetic-t19")
    tags = Registry(decision).version.tags
    version = client.create_model_version(
        "synthetic-t19", source=str(artifact), run_id=run.info.run_id, tags=tags
    )
    decision["target"].update(
        version=str(version.version), run_id=run.info.run_id, logged_model_uri=version.source
    )
    for role in ("tracking_audit", "registration"):
        info = decision["evidence"][role]
        path = tmp_path / info["path"]
        document = json.loads(path.read_text())
        row = document["models_verified" if role == "tracking_audit" else "models"]["lightgbm"]
        row.update(version=str(version.version), run_id=run.info.run_id)
        path.write_text(json.dumps(document))
        info["sha256"] = sha256(path)
    config.write_text(json.dumps(decision))
    first = module.approve_initial_champion(config, root=tmp_path, client=client, test_only=True)
    resolved = module.resolve_champion(config, root=tmp_path, client=client, test_only=True)
    assert resolved.version == str(version.version)
    assert client.get_model_version_by_alias("synthetic-t19", "champion").run_id == run.info.run_id
    assert (
        module.approve_initial_champion(config, root=tmp_path, client=client, test_only=True)
        == first
    )
    assert len(client.search_model_versions("name = 'synthetic-t19'")) == 1
