"""Vocabulario causal, lectura completa y cancelación de un proceso nativo real."""

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from src.features.schema import FeatureError
from src.training import native_supervisor
from src.training.lightgbm_model import BoundedBooster, NativeFeatures
from src.training.lightgbm_train import read_lightgbm
from src.training.lightgbm_worker import DiskSequence
from src.training.resources import ResourceLimitError


def test_native_categories_unknown_and_no_input_mutation():
    transformer = NativeFeatures((10, 100, 263)).fit()
    source = np.array([[100, 8, 1, 2, 0, 1], [999, 17, 6, 12, 2, 0]], dtype=float)
    original = source.copy()
    actual = transformer.transform(source)
    np.testing.assert_array_equal(actual[:, 0], [1, -1])
    np.testing.assert_array_equal(actual[:, 1:], original[:, 1:])
    np.testing.assert_array_equal(source, original)
    assert actual.dtype == np.float32
    assert transformer.categories_.tolist() == [10, 100, 263]


@pytest.mark.parametrize("origins", [(), (10, 10), (20, 10), (0, 20)])
def test_native_rejects_invalid_vocabulary(origins):
    with pytest.raises(FeatureError):
        NativeFeatures(origins).fit()


@pytest.mark.parametrize(
    "values", [np.zeros((2, 7)), [[10, 1, 2, 3, np.nan, 1]], [[1.5, 1, 2, 3, 0, 1]]]
)
def test_native_rejects_forbidden_shape_and_nonfinite(values):
    with pytest.raises(FeatureError):
        NativeFeatures((10,)).fit().transform(values)


def test_sequence_discretization_access_is_separate_from_complete_push(tmp_path):
    rows = np.arange(54, dtype="<f4").reshape(9, 6)
    path = tmp_path / "rows.f32"
    rows.tofile(path)
    sequence = DiskSequence(path, 9, 6, batch_size=4)
    np.testing.assert_array_equal(sequence[7], rows[7])
    assert sequence.sample_rows == 1 and sequence.range_rows == 0
    for start in (0, 4, 8):
        np.testing.assert_array_equal(sequence[start : min(9, start + 4)], rows[start : start + 4])
    assert sequence.range_rows == 9
    assert sequence.digest.hexdigest() == hashlib.sha256(rows.tobytes()).hexdigest()
    with pytest.raises(ValueError, match="no secuencial"):
        sequence[0:4]
    sequence.data._mmap.close()


@pytest.mark.parametrize("field", ["evaluation_scope", "num_boost_round", "parameters"])
def test_changed_protocol_requires_decision(tmp_path, field):
    value = json.loads(Path("configs/lightgbm.yaml").read_text())
    value[field] = "unapproved"
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="distinto del aprobado"):
        read_lightgbm(path)


def test_can_measure_own_process_peak():
    assert native_supervisor.process_peak_rss(os.getpid()) > 0


@pytest.mark.parametrize("failure", ["rss", "timeout"])
def test_native_process_is_killed_on_limit(tmp_path, monkeypatch, failure):
    processes = []
    original = native_supervisor.subprocess.Popen

    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    class Guard:
        def check(self):
            if failure == "timeout":
                raise ResourceLimitError("timeout de preparación y ajuste")

    monkeypatch.setattr(native_supervisor.subprocess, "Popen", launch)
    monkeypatch.setattr(native_supervisor, "process_peak_rss", lambda pid: 5 * 2**30)
    with pytest.raises(ResourceLimitError):
        native_supervisor.supervise(
            [sys._base_executable, "-I", "-c", "import time; time.sleep(30)"],
            policy={"process_rss_limit_gib": 4, "native_process_poll_seconds": 0.001},
            guard=Guard(),
            log_path=tmp_path / "native.log",
        )
    assert len(processes) == 1 and processes[0].poll() is not None


@pytest.mark.parametrize("failure", ["rss", "timeout"])
def test_venv_child_is_identified_and_killed_not_only_launcher(tmp_path, monkeypatch, failure):
    pid_path, ready_path = tmp_path / "pid.json", tmp_path / "ready"
    child = (
        "import os,json,time,pathlib,sys; "
        "p=pathlib.Path(sys.argv[1]); q=p.with_suffix('.tmp'); "
        "q.write_text(json.dumps({'pid':os.getpid(),'parent_pid':os.getppid(),'token':'proof'})); "
        "q.replace(p); time.sleep(30)"
    )
    actual_measure = native_supervisor.process_peak_rss
    measured_pids = []

    def measure(pid):
        measured_pids.append(pid)
        return 5 * 2**30 if failure == "rss" else actual_measure(pid)

    class Guard:
        def check(self):
            if failure == "timeout" and ready_path.exists():
                raise ResourceLimitError("timeout después de identificar el proceso real")

    monkeypatch.setattr(native_supervisor, "process_peak_rss", measure)
    with pytest.raises(ResourceLimitError):
        native_supervisor.supervise(
            [sys.executable, "-I", "-X", "utf8", "-c", child, str(pid_path)],
            policy={"process_rss_limit_gib": 4, "native_process_poll_seconds": 0.01},
            guard=Guard(),
            log_path=tmp_path / "native.log",
            identity=(pid_path, ready_path, "proof"),
        )
    identity = json.loads(pid_path.read_text())
    assert measured_pids and measured_pids[0] == identity["pid"]
    assert not native_supervisor.process_alive(identity["pid"])


def test_direct_fit_is_forbidden():
    with pytest.raises(ValueError, match="supervisado"):
        BoundedBooster().fit([[0] * 6], [1])


@pytest.mark.parametrize("changed", ["features", "target"])
def test_native_worker_rejects_changed_training_matrix(tmp_path, changed):
    protocol = read_lightgbm(Path("configs/lightgbm.yaml"))
    values = np.arange(54, dtype="<f4").reshape(9, 6)
    labels = np.arange(1, 10, dtype="<f8")
    features, target = tmp_path / "features.f32", tmp_path / "target.f64"
    values.tofile(features)
    labels.tofile(target)
    request = {
        "features": str(features),
        "target": str(target),
        "rows": 9,
        "feature_names": [f"column_{i}" for i in range(6)],
        "parameters": protocol["parameters"],
        "num_boost_round": 100,
        "feature_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
        "target_sha256": hashlib.sha256(labels.tobytes()).hexdigest(),
        "model": str(tmp_path / "model.txt"),
        "result": str(tmp_path / "result.json"),
    }
    path = features if changed == "features" else target
    with path.open("r+b") as stream:
        stream.write(np.asarray([99], dtype="<f4" if changed == "features" else "<f8").tobytes())
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))

    class Guard:
        def check(self):
            pass

    log_path = tmp_path / "log.txt"
    with pytest.raises(RuntimeError, match="código"):
        native_supervisor.run_worker(
            request_path,
            policy=protocol["resources"],
            guard=Guard(),
            log_path=log_path,
        )
    assert not (tmp_path / "model.txt").exists() and not (tmp_path / "result.json").exists()
    assert "alterad" in log_path.read_text(encoding="utf-8")


def test_nonfinite_prediction_fails_and_clips_are_counted():
    class Booster:
        def predict(self, X, num_threads):
            assert num_threads == 4
            return np.asarray(X)

    model = BoundedBooster()
    model.booster_ = Booster()
    values, changed = model.predict_with_diagnostics([-1, 10, 181])
    np.testing.assert_allclose(values, [1 / 60, 10, 180])
    assert changed == 2
    with pytest.raises(FeatureError, match="no finitas"):
        model.predict([np.nan])
