"""Transferencias acotadas incluso sin Content-Length y tras un fallo de red."""

import io

import pytest

from src.ingestion import download
from src.ingestion.manifest import IngestionError
from tests.unit.test_ingestion import PAYLOAD, Response, responses


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_limit_is_rejected_without_network(tmp_path, limit, monkeypatch):
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError, match="entero positivo"):
        download.ingest(2026, 1, raw_dir=tmp_path, max_download_bytes=limit)


def test_header_over_limit_never_reads_body(tmp_path, monkeypatch):
    class Unreadable(Response):
        def read(self, size=-1):
            pytest.fail("No se debe transferir un cuerpo sobre el límite anunciado")

    observed = responses(monkeypatch, [Unreadable(PAYLOAD.read_bytes())])
    with pytest.raises(IngestionError, match="Content-Length supera"):
        download.ingest(2026, 1, raw_dir=tmp_path, max_download_bytes=10)
    assert len(observed) == 1
    assert not list(tmp_path.rglob("*.part")) and not list(tmp_path.rglob("manifest.json"))


def test_unknown_length_stops_at_limit_and_removes_partial(tmp_path, monkeypatch):
    response = Response(PAYLOAD.read_bytes())
    response.headers = {}
    responses(monkeypatch, [response])
    budget = download.DownloadBudget(100)
    with pytest.raises(IngestionError, match="Límite de descarga alcanzado"):
        download.ingest(2026, 1, raw_dir=tmp_path, max_download_bytes=50, download_budget=budget)
    assert budget.used_bytes == 50
    assert not list(tmp_path.rglob("*.part")) and not list(tmp_path.rglob("manifest.json"))


@pytest.mark.parametrize("known_length", [True, False])
def test_valid_file_inside_limit_is_published(tmp_path, monkeypatch, known_length):
    body = PAYLOAD.read_bytes()
    response = Response(body)
    if not known_length:
        response.headers = {}
    responses(monkeypatch, [response])
    budget = download.DownloadBudget(len(body) + 1)
    result = download.ingest(
        2026,
        1,
        raw_dir=tmp_path,
        max_download_bytes=len(body) + (not known_length),
        download_budget=budget,
    )
    assert result["status"] == "DOWNLOADED" and budget.used_bytes == len(body)


def test_aggregate_limit_survives_between_files(tmp_path, monkeypatch):
    body = PAYLOAD.read_bytes()
    observed = responses(monkeypatch, [Response(body), Response(body)])
    budget = download.DownloadBudget(len(body) + 10)
    download.ingest(2026, 1, raw_dir=tmp_path, max_download_bytes=len(body), download_budget=budget)
    with pytest.raises(IngestionError, match="Content-Length supera"):
        download.ingest(
            2026, 2, raw_dir=tmp_path, max_download_bytes=len(body), download_budget=budget
        )
    assert len(observed) == 2 and budget.used_bytes == len(body)
    assert (tmp_path / "2026/01/manifest.json").exists()
    assert not (tmp_path / "2026/02/manifest.json").exists()


def test_incomplete_attempt_counts_against_aggregate_budget(tmp_path, monkeypatch):
    body = PAYLOAD.read_bytes()

    class Interrupted(Response):
        def read(self, size=-1):
            if self.tell():
                raise TimeoutError("interrupted")
            return io.BytesIO.read(self, 10)

    responses(monkeypatch, [Interrupted(body), Response(body)])
    monkeypatch.setattr(download.time, "sleep", lambda _: None)
    budget = download.DownloadBudget(len(body))
    with pytest.raises(IngestionError, match="Content-Length supera"):
        download.ingest(
            2026, 1, raw_dir=tmp_path, max_download_bytes=len(body), download_budget=budget
        )
    assert budget.used_bytes == 10
    assert not list(tmp_path.rglob("*.part")) and not list(tmp_path.rglob("manifest.json"))
