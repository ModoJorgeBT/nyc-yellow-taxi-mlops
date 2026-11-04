"""D-04 aprobado: calidad real UTC, normalizaciones y evidencia por lote completo."""

import json
import logging
import math
import re
import sqlite3
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

import pyarrow as pa

from src.features.schema import FeatureError
from src.features.target import TEMPORAL_POLICY, localize_historical
from src.validation.rules import _canonical, _columns
from src.validation.schema import check, fingerprint, validate_schema

LOGGER = logging.getLogger(__name__)
FAIL_METRICS = {
    "timestamp_null_or_uninterpretable",
    "timestamp_ambiguous_or_nonexistent",
    "duration_nonpositive",
    "duration_above_180",
    "pickup_outside_month",
    "origin_null_or_outside_catalog",
    "union_invalid_rows",
}
WARN_METRICS = {
    "union_invalid_rows",
    "passenger_null_after_normalization",
    "passenger_normalized",
    "origin_special_264_or_265",
    "duplicate_exact",
    "destination_null_or_outside_catalog",
    "optional_categories_null_or_outside_dictionary",
}


def validate_policy(policy: dict) -> None:
    if policy.get("status") != "APPROVED_REAL" or not policy.get("policy_version"):
        raise ValueError("Falta politica real aprobada")
    if (
        not isinstance(policy.get("approval"), dict)
        or policy["approval"].get("user_approved") is not True
    ):
        raise ValueError("Falta registro explicito de aprobacion")
    if policy.get("temporal_policy") != TEMPORAL_POLICY or policy.get("tzdata_version") != version(
        "tzdata"
    ):
        raise ValueError("Convencion temporal/tzdata no coincide con la politica aprobada")
    if type(policy.get("duration_max_minutes")) is not int or policy["duration_max_minutes"] != 180:
        raise ValueError("Este perfil requiere el maximo aprobado de 180 minutos")
    if policy.get("passenger_range") != [0, 6] or any(
        type(n) is not int for n in policy["passenger_range"]
    ):
        raise ValueError("Rango de pasajeros distinto del perfil aprobado")
    catalog = policy.get("zone_catalog", {})
    ids = catalog.get("ids")
    if (
        not isinstance(ids, list)
        or not ids
        or any(type(n) is not int or n <= 0 for n in ids)
        or len(set(ids)) != len(ids)
        or fingerprint(ids) != catalog.get("ids_sha256")
        or not catalog.get("version")
        or not re.fullmatch(r"[a-f0-9]{64}", catalog.get("sha256", ""))
    ):
        raise ValueError("Catalogo real incompleto o divergente")
    for key, expected in (("fail_rates", FAIL_METRICS), ("warn_rates", WARN_METRICS)):
        limits = policy.get(key)
        if not isinstance(limits, dict) or set(limits) != expected:
            raise ValueError(f"Reglas incompletas: {key}")
        for value in limits.values():
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"Umbral invalido: {key}")
    if policy["warn_rates"]["union_invalid_rows"] > policy["fail_rates"]["union_invalid_rows"]:
        raise ValueError("WARN no puede superar FAIL")
    volume = policy.get("volume", {})
    if any(
        type(volume.get(k)) is not int or volume[k] < 1 for k in ("min_rows", "min_eligible_rows")
    ):
        raise ValueError("Minimos de volumen invalidos")
    if set(volume.get("reference_2024", {})) != {f"{m:02}" for m in range(1, 13)} or any(
        type(n) is not int or n < 1 for n in volume["reference_2024"].values()
    ):
        raise ValueError("Referencia mensual incompleta")
    ratio = volume.get("warn_ratio")
    if (
        not isinstance(ratio, list)
        or len(ratio) != 2
        or any(type(n) not in (int, float) or not math.isfinite(n) for n in ratio)
        or not 0 < ratio[0] < ratio[1]
    ):
        raise ValueError("Banda de volumen invalida")
    categories = policy.get("category_values")
    if (
        not isinstance(categories, dict)
        or set(categories) != {"VendorID", "RatecodeID", "payment_type", "store_and_fwd_flag"}
        or any(not isinstance(values, list) or not values for values in categories.values())
    ):
        raise ValueError("Categorias informativas incompletas")
    if not isinstance(policy.get("local_authorizations"), list):
        raise ValueError("Autorizaciones locales ausentes")
    for entry in policy["local_authorizations"]:
        if (
            not isinstance(entry, dict)
            or type(entry.get("year")) is not int
            or type(entry.get("month")) is not int
            or not 1 <= entry["month"] <= 12
            or not re.fullmatch(r"[a-f0-9]{64}", entry.get("sha256", ""))
            or entry.get("academic_use_approved") is not True
        ):
            raise ValueError("Autorizacion local malformada")


