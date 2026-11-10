"""Ventanas sinteticas reproducibles, sin datos/modelos reales ni entrenamiento."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from src.features.schema import FEATURE_COLUMNS
from src.monitoring.drift import build_reference
from src.monitoring.protocol import POLICY, RESOURCES, MonitorGuard
from src.validation.run import _sha256
from src.validation.schema import fingerprint


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def prepared(root, *, count=2000, altered_august=True):
    source = root / "split"
    profile = {"schema": {"fixture": True}, "quality": {"policy_version": "synthetic"}}
    quality = {
        "status": "TEST_ONLY",
        "scope": "quality_schema_only",
        "new_thresholds_authorized": False,
        "training_authorized": False,
        "reference_year": 2024,
        "policy_identity_sha256": fingerprint(profile),
        "reference_reports": [],
        "current_reports": [],
    }
    entries, groups = [], {"train": [], "monitoring_replay": []}
    for year, month in [(2024, m) for m in range(1, 13)] + [(2025, 7), (2025, 8)]:
        identity = hashlib.md5(f"synthetic-{year}-{month}".encode()).hexdigest()
        start = datetime(year, month, 1, 13, tzinfo=UTC)
        start += timedelta(days=(7 - start.weekday()) % 7)
        pickups = [start + timedelta(seconds=i) for i in range(count)]
        labels = 10 + np.arange(count) % 3
        origins = np.where(np.arange(count) % 2, 1, 2)
        if year == 2025 and month == 8 and altered_august:
            origins = np.full(count, 99)
        values = [
            origins,
            np.asarray([p.astimezone(ZoneInfo("America/New_York")).hour for p in pickups]),
            np.full(count, 0),
            np.full(count, month),
            np.full(count, 1),
            np.full(count, 0),
        ]
        features = pa.table(
            {
                name: pa.array(v, type=pa.int64())
                for name, v in zip(FEATURE_COLUMNS, values, strict=True)
            }
        )
        context = pa.table(
            {
                "validated_row_index": pa.array(np.arange(count), type=pa.int64()),
                "pickup_datetime_utc": pa.array(pickups, type=pa.timestamp("us", "UTC")),
                "label_event_datetime_utc": pa.array(
                    [
                        instant + timedelta(minutes=int(y))
                        for instant, y in zip(pickups, labels, strict=True)
                    ],
                    type=pa.timestamp("us", "UTC"),
                ),
                "source_feature_id": pa.array([identity] * count),
            }
        )
        target = pa.table({"trip_duration_minutes": pa.array(labels, type=pa.float64())})
        validated = root / "validated" / str(year) / str(month)
        validated.mkdir(parents=True)
        pq.write_table(pa.table({"DOLocationID": np.full(count, 10)}), validated / "data.parquet")
        report = {
            "mode": "TEST_ONLY",
            "fixture_origin": "synthetic",
            "lineage_status": "VERIFIED_CONTENT",
            "year": year,
            "month": month,
            "configuration": profile,
            "input": {
                "manifest": {
                    "sha256": "f" * 64,
                    "year": year,
                    "month": month,
                    "row_count": count,
                    "schema": [{"name": "pickup", "type": "timestamp[us]", "nullable": True}],
                }
            },
            "scan_scope": "FULL_PARQUET",
            "eligibility_complete": True,
            "rows_scanned": count,
            "status": "PASS",
            "data_quality_approved": True,
            "excluded_rows": 0,
            "output": {"sha256": _sha256(validated / "data.parquet")},
            "checks": [
                {"rule": "rows.invalid", "status": "PASS", "observed": {"count": 0, "rate": 0}}
            ],
        }
        marker = validated / "validation.json"
        write_json(marker, report)
        quality["reference_reports" if year == 2024 else "current_reports"].append(
            {
                "path": str(marker.relative_to(root)),
                "sha256": _sha256(marker),
                "raw_sha256": "f" * 64,
                "year": year,
                "month": month,
            }
        )
        entries.append(
            {
                "year": year,
                "month": month,
                "validated_directory": str(validated),
                "verified": {
                    "feature": {
                        "feature_id": identity,
                        "validation_manifest_sha256": _sha256(marker),
                    }
                },
            }
        )
        groups["train" if year == 2024 else "monitoring_replay"].append((features, target, context))
    manifest = {
        "status": "SPLIT_TEST_ONLY",
        "publication_complete": True,
        "configuration": {
            "partitions": {"monitoring_replay": {"start": "2025-07-01", "end": "2026-01-01"}}
        },
        "inputs": entries,
        "partitions": {},
    }
    for partition, tables in groups.items():
        folder = source / partition
        folder.mkdir(parents=True)
        artifacts = {}
        for i, name in enumerate(("features", "target", "context")):
            table = pa.concat_tables([row[i] for row in tables]).replace_schema_metadata(
                {b"split_scope": b"TEST_ONLY", b"fixture_origin": b"synthetic"}
            )
            path = folder / f"{name}.parquet"
            pq.write_table(table, path, row_group_size=1001)
            artifacts[name] = {
                "file_size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "row_count": table.num_rows,
            }
        manifest["partitions"][partition] = {"rows": table.num_rows, "artifacts": artifacts}
    write_json(source / "split_manifest.json", manifest)
    write_json(root / "quality.json", quality)
    evaluation = {
        "route_catalog": {
            "selection_scope": "validation_frequency_only",
            "routes": [{"code": 1010}],
        },
        "metrics": {"all": {"mae_minutes": 5.0}},
    }
    write_json(root / "evaluation.json", evaluation)
    config = {
        "status": "TEST_ONLY",
        "fixture_origin": "synthetic",
        "protocol": "monthly-full-replay-v1",
        "policy": deepcopy(POLICY),
        "resources": deepcopy(RESOURCES),
        "feature_columns": list(FEATURE_COLUMNS),
        "split": {
            "path": "split/split_manifest.json",
            "sha256": _sha256(source / "split_manifest.json"),
        },
        "quality_config": {"path": "quality.json", "sha256": _sha256(root / "quality.json")},
        "validation_evaluation": {
            "path": "evaluation.json",
            "sha256": _sha256(root / "evaluation.json"),
        },
    }
    reference = root / "reference.json"
    build_reference(config, root, MonitorGuard(root, test_only=True), reference)
    config["reference"] = {"path": "reference.json", "sha256": _sha256(reference)}
    config_path = root / "monitoring.json"
    write_json(config_path, config)
    return config_path, config, source, manifest


def predictor(values):
    assert values.shape[1] == len(FEATURE_COLUMNS)
    return np.full(len(values), 10.0), 0


IDENTITY = {"name": "synthetic-champion", "version": "4", "model_sha256": "b" * 64}


def renderer(drift, output):
    write_json(output / "evidently.json", {"fixture": True, "status": drift["status"]})
    (output / "evidently.html").write_text("<p>Synthetic renderer fixture</p>", encoding="utf-8")
