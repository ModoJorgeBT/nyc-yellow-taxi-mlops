import json

from src.retraining.cohorts import prepare
from src.retraining.protocol import read_json
from src.retraining.train_challenger import train
from src.validation.run import _sha256
from src.validation.schema import fingerprint
from tests.integration.test_retraining_cohorts import prepared


def trigger(root, profile, decision="RETRAIN_RECOMMENDED"):
    path = root / "trigger.json"
    path.write_text(
        json.dumps(
            {
                "status": "TRIGGER_TEST_ONLY",
                "profile_sha256": fingerprint(profile),
                "publication_complete": True,
                "decision": decision,
            }
        ),
        encoding="utf-8",
    )
    return {"path": path.name, "sha256": _sha256(path)}


def test_no_recommendation_never_trains(tmp_path, monkeypatch):
    import pytest

    import src.retraining.train_challenger as module

    config, _, profile = prepared(tmp_path)
    monkeypatch.setattr(
        module, "run_worker", lambda *a, **k: pytest.fail("NO_ACTION no puede entrenar")
    )
    with pytest.raises(ValueError, match="Sin trigger"):
        train(
            tmp_path,
            trigger(tmp_path, profile, "NO_ACTION"),
            profile_path=config,
            root=tmp_path,
            test_only=True,
        )


def test_native_challenger_uses_all_train_without_future_files(tmp_path):
    config, catalog, profile = prepared(tmp_path)
    cohort, manifest = prepare(catalog, "train", profile_path=config, root=tmp_path, test_only=True)
    output, report = train(
        cohort, trigger(tmp_path, profile), profile_path=config, root=tmp_path, test_only=True
    )
    assert report["publication_complete"], report.get("error")
    assert report["rows"] == manifest["rows"] == 48
    assert report["native"]["dataset_rows"] == 48
    assert not report["validation_accessed"] and not report["final_accessed"]
    assert not report["champion_changed"] and not report["approved_for_serving"]
    assert read_json(output / "training_manifest.json")["model_sha256"] == _sha256(
        output / "lightgbm.joblib"
    )


def test_bounded_disk_writer_matches_legacy_native_bytes(tmp_path):
    from src.retraining.protocol import budget
    from src.retraining.train_challenger import prepare_disk as bounded
    from src.training.candidate_runtime import CandidateGuard
    from src.training.lightgbm_train import prepare_disk as legacy

    config, catalog, _ = prepared(tmp_path)
    cohort, manifest = prepare(catalog, "train", profile_path=config, root=tmp_path, test_only=True)
    left, right = tmp_path / "legacy", tmp_path / "bounded"
    left.mkdir()
    right.mkdir()
    guard = CandidateGuard(budget("training"), tmp_path, test_only=True)
    old = legacy(cohort, left, guard, manifest["rows"])
    new = bounded(cohort, right, guard, manifest["rows"])
    assert old[1:] == new[1:]
    assert (left / "features.f32").read_bytes() == (right / "features.f32").read_bytes()
    assert (left / "target.f64").read_bytes() == (right / "target.f64").read_bytes()
