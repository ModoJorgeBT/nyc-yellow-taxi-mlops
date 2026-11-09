"""Regresiones Linux descubiertas por CI; no relajar controles de procesos activos."""

from unittest.mock import MagicMock, Mock

import pytest

from src.training import native_supervisor as supervisor
from src.training import tracking
from src.training.native_supervisor import _linux_peak_rss
from src.training.resources import ResourceLimitError


def test_linux_exited_process_is_distinct_from_missing_live_rss():
    with pytest.raises(ProcessLookupError):
        _linux_peak_rss("State:\tZ (zombie)\nPid:\t10\n")
    with pytest.raises(ResourceLimitError, match="activo"):
        _linux_peak_rss("State:\tR (running)\nPid:\t10\n")
    assert _linux_peak_rss("State:\tS (sleeping)\nVmHWM:\t1234 kB\n") == 1234 * 1024


def test_absent_git_records_unknown_without_fabricating_a_revision(monkeypatch, tmp_path):
    monkeypatch.setattr(tracking.shutil, "which", lambda command: None)
    probe = Mock(side_effect=AssertionError("No invocar ejecutable ausente"))
    monkeypatch.setattr(tracking.subprocess, "run", probe)
    assert tracking._git_state(tmp_path) == (None, None)
    probe.assert_not_called()


@pytest.mark.parametrize("alive", [False, True])
def test_zombie_is_reaped_but_live_unmeasured_worker_still_blocks(monkeypatch, tmp_path, alive):
    process = MagicMock(pid=123, returncode=1)
    process.__enter__.return_value = process
    process.poll.side_effect = [None, None, 1, 1, 1]
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(supervisor, "process_alive", lambda pid: alive)
    monkeypatch.setattr(
        supervisor, "process_peak_rss", Mock(side_effect=ProcessLookupError("terminated"))
    )
    monkeypatch.setattr(supervisor.time, "sleep", lambda _: None)
    with pytest.raises(ProcessLookupError if alive else RuntimeError):
        supervisor.supervise(
            ["owned-fixture"],
            policy={"native_process_poll_seconds": 0.01, "process_rss_limit_gib": 1},
            guard=Mock(),
            log_path=tmp_path / "fixture.log",
        )
    assert supervisor.process_peak_rss.call_count == (1 if alive else 2)
