"""T35: promocion/rollback HTTP reales sobre fixtures y servicios propios aislados."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from pathlib import Path

from src.retraining.demo_fixture import bootstrap, gate, models
from src.retraining.lifecycle import events
from src.retraining.promote import promote
from src.retraining.protocol import exclusive_json
from src.retraining.rollback import restore
from src.retraining.services import DemoGuard, ManagedAPI, ManagedProcess, free_port
from src.validation.run import _sha256


def demo(directory, *, project=None, external_rollback=False):
    os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
    project = Path(project or Path.cwd()).resolve()
    root = Path(directory).resolve()
    if root == project or not root.is_relative_to(project):
        raise ValueError("Demo requiere subdirectorio nuevo del proyecto")
    root.mkdir(parents=True, exist_ok=False)
    scope = uuid.uuid4().hex
    exclusive_json(root / "ISOLATED_DEMO.json", {"status": "TEST_ONLY", "scope_id": scope})
    (root / "configs").mkdir()
    shutil.copyfile(project / "configs/data.yaml", root / "configs/data.yaml")
    guard = DemoGuard(root)
    tracking_port, api_port = free_port(), free_port()
    while api_port == tracking_port:
        api_port = free_port()
    registry = ManagedProcess(root, "mlflow", tracking_port, guard)
    active = root / "configs/active.json"
    api = ManagedAPI(root, active, api_port, guard, test_only=True)
    api.receipt_path = root / "controller.json"
    result = {
        "status": "FAIL",
        "scope": "TEST_ONLY",
        "fixture_origin": "synthetic",
        "real_champion_changed": False,
    }
    try:
        registry.start()
        uri = f"http://127.0.0.1:{tracking_port}"
        previous, next_model = models(root, uri)
        guard.check()
        bootstrap(root, previous, active)
        api.start()
        api.smoke(previous)
        negative = gate(root, next_model, positive=False)
        positive = gate(root, next_model, positive=True)

        def packet(operation, evidence):
            value = {
                **deepcopy(next_model),
                "action": "PROMOTE",
                "operation_id": operation,
                "gate": evidence,
                "previous_approval_sha256": _sha256(active),
            }
            path = root / f"{operation}.json"
            exclusive_json(path, value)
            return path, value

        bad, _ = packet("rejected", negative)
        try:
            promote(bad, active, api, root=root, test_only=True)
        except ValueError:
            pass
        else:
            raise AssertionError("Se promovio un gate rechazado")
        api.smoke(previous)
        approved, desired = packet("approved", positive)
        promote(approved, active, api, root=root, test_only=True)
        api.smoke(desired)
        if external_rollback:
            log = root / "external-rollback.log"
            command = [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "src.retraining.rollback",
                "--operation",
                "approved",
                "--controller",
                str(api.receipt_path),
                "--root",
                str(root),
                "--test-only",
            ]
            with log.open("wb") as stream:
                process = subprocess.Popen(
                    command,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                while process.poll() is None:
                    guard.check()
                    time.sleep(0.1)
                if process.returncode:
                    raise RuntimeError(f"Rollback externo fallo: {log}")
            adopted = ManagedAPI.from_receipt(api.receipt_path, root=root, test_only=True)
            adopted.guard = guard
            adopted.process.guard = guard
            guard.services.append(adopted.process)
            api = adopted
        else:
            restore("approved", api, root=root)
        api.smoke(previous)
        failure, _ = packet("failed-smoke", positive)

        def crash_new_api(phase):
            if phase == "before_smoke":
                api.stop()

        try:
            promote(failure, active, api, root=root, test_only=True, fault=crash_new_api)
        except OSError:
            pass
        else:
            raise AssertionError("No se produjo el fallo HTTP controlado")
        api.smoke(previous)
        if events(root, "failed-smoke")[-1]["state"] != "ROLLED_BACK":
            raise AssertionError("Fallo sin compensacion")
        result.update(
            status="LIFECYCLE_DEMO_TEST_ONLY_PASS",
            promotion_verified=True,
            manual_rollback_verified=True,
            failed_http_smoke_compensated=True,
            rejected_gate_blocked=True,
            restored_version=previous["target"]["version"],
            resources={"initial": guard.initial, "combined_peak_rss_bytes": guard.peak},
            registry_uri=uri,
            api_uri=f"http://127.0.0.1:{api_port}",
            source_scope_id=scope,
            external_rollback=external_rollback,
        )
    finally:
        try:
            api.stop()
        finally:
            registry.stop()
        result["owned_services_stopped"] = True
        exclusive_json(root / "demo-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-rollback", action="store_true")
    args = parser.parse_args()
    print(json.dumps(demo(args.output_dir, external_rollback=args.external_rollback)))


if __name__ == "__main__":
    main()
