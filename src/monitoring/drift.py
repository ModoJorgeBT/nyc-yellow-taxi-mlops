"""PSI mensual sobre conteos exhaustivos; referencia solo train, sin targets."""

from collections import Counter

import numpy as np

from src.features.schema import FEATURE_COLUMNS
from src.monitoring.protocol import (
    POLICY,
    batches,
    envelope,
    exclusive_json,
    read_json,
    source_manifest,
    verify_tables,
)
from src.validation.run import _sha256
from src.validation.schema import fingerprint

UNKNOWN = "__NEW__"
DOMAINS = {
    "pickup_hour": list(range(24)),
    "pickup_weekday": list(range(7)),
    "pickup_month": list(range(1, 13)),
    "passenger_count": list(range(7)),
    "passenger_count_missing": [0, 1],
}


def feature_array(batch):
    if tuple(batch.schema.names) != FEATURE_COLUMNS or any(c.null_count for c in batch.columns):
        raise ValueError("Features nulas o fuera de contrato")
    result = np.column_stack([c.to_numpy() for c in batch.columns])
    if not np.isfinite(result).all() or np.any(result != np.floor(result)):
        raise ValueError("Features discretas no enteras/finitas")
    return result.astype(np.int64)


def counts_by_month(directory, manifest, partition, guard):
    counts = {m: {name: Counter() for name in FEATURE_COLUMNS} for m in range(1, 13)}
    rows = 0
    for (batch,) in batches(directory, partition, ("features",), guard):
        values = feature_array(batch)
        months = values[:, 3]
        if np.any((months < 1) | (months > 12)):
            raise ValueError("Mes de feature fuera de calendario")
        rows += len(values)
        for month in np.unique(months):
            selection = values[months == month]
            for i, name in enumerate(FEATURE_COLUMNS):
                keys, numbers = np.unique(selection[:, i], return_counts=True)
                counts[int(month)][name].update(
                    {str(int(k)): int(n) for k, n in zip(keys, numbers, strict=True)}
                )
    if rows != manifest["partitions"][partition]["rows"]:
        raise ValueError("Escaneo de features no exhaustivo")
    return {str(month): dict(features) for month, features in counts.items()}, rows


def build_reference(config, root, guard, path):
    directory, manifest = source_manifest(config, root)
    test_only = config["status"] == "TEST_ONLY"
    verify_tables(directory, manifest, "train", ("features",), test_only=test_only)
    counts, rows = counts_by_month(directory, manifest, "train", guard)
    origins = sorted({int(k) for month in counts.values() for k in month["pickup_location_id"]})
    domains = {name: [str(v) for v in values] + [UNKNOWN] for name, values in DOMAINS.items()}
    domains["pickup_location_id"] = [str(v) for v in origins] + [UNKNOWN]
    payload = {**envelope(config), "counts": counts, "domains": domains, "rows": rows}
    verify_tables(directory, manifest, "train", ("features",), test_only=test_only)
    source_manifest(config, root)
    result = {"reference": payload, "reference_sha256": fingerprint(payload)}
    exclusive_json(path, result)
    return result


def load_reference(path, config):
    if _sha256(path) != config.get("reference", {}).get("sha256"):
        raise ValueError("Referencia diferente de la referencia sellada")
    value = read_json(path)
    reference = value["reference"]
    if (
        fingerprint(reference) != value["reference_sha256"]
        or any(reference.get(k) != v for k, v in envelope(config).items())
        or set(reference["counts"]) != {str(m) for m in range(1, 13)}
        or set(reference["domains"]) != set(FEATURE_COLUMNS)
    ):
        raise ValueError("Referencia no corresponde al train/configuracion congelados")
    return value


def aligned_counts(counts, domain):
    if len(set(domain)) != len(domain) or domain[-1] != UNKNOWN:
        raise ValueError("Dominio congelado invalido")
    result = np.zeros(len(domain), dtype=np.float64)
    positions = {key: i for i, key in enumerate(domain)}
    for key, count in counts.items():
        if type(count) is not int or count < 0:
            raise ValueError("Conteos invalidos")
        result[positions.get(str(key), len(domain) - 1)] += count
    return result


def psi(reference, current, *, alpha=0.5):
    left, right = np.asarray(reference, dtype=np.float64), np.asarray(current, dtype=np.float64)
    if (
        left.ndim != 1
        or left.shape != right.shape
        or not len(left)
        or not np.isfinite(left).all()
        or not np.isfinite(right).all()
        or np.any(left < 0)
        or np.any(right < 0)
        or not np.isfinite(alpha)
        or alpha <= 0
    ):
        raise ValueError("Distribuciones PSI invalidas")
    p = (left + alpha) / (left.sum() + alpha * len(left))
    q = (right + alpha) / (right.sum() + alpha * len(right))
    return float(np.sum((q - p) * np.log(q / p)))


def compare_counts(reference, current_counts, month):
    payload = reference["reference"]
    previous = payload["counts"][str(month)]
    result, bins = {}, []
    for name in FEATURE_COLUMNS:
        domain = payload["domains"][name]
        left, right = (
            aligned_counts(previous[name], domain),
            aligned_counts(current_counts[name], domain),
        )
        enough = min(left.sum(), right.sum()) >= POLICY["minimum_rows"]
        score = psi(left, right, alpha=POLICY["smoothing_alpha"]) if enough else None
        result[name] = {
            "status": "NOT_AVAILABLE" if not enough else "ALERT" if score > 0.2 else "OBSERVED",
            "psi": score,
            "threshold": POLICY["psi_threshold"],
            "reference_rows": int(left.sum()),
            "current_rows": int(right.sum()),
            "new_category_rows": int(right[-1]),
        }
        bins.extend(
            {
                "feature": name,
                "category": category,
                "reference_count": int(a),
                "current_count": int(b),
            }
            for category, a, b in zip(domain, left, right, strict=True)
        )
    statuses = {row["status"] for row in result.values()}
    status = (
        "ALERT"
        if "ALERT" in statuses
        else "NOT_AVAILABLE"
        if "NOT_AVAILABLE" in statuses
        else "OBSERVED"
    )
    return {
        "status": status,
        "features": result,
        "bins": bins,
        "reference_sha256": reference["reference_sha256"],
        "row_unit": "AGGREGATED_CATEGORY_BIN_NOT_TRIP",
        "sampling": "NONE_ALL_ELIGIBLE",
        "reference_year": 2024,
        "year": 2025,
        "month": month,
    }
