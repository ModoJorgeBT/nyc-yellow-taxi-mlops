import pytest

from src.retraining.evaluate import ACTIONS, execute
from src.validation.schema import fingerprint


def scenario(decision):
    trigger = {"publication_complete": True, "decision": decision}
    approval = {
        "status": "TEST_ONLY",
        "trigger_sha256": fingerprint(trigger),
        "allowed_actions": list(ACTIONS),
        "automatic_promotion": False,
    }
    calls = []

    def action(name):
        def run():
            calls.append(name)
            return {
                "publication_complete": True,
                "mode": "TEST_ONLY",
                "candidate_registered": name == "register",
            }

        return run

    return trigger, approval, {n: action(n) for n in ACTIONS}, calls


def test_no_trigger_never_calls_train_even_with_approval():
    t, a, actions, calls = scenario("NO_ACTION")
    assert execute(t, actions, approval=a)["status"] == "NO_ACTION" and not calls


def test_recommendation_without_execution_approval_does_not_train():
    t, _, actions, calls = scenario("RETRAIN_RECOMMENDED")
    assert execute(t, actions)["status"] == "EXECUTION_APPROVAL_REQUIRED" and not calls


def test_authorized_workflow_registers_but_has_no_promotion_stage():
    t, a, actions, calls = scenario("RETRAIN_RECOMMENDED")
    result = execute(t, actions, approval=a)
    assert calls == list(ACTIONS)
    assert result["steps"][3]["candidate_registered"] and not result["champion_changed"]
    actions["promote"] = lambda: pytest.fail("No promocion")
    with pytest.raises(ValueError, match="grafo"):
        execute(t, actions, approval=a)


def test_fixture_scope_not_accepted_for_real_execution():
    t, a, actions, calls = scenario("RETRAIN_RECOMMENDED")
    assert (
        execute(t, actions, approval=a, test_only=False)["status"] == "EXECUTION_APPROVAL_REQUIRED"
    )
    assert not calls
