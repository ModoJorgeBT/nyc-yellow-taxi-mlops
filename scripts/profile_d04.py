"""D-04: muestra aleatoria estratificada de 2024; no aplica quality gates."""

import argparse
import csv
import hashlib
import json
import platform
import random
import time
from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.profile_sample import windows_resources
from src.features.schema import FeatureError
from src.features.target import TEMPORAL_POLICY, localize_historical
from src.ingestion.manifest import describe_parquet
from src.validation.rules import _canonical
from src.validation.schema import load_config, validate_schema

CATEGORY_VALUES = {
    "VendorID": {1, 2, 6, 7},
    "RatecodeID": {1, 2, 3, 4, 5, 6, 99},
    "payment_type": set(range(7)),
    "store_and_fwd_flag": {"Y", "N"},
}
UPPER_LIMITS = (60, 120, 180, 240, 360, 1440)
METRICS = (
    "timestamp_null",
    "invalid_historical_time",
    "ambiguous_local_time",
    "nonexistent_local_time",
    "duration_nonpositive",
    "pickup_outside_month",
    "PU_null",
    "PU_outside_catalog",
    "PU_special",
    "DO_null",
    "DO_outside_catalog",
    "DO_special",
    "passenger_null",
    "passenger_zero",
    "passenger_negative",
    "passenger_above_6",
    "passenger_above_8",
    "passenger_adjustment_0_6",
    "category_unknown",
    "category_null",
    "category_outside_dictionary",
    "passenger_null_and_metadata_null",
    "duplicate_in_sample",
)
BASE_INVALID = {
    "timestamp_null",
    "invalid_historical_time",
    "ambiguous_local_time",
    "nonexistent_local_time",
    "duration_nonpositive",
    "pickup_outside_month",
    "PU_null",
    "PU_outside_catalog",
}
SCENARIOS = (
    "no_duration_cap",
    *[f"cap_{n}" for n in UPPER_LIMITS],
    "cap_180_exclude_special_origin",
    "cap_180_exclude_invalid_passengers",
)


def allocate_quotas(group_sizes: list[int], sample_size: int) -> list[int]:
    if type(sample_size) is not int or sample_size <= 0:
        raise ValueError("sample_size debe ser entero positivo")
    if any(type(size) is not int or size < 0 for size in group_sizes):
        raise ValueError("Tamanos de grupos invalidos")
    total = sum(group_sizes)
    if not total:
        return [0] * len(group_sizes)
    wanted = min(sample_size, total)
    quotas = [wanted * size // total for size in group_sizes]
    order = sorted(range(len(group_sizes)), key=lambda i: (-(wanted * group_sizes[i] % total), i))
    for index in order[: wanted - sum(quotas)]:
        quotas[index] += 1
    if any(size and not quota for size, quota in zip(group_sizes, quotas, strict=True)):
        raise ValueError("La muestra debe incluir todos los grupos no vacios")
    return quotas


def weighted_quantiles(values: list[tuple[float, float]]) -> dict:
    if not values:
        return dict.fromkeys(("min", "p50", "p95", "p99", "p999", "max"))
    ordered = sorted(values)
    total = sum(weight for _, weight in ordered)
    result = {"min": ordered[0][0], "max": ordered[-1][0]}
    for name, fraction in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99), ("p999", 0.999)):
        accumulated = 0.0
        for value, weight in ordered:
            accumulated += weight
            if accumulated >= fraction * total:
                result[name] = value
                break
    return result


