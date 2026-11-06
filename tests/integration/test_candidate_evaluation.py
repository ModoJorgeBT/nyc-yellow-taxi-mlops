"""Modelos de fixture: seleccion antes de test y destino exclusivamente segmentacion."""

import json
from pathlib import Path

import pytest

from src.evaluation import run as evaluation
from src.training.baseline import run_baseline
from src.training.train import train_candidates
from tests.integration.test_temporal_split_pipeline import make_catalog, run


def inputs(tmp_path):
    catalog = make_catalog(
        tmp_path / "data", durations={(2024, 12): 10, (2025, 3): 20, (2025, 6): 1}
    )
    split = run(catalog, tmp_path / "prepare")
    source = Path(split["output_directory"])
    trained = train_candidates(
        source,
        output_dir=tmp_path / "models",
        report_dir=tmp_path / "training-reports",
        test_only=True,
    )
    baseline = run_baseline(
        source,
        output_dir=tmp_path / "baselines",
        report_dir=tmp_path / "baseline-reports",
        scratch_dir=tmp_path / "median",
        test_only=True,
    )
    assert trained["publication_complete"], trained.get("error")
    assert baseline["publication_complete"], baseline.get("error")
    return source, Path(trained["output_directory"]), Path(baseline["output_directory"])


def evaluate(paths, tmp_path):
    return evaluation.evaluate_models(
        *paths,
        output_dir=tmp_path / "evaluation",
        report_dir=tmp_path / "evaluation-reports",
        scratch_dir=tmp_path / "errors",
        test_only=True,
    )


def test_selection_exists_before_test_and_replay_stays_unopened(tmp_path, monkeypatch):
    paths = inputs(tmp_path)
    original = evaluation.verify_scope
    original_open = Path.open
    events = []

    def verify(*args, **kwargs):
        if kwargs["partitions"] == ("test",):
            selection = list((tmp_path / "evaluation").rglob("selection.json"))
            assert len(selection) == 1
            assert json.loads(selection[0].read_text())["test_accessed_at_selection"] is False
            events.append("selection_before_test")
        return original(*args, **kwargs)

    def guarded(path, *args, **kwargs):
        if path.resolve().is_relative_to(paths[0] / "monitoring_replay"):
            pytest.fail("T17 no abre replay")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(evaluation, "verify_scope", verify)
    monkeypatch.setattr(Path, "open", guarded)
    result = evaluate(paths, tmp_path)
    assert result["status"] == "EVALUATION_TEST_ONLY", result.get("error")
    assert events and result["test_accessed"] and not result["monitoring_replay_accessed"]
    assert result["recommended_model"] == result["selection"]["recommended_model"] == "baseline"
    assert result["test"]["metrics"]["baseline"]["all"]["mae_minutes"] == 9
    assert min(result["test"]["metrics"][n]["all"]["mae_minutes"] for n in ("sgd", "mlp")) < 9
    assert not result["approved_for_serving"] and not result["model_registered"]
    assert result["validation"]["rows"] == result["test"]["rows"] == 11
    for part in ("validation", "test"):
        for name in ("baseline", "sgd", "mlp"):
            metrics = result[part]["metrics"][name]
            assert metrics["all"]["rows"] == sum(
                v["rows"] for k, v in metrics.items() if k.startswith("route_")
            )
    directory = Path(result["output_directory"])
    assert json.loads((directory / "evaluation_manifest.json").read_text()) == result


def test_altered_model_is_rejected_without_opening_test(tmp_path, monkeypatch):
    paths = inputs(tmp_path)
    with (paths[1] / "sgd.joblib").open("ab") as stream:
        stream.write(b"tampered")
    monkeypatch.setattr(evaluation, "route_catalog", lambda *a, **k: pytest.fail("No evaluar"))
    result = evaluate(paths, tmp_path)
    assert result["status"] == "FAIL" and not result["test_accessed"]
    assert not list((tmp_path / "evaluation").rglob("evaluation_manifest.json"))
