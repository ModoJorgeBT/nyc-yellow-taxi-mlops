"""Prepara solo el padre del temporal de Pytest dentro del checkout."""

from pathlib import Path

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    basetemp = config.getoption("basetemp")
    if basetemp is None:
        return
    destination = Path(basetemp).resolve()
    cache_root = config.rootpath.resolve() / ".cache"
    if destination.is_relative_to(cache_root):
        destination.parent.mkdir(parents=True, exist_ok=True)
