"""Excepcion puntual REAL con fixtures; FAIL original y exclusiones intactos."""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.features.artifacts import build_validated_features, verify_validated
from src.validation.run import validate
from tests.integration.test_real_data_quality import setup


def exception_fixture(tmp_path):
    options, _ = setup(tmp_path, case="nonpositive_duration")
    config = json.loads(options["config_path"].read_text())
    config["quality"]["fail_rates"]["duration_nonpositive"] = 0
    options["config_path"].write_text(json.dumps(config))
    rejected = validate(2024, 1, **options)
    assert rejected["status"] == "FAIL", rejected.get("error")
    failures = [c for c in rejected["checks"] if c["status"] == "FAIL"]
    assert len(failures) == 1 and failures[0]["rule"] == "rows.duration_nonpositive"
    original = Path(rejected["report_path"])
    document = {
        "format_version": 1,
        "approval_status": "APPROVED",
        "approved_by": "USER_EXPLICIT_IN_CONVERSATION",
        "exception_id": "synthetic-only",
        "preserve_invalid_row_exclusions": True,
        "allow_other_failures": False,
        "allow_other_lots": False,
        "year": 2024,
        "month": 1,
        "raw_sha256": rejected["input"]["manifest"]["sha256"],
        "config_sha256": rejected["config_sha256"],
        "policy_version": rejected["policy_version"],
        "allowed_failure": failures[0],
        "rejected_report": {
            "relative_path": str(original),
            "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        },
    }
    path = tmp_path / "exception.json"
    path.write_text(json.dumps(document))
    return options, rejected, path


def test_exact_exception_preserves_fail_and_all_invalid_exclusions(tmp_path):
    options, rejected, path = exception_fixture(tmp_path)
    original = Path(rejected["report_path"]).read_bytes()
    accepted = validate(2024, 1, exception_path=path, **options)
    assert accepted["execution_status"] == "VALIDATED_REAL_EXCEPTION", accepted.get("error")
    assert accepted["status"] == "WARN" and accepted["raw_quality_status"] == "FAIL"
    assert not accepted["quality_passed"] and accepted["data_quality_approved"]
    assert not accepted["approved_for_training"]
    assert [c for c in accepted["checks"] if c["status"] == "FAIL"] == [
        json.loads(path.read_text())["allowed_failure"]
    ]
    assert accepted["excluded_rows"] == rejected["excluded_rows"] > 0
    output = options["validated_dir"] / accepted["output"]["relative_path"]
    verified, _ = verify_validated(output.parent, test_only=False)
    assert verified == accepted
    with pq.ParquetFile(output) as data:
        assert data.metadata.num_rows == accepted["eligible_rows"]
    features = build_validated_features(output.parent, processed_dir=tmp_path / "features")
    assert features["rows_emitted"] == accepted["eligible_rows"]
    assert features["source_quality_exception"] == accepted["quality_exception"]
    assert Path(rejected["report_path"]).read_bytes() == original
    normal = validate(2024, 1, **options)
    assert normal["status"] == "FAIL" and normal["output"] is None


@pytest.mark.parametrize(
    "change", ["month", "hash", "policy", "unapproved", "broad", "malformed", "original"]
)
def test_wrong_authorization_blocks_before_scan(tmp_path, monkeypatch, change):
    options, rejected, path = exception_fixture(tmp_path)
    document = json.loads(path.read_text())
    if change == "month":
        document["month"] = 2
    elif change == "hash":
        document["raw_sha256"] = "0" * 64
    elif change == "policy":
        document["config_sha256"] = "0" * 64
    elif change == "unapproved":
        document["approval_status"] = "PENDING"
    elif change == "broad":
        document["allow_other_failures"] = True
    elif change == "malformed":
        document.pop("rejected_report")
    else:
        Path(rejected["report_path"]).write_text("{}")
    path.write_text(json.dumps(document))
    monkeypatch.setattr("src.validation.run._scan", lambda *a, **k: pytest.fail("No escanear"))
    result = validate(2024, 1, exception_path=path, **options)
    assert result["status"] == "FAIL" and result["output"] is None


@pytest.mark.parametrize("change", ["additional_failure", "changed_count"])
def test_exception_does_not_cover_new_failures_or_counts(tmp_path, monkeypatch, change):
    options, _, path = exception_fixture(tmp_path)
    from src.validation import run

    original = run._scan

    def changed(*args, **kwargs):
        report = original(*args, **kwargs)
        if change == "additional_failure":
            report["checks"].append({"rule": "rows.other", "status": "FAIL"})
        else:
            report["excluded_rows"] += 1
        return report

    monkeypatch.setattr(run, "_scan", changed)
    result = validate(2024, 1, exception_path=path, **options)
    assert result["status"] == "FAIL" and result["output"] is None


def test_revocation_blocks_downstream_consumption(tmp_path):
    options, _, path = exception_fixture(tmp_path)
    accepted = validate(2024, 1, exception_path=path, **options)
    assert accepted["data_quality_approved"], accepted.get("error")
    folder = (options["validated_dir"] / accepted["output"]["relative_path"]).parent
    doc = json.loads(path.read_text())
    doc["approval_status"] = "REVOKED"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="Excepcion"):
        verify_validated(folder, test_only=False)
