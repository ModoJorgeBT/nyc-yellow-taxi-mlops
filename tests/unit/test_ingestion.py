"""Ingesta con red simulada y Parquet sintetico; no abre data/raw real."""

import hashlib
import io
import json
import subprocess
import sys
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.ingestion import download, manifest
from src.ingestion.manifest import IngestionConflict, IngestionError, source_url

PAYLOAD = Path(__file__).resolve().parents[1] / "fixtures/valid.parquet"


class Response(io.BytesIO):
    def __init__(self, body: bytes, *, length: str | None = None, status: int = 200):
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Length": str(len(body)) if length is None else length}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError("Las pruebas no deben abrir red real")

    monkeypatch.setattr(download.urllib.request, "urlopen", blocked)
    monkeypatch.setattr(download.time, "sleep", lambda _: None)


def responses(monkeypatch: pytest.MonkeyPatch, outcomes: list) -> list:
    observed = []
    remaining = iter(outcomes)

    def open_mock(request, *, timeout):
        observed.append((request.full_url, timeout))
        value = next(remaining)
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setattr(download.urllib.request, "urlopen", open_mock)
    return observed


def paths(raw: Path) -> tuple[Path, Path, Path]:
    directory = raw / "2025/01"
    return directory, directory / "yellow_tripdata_2025-01.parquet", directory / "manifest.json"


def assert_clean(directory: Path) -> None:
    assert not list(directory.glob("*.part"))
    assert not (directory / ".ingestion.lock").exists()


def test_download_manifest_and_idempotency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = PAYLOAD.read_bytes()
    observed = responses(monkeypatch, [Response(body)])
    first = download.ingest(2025, 1, raw_dir=tmp_path, timeout=4)
    directory, data, record = paths(tmp_path)
    assert first["status"] == "DOWNLOADED"
    assert data.read_bytes() == body
    stored = json.loads(record.read_text())
    assert stored["sha256"] == hashlib.sha256(body).hexdigest()
    assert stored["row_count"] == 12
    assert stored["file_size_bytes"] == len(body)
    assert len(stored["schema"]) == 19
    assert len(stored["schema_fingerprint"]) == 64
    assert stored["source_url"] == source_url(2025, 1)
    assert stored["origin"] == "download"
    assert datetime.fromisoformat(stored["downloaded_at_utc"]).utcoffset() == UTC.utcoffset(None)
    original_manifest = record.read_bytes()
    second = download.ingest(2025, 1, raw_dir=tmp_path)
    assert second["status"] == "SKIPPED"
    assert record.read_bytes() == original_manifest
    assert observed == [(source_url(2025, 1), 4)]
    events = [
        json.loads(line) for line in (directory / "ingestion-events.jsonl").read_text().splitlines()
    ]
    assert [event["status"] for event in events] == ["DOWNLOADED", "SKIPPED"]
    assert_clean(directory)


def test_404_does_not_retry_or_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed = responses(
        monkeypatch, [urllib.error.HTTPError(source_url(2025, 1), 404, "missing", {}, None)]
    )
    with pytest.raises(IngestionError, match="404"):
        download.ingest(2025, 1, raw_dir=tmp_path)
    directory, data, record = paths(tmp_path)
    assert len(observed) == 1
    assert not data.exists() and not record.exists()
    assert_clean(directory)


@pytest.mark.parametrize("failure", [TimeoutError("timeout"), urllib.error.URLError("offline")])
def test_network_retry_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    observed = responses(monkeypatch, [failure, Response(PAYLOAD.read_bytes())])
    assert download.ingest(2025, 1, raw_dir=tmp_path)["status"] == "DOWNLOADED"
    assert len(observed) == 2
    assert_clean(paths(tmp_path)[0])


def test_server_error_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed = responses(
        monkeypatch,
        [
            urllib.error.HTTPError(source_url(2025, 1), 503, "busy", {}, None),
            Response(PAYLOAD.read_bytes()),
        ],
    )
    assert download.ingest(2025, 1, raw_dir=tmp_path)["status"] == "DOWNLOADED"
    assert len(observed) == 2


def test_timeout_budget_is_finite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed = responses(monkeypatch, [TimeoutError()] * 3)
    with pytest.raises(IngestionError, match="agotados"):
        download.ingest(2025, 1, raw_dir=tmp_path, retries=2)
    directory, data, record = paths(tmp_path)
    assert len(observed) == 3
    assert not data.exists() and not record.exists()
    assert_clean(directory)


def test_interrupted_read_cleans_its_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Interrupted(Response):
        def read(self, size=-1):
            if self.tell():
                raise TimeoutError("interrupted")
            return super().read(10)

    responses(monkeypatch, [Interrupted(PAYLOAD.read_bytes())])
    with pytest.raises(IngestionError):
        download.ingest(2025, 1, raw_dir=tmp_path, retries=0)
    directory, data, record = paths(tmp_path)
    assert not data.exists() and not record.exists()
    assert_clean(directory)


