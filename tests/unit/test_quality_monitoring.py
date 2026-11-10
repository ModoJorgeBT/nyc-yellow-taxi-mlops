"""Referencia train, alertas de DQ y rechazo de evidencia alterada; fixtures sinteticas."""

import copy
import hashlib
import json

import pytest

from src.monitoring import data_quality as module


@pytest.fixture
def evidence(tmp_path):
    configuration = {
        "schema": {"required": ["pickup"]},
        "quality": {"policy_version": "synthetic", "fail_rates": {"invalid": 0.01}},
    }
    config = {
        "status": "TEST_ONLY",
        "scope": "quality_schema_only",
        "new_thresholds_authorized": False,
        "training_authorized": False,
        "reference_year": 2024,
        "policy_identity_sha256": module.policy_identity(configuration),
        "reference_reports": [],
        "current_reports": [],
    }

    def write(year, month, *, fail=False, complete=True):
        report = {
            "mode": "TEST_ONLY",
            "fixture_origin": "synthetic",
            "lineage_status": "VERIFIED_CONTENT",
            "year": year,
            "month": month,
            "configuration": configuration,
            "input": {
                "manifest": {
                    "sha256": "a" * 64,
                    "year": year,
                    "month": month,
                    "row_count": 100,
                    "schema": [{"name": "pickup", "type": "timestamp[us]", "nullable": True}],
                }
            },
            "scan_scope": "FULL_PARQUET" if complete else "PREFLIGHT_ONLY",
            "eligibility_complete": complete,
            "rows_scanned": 100 if complete else None,
            "status": "FAIL" if fail else "PASS",
            "data_quality_approved": True,
            "excluded_rows": 2 if fail else 0,
            "checks": [
                {
                    "rule": "rows.invalid",
                    "status": "FAIL" if fail else "PASS",
                    "observed": {"count": 2 if fail else 0, "rate": 0.02 if fail else 0},
                }
            ],
        }
        path = tmp_path / f"{year}-{month:02}.json"
        path.write_text(json.dumps(report))
        return {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "raw_sha256": "a" * 64,
            "year": year,
            "month": month,
        }

    config["reference_reports"] = [write(2024, m) for m in range(1, 13)]
    config["current_reports"] = [write(2025, 7, fail=True)]
    return tmp_path, config, write


def test_reference_full_train_and_fail_preserved_despite_acceptance(evidence):
    root, config, _ = evidence
    reference = module.reference_payload(config, root)
    current = module.read_profile(config["current_reports"][0], config, root)
    result = module.compare(reference["profiles"][6], current)
    assert len(reference["profiles"]) == 12
    assert result["status"] == "ALERT_D04_FAIL" and current["dataset_acceptance"]
    assert not result["new_quality_exception_granted"]
    assert result["rate_changes_descriptive"]["rows.invalid"]["delta_percentage_points"] == 2


def test_schema_change_is_visible_and_does_not_authorize_new_features(evidence):
    root, config, _ = evidence
    reference = module.reference_payload(config, root)["profiles"][0]
    current = copy.deepcopy(reference)
    current["raw_schema"].append({"name": "after_trip_fee", "type": "double", "nullable": True})
    result = module.compare(reference, current)
    assert result["status"] == "SCHEMA_CHANGE"
    assert result["schema_changes"]["added_columns"] == ["after_trip_fee"]
    assert not result["monitoring_grants_dataset_approval"]


def test_incompatible_schema_rejection_is_observed_without_row_statistics(evidence):
    root, config, write = evidence
    entry = write(2025, 8, fail=True, complete=False)
    path = root / entry["path"]
    report = json.loads(path.read_text())
    report["checks"] = [
        {"rule": "schema.structure", "status": "FAIL", "observed": {"missing": ["pickup"]}}
    ]
    path.write_text(json.dumps(report))
    entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    current = module.read_profile(entry, config, root)
    assert not current["complete_row_statistics"] and current["metrics"] == {}
    assert (
        module.compare(module.reference_payload(config, root)["profiles"][7], current)["status"]
        == "ALERT_D04_FAIL"
    )


def test_altered_report_and_test_only_reference_cannot_be_used_as_real(evidence):
    root, config, _ = evidence
    path = root / config["reference_reports"][0]["path"]
    path.write_text("{}")
    with pytest.raises(ValueError, match="modificado"):
        module.reference_payload(config, root)
    config_path = root / "monitoring.yaml"
    config_path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        module.load_monitoring_config(config_path)
    assert module.load_monitoring_config(config_path, test_only=True)["status"] == "TEST_ONLY"


def test_reference_with_quality_fail_or_future_period_is_blocked(evidence):
    root, config, write = evidence
    config["reference_reports"][0] = write(2024, 1, fail=True)
    with pytest.raises(ValueError, match="referencia"):
        module.reference_payload(config, root)
    config["reference_year"] = 2025
    path = root / "config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        module.load_monitoring_config(path, test_only=True)


def test_authorization_metadata_is_excluded_but_threshold_changes_are_detected(evidence):
    _, _, _ = evidence
    original = {
        "schema": {},
        "quality": {"fail_rates": {"invalid": 0.01}, "local_authorizations": [1]},
    }
    changed = copy.deepcopy(original)
    changed["quality"]["local_authorizations"] = [1, 2]
    assert module.policy_identity(original) == module.policy_identity(changed)
    changed["quality"]["fail_rates"]["invalid"] = 0.02
    assert module.policy_identity(original) != module.policy_identity(changed)
