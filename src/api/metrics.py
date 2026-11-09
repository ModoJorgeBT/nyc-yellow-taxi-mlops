"""T27: ventanas acotadas; latencia ASGI observada, sin payloads ni disponibilidad inferida."""

import argparse
import json
import math
import threading
import time
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROUTES = frozenset({"/predict", "/health", "/model-info", "/docs", "/openapi.json"})


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


class WindowMetrics:
    def __init__(self, emit, *, clock=time.monotonic, wall_clock=time.time, sample_limit=10_000):
        if type(sample_limit) is not int or sample_limit <= 0:
            raise ValueError("Limite de muestras invalido")
        self.emit, self.clock, self.sample_limit = emit, clock, sample_limit
        self.boot_id = uuid.uuid4().hex
        wall = wall_clock()
        self.utc_anchor = math.floor(wall / 60) * 60
        self.started = clock()
        self.anchor = self.started - (wall - self.utc_anchor)
        self.lock = threading.Lock()
        self.index = 0
        self.closed = False
        self._reset()

    def _reset(self):
        self.count = 0
        self.codes = Counter()
        self.routes = defaultdict(Counter)
        self.samples = []
        self.by_route = defaultdict(list)
        self.incomplete = self.exceptions = 0
        self.overflow = False

    def _report(self, now, *, partial):
        start = max(self.started, self.anchor + self.index * 60)
        end = (
            min(now, self.anchor + (self.index + 1) * 60)
            if partial
            else self.anchor + (self.index + 1) * 60
        )
        elapsed = max(0.0, end - start)
        available = not self.overflow

        def latencies(values):
            return {
                "p50_ms": percentile(values, 0.50) if available else None,
                "p95_ms": percentile(values, 0.95) if available else None,
            }

        return {
            "format_version": 1,
            "boot_id": self.boot_id,
            "window_index": self.index,
            "window_start_utc": datetime.fromtimestamp(
                self.utc_anchor + self.index * 60, UTC
            ).isoformat(),
            "period_seconds": elapsed,
            "partial": partial or start > self.anchor + self.index * 60,
            "requests": self.count,
            "throughput_rps": self.count / elapsed if elapsed > 0 else None,
            "status_codes": dict(self.codes),
            "http_4xx": sum(
                count
                for code, count in self.codes.items()
                if code.isdecimal() and 400 <= int(code) < 500
            ),
            "http_5xx": sum(
                count
                for code, count in self.codes.items()
                if code.isdecimal() and 500 <= int(code) < 600
            ),
            "incomplete_responses": self.incomplete,
            "exceptions": self.exceptions,
            "percentile_status": "NOT_AVAILABLE_OVERFLOW" if self.overflow else "EXACT_LINEAR",
            "sample_limit": self.sample_limit,
            "completed_latency_samples": len(self.samples),
            **latencies(self.samples),
            "routes": {
                route: {"status_codes": dict(counts), **latencies(self.by_route[route])}
                for route, counts in self.routes.items()
            },
            "availability": "NOT_INFERRED",
        }

    def record(self, route, code, milliseconds, *, complete=True, exception=False):
        if (
            not math.isfinite(milliseconds)
            or milliseconds < 0
            or (code is not None and not 100 <= code <= 599)
        ):
            raise ValueError("Observacion operativa invalida")
        route = route if route in ROUTES else "unmatched"
        report = None
        with self.lock:
            if self.closed:
                return
            now = self.clock()
            index = max(self.index, math.floor((now - self.anchor) / 60))
            if index > self.index:
                report = self._report(now, partial=False)
                report["unobserved_gap_windows"] = index - self.index - 1
                self.index = index
                self._reset()
            self.count += 1
            code_key = str(code) if code is not None else "no_response"
            self.codes[code_key] += 1
            self.routes[route][code_key] += 1
            self.incomplete += not complete
            self.exceptions += bool(exception)
            if self.count > self.sample_limit:
                self.overflow = True
            elif complete:
                self.samples.append(milliseconds)
                self.by_route[route].append(milliseconds)
        if report is not None:
            self.emit(report)

    def snapshot(self):
        with self.lock:
            return self._report(self.clock(), partial=True)

    def close(self):
        with self.lock:
            if self.closed:
                return
            report = self._report(self.clock(), partial=True)
            self.closed = True
        self.emit(report)


class MetricsMiddleware:
    def __init__(self, app, *, collector, logger):
        self.app, self.collector, self.logger = app, collector, logger

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start = time.perf_counter()
        status, complete, failed, finished = None, False, False, None

        async def observed_send(message):
            nonlocal status, complete, finished
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                complete = True
                finished = time.perf_counter()

        try:
            await self.app(scope, receive, observed_send)
        except BaseException:
            failed = True
            raise
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            route = route if route in ROUTES else "unmatched"
            elapsed = ((finished if finished is not None else time.perf_counter()) - start) * 1000
            self.collector.record(route, status, elapsed, complete=complete, exception=failed)
            self.logger.info("request route=%s status=%s duration_ms=%.3f", route, status, elapsed)


def export_logs(log_file: Path, output: Path) -> dict:
    windows = {}
    for line in log_file.read_text(encoding="utf-8-sig").splitlines():
        if "metrics_window " not in line:
            continue
        record = json.loads(line.split("metrics_window ", 1)[1])
        key = (record["boot_id"], record["window_index"])
        if key in windows and windows[key] != record:
            raise ValueError("Ventana duplicada divergente")
        windows[key] = record
    if not windows:
        raise ValueError("No hay ventanas cerradas; esperar rollover o cierre del proceso")
    result = {
        "format_version": 1,
        "windows": list(windows.values()),
        "availability": "NOT_INFERRED",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export_logs(args.log_file, args.output)
    print(json.dumps({"status": "EXPORTED", "windows": len(result["windows"])}))


if __name__ == "__main__":
    main()
