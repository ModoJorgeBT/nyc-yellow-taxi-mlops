"""Dos ventanas offline: estabilidad/drift, uniones y etiquetas ausentes."""

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.monitoring.performance import evaluate_predictions, make_predictions
from src.monitoring.protocol import MonitorGuard
from src.monitoring.run import monthly
from src.validation.run import _sha256
from tests.fixtures.monitoring import IDENTITY, predictor, prepared, renderer, write_json


def test_two_complete_months_and_missing_labels(tmp_path):
    config_path, _, _, _ = prepared(tmp_path)
    rows = []
    for month in (7, 8):
        result = monthly(
            config_path,
            tmp_path,
            2025,
            month,
            test_only=True,
            prediction_fixture=(predictor, IDENTITY),
            render_fixture=renderer,
        )
        assert result["publication_complete"], result.get("error")
        assert result["prediction"]["rows"] == 2000
        assert result["performance"]["observed_label_rows"] == 2000
        errors = np.arange(2000) % 3
        metrics = result["performance"]["metrics"]["all"]
        assert metrics["mae_minutes"] == pytest.approx(errors.mean())
        assert metrics["rmse_minutes"] == pytest.approx(np.sqrt(np.mean(errors**2)))
        assert metrics["medae_minutes"] == np.quantile(errors, 0.5)
        assert metrics["p90_absolute_error_minutes"] == np.quantile(errors, 0.9)
        assert result["service"]["status"] == "NOT_AVAILABLE"
        assert not result["models_fitted"] and not result["model_changed"]
        rows.append(result)
    assert rows[0]["drift"]["status"] == "OBSERVED"
    assert rows[1]["drift"]["status"] == "ALERT"
    assert rows[1]["preliminary_decision"] == "ALERT_REVIEW_REQUIRED"
    missing = monthly(
        config_path,
        tmp_path,
        2025,
        7,
        test_only=True,
        labels_available=False,
        prediction_fixture=(predictor, IDENTITY),
        render_fixture=renderer,
    )
    assert missing["performance"]["status"] == "NOT_AVAILABLE"
    assert missing["performance"]["metrics"] is None
    assert missing["preliminary_decision"] == "NOT_AVAILABLE"
    assert missing["output"] != rows[0]["output"]


def test_different_parquet_row_groups_join_by_identity(tmp_path):
    _, config, _, _ = prepared(tmp_path, count=5000)
    guard = MonitorGuard(tmp_path, test_only=True)
    output = tmp_path / "predictions.parquet"
    prediction = make_predictions(config, tmp_path, guard, 2025, 8, output, predictor, IDENTITY)
    performance = evaluate_predictions(config, tmp_path, guard, prediction, tmp_path / "errors")
    assert prediction["rows"] == performance["observed_label_rows"] == 5000


def test_future_partitions_and_target_not_opened_during_prediction(tmp_path, monkeypatch):
    _, config, source, _ = prepared(tmp_path)
    actual = Path.open

    def guarded(path, *args, **kwargs):
        if path == source / "monitoring_replay/target.parquet" or "test" in path.parts:
            pytest.fail("Etiquetas o test abiertos durante prediccion")
        return actual(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    result = make_predictions(
        config,
        tmp_path,
        MonitorGuard(tmp_path, test_only=True),
        2025,
        7,
        tmp_path / "prediction.parquet",
        predictor,
        IDENTITY,
    )
    assert not result["labels_read_for_prediction"]


def test_altered_source_retains_failure_without_publishing_success(tmp_path):
    config_path, _, source, _ = prepared(tmp_path)
    with (source / "monitoring_replay/features.parquet").open("ab") as stream:
        stream.write(b"tampered")
    result = monthly(
        config_path,
        tmp_path,
        2025,
        7,
        test_only=True,
        prediction_fixture=(predictor, IDENTITY),
        render_fixture=renderer,
    )
    assert result["status"] == "FAIL" and not result["publication_complete"]
    assert "alterado" in result["error"]
    assert (tmp_path / result["output"] / "monitoring.json").is_file()


def test_evidently_real_adapter_on_full_aggregates(tmp_path):
    pytest.importorskip("evidently")
    config_path, _, _, _ = prepared(tmp_path)
    result = monthly(
        config_path, tmp_path, 2025, 8, test_only=True, prediction_fixture=(predictor, IDENTITY)
    )
    assert result["publication_complete"], result.get("error")
    output = tmp_path / result["output"]
    assert (output / "evidently.html").stat().st_size > 1000
    assert (output / "evidently.json").stat().st_size > 100
    evidence = json.loads((output / "evidently.json").read_text(encoding="utf-8"))
    scores = {
        item["config"]["feature"]: item["value"]
        for item in evidence["metrics"]
        if item["config"]["type"].endswith("HistogramPSI")
    }
    assert len(scores) == 6
    for name, score in scores.items():
        assert score == result["drift"]["features"][name]["psi"]


def test_identity_join_rejects_wrong_prediction_even_with_its_correct_file_hash(tmp_path):
    _, config, _, _ = prepared(tmp_path)
    guard = MonitorGuard(tmp_path, test_only=True)
    path = tmp_path / "prediction.parquet"
    prediction = make_predictions(config, tmp_path, guard, 2025, 7, path, predictor, IDENTITY)
    table = pq.read_table(path)
    column = table.schema.get_field_index("validated_row_index")
    table = table.set_column(column, "validated_row_index", pa.array(np.arange(2000) + 1))
    pq.write_table(table, path)
    prediction["sha256"] = _sha256(path)
    with pytest.raises(ValueError, match="identidades"):
        evaluate_predictions(config, tmp_path, guard, prediction, tmp_path / "errors")


def test_no_mature_labels_produces_no_metrics(tmp_path):
    _, config, source, manifest = prepared(tmp_path)
    path = source / "monitoring_replay/context.parquet"
    table = pq.read_table(path)
    events = table.column("label_event_datetime_utc").to_pylist()
    events[:2000] = [None] * 2000
    table = table.set_column(
        table.schema.get_field_index("label_event_datetime_utc"),
        "label_event_datetime_utc",
        pa.array(events, type=pa.timestamp("us", "UTC")),
    )
    pq.write_table(table, path)
    manifest["partitions"]["monitoring_replay"]["artifacts"]["context"].update(
        sha256=_sha256(path), file_size_bytes=path.stat().st_size
    )
    write_json(source / "split_manifest.json", manifest)
    config["split"]["sha256"] = _sha256(source / "split_manifest.json")
    guard = MonitorGuard(tmp_path, test_only=True)
    prediction = make_predictions(
        config, tmp_path, guard, 2025, 7, tmp_path / "predictions.parquet", predictor, IDENTITY
    )
    result = evaluate_predictions(config, tmp_path, guard, prediction, tmp_path / "errors")
    assert result["status"] == "NOT_AVAILABLE" and result["metrics"] is None
    assert result["pending_label_rows"] == 2000


def test_real_mode_rejects_fixture_injection_before_data_access(tmp_path):
    config_path, config, _, _ = prepared(tmp_path)
    config["status"] = "APPROVED"
    write_json(config_path, config)
    with pytest.raises(ValueError, match="Inyeccion"):
        monthly(config_path, tmp_path, 2025, 7, prediction_fixture=(predictor, IDENTITY))
