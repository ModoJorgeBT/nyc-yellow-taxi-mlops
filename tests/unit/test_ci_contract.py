"""CI permanece aislado de datos reales y distingue presupuesto local del runner."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import container_build

ROOT = Path(__file__).resolve().parents[2]


def test_ci_actions_are_pinned_and_workflow_has_no_write_token():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    actions = re.findall(r"uses:\s+([^\s]+)", workflow)
    assert actions and all(re.fullmatch(r"actions/checkout@[a-f0-9]{40}", item) for item in actions)
    assert "contents: read" in workflow and "pull_request_target" not in workflow
    assert "persist-credentials: false" in workflow and "timeout-minutes: 20" in workflow
    assert "--cpus=2 --memory=4g" in workflow and "BUILD_PROFILE=ci" in workflow
    assert "--driver docker-container" in workflow
    assert "--driver-opt memory=4g --driver-opt memory-swap=4g" in workflow
    assert "--driver-opt cpu-quota=200000 --driver-opt cpu-period=100000" in workflow
    assert re.search(r"moby/buildkit:v0\.34\.2@sha256:[a-f0-9]{64}", workflow)


def test_ci_disk_profile_never_relaxes_default_local_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(
        container_build.shutil, "disk_usage", lambda _: SimpleNamespace(free=12 * 1024**3)
    )
    container_build.preflight(tmp_path, profile="ci")
    with pytest.raises(ValueError, match="50 GiB"):
        container_build.preflight(tmp_path)


def test_ci_ruff_binary_is_frozen_and_runtime_remains_default_target():
    tools = json.loads((ROOT / "configs/ci-tools-linux.json").read_text())
    assert tools["ruff"]["sha256"] in (ROOT / "requirements-ci-linux.lock").read_text()
    assert tools["ruff"]["filename"].startswith("ruff-0.17.3-")
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert dockerfile.index(" AS ci") < dockerfile.index(" AS runtime")


def test_ci_build_limits_are_checked_not_just_documented(tmp_path):
    (tmp_path / "memory.max").write_text(str(4 * 1024**3))
    (tmp_path / "cpu.max").write_text("200000 100000")
    container_build.check_ci_limits(tmp_path)
    (tmp_path / "cpu.max").write_text("max 100000")
    with pytest.raises(ValueError, match="efectivos"):
        container_build.check_ci_limits(tmp_path)
