import json
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from src.retraining import lifecycle, promote, rollback
from src.retraining.compare import CONTROLS
from src.retraining.protocol import exclusive_json
from src.training.champion import ChampionUnavailable
from src.validation.run import _sha256
from src.validation.schema import fingerprint


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    root = tmp_path
    exclusive_json(root / "ISOLATED_DEMO.json", {"status": "TEST_ONLY", "scope_id": "a" * 32})

    def decision(version):
        return {
            "format_version": 2,
            "scope": "controlled_champion_v2",
            "approval_status": "TEST_ONLY",
            "approved_by": "USER_APPROVED_SYNTHETIC_DEMO",
            "automatic_future_promotion_authorized": False,
            "action": "BOOTSTRAP_FIXTURE",
            "operation_id": "initial",
            "tracking_uri": "http://127.0.0.1:55443",
            "fixture_origin": "synthetic",
            "scope_id": "a" * 32,
            "artifact_files": {"model": version * 64},
            "frozen_model_artifact": "model",
            "target": {
                "name": "synthetic-demo",
                "version": version,
                "run_id": "run" + version,
                "family": "fixture_constant",
                "model_sha256": version * 64,
                "logged_model_uri": "models:/m" + version,
                "run_metrics_sha256": fingerprint({}),
                "run_params_sha256": fingerprint({}),
            },
            "smoke": {"payloads": [{}], "expected_minutes": [10.0]},
        }

    before, after = decision("1"), decision("2")
    active = root / "active.json"
    exclusive_json(active, before)
    after.update(action="PROMOTE", operation_id="promote", previous_approval_sha256=_sha256(active))
    metric = {
        "rows": 1000,
        "mae_minutes": 2.0,
        "rmse_minutes": 2.0,
        "medae_minutes": 2.0,
        "p90_absolute_error_minutes": 2.0,
    }
    good = {k: (v if k == "rows" else 0.0) for k, v in metric.items()}
    evaluation = {
        "status": "PAIRED_EVALUATION_TEST_ONLY",
        "publication_complete": True,
        "fixture_origin": "synthetic",
        "candidate_sha256": "2" * 64,
        "metrics": {"champion": {"all": metric}, "challenger": {"all": good}},
        "required_segments": [],
        "controls": dict.fromkeys(CONTROLS, True),
    }
    exclusive_json(root / "evaluation.json", evaluation)
    gate = {
        "status": "COMPARISON_TEST_ONLY",
        "decision": "ELIGIBLE_FOR_HUMAN_REVIEW",
        "publication_complete": True,
        "evaluation": {"path": "evaluation.json", "sha256": _sha256(root / "evaluation.json")},
    }
    exclusive_json(root / "gate.json", gate)
    after["gate"] = {"path": "gate.json", "sha256": _sha256(root / "gate.json")}
    approval = root / "approval.json"
    exclusive_json(approval, after)

    class Registry:
        def __init__(self):
            self.aliases = {"champion": "1"}
            self.writes = []

        def get_registered_model(self, name):
            return NS(aliases=dict(self.aliases))

        def get_model_version(self, name, version):
            return NS(
                run_id="run" + version,
                status="READY",
                source="models:/m" + version,
                tags={"family": "fixture_constant", "model_sha256": version * 64},
            )

        def get_run(self, run):
            return NS(info=NS(status="FINISHED"), data=NS(metrics={}, params={}))

        def set_registered_model_alias(self, name, alias, version):
            self.writes.append(version)
            self.aliases[alias] = version

    client = Registry()
    for module in [lifecycle, promote, rollback]:
        monkeypatch.setattr(module, "client_for", lambda _: client)
    lifecycle.event(root, "initial", "VERIFIED", approval_sha256=fingerprint(before))

    class API:
        def __init__(self):
            self.starts = 0
            self.stops = 0

        def verify_binding(self, r, a):
            assert r == root and a == active

        def binding(self):
            return {"root": str(root), "active": str(active)}

        def verify_package(self, decision):
            pass

        def stop(self):
            self.stops += 1

        def start(self):
            self.starts += 1

        def smoke(self, decision):
            assert json.loads(active.read_text())["target"] == decision["target"]

    return root, active, approval, before, after, client, API()


def test_promotion_and_idempotent_rollback_preserve_prior_bytes(scenario):
    root, active, approval, _, _, client, api = scenario
    original = active.read_bytes()
    assert promote.promote(approval, active, api, root=root, test_only=True)["state"] == "VERIFIED"
    assert lifecycle.resolve_champion(active, root=root, test_only=True).version == "2"
    rollback.restore("promote", api, root=root)
    assert client.aliases == {"champion": "1"} and active.read_bytes() == original
    starts = api.starts
    rollback.restore("promote", api, root=root)
    assert api.starts == starts


