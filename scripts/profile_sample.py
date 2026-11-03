"""T05: perfilado posicional acotado de 2024, sin modificar raw ni leer filas de 2025."""

import argparse
import ctypes
import hashlib
import json
import math
import os
import platform
import shutil
import time
import tracemalloc
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def number_summary(values: list[float]) -> dict[str, float | int | None]:
    """Cuantiles por interpolacion lineal, sin eliminar valores extremos."""
    ordered = sorted(value for value in values if math.isfinite(value))
    result: dict[str, float | int | None] = {"count": len(ordered)}
    if not ordered:
        return {**result, **dict.fromkeys(("min", "p50", "p95", "p99", "max"))}
    for name, fraction in (("min", 0.0), ("p50", 0.5), ("p95", 0.95), ("p99", 0.99), ("max", 1.0)):
        position = (len(ordered) - 1) * fraction
        left = int(position)
        right = min(left + 1, len(ordered) - 1)
        result[name] = ordered[left] + (ordered[right] - ordered[left]) * (position - left)
    return result


def summarize_table(table: pa.Table, *, year: int, month: int) -> dict:
    """Describe una muestra historica; no emite PASS/FAIL ni limpia datos."""
    essential = ("tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID", "DOLocationID")
    if any(name not in table.column_names for name in essential):
        raise ValueError("La muestra no tiene columnas esenciales para el perfilado")
    for name in essential[:2]:
        if not pa.types.is_timestamp(table.schema.field(name).type):
            raise ValueError(f"Timestamp incompatible en muestra: {name}")
    for name in essential[2:]:
        if not pa.types.is_integer(table.schema.field(name).type):
            raise ValueError(f"Zona incompatible en muestra: {name}")

    rows = table.to_pylist()
    durations = []
    pickups = []
    outside = nonpositive = 0
    seen: set[tuple] = set()
    duplicates = 0
    for row in rows:
        pickup = row["tpep_pickup_datetime"]
        dropoff = row["tpep_dropoff_datetime"]
        if pickup is not None:
            pickups.append(pickup)
            outside += (pickup.year, pickup.month) != (year, month)
        if pickup is not None and dropoff is not None:
            minutes = (dropoff - pickup).total_seconds() / 60
            durations.append(minutes)
            nonpositive += minutes <= 0
        key = tuple(
            "__nan__" if isinstance(value, float) and math.isnan(value) else value
            for value in row.values()
        )
        duplicates += key in seen
        seen.add(key)

    zones = {}
    for name in essential[2:]:
        values = [row[name] for row in rows if row[name] is not None]
        zones[name] = {
            "nonpositive": sum(value <= 0 for value in values),
            "min": min(values, default=None),
            "max": max(values, default=None),
            "unique": len(set(values)),
            "frequent": Counter(values).most_common(5),
            "catalog_membership": "NOT_EVALUATED",
        }
    passengers = [row["passenger_count"] for row in rows if row.get("passenger_count") is not None]
    return {
        "rows": table.num_rows,
        "nulls": {name: table[name].null_count for name in table.column_names},
        "pickup_min": min(pickups).isoformat() if pickups else None,
        "pickup_max": max(pickups).isoformat() if pickups else None,
        "pickup_outside_file_month": outside,
        "nonpositive_duration": nonpositive,
        "duration_minutes": number_summary(durations),
        "positive_duration_minutes": number_summary([value for value in durations if value > 0]),
        "duplicate_exact_sample_rows": duplicates,
        "zones": zones,
        "passenger_count": {
            "negative": sum(value < 0 for value in passengers),
            "zero": sum(value == 0 for value in passengers),
            "range": [min(passengers, default=None), max(passengers, default=None)],
        },
        "sample_arrow_bytes": table.nbytes,
    }