def authorize_source(manifest: dict, policy: dict) -> dict:
    validate_policy(policy)
    if manifest["origin"] == "download":
        return {"status": "RECORDED_DOWNLOAD", "provenance_status": manifest["provenance_status"]}
    for entry in policy["local_authorizations"]:
        if (
            entry.get("year") == manifest["year"]
            and entry.get("month") == manifest["month"]
            and entry.get("sha256") == manifest["sha256"]
            and entry.get("academic_use_approved") is True
        ):
            return {
                "status": "APPROVED_LOCAL_ACADEMIC",
                "authorization": entry,
                "provenance_status": "UNVERIFIED_LOCAL",
            }
    raise ValueError("Archivo LOCAL_UNVERIFIED sin autorizacion academica para ese mes y hash")


@lru_cache(maxsize=8192)
def _local_us(value: int | None):
    if value is None:
        return None, "timestamp_null_or_uninterpretable"
    try:
        wall = datetime(1970, 1, 1) + timedelta(microseconds=value)
        return localize_historical(wall), None
    except FeatureError as error:
        reason = (
            "timestamp_ambiguous_or_nonexistent"
            if error.reason in ("ambiguous_local_time", "nonexistent_local_time")
            else "timestamp_null_or_uninterpretable"
        )
        return None, reason
    except OverflowError, ValueError:
        return None, "timestamp_null_or_uninterpretable"


