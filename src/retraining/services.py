"""Procesos propios, puertos loopback y presupuesto agregado para demos locales."""

import ctypes
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from src.retraining.lifecycle import PROTECTED_PORTS, local_uri, verified_package
from src.retraining.protocol import inside, read_json
from src.training.native_supervisor import process_alive, process_peak_rss, worker_identity
from src.training.resources import ResourceLimitError, snapshot


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    if port in PROTECTED_PORTS:
        return free_port()
    return port


def descendants(roots):
    parents = {}
    if os.name == "nt":
        from ctypes import wintypes

        class Entry(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD),
                ("usage", wintypes.DWORD),
                ("pid", wintypes.DWORD),
                ("heap", ctypes.c_size_t),
                ("module", wintypes.DWORD),
                ("threads", wintypes.DWORD),
                ("parent", wintypes.DWORD),
                ("priority", wintypes.LONG),
                ("flags", wintypes.DWORD),
                ("exe", wintypes.WCHAR * 260),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        handle = kernel.CreateToolhelp32Snapshot(2, 0)
        if handle == ctypes.c_void_p(-1).value:
            raise ResourceLimitError("No se pudo observar el arbol de procesos propios")
        value = Entry()
        value.size = ctypes.sizeof(value)
        try:
            more = kernel.Process32FirstW(handle, ctypes.byref(value))
            while more:
                parents[value.pid] = value.parent
                more = kernel.Process32NextW(handle, ctypes.byref(value))
        finally:
            kernel.CloseHandle(handle)
    else:
        for path in Path("/proc").glob("[0-9]*/status"):
            try:
                fields = dict(line.split(":", 1) for line in path.read_text().splitlines())
                parents[int(path.parent.name)] = int(fields["PPid"])
            except OSError, ValueError, KeyError:
                continue
    result = set(roots)
    while True:
        added = {pid for pid, parent in parents.items() if parent in result} - result
        if not added:
            return result
        result.update(added)


def verified_command(pid, token, root):
    if os.name == "nt":
        command = (
            "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
            f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}').CommandLine"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        value = result.stdout.decode("utf-8")
    else:
        value = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode()
    if "src.retraining.service_runner" not in value or token not in value or str(root) not in value:
        raise ValueError("PID reutilizado o comando ajeno al controlador")


class AdoptedProcess:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None if process_alive(self.pid) else 0

    def wait(self, timeout):
        deadline = time.monotonic() + timeout
        while self.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if self.poll() is None:
            raise TimeoutError("Proceso propio no termino")
        return 0


class DemoGuard:
    def __init__(self, root):
        initial = snapshot(Path(root))
        if initial["available_ram_bytes"] < 4 * 2**30 or initial["free_disk_bytes"] < 50 * 2**30:
            raise ResourceLimitError("Demo requiere 4 GiB RAM/50 GiB disco libres")
        self.root = Path(root)
        self.started = time.monotonic()
        self.services = []
        self.peak = 0
        self.initial = initial

    def check(self):
        total = process_peak_rss(os.getpid())
        roots = [
            s.process.pid
            for s in self.services
            if s.process is not None and s.process.poll() is None
        ]
        for pid in descendants([os.getpid(), *roots]) - {os.getpid()}:
            try:
                total += process_peak_rss(pid)
            except OSError, ProcessLookupError:
                continue
            except ResourceLimitError:
                if process_alive(pid):
                    raise
        self.peak = max(self.peak, total)
        if self.peak > 2 * 2**30 or time.monotonic() - self.started > 1200:
            raise ResourceLimitError("Demo excede 2 GiB RSS agregado o 20 minutos")
        if snapshot(self.root)["free_disk_bytes"] < 50 * 2**30:
            raise ResourceLimitError("Demo sin 50 GiB disco libres")