def sample_file(path: Path, *, rows_per_group: int = 2048) -> dict:
    """Lee solo un primer batch por row group y registra sus limites exactos."""
    if not 1 <= rows_per_group <= 2048:
        raise ValueError("rows_per_group debe estar entre 1 y 2048")
    before = path.stat()
    parquet = pq.ParquetFile(path)
    try:
        groups = []
        batches = []
        schema = parquet.schema_arrow
        footer_rows = parquet.metadata.num_rows
        for index in range(parquet.metadata.num_row_groups):
            iterator = parquet.iter_batches(
                batch_size=rows_per_group, row_groups=[index], use_threads=False
            )
            batch = next(iterator, None)
            del iterator
            if batch is not None:
                batches.append(batch)
                groups.append({"row_group": index, "start_row_in_group": 0, "rows": batch.num_rows})
        table = pa.Table.from_batches(batches, schema=schema).combine_chunks()
    finally:
        parquet.close()
    sample = table.replace_schema_metadata(None)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, sample.schema) as writer:
        writer.write_table(sample)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"El archivo cambio durante el perfilado: {path.name}")
    return {
        "file": path.name,
        "source_bytes": before.st_size,
        "source_sha256": digest.hexdigest(),
        "footer_rows": footer_rows,
        "schema": [{"name": field.name, "type": str(field.type)} for field in schema],
        "selected_ranges": groups,
        "sample_sha256": hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest(),
        "sample_table": table,
    }


def windows_resources() -> dict:
    """Medidas del host/proceso con APIs nativas; no presupone limites Docker."""
    if os.name != "nt":
        return {"ram_total_bytes": None, "process_peak_rss_bytes": None}
    from ctypes import wintypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong)
            for name in (
                "total",
                "available",
                "page_total",
                "page_available",
                "v_total",
                "v_available",
                "extended",
            )
        ]

    class ProcessMemory(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak_rss",
                "rss",
                "peak_paged",
                "paged",
                "peak_nonpaged",
                "nonpaged",
                "pagefile",
                "peak_pagefile",
            )
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatus)]
    kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
    ram = status.total if kernel.GlobalMemoryStatusEx(ctypes.byref(status)) else None
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    counters = ProcessMemory()
    counters.cb = ctypes.sizeof(counters)
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemory),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    success = psapi.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    )
    return {
        "ram_total_bytes": ram,
        "process_peak_rss_bytes": counters.peak_rss if success else None,
    }


def profile_year(raw_dir: Path, *, rows_per_group: int = 2048) -> dict:
    """Alcance aprobado: 12 meses de 2024; las filas de 2025 no se abren."""
    paths = [
        raw_dir / "2024" / f"{month:02}" / f"yellow_tripdata_2024-{month:02}.parquet"
        for month in range(1, 13)
    ]
    if not all(path.is_file() for path in paths):
        raise ValueError("Se requieren los doce Parquet 2024 en raw/YYYY/MM")
    started = time.perf_counter()
    tracemalloc.start()
    files = []
    try:
        for month, path in enumerate(paths, 1):
            info = sample_file(path, rows_per_group=rows_per_group)
            table = info.pop("sample_table")
            info["profile"] = summarize_table(table, year=2024, month=month)
            files.append(info)
            del table
        python_peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return {
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "pyarrow": pa.__version__,
        "year": 2024,
        "method": "first_batch_per_row_group",
        "rows_per_group": rows_per_group,
        "sample_rows": sum(info["profile"]["rows"] for info in files),
        "footer_rows": sum(info["footer_rows"] for info in files),
        "files": files,
        "resources": {
            "logical_cpus": os.cpu_count(),
            "disk_free_bytes": shutil.disk_usage(raw_dir).free,
            **windows_resources(),
            "python_tracemalloc_peak_bytes": python_peak,
            "arrow_pool_peak_bytes": pa.default_memory_pool().max_memory(),
            "elapsed_seconds": time.perf_counter() - started,
            "docker_limits": "NOT_MEASURED",
        },
    }