def test_failed_smoke_compensates_without_losing_evidence(scenario):
    root, active, approval, _, _, client, api = scenario

    def fail(phase):
        if phase == "before_smoke":
            raise ValueError("smoke failure")

    with pytest.raises(ValueError, match="smoke failure"):
        promote.promote(approval, active, api, root=root, test_only=True, fault=fail)
    assert client.aliases == {"champion": "1"}
    assert [e["state"] for e in lifecycle.events(root, "promote")] == [
        "PREPARED",
        "ALIAS_APPLIED",
        "APPLIED",
        "FAILED",
        "ROLLED_BACK",
    ]


def test_idempotent_promotion_detects_external_alias_change(scenario):
    root, active, approval, _, _, client, api = scenario
    promote.promote(approval, active, api, root=root, test_only=True)
    starts = api.starts
    promote.promote(approval, active, api, root=root, test_only=True)
    assert api.starts == starts and client.writes == ["2"]
    client.aliases["champion"] = "3"
    with pytest.raises(ChampionUnavailable, match="Alias"):
        promote.promote(approval, active, api, root=root, test_only=True)
    assert client.aliases == {"champion": "3"} and client.writes == ["2"]


def test_external_alias_conflict_never_overwritten(scenario):
    root, active, approval, _, _, client, api = scenario

    def conflict(phase):
        if phase == "after_alias":
            client.aliases["champion"] = "3"
            raise ValueError("external")

    with pytest.raises(ChampionUnavailable, match="ajeno"):
        promote.promote(approval, active, api, root=root, test_only=True, fault=conflict)
    assert client.aliases == {"champion": "3"} and client.writes == ["2"]
    assert lifecycle.events(root, "promote")[-1]["state"] == "CONFLICT"


@pytest.mark.parametrize("field", ["approval_status", "approved_by", "scope_id", "gate"])
def test_missing_approval_rejected_before_registry_write(scenario, field):
    root, active, approval, _, after, client, api = scenario
    value = deepcopy(after)
    value[field] = "invalid" if field != "gate" else {"path": "missing", "sha256": "0" * 64}
    approval.write_text(json.dumps(value))
    with pytest.raises((ValueError, OSError)):
        promote.promote(approval, active, api, root=root, test_only=True)
    assert not client.writes and not api.stops


def test_fixture_cannot_be_real_or_target_protected_endpoint(scenario):
    root, _, approval, _, after, _, _ = scenario
    with pytest.raises(ChampionUnavailable):
        lifecycle.read_approval(approval, root=root)
    after["tracking_uri"] = "http://127.0.0.1:5000"
    approval.write_text(json.dumps(after))
    with pytest.raises(ChampionUnavailable):
        lifecycle.read_approval(approval, root=root, test_only=True)


def test_gate_cannot_compare_against_a_different_previous_champion(scenario):
    root, _, _, before, after, _, _ = scenario
    evaluation = json.loads((root / "evaluation.json").read_text())
    evaluation["champion"] = before["target"]
    (root / "evaluation.json").write_text(json.dumps(evaluation))
    gate = json.loads((root / "gate.json").read_text())
    gate["evaluation"]["sha256"] = _sha256(root / "evaluation.json")
    (root / "gate.json").write_text(json.dumps(gate))
    entry = {"path": "gate.json", "sha256": _sha256(root / "gate.json")}
    lifecycle.require_gate(root, entry, after["target"], test_only=True, previous=before["target"])
    with pytest.raises(ChampionUnavailable, match="champion evaluado"):
        lifecycle.require_gate(
            root,
            entry,
            after["target"],
            test_only=True,
            previous={**before["target"], "model_sha256": "9" * 64},
        )


def test_partial_operation_with_stale_lock_recovers_without_removing_active_lock(
    scenario, monkeypatch
):
    root, active, approval, before, after, client, api = scenario
    lifecycle.event(
        root,
        "partial",
        "PREPARED",
        previous=before,
        proposed=after,
        previous_bytes_hex=active.read_bytes().hex(),
        previous_aliases={"champion": "1"},
        active_path="active.json",
        controller=api.binding(),
    )
    client.aliases["champion"] = "2"
    marker = root / "tracking/lifecycle/.ingestion.lock"
    marker.write_text("12345")
    monkeypatch.setattr(rollback, "process_alive", lambda pid: True)
    with pytest.raises(ChampionUnavailable, match="activo"):
        rollback.restore("partial", api, root=root, recover_stale_lock=True)
    assert marker.exists() and client.aliases["champion"] == "2"
    monkeypatch.setattr(rollback, "process_alive", lambda pid: False)
    rollback.restore("partial", api, root=root, recover_stale_lock=True)
    assert client.aliases["champion"] == "1"
    assert list(marker.parent.glob("stale-lock-*.txt"))