class ManagedProcess:
    def __init__(self, root, kind, port, guard, *, active=None, test_only=True):
        self.root = Path(root).resolve()
        self.kind = kind
        self.port = port
        self.guard = guard
        self.active = Path(active).resolve() if active else None
        self.test_only = test_only
        local_uri(f"http://127.0.0.1:{port}", test_only=True)
        self.process = None
        self.identity = None
        self.log = None
        self.stream = None
        self.token = None
        guard.services.append(self)

    def start(self):
        if self.process is not None and self.process.poll() is None:
            raise ValueError("Proceso gestionado ya esta activo")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", self.port))
        self.token = uuid.uuid4().hex
        directory = self.root / ".cache/services"
        directory.mkdir(parents=True, exist_ok=True)
        self.identity = directory / f"{self.token}.json"
        self.log = directory / f"{self.token}.log"
        command = [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "src.retraining.service_runner",
            "--root",
            str(self.root),
            "--kind",
            self.kind,
            "--port",
            str(self.port),
            "--identity",
            str(self.identity),
            "--token",
            self.token,
        ]
        if self.active:
            command.extend(["--active", str(self.active)])
        if self.test_only:
            command.append("--test-only")
        env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "MLFLOW_DISABLE_AGENT_HINT": "1",
            "DO_NOT_TRACK": "1",
            "MLFLOW_DISABLE_TELEMETRY": "true",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        env.pop("NYC_MLFLOW_TRACKING_URI", None)
        self.stream = self.log.open("wb")
        self.process = subprocess.Popen(
            command,
            cwd=self.root,
            env=env,
            stdout=self.stream,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            self.guard.check()
            if self.process.poll() is not None:
                raise RuntimeError(f"Servicio fallo; revisar {self.log}")
            if self.identity.exists():
                worker_identity((self.identity, None, self.token), self.process.pid)
                try:
                    with urlopen(f"http://127.0.0.1:{self.port}/health", timeout=0.5) as response:
                        if response.status == 200:
                            return
                except OSError, URLError:
                    pass
            time.sleep(0.1)
        raise RuntimeError(f"Timeout de servicio propio; revisar {self.log}")

    def stop(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            if not self.identity.exists():
                raise RuntimeError("No detener un proceso sin identidad")
            pid = worker_identity((self.identity, None, self.token), self.process.pid)
            verified_command(pid, self.token, self.root)
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=True
                )
            else:
                os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=20)
        if self.stream:
            self.stream.close()


class ManagedAPI:
    def __init__(self, root, active, port, guard, *, test_only):
        self.root = Path(root).resolve()
        self.active = inside(self.root, active)
        self.port = port
        self.test_only = test_only
        self.guard = guard
        self.process = ManagedProcess(
            self.root, "api", port, guard, active=self.active, test_only=test_only
        )

    def binding(self):
        return {
            "root": str(self.root),
            "active": str(self.active),
            "port": self.port,
            "test_only": self.test_only,
        }

    def write_receipt(self):
        if not hasattr(self, "receipt_path"):
            return
        value = self.binding()
        process = self.process
        value["process_active"] = bool(process.process and process.process.poll() is None)
        if value["process_active"]:
            value["owned_process"] = {
                "launcher_pid": process.process.pid,
                "identity": str(process.identity),
                "token": process.token,
            }
        from src.retraining.lifecycle import atomic_json

        atomic_json(self.receipt_path, value)

    def verify_binding(self, root, active):
        if Path(root).resolve() != self.root or Path(active).resolve() != self.active:
            raise ValueError("Controlador de otro directorio/aprobacion")
        if self.port in PROTECTED_PORTS:
            raise ValueError("Puerto de servicio existente protegido")

    @classmethod
    def from_receipt(cls, path, *, root, test_only):
        receipt = read_json(inside(root, path))
        if receipt["root"] != str(Path(root).resolve()) or receipt["test_only"] != test_only:
            raise ValueError("Recibo de controlador incompatible")
        api = cls(root, receipt["active"], receipt["port"], DemoGuard(root), test_only=test_only)
        api.receipt_path = inside(root, path)
        if receipt.get("process_active"):
            own = receipt["owned_process"]
            identity = inside(root, own["identity"])
            pid = worker_identity((identity, None, own["token"]), own["launcher_pid"])
            verified_command(pid, own["token"], Path(root).resolve())
            api.process.process = AdoptedProcess(own["launcher_pid"])
            api.process.identity = identity
            api.process.token = own["token"]
        return api

    def verify_package(self, decision):
        import mlflow

        from src.api.model_loader import restore_generated_metadata

        local_uri(decision["tracking_uri"], test_only=self.test_only)
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            downloaded = Path(
                mlflow.artifacts.download_artifacts(
                    artifact_uri=f"models:/{decision['target']['name']}/{decision['target']['version']}",
                    dst_path=directory,
                    tracking_uri=decision["tracking_uri"],
                    registry_uri=decision["tracking_uri"],
                )
            )
            if not downloaded.resolve().is_relative_to(Path(directory).resolve()):
                raise ValueError("Paquete fuera del temporal")
            restore_generated_metadata(downloaded, decision)
            verified_package(decision, downloaded)
        self.guard.check()

    def start(self):
        self.process.start()
        self.write_receipt()

    def stop(self):
        self.process.stop()
        self.write_receipt()

    def smoke(self, decision):
        from scripts.smoke_api import request_json

        base = f"http://127.0.0.1:{self.port}"
        code, info = request_json(base + "/model-info")
        if code != 200 or info["version"] != decision["target"]["version"]:
            raise ValueError("API no sirve la version aprobada")
        for payload, expected in zip(
            decision["smoke"]["payloads"], decision["smoke"]["expected_minutes"], strict=True
        ):
            code, value = request_json(base + "/predict", payload)
            if code != 200 or abs(value["predicted_duration_minutes"] - expected) > 1e-10:
                raise ValueError("Smoke de prediccion fallo")
        self.guard.check()
