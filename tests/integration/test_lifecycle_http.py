import importlib.util
import json
import os
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.skipif(importlib.util.find_spec("mlflow") is None, reason="Requiere SDK aprobado"),
    pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Demo local 4 GiB libres/50 GiB disco; CI mantiene perfil 4 GiB totales/10 GiB",
    ),
]


@pytest.mark.parametrize(
    "module,result_file,expected",
    [
        ("scripts.demo_lifecycle", "demo-result.json", "LIFECYCLE_DEMO_TEST_ONLY_PASS"),
        ("scripts.demo_workflow", "workflow-result.json", "WORKFLOW_TEST_ONLY_COMPLETE"),
    ],
)
def test_owned_http_demo_and_workflow(module, result_file, expected, tmp_path):
    root = tmp_path / "scenario"
    command = [sys.executable, "-X", "utf8", "-m", module, "--output-dir", str(root)]
    if module.endswith("demo_lifecycle"):
        command.append("--external-rollback")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        env={**os.environ, "PYTHONUTF8": "1", "MLFLOW_DISABLE_AGENT_HINT": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((root / result_file).read_text(encoding="utf-8"))
    assert report["status"] == expected and report["owned_services_stopped"]
    assert not report.get("real_champion_changed", report.get("champion_changed", False))
    if module.endswith("demo_lifecycle"):
        assert report["external_rollback"] and report["failed_http_smoke_compensated"]
    else:
        assert report["candidate_registered"]["aliases"] == {}