@pytest.mark.parametrize("body,length", [(b"not parquet", None), (b"x", "5"), (b"x", "invalid")])
def test_invalid_or_truncated_download_is_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes, length: str | None
) -> None:
    responses(monkeypatch, [Response(body, length=length)])
    with pytest.raises(IngestionError):
        download.ingest(2025, 1, raw_dir=tmp_path, retries=0)
    directory, data, record = paths(tmp_path)
    assert not data.exists() and not record.exists()
    assert_clean(directory)


def test_expected_hash_blocks_publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    responses(monkeypatch, [Response(PAYLOAD.read_bytes())])
    with pytest.raises(IngestionConflict, match="SHA-256"):
        download.ingest(2025, 1, raw_dir=tmp_path, expected_sha256="0" * 64)
    directory, data, record = paths(tmp_path)
    assert not data.exists() and not record.exists()
    assert_clean(directory)


def test_unregistered_local_file_requires_explicit_action(tmp_path: Path) -> None:
    directory, data, record = paths(tmp_path)
    directory.mkdir(parents=True)
    body = PAYLOAD.read_bytes()
    data.write_bytes(body)
    with pytest.raises(IngestionConflict, match="sin manifiesto"):
        download.ingest(2025, 1, raw_dir=tmp_path)
    assert data.read_bytes() == body and not record.exists()
    result = download.ingest(2025, 1, raw_dir=tmp_path, register_local=True)
    stored = json.loads(record.read_text())
    assert result["status"] == "REGISTERED_LOCAL_UNVERIFIED"
    assert stored["source_url"] is None
    assert stored["downloaded_at_utc"] is None
    assert stored["provenance_status"] == "UNVERIFIED_LOCAL"
    assert stored["status"] == "LOCAL_UNVERIFIED"
    assert stored["expected_source_url"] == source_url(2025, 1)
    second = download.ingest(2025, 1, raw_dir=tmp_path)
    assert second["status"] == "SKIPPED" and second["manifest_status"] == "LOCAL_UNVERIFIED"
    assert data.read_bytes() == body
    assert_clean(directory)


def test_register_local_never_downloads(tmp_path: Path) -> None:
    with pytest.raises(IngestionConflict, match="requiere"):
        download.ingest(2025, 1, raw_dir=tmp_path, register_local=True)


def test_changed_bytes_preserve_manifest_and_conflict(tmp_path: Path) -> None:
    directory, data, record = paths(tmp_path)
    directory.mkdir(parents=True)
    data.write_bytes(PAYLOAD.read_bytes())
    download.ingest(2025, 1, raw_dir=tmp_path, register_local=True)
    original = record.read_bytes()
    changed = (PAYLOAD.parent / "extra_column.parquet").read_bytes()
    data.write_bytes(changed)
    with pytest.raises(IngestionConflict, match="divergente"):
        download.ingest(2025, 1, raw_dir=tmp_path)
    assert data.read_bytes() == changed and record.read_bytes() == original
    assert_clean(directory)


@pytest.mark.parametrize(
    "key,value",
    [
        ("sha256", "0" * 64),
        ("row_count", False),
        ("year", 2024),
        ("recorded_at_utc", "2026-01-01"),
        ("schema_fingerprint", "broken"),
    ],
)
def test_manifest_tampering_is_explicit(tmp_path: Path, key: str, value: object) -> None:
    directory, data, record = paths(tmp_path)
    directory.mkdir(parents=True)
    data.write_bytes(PAYLOAD.read_bytes())
    download.ingest(2025, 1, raw_dir=tmp_path, register_local=True)
    stored = json.loads(record.read_text())
    stored[key] = value
    record.write_text(json.dumps(stored))
    before = record.read_bytes()
    with pytest.raises(IngestionConflict):
        download.ingest(2025, 1, raw_dir=tmp_path)
    assert record.read_bytes() == before


def test_existing_lock_is_not_deleted(tmp_path: Path) -> None:
    directory = paths(tmp_path)[0]
    directory.mkdir(parents=True)
    lock = directory / ".ingestion.lock"
    lock.write_text("another writer")
    with pytest.raises(IngestionConflict, match="bloqueado"):
        download.ingest(2025, 1, raw_dir=tmp_path)
    assert lock.read_text() == "another writer"


