"""Lectura local y supervision cooperativa D-02; no modifica limites del host."""

import ctypes
import os
import shutil
from pathlib import Path


class ResourceLimitError(RuntimeError):
    pass


def snapshot(directory: Path) -> dict:
    if os.name == "nt":
        from ctypes import wintypes

        class Memory(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong)
                for name in ("total", "available", "p1", "p2", "v1", "v2", "extended")
            ]

        class Process(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("peak", "rss", "a", "b", "c", "d", "e", "f")
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        memory, process = Memory(), Process()
        memory.length, process.cb = ctypes.sizeof(memory), ctypes.sizeof(process)
        kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(Memory)]
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Process),
            wintypes.DWORD,
        ]
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(memory)) or not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(process), process.cb
        ):
            raise ResourceLimitError("No se pudieron medir recursos Windows")
        available, peak = memory.available, process.peak
    elif os.name == "posix" and Path("/proc/meminfo").is_file():
        import resource

        entries = dict(
            line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()
        )
        available = int(entries["MemAvailable"].split()[0]) * 1024
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        # No presentar memoria del host como disponible dentro de un cgroup v2.
        limit_file = Path("/sys/fs/cgroup/memory.max")
        if limit_file.is_file():
            limit = limit_file.read_text().strip()
            if limit != "max":
                current = int(Path("/sys/fs/cgroup/memory.current").read_text())
                available = min(available, max(0, int(limit) - current))
    else:
        raise ResourceLimitError("Plataforma sin medicion de recursos implementada")
    return {
        "available_ram_bytes": available,
        "peak_rss_bytes": peak,
        "free_disk_bytes": shutil.disk_usage(directory).free,
    }


class ResourceGuard:
    """Preflight y chequeos entre bloques; no es un limite duro del SO/contenedor."""

    def __init__(self, policy: dict, directory: Path, *, test_only: bool):
        self.policy, self.directory, self.test_only = policy, directory, test_only
        self.initial = None
        self.last = None

    def check(self, *, start: bool = False) -> None:
        if self.test_only:
            return
        self.last = snapshot(self.directory)
        if start:
            self.initial = self.last
        limits = [
            ("peak_rss_bytes", "process_rss_limit_gib", False),
            ("free_disk_bytes", "preflight_min_free_disk_gib", True),
        ]
        if start:
            limits.append(("available_ram_bytes", "preflight_min_free_ram_gib", True))
        for measured, configured, minimum in limits:
            limit = self.policy[configured] * 2**30
            observed = self.last[measured]
            if (minimum and observed < limit) or (not minimum and observed > limit):
                raise ResourceLimitError(f"D-02: {measured}={observed}; limite={limit}")