def assess(row: dict, *, month: int, zone_ids: set[int]) -> tuple[set[str], float | None]:
    flags, localized = set(), []
    for field in ("tpep_pickup_datetime", "tpep_dropoff_datetime"):
        value = row[field]
        if value is None:
            flags.add("timestamp_null")
            localized.append(None)
        else:
            try:
                localized.append(localize_historical(value))
            except FeatureError as error:
                flags.add(error.reason)
                localized.append(None)
    pickup = row["tpep_pickup_datetime"]
    if isinstance(pickup, datetime) and (pickup.year, pickup.month) != (2024, month):
        flags.add("pickup_outside_month")
    duration = None
    if all(value is not None for value in localized):
        duration = (
            localized[1].astimezone(UTC) - localized[0].astimezone(UTC)
        ).total_seconds() / 60
        if duration <= 0:
            flags.add("duration_nonpositive")
    for prefix, field in (("PU", "PULocationID"), ("DO", "DOLocationID")):
        value = row[field]
        if value is None:
            flags.add(f"{prefix}_null")
        elif value not in zone_ids:
            flags.add(f"{prefix}_outside_catalog")
        elif value in (264, 265):
            flags.add(f"{prefix}_special")
    passengers = row.get("passenger_count")
    if passengers is None:
        flags.add("passenger_null")
    else:
        if passengers == 0:
            flags.add("passenger_zero")
        if passengers < 0:
            flags.add("passenger_negative")
        if passengers > 6:
            flags.add("passenger_above_6")
        if passengers > 8:
            flags.add("passenger_above_8")
        if not 0 <= passengers <= 6:
            flags.add("passenger_adjustment_0_6")
    metadata_null = any(name in row and row[name] is None for name in CATEGORY_VALUES)
    if metadata_null:
        flags.add("category_null")
        if passengers is None:
            flags.add("passenger_null_and_metadata_null")
    if any(
        name in row and row[name] is not None and row[name] not in allowed
        for name, allowed in CATEGORY_VALUES.items()
    ):
        flags.add("category_outside_dictionary")
    if metadata_null or "category_outside_dictionary" in flags:
        flags.add("category_unknown")
    return flags, duration


