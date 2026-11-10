import json
from copy import deepcopy

from src.monitoring.protocol import envelope
from src.retraining.protocol import read_json
from src.retraining.triggers import evaluate
from src.validation.run import _sha256
from tests.unit.test_retraining_triggers import report


def inputs(root):
    monitor = deepcopy(read_json("configs/monitoring.yaml"))
    monitor.update(status="TEST_ONLY", fixture_origin="synthetic")
    mon_path = root / "monitor.json"
    mon_path.write_text(json.dumps(monitor))
    quality = {"schema_changes": {"removed_columns": [], "changed_fields": {}}}
    entries = []
    for month in [7, 8]:
        value = report(mae=20)
        value.update(
            **envelope(monitor),
            status="MONITORING_TEST_ONLY",
            scope="TEST_ONLY",
            publication_complete=True,
            year=2025,
            month=month,
            models_fitted=False,
            model_changed=False,
            quality=quality,
        )
        value["prediction"]["model"] = {"model_sha256": monitor["model"]["sha256"]}
        path = root / f"{month}.json"
        path.write_text(json.dumps(value))
        entries.append({"path": path.name, "sha256": _sha256(path), "year": 2025, "month": month})
    profile = deepcopy(read_json("configs/retraining.yaml"))
    profile.update(
        status="TEST_ONLY",
        fixture_origin="synthetic",
        monitoring_config={"path": mon_path.name, "sha256": _sha256(mon_path)},
        monitoring_reports=entries,
    )
    path = root / "profile.json"
    path.write_text(json.dumps(profile))
    return path, profile, quality


def test_frozen_reports_recommend_without_reading_training_data(tmp_path, monkeypatch):
    config, _, quality = inputs(tmp_path)
    monkeypatch.setattr("src.retraining.triggers.quality_observation", lambda *a: quality)
    _, result = evaluate(config, root=tmp_path, test_only=True)
    assert result["publication_complete"] and result["decision"] == "RETRAIN_RECOMMENDED"
    assert not result["training_started"] and not result["champion_changed"]
    (tmp_path / "7.json").write_text("{}")
    _, blocked = evaluate(config, root=tmp_path, test_only=True)
    assert blocked["decision"] == "BLOCKED_REVIEW" and not blocked["publication_complete"]


def test_wrong_model_and_unaccepted_quality_block(tmp_path, monkeypatch):
    config, profile, quality = inputs(tmp_path)
    monkeypatch.setattr("src.retraining.triggers.quality_observation", lambda *a: quality)
    path = tmp_path / "7.json"
    value = read_json(path)
    value["prediction"]["model"]["model_sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    profile["monitoring_reports"][0]["sha256"] = _sha256(path)
    config.write_text(json.dumps(profile))
    _, blocked = evaluate(config, root=tmp_path, test_only=True)
    assert blocked["decision"] == "BLOCKED_REVIEW"
