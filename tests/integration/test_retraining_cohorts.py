import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.features.artifacts import build_validated_features
from src.ingestion.manifest import IngestionError, describe_parquet
from src.retraining.audit import audit_cohort
from src.retraining.cohorts import prepare, verify_cohort
from src.retraining.protocol import read_json
from src.validation.run import _sha256
from tests.fixtures.factory import make_table
from tests.integration.test_feature_pipeline import validated_fixture


def prepared(root):
    root.mkdir(parents=True, exist_ok=True)
    profile = deepcopy(read_json("configs/retraining.yaml"))
    profile.update(status="TEST_ONLY", fixture_origin="synthetic")
    data = root / "data-config.json"
    data.write_bytes(Path("configs/data.yaml").read_bytes())
    old = root / "original.json"
    old.write_text(json.dumps({"configuration": {"quality_rules_sha256": "synthetic"}}))
    for key, path in [("data_config", data), ("original_split", old)]:
        profile[key] = {"path": path.name, "sha256": _sha256(path)}
    monitor = read_json("configs/monitoring.yaml")
    monitor.update(status="TEST_ONLY", fixture_origin="synthetic")
    extras = {
        "monitoring_config": monitor,
        "champion_approval": {},
        "original_validation": {"route_catalog": {"routes": []}},
    }
    for key, value in extras.items():
        path = root / f"{key}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        profile[key] = {"path": path.name, "sha256": _sha256(path)}
    for key, name in [
        ("lightgbm_config", "configs/lightgbm.yaml"),
        ("runtime_lock", "requirements-serving.lock"),
    ]:
        path = root / Path(name).name
        path.write_bytes(Path(name).read_bytes())
        profile[key] = {"path": path.name, "sha256": _sha256(path)}
    config = root / "config.json"
    config.write_text(json.dumps(profile), encoding="utf-8")
    base = make_table().to_pylist()[0]
    entries = []
    for month in range(1, 13):
        rows = []
        for minute in range(4):
            pickup = datetime(2025, month, 15, 8, minute)
            rows.append(
                {
                    **base,
                    "tpep_pickup_datetime": pickup,
                    "tpep_dropoff_datetime": pickup + timedelta(minutes=10),
                }
            )
        if month == 12:
            rows.append(
                {
                    **base,
                    "tpep_pickup_datetime": datetime(2025, 12, 31, 23, 59),
                    "tpep_dropoff_datetime": datetime(2026, 1, 1),
                }
            )
        table = pa.Table.from_pylist(rows, schema=make_table().schema)
        valid = validated_fixture(root / f"valid-{month}", table, year=2025, month=month)
        features = build_validated_features(
            valid, processed_dir=root / f"features-{month}", test_only=True
        )
        entries.append(
            {
                "year": 2025,
                "month": month,
                "validated_directory": str(valid.relative_to(root)),
                "features_directory": str(Path(features["output_directory"]).relative_to(root)),
            }
        )
    catalog = root / "catalog.json"
    catalog.write_text(json.dumps({"batches": entries}), encoding="utf-8")
    return config, catalog, profile


def test_new_annual_cut_restores_intermediate_months_and_excludes_final_label(tmp_path):
    config, catalog, profile = prepared(tmp_path)
    output, result = prepare(catalog, "train", profile_path=config, root=tmp_path, test_only=True)
    assert result["rows"] == 48 and result["label_cutoff_exclusions"] == 1
    assert result["source_rows"] == 49
    assert verify_cohort(output, "train", profile, test_only=True) == result
    _, audited = audit_cohort(output, "train", profile_path=config, root=tmp_path, test_only=True)
    assert audited["all_values_verified"] and audited["matched_rows"] == 48
    with pytest.raises(ValueError):
        verify_cohort(output, "train", profile, test_only=False)
    with (output / "train/target.parquet").open("ab") as stream:
        stream.write(b"altered")
    with pytest.raises(IngestionError):
        verify_cohort(output, "train", profile, test_only=True)


def test_missing_month_cannot_publish_cohort(tmp_path):
    config, catalog, _ = prepared(tmp_path)
    data = read_json(catalog)
    data["batches"].pop()
    catalog.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="exactamente"):
        prepare(catalog, "train", profile_path=config, root=tmp_path, test_only=True)


def test_independent_audit_catches_rehashed_wrong_labels(tmp_path):
    config, catalog, profile = prepared(tmp_path)
    output, result = prepare(catalog, "train", profile_path=config, root=tmp_path, test_only=True)
    path = output / "train/target.parquet"
    table = pq.read_table(path)
    table = table.set_column(0, table.schema.field(0), pa.array([11.0] * len(table)))
    pq.write_table(table, path)
    result["artifacts"]["target"] = describe_parquet(path)
    (output / "cohort.json").write_text(json.dumps(result), encoding="utf-8")
    verify_cohort(output, "train", profile, test_only=True)
    with pytest.raises(ValueError, match="target"):
        audit_cohort(output, "train", profile_path=config, root=tmp_path, test_only=True)