def profile_file(
    path: Path,
    *,
    month: int,
    zone_ids: set[int],
    config: dict,
    sample_size: int,
    seed: int,
    batch_size: int,
) -> dict:
    before = describe_parquet(path)
    if before["row_count"] == 0:
        raise ValueError("Lote vacio: no se puede estimar una tasa por muestreo")
    schema_report = None
    counts, weighted = Counter(), Counter()
    nulls, passengers, zones = (
        Counter(),
        Counter(),
        {"PULocationID": Counter(), "DOLocationID": Counter()},
    )
    categories = {name: Counter() for name in CATEGORY_VALUES}
    duplicate_keys = set()
    durations, eligible_durations = [], []
    selection, sample_count, decoded = [], 0, 0
    sample_digest = hashlib.sha256()
    with path.open("rb") as source, pq.ParquetFile(source) as parquet:
        schema_report = validate_schema(parquet.schema_arrow, config)
        if schema_report["status"] == "FAIL":
            raise ValueError(f"Esquema incompatible: {path.name}")
        sizes = [parquet.metadata.row_group(i).num_rows for i in range(parquet.num_row_groups)]
        quotas = allocate_quotas(sizes, sample_size)
        names = parquet.schema_arrow.names
        for group, (size, quota) in enumerate(zip(sizes, quotas, strict=True)):
            if not quota:
                continue
            rng = random.Random(f"d04-v1:{seed}:2024:{month}:{group}")
            positions = sorted(rng.sample(range(size), quota))
            weight = size / quota
            selection.append(
                {
                    "row_group": group,
                    "population_rows": size,
                    "sample_rows": quota,
                    "design_weight": weight,
                    "selected_rows_in_group": positions,
                }
            )
            cursor, offset = 0, 0
            for batch in parquet.iter_batches(
                batch_size=batch_size, row_groups=[group], use_threads=False
            ):
                decoded += batch.num_rows
                columns = list(batch.columns)
                while cursor < quota and positions[cursor] < offset + batch.num_rows:
                    index = positions[cursor] - offset
                    # Scalar.as_py copia solo las celdas seleccionadas; no retiene el bloque.
                    row = {
                        name: column[index].as_py()
                        for name, column in zip(names, columns, strict=True)
                    }
                    encoded = json.dumps(
                        [_canonical(row[name]) for name in names],
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ).encode()
                    sample_digest.update(encoded + b"\n")
                    flags, duration = assess(row, month=month, zone_ids=zone_ids)
                    if encoded in duplicate_keys:
                        flags.add("duplicate_in_sample")
                    duplicate_keys.add(encoded)
                    for name, value in row.items():
                        nulls[name] += value is None
                    passengers[str(row.get("passenger_count"))] += 1
                    for name in zones:
                        zones[name][str(row[name])] += 1
                    for name in categories:
                        if name in row:
                            categories[name][str(row[name])] += 1
                    invalid = bool(flags & BASE_INVALID)
                    invalid180 = invalid or duration is not None and duration > 180
                    scenarios = {
                        "no_duration_cap": invalid,
                        **{
                            f"cap_{n}": invalid or duration is not None and duration > n
                            for n in UPPER_LIMITS
                        },
                        "cap_180_exclude_special_origin": invalid180 or "PU_special" in flags,
                        "cap_180_exclude_invalid_passengers": invalid180
                        or "passenger_adjustment_0_6" in flags,
                    }
                    for name in flags:
                        counts[name] += 1
                        weighted[name] += weight
                    for name, excluded in scenarios.items():
                        if excluded:
                            counts[name] += 1
                            weighted[name] += weight
                    for n in UPPER_LIMITS:
                        if duration is not None and duration > n:
                            counts[f"duration_above_{n}"] += 1
                            weighted[f"duration_above_{n}"] += weight
                    if duration is not None and duration > 0:
                        durations.append((duration, weight))
                        if not invalid:
                            eligible_durations.append((duration, weight))
                    sample_count += 1
                    cursor += 1
                offset += batch.num_rows
                if cursor == quota:
                    break
            if cursor != quota:
                raise ValueError("Lectura de muestra incompleta")
    after = describe_parquet(path)
    if before != after:
        raise ValueError("El archivo cambio durante el perfilado")
    metrics = {}
    for name in (*METRICS, *SCENARIOS, *[f"duration_above_{n}" for n in UPPER_LIMITS]):
        metrics[name] = {
            "sample_count": counts[name],
            "sample_rate": counts[name] / sample_count,
            "estimated_rate": None
            if name == "duplicate_in_sample"
            else weighted[name] / before["row_count"],
        }
    return {
        "file_name": path.name,
        "month": month,
        "source": before,
        "source_hash_unchanged": True,
        "schema_status": schema_report["status"],
        "sample_rows": sample_count,
        "decoded_rows": decoded,
        "selection": selection,
        "sample_sha256": sample_digest.hexdigest(),
        "metrics": metrics,
        "null_counts": dict(nulls),
        "passenger_frequencies": dict(passengers),
        "zone_frequencies": {k: dict(v) for k, v in zones.items()},
        "category_frequencies": {k: dict(v) for k, v in categories.items()},
        "positive_duration_minutes": weighted_quantiles(durations),
        "eligible_positive_duration_minutes": weighted_quantiles(eligible_durations),
    }


