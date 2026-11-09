"""Ventanas, limites, percentiles y tiempos de entrega ASGI deterministas."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.api import metrics as module


@pytest.fixture
def meter():
    now, reports = [0.0], []
    collector = module.WindowMetrics(reports.append, clock=lambda: now[0], wall_clock=lambda: 120.0)
    return collector, now, reports


def test_percentiles_counts_throughput_and_observed_health(meter):
    collector, now, _ = meter
    collector.record("/predict", 200, 100)
    collector.record("/predict", 422, 200)
    collector.record("/health", 503, 300)
    now[0] = 30
    report = collector.snapshot()
    assert report["requests"] == 3 and report["throughput_rps"] == 0.1
    assert report["p50_ms"] == 200 and report["p95_ms"] == 290
    assert report["routes"]["/predict"]["p50_ms"] == 150
    assert report["http_4xx"] == report["http_5xx"] == 1
    assert report["routes"]["/health"]["status_codes"] == {"503": 1}
    assert report["availability"] == "NOT_INFERRED"


def test_overflow_disables_percentiles_without_losing_counts():
    collector = module.WindowMetrics(lambda report: None, sample_limit=3)
    for _ in range(4):
        collector.record("/predict", 200, 2)
    report = collector.snapshot()
    assert report["requests"] == 4 and report["completed_latency_samples"] == 3
    assert report["p50_ms"] is report["p95_ms"] is None
    assert report["percentile_status"] == "NOT_AVAILABLE_OVERFLOW"


def test_rollover_gaps_shutdown_and_bounded_route_labels(meter):
    collector, now, reports = meter
    collector.record("/untrusted/user-id?secret=123", 404, 10)
    now[0] = 180
    collector.record("/health", 200, 1)
    assert reports[0]["unobserved_gap_windows"] == 2
    assert set(reports[0]["routes"]) == {"unmatched"}
    assert "secret" not in json.dumps(reports)
    collector.close()
    collector.close()
    assert len(reports) == 2 and reports[1]["requests"] == 1


def test_first_window_does_not_count_time_before_process_started():
    now = [0.0]
    collector = module.WindowMetrics(
        lambda report: None, clock=lambda: now[0], wall_clock=lambda: 150.0
    )
    collector.record("/health", 200, 1)
    now[0] = 10
    assert collector.snapshot()["period_seconds"] == 10


def test_incomplete_responses_have_counters_but_no_latency_samples(meter):
    collector, _, _ = meter
    collector.record("/predict", 500, 300, complete=False, exception=True)
    report = collector.snapshot()
    assert report["incomplete_responses"] == report["exceptions"] == 1
    assert report["p50_ms"] is None and report["http_5xx"] == 1


def test_asgi_measures_last_body_not_background_work(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(module.time, "perf_counter", lambda: now[0])
    collector, logger = Mock(), Mock()

    async def application(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        now[0] = 2
        await send({"type": "http.response.body", "body": b"one", "more_body": True})
        now[0] = 4
        await send({"type": "http.response.body", "body": b"two"})
        now[0] = 100

    async def sink(message):
        pass

    middleware = module.MetricsMiddleware(application, collector=collector, logger=logger)
    asyncio.run(middleware({"type": "http", "route": SimpleNamespace(path="/predict")}, sink, sink))
    collector.record.assert_called_once_with("/predict", 200, 4000, complete=True, exception=False)


def test_exception_is_counted_and_reraised_without_logging_message():
    collector, logger = Mock(), Mock()

    async def application(scope, receive, send):
        raise RuntimeError("secret-token")

    middleware = module.MetricsMiddleware(application, collector=collector, logger=logger)
    with pytest.raises(RuntimeError):
        asyncio.run(middleware({"type": "http"}, None, None))
    assert collector.record.call_args.kwargs == {"complete": False, "exception": True}
    assert collector.record.call_args.args[1] is None
    assert "secret-token" not in str(logger.mock_calls)


def test_log_export_deduplicates_and_refuses_overwrite(meter, tmp_path):
    collector, now, reports = meter
    collector.record("/health", 200, 1)
    now[0] = 1
    collector.close()
    line = "api-1 | INFO nyc_taxi.api metrics_window " + json.dumps(reports[0])
    log, output = tmp_path / "api.log", tmp_path / "out.json"
    log.write_text(line + "\n" + line, encoding="utf-8-sig")
    assert len(module.export_logs(log, output)["windows"]) == 1
    with pytest.raises(FileExistsError):
        module.export_logs(log, output)


def test_empty_or_divergent_logs_do_not_invent_windows(tmp_path):
    log = tmp_path / "api.log"
    log.write_text("no metrics yet")
    with pytest.raises(ValueError):
        module.export_logs(log, tmp_path / "result.json")
