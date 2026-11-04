"""T15: ajuste exacto independiente sobre train aprobado; evaluacion pendiente."""

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import tempfile
import time
import uuid
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.features.target import nyc_zone
from src.ingestion.manifest import describe_parquet, publish_file, publish_manifest, utc_now
from src.training.baseline import BASELINE_POLICY, exact_disk_median
from src.training.resources import ResourceGuard, ResourceLimitError
from src.training.split import (
    PARTITIONS,
    SCHEMAS,
    SplitError,
    _catalog,
    _source_rows,
    boundaries,
    preparation_budget,
    quality_rules,
    read_model_config,
    verify_features,
)
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint, load_config

LOGGER = logging.getLogger(__name__)
FIT_ONLY_POLICY = {
    "approval_status": "APPROVED",
    "fit_partition": "train",
    "requires_complete_train_coverage": True,
    "allow_before_complete_t14": True,
    "evaluation_status": "PENDING_VALIDATION",
    "closes_t14_or_t15": False,
    "source_quality_override": False,
}


def train_months(config: dict) -> set[tuple[int, int]]:
    start, end = (t.astimezone(nyc_zone()) for t in boundaries(config, "train"))
    year, month = start.year, start.month
    result = set()
    while (year, month) < (end.year, end.month):
        result.add((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def fit_baseline(
    catalog_path: Path,
    *,
    config_path: Path = Path("configs/model.yaml"),
    data_config_path: Path = Path("configs/data.yaml"),
    output_dir: Path = Path("data/processed/baseline_fits"),
    report_dir: Path = Path("reports/baseline_fits"),
    scratch_dir: Path = Path(".cache/baseline"),
    batch_size: int = 65536,
    test_only: bool = False,
) -> dict:
    """Consume solo un catalogo train explicito, no una T14 incompleta disfrazada."""
    if type(test_only) is not bool or type(batch_size) is not int or not 1 <= batch_size <= 65536:
        raise SplitError("Modo o tamano de bloque incompatible")
    catalog, output, reports, scratch = [
        Path(p).resolve() for p in (catalog_path, output_dir, report_dir, scratch_dir)
    ]
    roots = (output, reports, scratch)
    if any(
        a.is_relative_to(b) or b.is_relative_to(a)
        for i, a in enumerate(roots)
        for b in roots[i + 1 :]
    ) or any(catalog.is_relative_to(root) for root in roots):
        raise SplitError("Catalogo, salidas, reportes y scratch deben estar separados")
    fit_id = uuid.uuid4().hex
    scopes = ("_test_only",) if test_only else ()
    reports = _under(reports, *scopes)
    reports.mkdir(parents=True, exist_ok=True)
    report = {
        "report_version": 1,
        "baseline_fit_id": fit_id,
        "status": "FAIL",
        "mode": "TEST_ONLY" if test_only else "REAL",
        "started_at_utc": utc_now(),
        "fit_partition": "train",
        "fit_complete": False,
        "evaluation_status": "PENDING_VALIDATION",
        "validation_accessed": False,
        "test_accessed": False,
        "monitoring_replay_accessed": False,
        "t14_complete": False,
        "t15_complete": False,
        "approved_for_serving": False,
        "model_registered": False,
        "publication_complete": False,
        "output_directory": None,
        "validation_metrics": None,
    }
    try:
        config = read_model_config(Path(config_path))
        policy = config.get("baseline_fit_only")
        if (
            config.get("baseline") != BASELINE_POLICY
            or not isinstance(policy, dict)
            or set(policy) != set(FIT_ONLY_POLICY)
            or any(
                type(policy[k]) is not type(v) or policy[k] != v for k, v in FIT_ONLY_POLICY.items()
            )
        ):
            raise SplitError("Ajuste independiente de baseline no aprobado")
        data_config = load_config(Path(data_config_path))
        if fingerprint(quality_rules(data_config["quality"])) != config["quality_rules_sha256"]:
            raise SplitError("Politica de calidad distinta de D-04 congelada")
        catalog_hash = _sha256(catalog)
        required = train_months(config)
        entries = _catalog(catalog, config, test_only=test_only, required=required)
        for entry in entries:
            for name in ("features_directory", "validated_directory"):
                source = entry[name]
                if any(
                    root.is_relative_to(source) or source.is_relative_to(root) for root in roots
                ):
                    raise SplitError("Salidas/reportes/scratch se solapan con fuentes")
        output.mkdir(parents=True, exist_ok=True)
        guard = ResourceGuard(preparation_budget(config), output, test_only=test_only)
        guard.check(start=True)
        started = time.monotonic()

        def checked():
            guard.check()
            if time.monotonic() - started > config["resources"]["candidate_timeout_seconds"]:
                raise ResourceLimitError("Ajuste de baseline excedio dos horas")

        # El lector compartido tambien supervisa el plazo entre bloques.
        class ScanGuard:
            def check(self):
                checked()

        validation_ids = set()
        for entry in entries:
            checked()
            verified = verify_features(
                entry["features_directory"],
                entry["validated_directory"],
                config=config,
                data_config=data_config,
                test_only=test_only,
            )
            feature = verified["feature"]
            if (feature["year"], feature["month"]) != (entry["year"], entry["month"]):
                raise SplitError("Mes declarado distinto de la fuente")
            if feature["validation_id"] in validation_ids:
                raise SplitError("Validacion de origen repetida")
            validation_ids.add(feature["validation_id"])
            entry["verified"] = verified
        expected = sum(e["verified"]["feature"]["rows_emitted"] for e in entries)
        if test_only and expected > 65536:
            raise SplitError("Ajuste TEST_ONLY excede 65536 filas")
        counters, exclusions = Counter(), []
        digests = {part: hashlib.sha256() for part in PARTITIONS}
        ranges = {part: {} for part in PARTITIONS}
        target_digest = hashlib.sha256()
        schema = SCHEMAS["target"].with_metadata(
            {
                b"baseline_fit_scope": report["mode"].encode(),
                b"evaluation_status": b"PENDING_VALIDATION",
                b"approved_for_serving": b"false",
            }
        )
        if test_only:
            schema = schema.with_metadata({**schema.metadata, b"fixture_origin": b"synthetic"})
        parent = _under(output, *scopes)
        parent.mkdir(parents=True, exist_ok=True)
        with (
            tempfile.TemporaryDirectory(prefix=".fit-", dir=parent) as owned,
            threadpool_limits(limits=4),
        ):
            staged = Path(owned)
            target_path = staged / "train_target.parquet"
            with pq.ParquetWriter(target_path, schema) as writer:

                def batches():
                    for entry in entries:
                        for grouped in _source_rows(
                            entry,
                            config,
                            counters,
                            digests,
                            ranges,
                            ScanGuard(),
                            exclusions,
                            batch_size=batch_size,
                            test_only=test_only,
                        ):
                            if any(grouped[p]["target"] for p in PARTITIONS if p != "train"):
                                raise SplitError(
                                    "Ajuste independiente intento consumir otra particion"
                                )
                            rows = grouped["train"]["target"]
                            if rows:
                                table = pa.Table.from_pylist(rows, schema=schema)
                                # IEEE754 float64 little-endian, independiente de row groups.
                                target_digest.update(
                                    table.column(0)
                                    .chunk(0)
                                    .to_numpy(zero_copy_only=False)
                                    .astype("<f8", copy=False)
                                    .tobytes()
                                )
                                writer.write_table(table)
                                yield from table.to_batches()
                        LOGGER.info(
                            "Ajuste train %04d-%02d: %d filas conservadas",
                            entry["year"],
                            entry["month"],
                            counters["train"],
                        )

                learned = exact_disk_median(batches(), scratch_dir=scratch, resource_check=checked)
            if (
                counters["rows_seen"] != expected
                or counters["train"] + counters["label_not_available_at_cutoff"] != expected
                or learned["train_rows"] != counters["train"]
            ):
                raise SplitError("Cobertura del ajuste no exhaustiva")
            for entry in entries:
                checked()
                after = verify_features(
                    entry["features_directory"],
                    entry["validated_directory"],
                    config=config,
                    data_config=data_config,
                    test_only=test_only,
                )
                if after != entry["verified"]:
                    raise SplitError("Fuente cambio durante el ajuste")
            if _sha256(catalog) != catalog_hash:
                raise SplitError("Catalogo cambio durante el ajuste")
            target = describe_parquet(target_path)
            if target["row_count"] != learned["train_rows"]:
                raise SplitError("Artefacto de etiquetas incompleto")
            model = {
                "kind": "exact_global_train_median",
                "prediction_minutes": learned["median_minutes"],
                "train_rows": learned["train_rows"],
                "train_target_logical_sha256": target_digest.hexdigest(),
                "evaluation_status": "PENDING_VALIDATION",
                "approved_for_serving": False,
            }
            model_path = staged / "model.json"
            model_path.write_text(
                json.dumps(model, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
            for path in (model_path, target_path):
                with path.open("r+b") as stream:
                    os.fsync(stream.fileno())
            checked()
            report.update(
                status="BASELINE_FIT_TEST_ONLY_PENDING_VALIDATION"
                if test_only
                else "BASELINE_FIT_REAL_PENDING_VALIDATION",
                fit_complete=True,
                configuration=config,
                config_sha256=fingerprint(config),
                source_catalog_sha256=catalog_hash,
                inputs=[
                    {
                        **e,
                        "features_directory": str(e["features_directory"]),
                        "validated_directory": str(e["validated_directory"]),
                    }
                    for e in entries
                ],
                complete_train_coverage={(e["year"], e["month"]) for e in entries} == required,
                complete_protocol_coverage=False,
                counts=dict(counters),
                exclusion_examples=exclusions,
                train_logical_sha256=digests["train"].hexdigest(),
                target_logical_sha256=target_digest.hexdigest(),
                target_hash_encoding="IEEE754_float64_little_endian_contiguous",
                pickup_range_utc={k: v.isoformat() for k, v in ranges["train"].items()},
                learned=learned,
                model=model,
                model_sha256=_sha256(model_path),
                train_target=target,
                resources={
                    "initial": guard.initial,
                    "final": guard.last,
                    "elapsed_seconds": time.monotonic() - started,
                },
                finished_at_utc=utc_now(),
            )
            destination = _under(parent, fit_id)
            destination.mkdir(exist_ok=False)
            report["output_directory"] = str(destination)
            for name in ("model.json", "train_target.parquet"):
                publish_file(staged / name, _under(destination, name))
            report["publication_complete"] = True
            publish_manifest(_under(destination, "fit_manifest.json"), report)
    except (
        ValueError,
        RuntimeError,
        OSError,
        KeyError,
        TypeError,
        sqlite3.Error,
        pa.ArrowException,
    ) as error:
        report.update(
            status="FAIL",
            error=str(error),
            fit_complete=False,
            publication_complete=False,
            finished_at_utc=utc_now(),
        )
    publish_manifest(_under(reports, f"{fit_id}.json"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/model.yaml"))
    parser.add_argument("--data-config", type=Path, default=Path("configs/data.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/baseline_fits"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/baseline_fits"))
    parser.add_argument("--scratch-dir", type=Path, default=Path(".cache/baseline"))
    parser.add_argument("--batch-size", type=int, default=65536)
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    try:
        report = fit_baseline(
            args.inputs,
            config_path=args.config,
            data_config_path=args.data_config,
            output_dir=args.output_dir,
            report_dir=args.report_dir,
            scratch_dir=args.scratch_dir,
            batch_size=args.batch_size,
            test_only=args.test_only,
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Ajuste de baseline fallido: {error}\n")
    print(json.dumps(report))
    if report["status"] == "FAIL":
        parser.exit(1)


if __name__ == "__main__":
    main()