def profile_2024(
    raw_dir: Path,
    catalog_path: Path,
    *,
    sample_size: int = 20_000,
    seed: int = 20241104,
    batch_size: int = 65_536,
    config_path: Path = Path("configs/data.yaml"),
) -> dict:
    if type(sample_size) is not int or not 1 <= sample_size <= 20_000:
        raise ValueError("sample_size debe estar entre 1 y 20000 por mes")
    if type(batch_size) is not int or not 1 <= batch_size <= 65_536:
        raise ValueError("batch_size debe estar entre 1 y 65536")
    config = load_config(config_path)
    payload = catalog_path.read_bytes()
    with catalog_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = {int(row["LocationID"]) for row in rows}
    if len(ids) != len(rows) or any(value <= 0 for value in ids):
        raise ValueError("Catalogo invalido")
    started = time.perf_counter()
    files = []
    for month in range(1, 13):
        path = raw_dir / f"2024/{month:02}/yellow_tripdata_2024-{month:02}.parquet"
        files.append(
            profile_file(
                path,
                month=month,
                zone_ids=ids,
                config=config,
                sample_size=sample_size,
                seed=seed,
                batch_size=batch_size,
            )
        )
        print(f"2024-{month:02}: {files[-1]['sample_rows']} filas analizadas", flush=True)
    population = sum(item["source"]["row_count"] for item in files)
    total_sample = sum(item["sample_rows"] for item in files)
    metrics = {
        name: {
            "sample_count": sum(item["metrics"][name]["sample_count"] for item in files),
            "sample_rate": sum(item["metrics"][name]["sample_count"] for item in files)
            / total_sample,
            "estimated_rate": None
            if name == "duplicate_in_sample"
            else sum(
                item["metrics"][name]["estimated_rate"] * item["source"]["row_count"]
                for item in files
            )
            / population,
        }
        for name in files[0]["metrics"]
    }
    return {
        "report_version": 1,
        "status": "PROPOSAL_EVIDENCE_NOT_APPLIED",
        "year": 2024,
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "seed": seed,
        "sample_per_month": sample_size,
        "batch_size": batch_size,
        "sampling": "stratified_srs_without_replacement_proportional_row_groups",
        "temporal_policy": TEMPORAL_POLICY,
        "tzdata_version": version("tzdata"),
        "python": platform.python_version(),
        "pyarrow": pa.__version__,
        "catalog_sha256": hashlib.sha256(payload).hexdigest(),
        "catalog_rows": len(rows),
        "sample_rows": total_sample,
        "population_footer_rows": population,
        "decoded_rows": sum(item["decoded_rows"] for item in files),
        "metrics": metrics,
        "files": files,
        "resources": {
            **windows_resources(),
            "arrow_allocated_at_finish_bytes": pa.total_allocated_bytes(),
            "arrow_pool_peak_bytes": pa.default_memory_pool().max_memory(),
            "elapsed_seconds": time.perf_counter() - started,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/d04_profile_2024.json"))
    parser.add_argument("--sample-per-month", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20241104)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.raw_dir.resolve()):
        parser.error("La salida debe estar fuera de raw")
    result = profile_2024(
        args.raw_dir, args.catalog, sample_size=args.sample_per_month, seed=args.seed
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    args.output.with_suffix(".md").write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps({"sample_rows": result["sample_rows"], "resources": result["resources"]}))


def render_markdown(result: dict) -> str:
    lines = [
        "# D-04 — Perfilado aleatorio acotado de 2024",
        "",
        f"Estado: {result['status']}. Ejecución UTC: {result['recorded_at_utc']}.",
        "",
        f"Muestra: {result['sample_rows']:,} filas; 20.000 por mes de 2024. "
        f"Población declarada en footers: {result['population_footer_rows']:,}. "
        f"Semilla: {result['seed']}. Bloques de hasta {result['batch_size']:,} filas.",
        "",
        "## Diseño y límites",
        "",
        "Muestreo aleatorio sin reemplazo dentro de cada row group. Las cuotas mensuales se "
        "reparten proporcionalmente al número de filas del grupo con redondeo por restos mayores. "
        "Cada fila seleccionada tiene peso N_grupo/n_muestra_grupo. Las tasas estimadas anuales "
        "ponderan los grupos y meses por sus filas de footer; no son la media simple de meses.",
        "",
        f"Para extraer la muestra se decodificaron {result['decoded_rows']:,} filas por las "
        "restricciones de lectura de Parquet. El límite aplica a filas analizadas y memoria; "
        "no se presenta como lectura física de solo 240.000 filas. "
        "No se abrieron archivos de 2025.",
        "",
        "Los índices seleccionados, hashes de muestra/archivos, frecuencias y métricas completas "
        "están en d04_profile_2024.json, excluido de Git. Se comprobaron los hashes antes/después. "
        "Las tasas de filas inválidas son estimaciones, "
        "no conteos completos ni decisiones sobre lotes.",
        "",
        "Las repeticiones exactas se miden solo entre filas muestreadas: cero coincidencias no "
        "permite estimar la tasa de duplicados del lote. "
        "Tampoco cero nulos/códigos nuevos demuestra "
        "ausencia anual. No se publican datasets aprobados ni se modifica raw.",
        "",
        f"Tiempo: {result['temporal_policy']}; tzdata {result['tzdata_version']}. "
        "Se apartan horas locales ambiguas/inexistentes y se compara duración en UTC.",
        "",
        f"Catálogo candidato: {result['catalog_rows']} registros, SHA-256 "
        f"`{result['catalog_sha256']}`. Su uso operativo sigue pendiente de aprobación.",
        "",
        "## Métricas anuales de muestra",
        "",
        "| Regla | Conteo observado en muestra | Tasa estimada ponderada (%) |",
        "|---|---:|---:|",
    ]
    for name in METRICS:
        metric = result["metrics"][name]
        rate = metric["estimated_rate"]
        formatted = f"{100 * rate:.5f}" if rate is not None else "No estimable con esta muestra"
        lines.append(f"| {name} | {metric['sample_count']} | {formatted} |")
    lines += [
        "",
        "## Comparación de población elegible candidata",
        "",
        "Unión sin doble conteo: fechas interpretables, duración positiva, pickup en el mes "
        "nominal y origen perteneciente al catálogo. Destino y categorías no predictoras "
        "solo se miden. Pasajeros ausentes se conservan; valores fuera del rango candidato "
        "podrían normalizarse a ausencia, sujeto a aprobación.",
        "",
        "| Alternativa | Exclusiones observadas | Tasa anual estimada (%) |",
        "|---|---:|---:|",
    ]
    for name in SCENARIOS:
        metric = result["metrics"][name]
        lines.append(
            f"| {name} | {metric['sample_count']} | {100 * metric['estimated_rate']:.5f} |"
        )
    lines += [
        "",
        "## Comparación mensual",
        "",
        "Los conteos de footer son exactos para estos archivos; las tasas son estimaciones "
        "de 20.000 filas por mes. Ninguna fila fue descartada del archivo original.",
        "",
        "| Mes | Filas footer | Sin máximo (%) | Máximo 120 (%) | Máximo 180 (%) | "
        "Máximo 240 (%) | Pasajeros nulos (%) | p99 duración (min) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for info in result["files"]:
        metrics = info["metrics"]
        rates = " | ".join(
            f"{100 * metrics[name]['estimated_rate']:.4f}"
            for name in ("no_duration_cap", "cap_120", "cap_180", "cap_240", "passenger_null")
        )
        lines.append(
            f"| 2024-{info['month']:02} | {info['source']['row_count']:,} | {rates} | "
            f"{info['eligible_positive_duration_minutes']['p99']:.2f} |"
        )
    lines += ["", "## Recursos y reproducción", "", "| Medida | Observación |", "|---|---:|"]
    lines.extend(f"| {key} | {value} |" for key, value in result["resources"].items())
    lines += [
        "",
        "El tiempo incluye muestreo y hashes; RSS y memoria Arrow son mediciones "
        "distintas y no se suman. No es presupuesto de entrenamiento/Docker ni benchmark.",
        "",
        "```powershell",
        ".\\.venv\\Scripts\\python.exe -m scripts.profile_d04 "
        "--catalog docs/reference/taxi_zone_lookup_candidate.csv "
        "--output reports/d04_profile_2024.json",
        "```",
        "",
        "Se repitió la extracción con la misma semilla: índices, hashes, métricas comunes "
        "y cuantiles idénticos. La segunda ejecución añadió desglose de categorías nulas "
        "frente a códigos no nulos fuera del diccionario. Recursos/fecha varían entre ejecuciones.",
        "",
        "[Propuesta pendiente de aprobación](../docs/d04-quality-proposal.md).",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