def render_markdown(result: dict) -> str:
    """Reporte con observaciones y propuestas; nunca aprueba gates."""
    resources = result["resources"]
    lines = [
        "# T05 — Perfilado tecnico acotado de 2024",
        "",
        f"Ejecucion UTC: {result['executed_at_utc']}. "
        f"Python {result['python']}; PyArrow {result['pyarrow']}.",
        "",
        f"Muestra: {result['sample_rows']:,} filas; footers 2024: {result['footer_rows']:,}. "
        f"Primeras {result['rows_per_group']} filas de cada row group; "
        "rangos exactos y hashes en el JSON local.",
        "",
        "La muestra es posicional determinista y sesgada, no representativa del anio. "
        "Tasas, extremos y cuantiles describen solo las filas leidas. "
        "No se perfilaron filas de 2025 ni se eligieron particiones o entrenaron modelos. "
        "Para SHA-256 se leyeron los bytes comprimidos por bloques; "
        "solo se decodificaron las filas seleccionadas.",
        "",
        "Los timestamps se restaron tal como estan almacenados, sin convertir zona horaria. "
        "La interpretacion historica/DST sigue pendiente; estas duraciones son exploratorias.",
        "",
        "## Observaciones por mes",
        "",
        "| Mes | Filas | Fuera mes | Duracion <=0 | Positiva p50/p95/p99/max (min) | Duplicados |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for index, info in enumerate(result["files"], 1):
        stats = info["profile"]
        duration = stats["positive_duration_minutes"]
        values = "/".join(
            "NA" if duration[key] is None else f"{duration[key]:.2f}"
            for key in ("p50", "p95", "p99", "max")
        )
        lines.append(
            f"| 2024-{index:02} | {stats['rows']} | {stats['pickup_outside_file_month']} | "
            f"{stats['nonpositive_duration']} | {values} | {stats['duplicate_exact_sample_rows']} |"
        )
    lines += [
        "",
        "## Nulos y pasajeros en la muestra",
        "",
        "| Mes | Origen nulo | Destino nulo | Pickup/dropoff nulos | Pasajeros nulos/cero/neg. |",
        "|---|---:|---:|---|---|",
    ]
    for index, info in enumerate(result["files"], 1):
        stats = info["profile"]
        nulls = stats["nulls"]
        passengers = stats["passenger_count"]
        lines.append(
            f"| 2024-{index:02} | {nulls['PULocationID']} | {nulls['DOLocationID']} | "
            f"{nulls['tpep_pickup_datetime']}/{nulls['tpep_dropoff_datetime']} | "
            f"{nulls.get('passenger_count', 'NA')}/{passengers['zero']}/{passengers['negative']} |"
        )
    lines += [
        "",
        "## Zonas observadas (sin validacion contra catalogo)",
        "",
        "| Mes | Origen min/max/unicos | Destino min/max/unicos |",
        "|---|---|---|",
    ]
    for index, info in enumerate(result["files"], 1):
        zones = info["profile"]["zones"]
        origin = zones["PULocationID"]
        destination = zones["DOLocationID"]
        lines.append(
            f"| 2024-{index:02} | {origin['min']}/{origin['max']}/{origin['unique']} | "
            f"{destination['min']}/{destination['max']}/{destination['unique']} |"
        )
    lines += ["", "## Recursos observados", "", "| Medida | Valor |", "|---|---:|"]
    lines.extend(f"| {name} | {value} |" for name, value in resources.items())
    notes = Path(__file__).with_name("eda_notes.md").read_text(encoding="utf-8")
    return "\n".join(lines) + "\n\n" + notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--rows-per-group", type=int, default=2048, choices=range(1, 2049), metavar="1..2048"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    if args.output_dir.resolve().is_relative_to(args.raw_dir.resolve()):
        parser.error("El directorio de salida no puede estar dentro de raw")
    try:
        result = profile_year(args.raw_dir, rows_per_group=args.rows_per_group)
    except (OSError, ValueError, pa.ArrowException) as error:
        parser.exit(1, f"Perfilado fallido: {error}\n")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "eda_schema.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (args.output_dir / "eda_schema.md").write_text(render_markdown(result), encoding="utf-8")
    print(f"Perfiladas {result['sample_rows']} filas de 2024; recursos: {result['resources']}")


if __name__ == "__main__":
    main()
