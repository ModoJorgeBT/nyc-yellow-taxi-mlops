"""Supervisor de un proceso propio: también observa llamadas nativas bloqueantes."""

import ctypes
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from src.training.resources import ResourceLimitError


def _linux_peak_rss(status: str) -> int:
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    if "VmHWM" not in fields:
        if fields.get("State", "").strip().startswith(("Z", "X")):
            raise ProcessLookupError("El proceso propio ya termino")
        raise ResourceLimitError("Proceso activo sin medicion VmHWM; no continuar sin control RSS")
    return int(fields["VmHWM"].split()[0]) * 1024


def process_peak_rss(pid: int) -> int:
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("peak", "rss", "a", "b", "c", "d", "e", "f")
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
        if not handle:
            raise ResourceLimitError("No se pudo inspeccionar el proceso LightGBM propio")
        try:
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                raise ResourceLimitError("No se pudo medir RSS del proceso LightGBM")
            return counters.peak
        finally:
            kernel.CloseHandle(handle)
    if os.name == "posix":
        return _linux_peak_rss(Path(f"/proc/{pid}/status").read_text())
    raise ResourceLimitError("Sin medición externa de RSS para esta plataforma")


def worker_identity(identity, launcher_pid):
    path, _, token = identity
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    pid, parent = value.get("pid"), value.get("parent_pid")
    if (
        type(pid) is not int
        or pid <= 0
        or type(parent) is not int
        or value.get("token") != token
        or (pid != launcher_pid and parent != launcher_pid)
    ):
        raise ResourceLimitError("Identidad del proceso nativo no verificable")
    return pid


def process_alive(pid):
    if os.name != "nt":
        try:
            return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
        except FileNotFoundError:
            return False
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


def terminate_worker(pid):
    if os.name != "nt":
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        return
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00101001, False, pid)
    if not handle:
        if not process_alive(pid):
            return
        raise ResourceLimitError("No se pudo cancelar el proceso nativo propio")
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ResourceLimitError("No se pudo verificar la cancelación nativa")
        if code.value == 259 and not kernel.TerminateProcess(handle, 1):
            raise ResourceLimitError("Falló la cancelación del proceso nativo")
        if kernel.WaitForSingleObject(handle, 10000) != 0:
            raise ResourceLimitError("El proceso nativo no confirmó su terminación")
    finally:
        kernel.CloseHandle(handle)


def supervise(command, *, policy, guard, log_path, env=None, identity=None):
    peak = 0
    worker_pid = None
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with Path(log_path).open("w", encoding="utf-8") as log:
        with subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=flags
        ) as process:
            try:
                while process.poll() is None:
                    guard.check()
                    if identity is not None and worker_pid is None:
                        if not Path(identity[0]).exists():
                            time.sleep(policy["native_process_poll_seconds"])
                            continue
                        worker_pid = worker_identity(identity, process.pid)
                    observed_pid = process.pid if identity is None else worker_pid
                    try:
                        peak = max(peak, process_peak_rss(observed_pid))
                    except ProcessLookupError:
                        if process_alive(observed_pid):
                            raise
                        # /proc puede mostrar Z antes de que poll recoja el codigo de salida.
                        # Conservar el pico anterior; nunca sustituir RSS de un proceso activo.
                        time.sleep(policy["native_process_poll_seconds"])
                        continue
                    except OSError, ResourceLimitError:
                        if process.poll() is None:
                            raise
                    if peak > policy["process_rss_limit_gib"] * 2**30:
                        raise ResourceLimitError("D-02: RSS nativo excedido; intento cancelado")
                    if identity is not None and not Path(identity[1]).exists():
                        ready = Path(identity[1])
                        temporary = ready.with_suffix(".tmp")
                        temporary.write_text(identity[2], encoding="utf-8")
                        temporary.replace(ready)
                    time.sleep(policy["native_process_poll_seconds"])
                guard.check()
                if process.returncode != 0:
                    raise RuntimeError(f"LightGBM terminó con código {process.returncode}; ver log")
                if identity is not None and worker_pid is None:
                    raise ResourceLimitError("El proceso terminó sin supervisión nativa verificada")
            except BaseException:
                if identity is not None and worker_pid is None and Path(identity[0]).exists():
                    worker_pid = worker_identity(identity, process.pid)
                if process.poll() is None and worker_pid is not None and worker_pid != process.pid:
                    terminate_worker(worker_pid)
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                raise
    return {
        "native_peak_rss_bytes": peak,
        "exit_code": process.returncode,
        "worker_pid_verified": identity is not None and worker_pid is not None,
        "worker_pid": worker_pid,
        "launcher_pid": process.pid,
    }


def run_worker(request_path, *, policy, guard, log_path):
    request_path = Path(request_path).resolve()
    pid_path, ready_path = request_path.with_suffix(".pid.json"), request_path.with_suffix(".ready")
    if pid_path.exists() or ready_path.exists():
        raise ValueError("Una petición nativa no puede reutilizar su identidad")
    token = uuid.uuid4().hex
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request.update(pid_path=str(pid_path), ready_path=str(ready_path), identity_token=token)
    request_path.write_text(json.dumps(request), encoding="utf-8")
    environment = dict(os.environ)
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        environment[name] = "4"
    command = [
        sys.executable,
        "-I",
        "-X",
        "utf8",
        "-B",
        str(Path(__file__).with_name("lightgbm_worker.py").resolve()),
        "--request",
        str(Path(request_path).resolve()),
    ]
    return supervise(
        command,
        policy=policy,
        guard=guard,
        log_path=log_path,
        env=environment,
        identity=(pid_path, ready_path, token),
    )
