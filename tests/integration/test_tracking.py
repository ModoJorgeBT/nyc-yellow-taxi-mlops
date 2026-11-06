"""Tracking opcional: fixture sintetica, HTTP loopback y reinicio de SQLite."""

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import joblib
import pytest
from sklearn.dummy import DummyRegressor

from src.features.build import make_model_pipeline
from src.training.tracking import EXAMPLE, FAMILIES, sha256, verify_bundle


def fixture_profile(root):
    # Ningun archivo o modelo real se lee para construir este fixture.
    root.mkdir(parents=True, exist_ok=True)
    (root / "model.json").write_text(
        json.dumps({"kind": "exact_global_train_median", "prediction_minutes": 2.0})
    )
    pipeline = make_model_pipeline(DummyRegressor(strategy="mean")).fit(EXAMPLE, [1, 3])
    joblib.dump(pipeline, root / "toy.joblib")
    models = {}
    for family in FAMILIES:
        path = "model.json" if family == "baseline" else "toy.joblib"
        model_sha = sha256(root / path)
        if family in ("sgd", "mlp"):
            marker_path = "incremental.json"
            marker = {
                "status": "TRAINING_TEST_ONLY",
                "models": {name: {"sha256": model_sha, "train_rows": 2} for name in ("sgd", "mlp")},
                "candidate_configuration": {
                    "candidates": {name: {"fixture": "constant"} for name in ("sgd", "mlp")},
                    "epochs": 1,
                },
            }
        else:
            marker_path = family + ".json"
            marker = {
                "status": "BASELINE_TEST_ONLY"
                if family == "baseline"
                else "LIGHTGBM_TRAINING_TEST_ONLY",
                "model_sha256": model_sha,
                "configuration": {"parameters": {"fixture": "constant"}, "num_boost_round": 1},
                "model": {"kind": "exact_global_train_median", "train_rows": 2},
            }
        (root / marker_path).write_text(json.dumps(marker))
        models[family] = {
            "path": path,
            "sha256": model_sha,
            "training_manifest_path": marker_path,
            "training_manifest_sha256": sha256(root / marker_path),
        }
    metric = {
        "all": {
            "rows": 2,
            "mae_minutes": 1.0,
            "rmse_minutes": 1.0,
            "medae_minutes": 1.0,
            "p90_absolute_error_minutes": 1.0,
        }
    }
    selection = {
        "training_manifest_sha256": models["sgd"]["training_manifest_sha256"],
        "baseline_manifest_sha256": models["baseline"]["training_manifest_sha256"],
    }
    reports = {
        "original_2025": {
            "status": "EVALUATION_TEST_ONLY",
            "selection": selection,
            **{
                w: {"metrics": {f: metric for f in ("baseline", "sgd", "mlp")}}
                for w in ("validation", "test")
            },
        },
        "lightgbm_validation_2025": {
            "status": "LIGHTGBM_EVALUATION_TEST_ONLY",
            "metrics": metric,
            "training_manifest_sha256": models["lightgbm"]["training_manifest_sha256"],
        },
        "final_2026": {
            "status": "FINAL_EVALUATION_TEST_ONLY",
            "configuration": {"models": models},
            "results": {f: {"metrics": metric} for f in ("baseline", "sgd", "lightgbm")},
        },
    }
    evaluations = {}
    for name, value in reports.items():
        value.update(publication_complete=True, mode="TEST_ONLY")
        path = root / f"{name}.json"
        path.write_text(json.dumps(value))
        evaluations[name] = {"path": path.name, "sha256": sha256(path), "status": value["status"]}
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    profile = {
        "approval_status": "TEST_ONLY",
        "fixture_origin": "synthetic",
        "scope": "register_frozen_candidates_without_promotion",
        "champion_assignment_authorized": False,
        "tracking_uri": f"http://127.0.0.1:{port}",
        "backend_store_uri": "sqlite:///tracking/mlflow.db",
        "experiment_name": "synthetic-duration",
        "registered_model_name": "synthetic-duration",
        "mlflow_version": "3.16.1",
        "resources": {"candidate_timeout_seconds": 7200},
        "training_scope": "synthetic_fixture_only",
        "models": models,
        "evaluations": evaluations,
        "lineage_files": {p.name: sha256(p) for p in root.glob("*.json")},
    }
    path = root / "tracking.json"
    path.write_text(json.dumps(profile))
    return path, profile


def test_tracking_rejects_changed_model_lineage_scope_and_incomplete_evaluation(tmp_path):
    path, profile = fixture_profile(tmp_path)
    verify_bundle(profile, tmp_path, test_only=True)
    with pytest.raises(ValueError):
        verify_bundle(profile, tmp_path)
    for uri in ("http://0.0.0.0:5000", "file:///mlruns", "https://remote:5000"):
        with pytest.raises(ValueError):
            verify_bundle({**profile, "tracking_uri": uri}, tmp_path, test_only=True)
    toy = tmp_path / "toy.joblib"
    toy.write_bytes(b"altered")
    with pytest.raises(ValueError, match="alterado"):
        verify_bundle(profile, tmp_path, test_only=True)


@pytest.mark.parametrize("fault", ["incomplete", "foreign_model", "foreign_fit"])
def test_tracking_rejects_semantically_invalid_reports_even_with_matching_hash(tmp_path, fault):
    _, profile = fixture_profile(tmp_path)
    key = "original_2025" if fault == "foreign_fit" else "final_2026"
    info = profile["evaluations"][key]
    path = tmp_path / info["path"]
    report = json.loads(path.read_text())
    if fault == "incomplete":
        report["publication_complete"] = False
    elif fault == "foreign_fit":
        report["selection"]["training_manifest_sha256"] = "0" * 64
    else:
        report["configuration"]["models"]["sgd"]["sha256"] = "0" * 64
    path.write_text(json.dumps(report))
    info["sha256"] = profile["lineage_files"][path.name] = sha256(path)
    with pytest.raises(ValueError):
        verify_bundle(profile, tmp_path, test_only=True)


@pytest.mark.skipif(
    importlib.util.find_spec("mlflow") is None, reason="T18 requiere entorno MLflow separado"
)
def test_registry_persists_after_real_server_restart_without_alias(tmp_path):
    path, _ = fixture_profile(tmp_path)
    shutil.copyfile("requirements-mlflow.lock", tmp_path / "requirements-mlflow.lock")
    script = Path("scripts/smoke_mlflow.py").resolve()
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--config",
            str(path),
            "--root",
            str(tmp_path),
            "--test-only",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1", "MLFLOW_DISABLE_AGENT_HINT": "1"},
        check=False,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads((tmp_path / "reports/tracking/_test_only/persistence.json").read_text())
    assert receipt["status"] == "TRACKING_PERSISTENCE_TEST_ONLY"
    assert receipt["same_runs_and_versions"] and not receipt["champion_assigned"]
    assert len(receipt["receipt"]["models"]) == 4