def evaluate_real(
    schema, batches, *, year, month, config, scratch_dir: Path, on_batch=None
) -> dict:
    policy = config["quality"]
    validate_policy(policy)
    structural = validate_schema(schema, config)
    checks = list(structural["checks"])
    checks.append(
        check(
            "policy.ready",
            "PASS",
            policy["policy_version"],
            "APPROVED_REAL",
            {"approval": policy["approval"], "config_sha256": fingerprint(config)},
        )
    )
    counts, examples, normalized_examples = Counter(), {}, []
    total = normalized_eligible = index_peak = 0
    complete = structural["status"] != "FAIL"
    epoch = datetime(1970, 1, 1)
    start = (datetime(year, month, 1) - epoch).days * 86_400_000_000
    # La frontera por mes se evalua en calendario local naive; no en calendario UTC.
    import calendar

    end = start + calendar.monthrange(year, month)[1] * 86_400_000_000
    ids = set(policy["zone_catalog"]["ids"])
    categories = {key: set(values) for key, values in policy["category_values"].items()}
    started = time.perf_counter()
    if complete:
        scratch_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="dq-real-", dir=scratch_dir) as owned:
            index_path = Path(owned) / "exact-rows.sqlite"
            connection = sqlite3.connect(index_path)
            try:
                connection.execute("PRAGMA cache_size=-16384")
                connection.execute("CREATE TABLE seen (row_key BLOB PRIMARY KEY) WITHOUT ROWID")
                cursor = connection.cursor()
                for batch in batches:
                    if not batch.schema.equals(schema, check_metadata=True):
                        complete = False
                        checks.append(
                            check(
                                "scan.schema_consistency",
                                "FAIL",
                                str(batch.schema),
                                str(schema),
                                total,
                            )
                        )
                        break
                    columns = _columns(batch)
                    ordered = list(columns.values())
                    passenger_values = columns.get("passenger_count")
                    normalized = passenger_values.copy() if passenger_values is not None else None
                    mask = []
                    for index in range(batch.num_rows):
                        flags = set()
                        pickup = columns["tpep_pickup_datetime"][index]
                        dropoff = columns["tpep_dropoff_datetime"][index]
                        begin, begin_error = _local_us(pickup)
                        finish, finish_error = _local_us(dropoff)
                        flags.update(error for error in (begin_error, finish_error) if error)
                        if begin is not None and finish is not None:
                            minutes = (
                                finish.astimezone(UTC) - begin.astimezone(UTC)
                            ).total_seconds() / 60
                            if minutes <= 0:
                                flags.add("duration_nonpositive")
                            if minutes > policy["duration_max_minutes"]:
                                flags.add("duration_above_180")
                        if pickup is not None and not start <= pickup < end:
                            flags.add("pickup_outside_month")
                        origin, destination = (
                            columns["PULocationID"][index],
                            columns["DOLocationID"][index],
                        )
                        if origin not in ids:
                            flags.add("origin_null_or_outside_catalog")
                        elif origin in (264, 265):
                            flags.add("origin_special_264_or_265")
                        if destination not in ids:
                            flags.add("destination_null_or_outside_catalog")
                        passengers = (
                            passenger_values[index] if passenger_values is not None else None
                        )
                        changed = passengers is not None and not 0 <= passengers <= 6
                        if changed:
                            flags.add("passenger_normalized")
                            normalized[index] = None
                            if len(normalized_examples) < 10:
                                normalized_examples.append(
                                    {
                                        "raw_row_index": total,
                                        "original": passengers,
                                        "replacement": None,
                                    }
                                )
                        if passengers is None or changed:
                            flags.add("passenger_null_after_normalization")
                        if any(
                            name in columns and columns[name][index] not in allowed
                            for name, allowed in categories.items()
                        ):
                            flags.add("optional_categories_null_or_outside_dictionary")
                        # Clave exacta original: la normalizacion nunca crea duplicados ficticios.
                        key = json.dumps(
                            [_canonical(values[index]) for values in ordered],
                            separators=(",", ":"),
                            ensure_ascii=True,
                        ).encode()
                        cursor.execute("INSERT OR IGNORE INTO seen VALUES (?)", (key,))
                        if cursor.rowcount == 0:
                            flags.add("duplicate_exact")
                        invalid = bool(flags & (FAIL_METRICS - {"union_invalid_rows"}))
                        if invalid:
                            flags.add("union_invalid_rows")
                        mask.append(not invalid)
                        normalized_eligible += changed and not invalid
                        for name in flags:
                            counts[name] += 1
                            if len(examples.setdefault(name, [])) < 5:
                                examples[name].append(total)
                        total += 1
                    connection.commit()
                    index_peak = max(index_peak, index_path.stat().st_size)
                    if on_batch is not None:
                        outgoing = batch
                        if normalized is not None:
                            position = batch.schema.get_field_index("passenger_count")
                            field = batch.schema.field(position).with_nullable(True)
                            outgoing = batch.set_column(
                                position, field, pa.array(normalized, type=field.type)
                            )
                        on_batch(outgoing, mask)
                    LOGGER.info(
                        "D-04: %d filas; %d excluidas; %d normalizadas",
                        total,
                        counts["union_invalid_rows"],
                        counts["passenger_normalized"],
                    )
            finally:
                connection.close()
    for name in sorted(FAIL_METRICS | WARN_METRICS):
        rate = counts[name] / total if total and complete else None
        failure = policy["fail_rates"].get(name)
        warning = policy["warn_rates"].get(name)
        status = (
            "WARN"
            if rate is None
            else (
                "FAIL"
                if failure is not None and rate > failure
                else "WARN"
                if warning is not None and rate > warning
                else "WARN"
                if failure is not None and warning is None and counts[name]
                else "PASS"
            )
        )
        checks.append(
            check(
                f"rows.{name}",
                status,
                {"count": counts[name] if complete else None, "rate": rate},
                {"fail_above": failure, "warn_above": warning, "denominator": "all_raw_rows"},
                {"first_raw_row_indexes": examples.get(name, []), "index_base": 0},
            )
        )
    eligible = total - counts["union_invalid_rows"] if complete else None
    checks.append(check("scan.complete", "PASS" if complete else "FAIL", complete, True, total))
    for name, value in (("min_rows", total), ("min_eligible_rows", eligible)):
        limit = policy["volume"][name]
        checks.append(
            check(
                f"volume.{name}",
                "FAIL" if value is None or value < limit else "PASS",
                value,
                {"minimum": limit},
                "Monthly lot, not training sample size",
            )
        )
    reference = policy["volume"]["reference_2024"][f"{month:02}"]
    ratio = total / reference
    band = policy["volume"]["warn_ratio"]
    checks.append(
        check(
            "volume.reference_ratio",
            "PASS" if band[0] <= ratio <= band[1] else "WARN",
            ratio,
            band,
            {"reference_2024_rows": reference},
        )
    )
    statuses = {entry["status"] for entry in checks}
    status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
    return {
        "report_version": 2,
        "year": year,
        "month": month,
        "schema_version": config["schema_version"],
        "schema_fingerprint": structural["schema_fingerprint"],
        "config_sha256": fingerprint(config),
        "policy_version": policy["policy_version"],
        "temporal_policy": TEMPORAL_POLICY,
        "tzdata_version": version("tzdata"),
        "zone_catalog_version": policy["zone_catalog"]["version"],
        "status": status,
        "quality_passed": status != "FAIL",
        "data_quality_approved": False,
        "approved_for_training": False,
        "lineage_status": "NOT_CHECKED_T10",
        "rows_scanned": total,
        "eligible_rows": eligible,
        "excluded_rows": counts["union_invalid_rows"] if complete else None,
        "eligibility_complete": complete,
        "checks": checks,
        "normalizations": {
            "passenger_count": {
                "count": counts["passenger_normalized"],
                "in_eligible_rows": normalized_eligible,
                "examples": normalized_examples,
            }
        },
        "resources": {
            "scan_elapsed_seconds": time.perf_counter() - started,
            "duplicate_index_peak_bytes": index_peak,
            "sqlite_cache_kib": 16384,
        },
        "duplicate_semantics": "all original columns, repetitions beyond first; no deletion",
    }
