"""Motor de calidad historica. No publica datos ni aprueba entrenamiento (T10)."""

import calendar
import json
import math
import sqlite3
import tempfile
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow as pa

from src.ingestion.manifest import source_url
from src.validation.schema import check, fingerprint, validate_schema

METRICS = (
    "timestamp_null",
    "duration_nonpositive",
    "duration_exceeds_max",
    "pickup_outside_month",
    "zone_null",
    "zone_unknown",
    "duplicate",
    "passenger_null",
    "passenger_negative",
    "passenger_out_of_range",
    "category_invalid",
    "invalid_rows",
)


def _policy_issues(policy: dict) -> list[str]:
    """Los valores pendientes bloquean; los valores mal formados son errores."""
    issues = []
    if not isinstance(policy.get("policy_version"), str) or not policy["policy_version"]:
        raise ValueError("policy_version ausente")
    status = policy.get("status")
    if status not in ("PENDIENTE", "TEST_ONLY"):
        raise ValueError("No hay perfil real aprobado; status debe ser PENDIENTE o TEST_ONLY")
    if status == "PENDIENTE":
        issues.append("status")
    validators = {
        "timestamp_policy": lambda v: v == "naive_wall_clock",
        "min_rows": lambda v: type(v) is int and v >= 1,
        "min_eligible_rows": lambda v: type(v) is int and v >= 1,
        "duration_max_minutes": lambda v: (
            v == "disabled" or (type(v) in (int, float) and math.isfinite(v) and v > 0)
        ),
        "duplicate_action": lambda v: v == "measure_only",
        "passenger_range": lambda v: (
            isinstance(v, list)
            and len(v) == 2
            and all(type(n) is int for n in v)
            and 0 <= v[0] <= v[1]
        ),
        "passenger_action": lambda v: v in ("measure_only", "exclude_invalid"),
        "category_action": lambda v: v in ("measure_only", "exclude_invalid"),
        "category_values": lambda v: (
            isinstance(v, dict)
            and all(
                isinstance(k, str)
                and isinstance(values, list)
                and bool(values)
                and all(type(item) in (str, int) for item in values)
                for k, values in v.items()
            )
        ),
        "zone_catalog": lambda v: (
            isinstance(v, dict)
            and isinstance(v.get("version"), str)
            and bool(v["version"])
            and isinstance(v.get("ids"), list)
            and bool(v["ids"])
            and all(type(n) is int and n > 0 for n in v["ids"])
        ),
    }
    for name, valid in validators.items():
        value = policy.get(name)
        if value is None:
            issues.append(name)
        elif not valid(value):
            raise ValueError(f"Politica invalida: {name}")
    rates = policy.get("max_rates")
    if not isinstance(rates, dict) or set(rates) != set(METRICS):
        raise ValueError("max_rates debe declarar todas las metricas, sin claves desconocidas")
    for name, value in rates.items():
        if value is None:
            issues.append(f"max_rates.{name}")
        elif type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Tolerancia invalida: {name}")
    return issues


def _canonical(value: object) -> object:
    """Igualdad exacta tipada; NaN se agrupa con NaN, -0.0 con 0.0."""
    if value is None:
        return ["null"]
    if isinstance(value, float):
        return ["float", "nan" if math.isnan(value) else (0.0 if value == 0 else value).hex()]
    if isinstance(value, (str, int, bool)):
        return [type(value).__name__, value]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if isinstance(value, (datetime, date, time)):
        return [type(value).__name__, value.isoformat()]
    if isinstance(value, Decimal):
        return ["decimal", str(value)]
    if isinstance(value, timedelta):
        return ["timedelta", value.days, value.seconds, value.microseconds]
    if isinstance(value, (list, tuple)):
        return [type(value).__name__, [_canonical(item) for item in value]]
    if isinstance(value, dict):
        return ["dict", [[key, _canonical(value[key])] for key in sorted(value)]]
    raise ValueError(f"Tipo adicional sin comparacion exacta soportada: {type(value).__name__}")


def _columns(batch: pa.RecordBatch) -> dict[str, list]:
    # Evita overflow de datetime Python y perdida de precision en timestamps extremos.
    return {
        field.name: (
            batch.column(index).view(pa.int64()).to_pylist()
            if pa.types.is_timestamp(field.type)
            else batch.column(index).to_pylist()
        )
        for index, field in enumerate(batch.schema)
    }


