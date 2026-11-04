"""Perfil real ejercitado solo con fixtures; nunca abre el piloto TLC real."""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.features.artifacts import build_validated_features
from src.ingestion.download import ingest
from src.validation import run
from src.validation.schema import load_config
from tests.fixtures.factory import make_table
from tests.fixtures.policies import real_fixture_policy

CONFIG = Path(__file__).resolve().parents[2] / "configs/data.yaml"


def setup(tmp_path, *, authorize=True, miniature_limits=True, case="valid"):
    folder = tmp_path / "raw/2024/01"
    folder.mkdir(parents=True)
    pq.write_table(make_table(case), folder / "yellow_tripdata_2024-01.parquet", row_group_size=6)
    ingested = ingest(2024, 1, raw_dir=tmp_path / "raw", register_local=True)
    config = load_config(CONFIG)
    if miniature_limits:
        config = real_fixture_policy(config)
    if authorize:
        config["quality"]["local_authorizations"] = [
            {"year": 2024, "month": 1, "sha256": ingested["sha256"], "academic_use_approved": True}
        ]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return {
        "raw_dir": tmp_path / "raw",
        "validated_dir": tmp_path / "validated",
        "report_dir": tmp_path / "reports",
        "scratch_dir": tmp_path / "scratch",
        "config_path": path,
        "batch_size": 2,
    }, ingested


def test_real_publish_preserves_unknown_provenance_and_blocks_training(tmp_path):
    options, ingested = setup(tmp_path, case="invalid_passengers")
    original = Path(ingested["data_path"]).read_bytes()
    report = run.validate(2024, 1, **options)
    assert report["execution_status"] == "VALIDATED_REAL" and report["data_quality_approved"]
    assert not report["approved_for_training"] and report["status"] == "WARN"
    assert report["input"]["manifest"]["provenance_status"] == "UNVERIFIED_LOCAL"
    assert report["input"]["manifest"]["source_url"] is None
    path = options["validated_dir"] / report["output"]["relative_path"]
    assert "_test_only" not in path.parts
    with path.open("rb") as stream, pq.ParquetFile(stream) as parquet:
        table = parquet.read()
        assert table["passenger_count"][0].as_py() is None
        assert parquet.metadata.num_row_groups <= 6  # Un grupo por bloque de dos filas.
        assert parquet.schema_arrow.metadata[b"validation_scope"] == b"REAL"
    assert Path(ingested["data_path"]).read_bytes() == original
    assert json.loads((path.parent / "validation.json").read_text()) == report
    features = build_validated_features(path.parent, processed_dir=tmp_path / "processed")
    assert features["status"] == "FEATURES_REAL" and features["data_quality_approved"]
    assert not features["approved_for_training"] and not features["preprocessor_fitted"]
    assert features["rows_emitted"] == 12


def test_local_authorization_is_bound_to_month_and_hash(tmp_path):
    options, _ = setup(tmp_path, authorize=False)
    report = run.validate(2024, 1, **options)
    assert report["status"] == "FAIL" and "autorizacion" in report["error"]
    assert not list(options["validated_dir"].rglob("*.parquet"))


def test_active_real_minimum_volume_blocks_tiny_month_without_scan(tmp_path, monkeypatch):
    options, _ = setup(tmp_path, miniature_limits=False)

    def forbidden(*args, **kwargs):
        pytest.fail("El preflight de volumen debe evitar el escaneo")

    monkeypatch.setattr(run, "_scan", forbidden)
    report = run.validate(2024, 1, **options)
    assert report["status"] == "FAIL" and report["scan_scope"] == "PREFLIGHT_ONLY"
    assert any(c["rule"] == "volume.min_rows" and c["status"] == "FAIL" for c in report["checks"])


def test_real_failure_does_not_publish_quality_approved_output(tmp_path):
    options, _ = setup(tmp_path, case="null_zone")
    config = json.loads(options["config_path"].read_text())
    config["quality"]["fail_rates"]["origin_null_or_outside_catalog"] = 0
    options["config_path"].write_text(json.dumps(config))
    report = run.validate(2024, 1, **options)
    assert report["status"] == "FAIL" and not report["data_quality_approved"]
    assert report["output"] is None and not list(options["validated_dir"].rglob("*.parquet"))
    assert not list(options["scratch_dir"].glob("dq-real-*"))


def test_resource_callback_aborts_validation_without_publishing(tmp_path):
    options, _ = setup(tmp_path)

    def exhausted():
        raise RuntimeError("D-02 limit")

    report = run.validate(2024, 1, resource_check=exhausted, **options)
    assert report["status"] == "FAIL" and "D-02" in report["error"]
    assert report["output"] is None
    assert not list(options["scratch_dir"].glob("dq-real-*"))