def test_publish_race_cannot_overwrite_competitor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses(monkeypatch, [Response(PAYLOAD.read_bytes())])
    original = manifest.os.link

    def competing_writer(source, destination):
        if destination.suffix == ".parquet":
            destination.write_bytes(b"competitor")
        original(source, destination)

    monkeypatch.setattr(manifest.os, "link", competing_writer)
    with pytest.raises(IngestionConflict, match="ya existe"):
        download.ingest(2025, 1, raw_dir=tmp_path)
    directory, data, record = paths(tmp_path)
    assert data.read_bytes() == b"competitor" and not record.exists()
    assert_clean(directory)


def test_manifest_publication_failure_leaves_explicit_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses(monkeypatch, [Response(PAYLOAD.read_bytes())])
    with monkeypatch.context() as context:

        def fail(*args):
            raise OSError("simulated manifest failure")

        context.setattr(download, "publish_manifest", fail)
        with pytest.raises(OSError, match="simulated"):
            download.ingest(2025, 1, raw_dir=tmp_path)
    directory, data, record = paths(tmp_path)
    assert data.read_bytes() == PAYLOAD.read_bytes() and not record.exists()
    with pytest.raises(IngestionConflict, match="sin manifiesto"):
        download.ingest(2025, 1, raw_dir=tmp_path)
    assert_clean(directory)


@pytest.mark.parametrize("year,month", [(2025, 0), (2025, 13), (0, 1), (True, 1)])
def test_invalid_period_has_no_side_effects(tmp_path: Path, year: int, month: int) -> None:
    with pytest.raises(ValueError):
        download.ingest(year, month, raw_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_cli_help_and_invalid_month(tmp_path: Path) -> None:
    help_result = subprocess.run(
        [sys.executable, "-I", "-m", "src.ingestion.download", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert help_result.returncode == 0 and "--register-local" in help_result.stdout
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "src.ingestion.download",
            "--year",
            "2025",
            "--month",
            "13",
            "--raw-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1 and "month" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_download_without_content_length(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    response = Response(PAYLOAD.read_bytes())
    response.headers = {}
    responses(monkeypatch, [response])
    assert download.ingest(2025, 1, raw_dir=tmp_path)["status"] == "DOWNLOADED"


@pytest.mark.parametrize("broken_manifest", ["{", "[]"])
def test_unreadable_manifest_preserves_data(tmp_path: Path, broken_manifest: str) -> None:
    directory, data, record = paths(tmp_path)
    directory.mkdir(parents=True)
    data.write_bytes(PAYLOAD.read_bytes())
    record.write_text(broken_manifest)
    with pytest.raises(IngestionConflict):
        download.ingest(2025, 1, raw_dir=tmp_path)
    assert data.read_bytes() == PAYLOAD.read_bytes()
    assert record.read_text() == broken_manifest
    assert_clean(directory)


def test_manifest_without_data_cannot_trigger_download(tmp_path: Path) -> None:
    directory, data, record = paths(tmp_path)
    directory.mkdir(parents=True)
    record.write_text("{}")
    with pytest.raises(IngestionConflict, match="sin archivo"):
        download.ingest(2025, 1, raw_dir=tmp_path)
    assert not data.exists() and record.read_text() == "{}"


def test_local_hash_mismatch_does_not_register(tmp_path: Path) -> None:
    directory, data, record = paths(tmp_path)
    directory.mkdir(parents=True)
    data.write_bytes(PAYLOAD.read_bytes())
    with pytest.raises(IngestionConflict, match="SHA-256"):
        download.ingest(2025, 1, raw_dir=tmp_path, register_local=True, expected_sha256="0" * 64)
    assert not record.exists() and data.read_bytes() == PAYLOAD.read_bytes()


def test_cli_explicit_registration_and_skip(tmp_path: Path) -> None:
    directory, data, _ = paths(tmp_path)
    directory.mkdir(parents=True)
    data.write_bytes(PAYLOAD.read_bytes())
    command = [
        sys.executable,
        "-I",
        "-m",
        "src.ingestion.download",
        "--year",
        "2025",
        "--month",
        "01",
        "--raw-dir",
        str(tmp_path),
        "--register-local",
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
    second = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(first.stdout)["status"] == "REGISTERED_LOCAL_UNVERIFIED"
    skipped = json.loads(second.stdout)
    assert skipped["status"] == "SKIPPED"
    assert skipped["provenance_status"] == "UNVERIFIED_LOCAL"
    assert data.read_bytes() == PAYLOAD.read_bytes()


@pytest.mark.parametrize(
    "options",
    [{"timeout": 0}, {"timeout": float("nan")}, {"retries": 6}, {"expected_sha256": "invalid"}],
)
def test_invalid_options_precede_side_effects(tmp_path: Path, options: dict) -> None:
    with pytest.raises(ValueError):
        download.ingest(2025, 1, raw_dir=tmp_path, **options)
    assert list(tmp_path.iterdir()) == []