def evaluate_batches(
    schema: pa.Schema,
    batches: Iterable[pa.RecordBatch],
    *,
    year: int,
    month: int,
    config: dict,
    scratch_dir: Path,
    on_batch: Callable[[pa.RecordBatch, list[bool]], None] | None = None,
) -> dict:
    """Consume un lote completo por bloques; devuelve reporte JSON, sin escribir datasets.

    Repeticiones exactas se cuentan mas alla de la primera y entre bloques. Su indice
    vive en SQLite temporal con claves completas (sin colisiones de hash), no en RAM.
    El llamador debe consumir todos los bloques del lote; la integracion Parquet/linaje
    y la persistencia corresponden a T10, no a esta API de evaluacion. on_batch recibe
    elegibilidad provisional por fila; sus salidas deben permanecer en staging hasta
    superar todos los gates y verificar linaje/exhaustividad.
    """
    source_url(year, month)  # Valida el periodo sin acceder a la red.
    if config.get("quality", {}).get("status") == "APPROVED_REAL":
        from src.validation.real import evaluate_real

        return evaluate_real(
            schema,
            batches,
            year=year,
            month=month,
            config=config,
            scratch_dir=scratch_dir,
            on_batch=on_batch,
        )
    month_start_us = (datetime(year, month, 1) - datetime(1970, 1, 1)).days * 86_400_000_000
    month_end_us = month_start_us + calendar.monthrange(year, month)[1] * 86_400_000_000
    structural = validate_schema(schema, config)
    policy = config["quality"]
    pending = _policy_issues(policy)
    checks = list(structural["checks"])
    synthetic = (schema.metadata or {}).get(b"fixture_origin") == b"synthetic"
    policy_ok = not pending and synthetic and policy["status"] == "TEST_ONLY"
    checks.append(
        check(
            "policy.ready",
            "PASS" if policy_ok else "FAIL",
            {"status": policy["status"], "pending": pending, "synthetic": synthetic},
            "TEST_ONLY completo, exclusivamente con fixture sintetica",
            {"policy_version": policy["policy_version"], "config_sha256": fingerprint(config)},
        )
    )
    counts = dict.fromkeys(METRICS, 0)
    examples = {name: [] for name in METRICS}
    catalog = policy.get("zone_catalog")
    zone_ids = set(catalog["ids"]) if catalog else None
    maximum = policy.get("duration_max_minutes")
    max_duration_us = Decimal(str(maximum)) * 60_000_000 if type(maximum) in (int, float) else None
    passenger_range = policy.get("passenger_range")
    categories = policy.get("category_values")
    unevaluated = set()
    if maximum is None:
        unevaluated.add("duration_exceeds_max")
    if zone_ids is None:
        unevaluated.add("zone_unknown")
    if passenger_range is None:
        unevaluated.add("passenger_out_of_range")
    if categories is None:
        unevaluated.add("category_invalid")
    total = 0
    complete = structural["status"] != "FAIL"
    if complete:
        scratch_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="dq-", dir=scratch_dir) as owned:
            connection = sqlite3.connect(Path(owned) / "exact-rows.sqlite")
            try:
                connection.execute("PRAGMA cache_size=-2048")
                connection.execute("CREATE TABLE seen (row_key BLOB PRIMARY KEY) WITHOUT ROWID")
                for batch in batches:
                    if not batch.schema.equals(schema, check_metadata=True):
                        checks.append(
                            check(
                                "scan.schema_consistency",
                                "FAIL",
                                str(batch.schema),
                                str(schema),
                                {"rows_scanned_before": total},
                            )
                        )
                        complete = False
                        break
                    columns = _columns(batch)
                    pickup = columns["tpep_pickup_datetime"]
                    dropoff = columns["tpep_dropoff_datetime"]
                    eligible_mask = []
                    for row_index in range(batch.num_rows):
                        flags = set()
                        start, end = pickup[row_index], dropoff[row_index]
                        if start is None or end is None:
                            flags.add("timestamp_null")
                        else:
                            duration_us = end - start  # Python int: sin wrap de int64.
                            if duration_us <= 0:
                                flags.add("duration_nonpositive")
                            if max_duration_us is not None and duration_us > max_duration_us:
                                flags.add("duration_exceeds_max")
                        if start is not None and not month_start_us <= start < month_end_us:
                            flags.add("pickup_outside_month")
                        for name in ("PULocationID", "DOLocationID"):
                            value = columns[name][row_index]
                            if value is None:
                                flags.add("zone_null")
                            elif zone_ids is not None and value not in zone_ids:
                                flags.add("zone_unknown")
                        passengers = columns.get("passenger_count")
                        passenger = passengers[row_index] if passengers is not None else None
                        if passenger is None:
                            flags.add("passenger_null")
                        else:
                            if passenger < 0:
                                flags.add("passenger_negative")
                            if (
                                passenger_range
                                and not passenger_range[0] <= passenger <= passenger_range[1]
                            ):
                                flags.add("passenger_out_of_range")
                        if categories is not None and any(
                            name in columns and columns[name][row_index] not in allowed
                            for name, allowed in categories.items()
                        ):
                            flags.add("category_invalid")
                        key = json.dumps(
                            [_canonical(values[row_index]) for values in columns.values()],
                            separators=(",", ":"),
                            ensure_ascii=True,
                        ).encode()
                        cursor = connection.execute("INSERT OR IGNORE INTO seen VALUES (?)", (key,))
                        if cursor.rowcount == 0:
                            flags.add("duplicate")
                        invalidating = {
                            "timestamp_null",
                            "duration_nonpositive",
                            "duration_exceeds_max",
                            "pickup_outside_month",
                            "zone_null",
                            "zone_unknown",
                        }
                        if policy.get("passenger_action") == "exclude_invalid":
                            invalidating |= {"passenger_negative", "passenger_out_of_range"}
                        if policy.get("category_action") == "exclude_invalid":
                            invalidating.add("category_invalid")
                        if flags & invalidating:
                            flags.add("invalid_rows")
                        eligible_mask.append("invalid_rows" not in flags)
                        for name in flags:
                            counts[name] += 1
                            if len(examples[name]) < 5:
                                examples[name].append(total)
                        total += 1
                    connection.commit()
                    if on_batch is not None:
                        on_batch(batch, eligible_mask)
            finally:
                connection.close()  # Cerrar antes de borrar scratch en Windows.
    eligible = total - counts["invalid_rows"] if complete else None
    checks.append(
        check(
            "scan.complete",
            "PASS" if complete else "FAIL",
            complete,
            True,
            {"rows_scanned": total, "scope": "caller_supplied_batches"},
        )
    )
    for name in METRICS:
        rate = counts[name] / total if total else None
        limit = policy["max_rates"][name]
        evaluated = complete and name not in unevaluated
        status = (
            "WARN"
            if not evaluated or limit is None or rate is None
            else "FAIL"
            if rate > limit
            else "WARN"
            if counts[name]
            else "PASS"
        )
        checks.append(
            check(
                f"rows.{name}",
                status,
                {"count": counts[name] if evaluated else None, "rate": rate if evaluated else None},
                {"max_rate": limit, "denominator": "all_rows", "comparison": ">"},
                {"evaluated": evaluated, "first_row_indexes": examples[name], "index_base": 0},
            )
        )
    for name, observed in (("min_rows", total), ("min_eligible_rows", eligible)):
        minimum = policy.get(name)
        status = (
            "WARN"
            if minimum is None or observed is None
            else ("FAIL" if observed < minimum else "PASS")
        )
        checks.append(check(f"volume.{name}", status, observed, {"minimum": minimum}, name))
    statuses = {item["status"] for item in checks}
    status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
    return {
        "report_version": 1,
        "year": year,
        "month": month,
        "schema_version": config["schema_version"],
        "schema_fingerprint": structural["schema_fingerprint"],
        "config_sha256": fingerprint(config),
        "policy_version": policy["policy_version"],
        "zone_catalog_version": catalog["version"] if catalog else None,
        "status": status,
        "quality_passed": status != "FAIL" and policy_ok,
        "approved_for_training": False,
        "data_quality_approved": False,
        "lineage_status": "NOT_CHECKED_T10",
        "rows_scanned": total,
        "eligible_rows": eligible,
        "excluded_rows": counts["invalid_rows"] if complete else None,
        "eligibility_complete": complete and not unevaluated,
        "temporal_semantics": "naive_wall_clock; DST real pendiente D-06",
        "duplicate_semantics": "all supplied columns; repetitions beyond first; no deletion",
        "checks": checks,
    }
