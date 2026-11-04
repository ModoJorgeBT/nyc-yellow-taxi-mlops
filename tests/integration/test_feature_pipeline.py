"""Datos sinteticos validados -> features/target/contexto, sin fit ni aprobacion real."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.features import artifacts
from src.features.schema import FEATURE_COLUMNS, FeatureError
from src.ingestion.download import ingest
from src.validation.run import validate
from src.validation.schema import load_config
from tests.fixtures.factory import make_table
from tests.fixtures.policies import synthetic_policy

CONFIG = Path(__file__).resolve().parents[2] / "configs/data.yaml"


def test_resource_callback_aborts_features_before_publication(tmp_path):
    source = validated_fixture(tmp_path)

    def exhausted():
        raise RuntimeError("D-02 limit")

    with pytest.raises(RuntimeError, match="D-02"):
        artifacts.build_validated_features(
            source, processed_dir=tmp_path / "processed", test_only=True, resource_check=exhausted
        )
    assert not list((tmp_path / "processed").rglob("features_manifest.json"))


def validated_fixture(tmp_path, table=None, *, year=2024, month=1):
    table = make_table() if table is None else table
    raw = tmp_path / "raw" / f"{year:04}/{month:02}"
    raw.mkdir(parents=True)
    pq.write_table(table, raw / f"yellow_tripdata_{year:04}-{month:02}.parquet", row_group_size=6)
    ingest(year, month, raw_dir=tmp_path / "raw", register_local=True)
    config_path = tmp_path / "policy.json"
    config_path.write_text(json.dumps(synthetic_policy(load_config(CONFIG))))
    report = validate(
        year,
        month,
        raw_dir=tmp_path / "raw",
        validated_dir=tmp_path / "validated",
        report_dir=tmp_path / "reports",
        scratch_dir=tmp_path / "scratch",
        config_path=config_path,
        test_only=True,
    )
    assert report["quality_passed"]
    return (tmp_path / "validated" / report["output"]["relative_path"]).parent


def read(path):
    with path.open("rb") as stream, pq.ParquetFile(stream) as parquet:
        return parquet.read()


def test_verified_artifact_features_labels_context_are_separate(tmp_path):
    source = validated_fixture(tmp_path)
    result = artifacts.build_validated_features(
        source, processed_dir=tmp_path / "processed", test_only=True, batch_size=2
    )
    output = Path(result["output_directory"])
    X, y, context = [read(output / f"{name}.parquet") for name in ("features", "target", "context")]
    assert X.column_names == list(FEATURE_COLUMNS)
    assert y.column_names == ["trip_duration_minutes"]
    assert context.column_names == [
        "validated_row_index",
        "pickup_datetime_utc",
        "label_event_datetime_utc",
    ]
    assert X.num_rows == y.num_rows == context.num_rows == result["rows_emitted"] == 12
    assert context["validated_row_index"].to_pylist() == list(range(12))
    assert not result["preprocessor_fitted"] and not result["approved_for_training"]
    assert result["status"] == "FEATURES_TEST_ONLY"
    assert json.loads((output / "features_manifest.json").read_text())["feature_columns"] == list(
        FEATURE_COLUMNS
    )
    assert result["tzdata_version"] == "2026.6"
    assert "DOLocationID" not in X.column_names


@pytest.mark.parametrize(
    "field,value",
    [
        ("approved_for_training", True),
        ("quality_passed", False),
        ("eligibility_complete", False),
        ("rows_scanned", 0),
        ("config_sha256", "bad"),
    ],
)
def test_invalid_validation_marker_blocks_before_output(tmp_path, field, value):
    source = validated_fixture(tmp_path)
    path = source / "validation.json"
    report = json.loads(path.read_text())
    report[field] = value
    path.write_text(json.dumps(report))
    with pytest.raises(FeatureError):
        artifacts.build_validated_features(
            source, processed_dir=tmp_path / "processed", test_only=True
        )
    assert not (tmp_path / "processed").exists()


@pytest.mark.parametrize("failure", ["missing_marker", "changed_data", "normal_mode"])
def test_no_raw_uncommitted_or_unapproved_consumption(tmp_path, failure):
    source = validated_fixture(tmp_path)
    if failure == "missing_marker":
        (source / "validation.json").unlink()
    if failure == "changed_data":
        (source / "data.parquet").write_bytes(b"bad")
    with pytest.raises((FeatureError, RuntimeError)):
        artifacts.build_validated_features(
            source, processed_dir=tmp_path / "processed", test_only=failure != "normal_mode"
        )
    assert not (tmp_path / "processed").exists()


def test_additional_feature_exclusion_preserves_alignment(tmp_path):
    table = make_table()
    values = table["passenger_count"].to_pylist()
    values[0] = -1
    table = table.set_column(
        table.schema.get_field_index("passenger_count"),
        "passenger_count",
        pa.array(values, type=pa.int64()),
    )
    source = validated_fixture(tmp_path, table)
    result = artifacts.build_validated_features(
        source, processed_dir=tmp_path / "processed", test_only=True, batch_size=2
    )
    assert result["rows_seen"] == 12 and result["rows_emitted"] == 11
    assert result["excluded_counts"] == {"invalid_passengers": 1}
    context = read(Path(result["output_directory"]) / "context.parquet")
    assert context["validated_row_index"].to_pylist() == list(range(1, 12))


@pytest.mark.parametrize(
    "pickup,dropoff,bad,expected,reason",
    [
        (
            datetime(2024, 3, 10, 1, 55),
            datetime(2024, 3, 10, 3, 5),
            datetime(2024, 3, 10, 2, 30),
            10.0,
            "nonexistent_local_time",
        ),
        (
            datetime(2024, 11, 3, 0, 55),
            datetime(2024, 11, 3, 2, 5),
            datetime(2024, 11, 3, 1, 30),
            130.0,
            "ambiguous_local_time",
        ),
    ],
)
def test_validated_dst_fixture_is_quarantined_without_guessing(
    tmp_path,
    pickup,
    dropoff,
    bad,
    expected,
    reason,
):
    table = make_table()
    for name, values in (
        ("tpep_pickup_datetime", [bad] + [pickup] * 11),
        ("tpep_dropoff_datetime", [dropoff] * 12),
    ):
        table = table.set_column(
            table.schema.get_field_index(name), name, pa.array(values, type=pa.timestamp("us"))
        )
    source = validated_fixture(tmp_path, table, month=pickup.month)
    result = artifacts.build_validated_features(
        source, processed_dir=tmp_path / "processed", test_only=True
    )
    assert result["rows_emitted"] == 11 and result["excluded_counts"] == {reason: 1}
    output = Path(result["output_directory"])
    assert read(output / "target.parquet")["trip_duration_minutes"].to_pylist() == [expected] * 11
    assert read(output / "context.parquet")["validated_row_index"].to_pylist() == list(range(1, 12))


def test_input_changed_during_feature_build_blocks_publication(tmp_path, monkeypatch):
    source = validated_fixture(tmp_path)
    original = artifacts.prepare_historical

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        path = source / "validation.json"
        report = json.loads(path.read_text())
        report["pipeline_version"] = "changed"
        path.write_text(json.dumps(report))
        return result

    monkeypatch.setattr(artifacts, "prepare_historical", changed)
    with pytest.raises(FeatureError, match="cambio"):
        artifacts.build_validated_features(
            source, processed_dir=tmp_path / "processed", test_only=True
        )
    assert not list((tmp_path / "processed").rglob("*.parquet"))
    assert not list((tmp_path / "processed").rglob(".features-*"))


def test_cli_help_and_rejection(tmp_path):
    source = validated_fixture(tmp_path)
    command = [sys.executable, "-I", "-m", "src.features.build"]
    help_result = subprocess.run(
        command + ["--help"], cwd=tmp_path, capture_output=True, text=True, timeout=60
    )
    assert help_result.returncode == 0 and "--validated-batch" in help_result.stdout
    args = ["--validated-batch", str(source), "--processed-dir", str(tmp_path / "processed")]
    success = subprocess.run(
        command + args + ["--test-only"], cwd=tmp_path, capture_output=True, text=True, timeout=60
    )
    assert success.returncode == 0, success.stderr
    assert json.loads(success.stdout)["status"] == "FEATURES_TEST_ONLY"
    failed = subprocess.run(
        command + args, cwd=tmp_path, capture_output=True, text=True, timeout=60
    )
    assert failed.returncode == 1 and "D-04" in failed.stderr


def test_feature_marker_failure_leaves_uncommitted_files(tmp_path, monkeypatch):
    source = validated_fixture(tmp_path)

    def failed(*args):
        raise OSError("marker publication failed")

    monkeypatch.setattr(artifacts, "publish_manifest", failed)
    with pytest.raises(OSError, match="marker"):
        artifacts.build_validated_features(
            source, processed_dir=tmp_path / "processed", test_only=True
        )
    assert len(list((tmp_path / "processed").rglob("*.parquet"))) == 3
    assert not list((tmp_path / "processed").rglob("features_manifest.json"))
    assert not list((tmp_path / "processed").rglob(".features-*"))


def test_no_usable_dst_rows_returns_reason_without_output(tmp_path):
    table = make_table()
    for name, value in (
        ("tpep_pickup_datetime", datetime(2024, 11, 3, 1, 30)),
        ("tpep_dropoff_datetime", datetime(2024, 11, 3, 2, 0)),
    ):
        table = table.set_column(
            table.schema.get_field_index(name),
            name,
            pa.array([value] * 12, type=pa.timestamp("us")),
        )
    source = validated_fixture(tmp_path, table, month=11)
    with pytest.raises(FeatureError, match="ambiguous_local_time"):
        artifacts.build_validated_features(
            source, processed_dir=tmp_path / "processed", test_only=True
        )
    assert not list((tmp_path / "processed").rglob("*.parquet"))
