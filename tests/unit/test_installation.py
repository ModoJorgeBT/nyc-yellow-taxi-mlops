"""Verifica que el paquete instalado no dependa del directorio de trabajo."""

import json
import subprocess
import sys
from pathlib import Path


def test_installed_package_imports_without_checkout_on_sys_path(tmp_path: Path) -> None:
    """Detecta errores de empaquetado que los imports desde la raiz ocultan."""
    probe = """
import importlib
import importlib.metadata
import importlib.util
import json

distribution = importlib.metadata.distribution("nyc-yellow-taxi-mlops")
packages = ["src", "src.ingestion", "src.validation", "src.features", "src.training",
            "src.evaluation", "src.api", "src.monitoring", "src.retraining",
            "src.validation.schema", "src.validation.rules", "src.validation.run",
            "src.features.schema", "src.features.target", "src.features.build",
            "src.features.artifacts", "src.validation.real", "src.training.split",
            "src.training.resources", "src.training.baseline", "src.features.vectorized",
            "src.training.baseline_fit", "src.training.baseline_evaluate",
            "src.validation.exceptions", "src.training.models",
            "src.training.candidate_runtime", "src.training.train",
            "src.evaluation.metrics", "src.evaluation.segments", "src.evaluation.run",
            "src.training.lightgbm_model", "src.training.lightgbm_train",
            "src.training.lightgbm_worker", "src.training.native_supervisor",
            "src.evaluation.lightgbm_run", "src.evaluation.final_data", "src.evaluation.final_run",
            "src.training.tracking", "src.training.tracking_model", "src.training.champion",
            "src.api.model_loader", "src.api.metrics", "src.monitoring.data_quality"]
if importlib.util.find_spec("fastapi") is not None:
    packages += ["src.api.schemas", "src.api.main"]
for package in packages:
    importlib.import_module(package)
print(json.dumps({"version": distribution.version, "packages": packages}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["version"] == "0.1.0"
    assert "src.api.model_loader" in observed["packages"]
    assert len(observed["packages"]) in (43, 45)
