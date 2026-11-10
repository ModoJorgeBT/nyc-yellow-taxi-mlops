from io import BytesIO

import pytest

from src.ingestion.manifest import IngestionError
from src.retraining.downloads import PersistentBudget


def test_reservation_survives_read_failure_and_restart(tmp_path):
    class Broken:
        def read(self, size):
            raise TimeoutError

    path = tmp_path / "counter.json"
    budget = PersistentBudget(path, profile_sha256="f" * 64, limit=100)
    with pytest.raises(TimeoutError):
        budget.read(Broken(), 60)
    restarted = PersistentBudget(path, profile_sha256="f" * 64, limit=100)
    assert restarted.used_bytes == 60
    with pytest.raises(IngestionError):
        restarted.read(BytesIO(b"x" * 41), 41)
    assert restarted.read(BytesIO(b"123"), 40) == b"123"
    assert restarted.remaining == 0


def test_other_protocol_cannot_reset_transfer_allowance(tmp_path):
    path = tmp_path / "counter.json"
    PersistentBudget(path, profile_sha256="a", limit=100)
    with pytest.raises(ValueError):
        PersistentBudget(path, profile_sha256="b", limit=100)
