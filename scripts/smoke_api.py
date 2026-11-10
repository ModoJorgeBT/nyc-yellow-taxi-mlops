"""T25: comprobaciones HTTP de serving sin modificar Registry ni sus aliases."""

import argparse
import json
import math
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SmokeError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SmokeError("unexpected_redirect")


def check_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("127.0.0.1", "localhost")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or not parsed.port
    ):
        raise SmokeError("expected_explicit_loopback_http_port")
    return value.rstrip("/")


def request_json(url: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    opener = build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        content = response.read(65537)
        if len(content) > 65536:
            raise SmokeError("response_too_large")
        return response.status, json.loads(content)


def smoke(base_url: str, approval: dict, *, unavailable=False, request=request_json) -> dict:
    base_url = check_url(base_url)
    target = approval["target"]
    payloads = approval["smoke"]["payloads"]
    expected = approval["smoke"]["expected_minutes"]
    observations = []
    for path in ("/health", "/model-info"):
        status, data = request(base_url + path)
        if status != (503 if unavailable else 200):
            raise SmokeError("unexpected_readiness_status")
        if (
            not unavailable
            and path == "/model-info"
            and (data.get("version") != target["version"] or data.get("name") != target["name"])
        ):
            raise SmokeError("unexpected_model_identity")
        if (
            not unavailable
            and path == "/health"
            and (data.get("model_loaded") is not True or data.get("status") != "ok")
        ):
            raise SmokeError("unexpected_health_body")
        observations.append({"path": path, "status": status})
    if unavailable:
        status, _ = request(base_url + "/predict", payloads[0])
        if status != 503:
            raise SmokeError("unavailable_model_must_not_predict")
        observations.append({"path": "/predict", "status": status})
    else:
        for payload, value in zip(payloads, expected, strict=True):
            status, data = request(base_url + "/predict", payload)
            # Smoke histórico incluye un origen deliberadamente desconocido.
            if payload["pickup_location_id"] not in range(1, 266):
                if status != 422:
                    raise SmokeError("unknown_origin_not_rejected")
            else:
                observed = data.get("predicted_duration_minutes")
                try:
                    timestamp = datetime.fromisoformat(data["predicted_at_utc"])
                    valid_time = timestamp.utcoffset().total_seconds() == 0
                except KeyError, TypeError, ValueError, AttributeError:
                    valid_time = False
                if (
                    status != 200
                    or type(observed) not in (int, float)
                    or not math.isfinite(observed)
                    or not math.isclose(observed, value, rel_tol=0, abs_tol=1e-10)
                    or data.get("model_version") != target["version"]
                    or data.get("unit") != "minutes"
                    or not valid_time
                ):
                    raise SmokeError("prediction_not_equal_to_approved_smoke")
            observations.append({"path": "/predict", "status": status})
        invalid = {**payloads[0], "trip_duration_minutes": 123}
        status, _ = request(base_url + "/predict", invalid)
        if status != 422:
            raise SmokeError("forbidden_feature_not_rejected")
        observations.append({"path": "/predict", "status": status})
    return {
        "status": "PASS",
        "mode": "UNAVAILABLE" if unavailable else "APPROVED_CHAMPION",
        "model_name": target["name"],
        "expected_version": target["version"],
        "observations": observations,
        "registry_mutated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--approval", type=Path, default=Path("configs/champion.yaml"))
    parser.add_argument("--expect-unavailable", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        approval = json.loads(args.approval.read_text(encoding="utf-8"))
        result = smoke(args.url, approval, unavailable=args.expect_unavailable)
    except Exception:
        result = {"status": "FAIL", "reason": "smoke_failed", "registry_mutated": False}
    result["recorded_at_utc"] = datetime.now(UTC).isoformat()
    output = args.output or Path("reports/smoke/api") / f"{uuid.uuid4().hex}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({"status": result["status"], "report": output.as_posix()}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
