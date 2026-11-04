"""T15: evaluar el ajuste congelado sobre validation; test/replay sellados."""

import argparse
import hashlib
import json
import logging
import math
import os
import tempfile
import time
import uuid
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.features.target import nyc_zone
from src.ingestion.manifest import describe_parquet, publish_file, publish_manifest, utc_now
from src.training.baseline import BASELINE_POLICY
from src.training.baseline_fit import train_months
from src.training.resources import ResourceGuard, ResourceLimitError
from src.training.split import (
    CONTEXT,
    PARTITIONS,
    SCHEMAS,
    SplitError,
    _catalog,
    _read_object,
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


def verify_fit(
    directory: Path, *, config: dict, data_config: dict, test_only: bool, resource_check=None
) -> dict:
    """Verifica fuentes y estadistico exacto sin reajustar ni leer 2025."""
    directory = directory.resolve()
    marker = _under(directory, "fit_manifest.json")
    marker_hash = _sha256(marker)
    report = _read_object(marker)
    expected = {
        "report_version": 1,
        "status": "BASELINE_FIT_TEST_ONLY_PENDING_VALIDATION"
        if test_only
        else "BASELINE_FIT_REAL_PENDING_VALIDATION",
        "mode": "TEST_ONLY" if test_only else "REAL",
        "fit_complete": True,
        "publication_complete": True,
        "evaluation_status": "PENDING_VALIDATION",
        "approved_for_serving": False,
        "model_registered": False,
        "validation_accessed": False,
        "test_accessed": False,
        "monitoring_replay_accessed": False,
    }
    if any(type(report.get(k)) is not type(v) or report[k] != v for k, v in expected.items()):
        raise SplitError("Ajuste congelado incompleto o de otro ambito")
    if (
        report.get("baseline_fit_id") != directory.name
        or report.get("config_sha256") != fingerprint(config)
        or report.get("configuration") != config
        or config.get("baseline") != BASELINE_POLICY
    ):
        raise SplitError("Identidad/configuracion del ajuste divergente")
    months = set()
    for entry in report["inputs"]:
        if resource_check:
            resource_check()
        period = (entry["year"], entry["month"])
        if period not in train_months(config) or period in months:
            raise SplitError("El ajuste contiene entradas ajenas o repetidas en train")
        months.add(period)
        actual = verify_features(
            Path(entry["features_directory"]),
            Path(entry["validated_directory"]),
            config=config,
            data_config=data_config,
            test_only=test_only,
        )
        if actual != entry["verified"]:
            raise SplitError("Fuentes del ajuste cambiaron")
    if not test_only and (
        months != train_months(config) or report.get("complete_train_coverage") is not True
    ):
        raise SplitError("Faltan meses de train")
    model_path = _under(directory, "model.json")
    model = _read_object(model_path)
    if _sha256(model_path) != report["model_sha256"] or model != report["model"]:
        raise SplitError("Modelo congelado alterado")
    median = model["prediction_minutes"]
    if (
        model.get("kind") != "exact_global_train_median"
        or type(median) is not float
        or not math.isfinite(median)
        or median <= 0
        or model.get("approved_for_serving") is not False
    ):
        raise SplitError("Constante de baseline invalida")
    target = _under(directory, "train_target.parquet")
    if describe_parquet(target) != report["train_target"]:
        raise SplitError("Etiquetas del ajuste alteradas")
    seen = less = equal = 0
    below = above = None
    digest = hashlib.sha256()
    with pq.ParquetFile(target) as parquet:
        if not parquet.schema_arrow.equals(SCHEMAS["target"], check_metadata=False):
            raise SplitError("Esquema de etiquetas de ajuste incompatible")
        for batch in parquet.iter_batches(batch_size=65536, use_threads=False):
            if resource_check:
                resource_check()
            values = batch.column(0).to_numpy(zero_copy_only=False)
            if not np.all(np.isfinite(values) & (values > 0)):
                raise SplitError("Etiquetas no positivas/finitas en ajuste")
            digest.update(values.astype("<f8", copy=False).tobytes())
            lower, upper = values[values < median], values[values > median]
            less += len(lower)
            equal += int(np.count_nonzero(values == median))
            seen += len(values)
            if len(lower):
                below = float(np.max(lower)) if below is None else max(below, float(np.max(lower)))
            if len(upper):
                above = float(np.min(upper)) if above is None else min(above, float(np.min(upper)))
    if (
        seen != model["train_rows"]
        or seen != report["counts"]["train"]
        or digest.hexdigest() != model["train_target_logical_sha256"]
        or digest.hexdigest() != report["target_logical_sha256"]
    ):
        raise SplitError("Cobertura/hash logico de train divergente")
    central = []
    for rank in ((seen - 1) // 2, seen // 2):
        if rank < less:
            if rank != less - 1 or below is None:
                raise SplitError("La constante no es la mediana exacta de train")
            central.append(below)
        elif rank < less + equal:
            central.append(median)
        else:
            if rank != less + equal or above is None:
                raise SplitError("La constante no es la mediana exacta de train")
            central.append(above)
    if central[0] + (central[1] - central[0]) / 2 != median or _sha256(marker) != marker_hash:
        raise SplitError("Mediana/marcador de ajuste no verificable")
    return {"manifest": report, "marker_sha256": marker_hash}


def validation_months(config: dict) -> set[tuple[int, int]]:
    start, end = (t.astimezone(nyc_zone()) for t in boundaries(config, "validation"))
    year, month = start.year, start.month
    result = set()
    while (year, month) < (end.year, end.month):
        result.add((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def evaluate_fit(
    fit_directory: Path,
    catalog_path: Path,
    *,
    config_path: Path = Path("configs/model.yaml"),
    data_config_path: Path = Path("configs/data.yaml"),
    output_dir: Path = Path("data/processed/baselines"),
    report_dir: Path = Path("reports/baseline"),
    batch_size: int = 65536,
    test_only: bool = False,
) -> dict:
    if type(test_only) is not bool or type(batch_size) is not int or not 1 <= batch_size <= 65536:
        raise SplitError("Modo/tamano de bloque incompatible")
    fit, catalog, output, reports = [
        Path(p).resolve() for p in (fit_directory, catalog_path, output_dir, report_dir)
    ]
    if (
        output.is_relative_to(reports)
        or reports.is_relative_to(output)
        or any(
            fit.is_relative_to(p) or p.is_relative_to(fit) or catalog.is_relative_to(p)
            for p in (output, reports)
        )
    ):
        raise SplitError("Entradas y salidas deben estar separadas")
    identifier = uuid.uuid4().hex
    scopes = ("_test_only",) if test_only else ()
    reports = _under(reports, *scopes)
    reports.mkdir(parents=True, exist_ok=True)
    report = {
        "report_version": 2,
        "baseline_id": identifier,
        "status": "FAIL",
        "mode": "TEST_ONLY" if test_only else "REAL",
        "started_at_utc": utc_now(),
        "fit_partition": "train",
        "prediction_partition": "validation",
        "fit_reused": True,
        "test_accessed": False,
        "monitoring_replay_accessed": False,
        "t14_complete": False,
        "t15_complete": False,
        "human_review_complete": False,
        "approved_for_serving": False,
        "model_registered": False,
        "publication_complete": False,
        "output_directory": None,
    }
    try:
        config = read_model_config(Path(config_path))
        data_config = load_config(Path(data_config_path))
        if fingerprint(quality_rules(data_config["quality"])) != config["quality_rules_sha256"]:
            raise SplitError("D-04 global modificada")
        catalog_hash = _sha256(catalog)
        entries = _catalog(catalog, config, test_only=test_only, required=validation_months(config))
        for entry in entries:
            for name in ("features_directory", "validated_directory"):
                source = entry[name]
                if any(
                    source.is_relative_to(p) or p.is_relative_to(source) for p in (output, reports)
                ):
                    raise SplitError("Salidas se solapan con fuentes")
        output.mkdir(parents=True, exist_ok=True)
        guard = ResourceGuard(preparation_budget(config), output, test_only=test_only)
        guard.check(start=True)
        started = time.monotonic()

        def checked():
            guard.check()
            if time.monotonic() - started > config["resources"]["candidate_timeout_seconds"]:
                raise ResourceLimitError("Evaluacion de baseline excedio dos horas")

        class ScanGuard:
            def check(self):
                checked()

        initial = verify_fit(
            fit, config=config, data_config=data_config, test_only=test_only, resource_check=checked
        )
        LOGGER.info(
            "Ajuste congelado verificado; se conserva mediana %.12f",
            initial["manifest"]["model"]["prediction_minutes"],
        )
        for entry in entries:
            checked()
            entry["verified"] = verify_features(
                entry["features_directory"],
                entry["validated_directory"],
                config=config,
                data_config=data_config,
                test_only=test_only,
            )
            if (entry["year"], entry["month"]) != (
                entry["verified"]["feature"]["year"],
                entry["verified"]["feature"]["month"],
            ):
                raise SplitError("Mes declarado distinto de validation")
        expected = sum(e["verified"]["feature"]["rows_emitted"] for e in entries)
        if test_only and expected > 65536:
            raise SplitError("Validation TEST_ONLY excede 65536 filas")
        median = initial["manifest"]["model"]["prediction_minutes"]
        counters, exclusions = Counter(), []
        digests = {p: hashlib.sha256() for p in PARTITIONS}
        ranges = {p: {} for p in PARTITIONS}
        metadata = {b"baseline_scope": report["mode"].encode(), b"approved_for_serving": b"false"}
        if test_only:
            metadata[b"fixture_origin"] = b"synthetic"
        prediction_schema = pa.schema(
            [("validation_row_index", pa.int64()), ("predicted_duration_minutes", pa.float64())],
            metadata=metadata,
        )
        target_schema = SCHEMAS["target"].with_metadata(metadata)
        context_schema = CONTEXT.append(pa.field("source_feature_id", pa.string())).with_metadata(
            metadata
        )
        parent = _under(output, *scopes)
        parent.mkdir(parents=True, exist_ok=True)
        sums, squares = [], []
        seen = 0
        with (
            tempfile.TemporaryDirectory(prefix=".evaluate-", dir=parent) as owned,
            threadpool_limits(limits=4),
        ):
            staged = Path(owned)
            with (
                pq.ParquetWriter(
                    staged / "validation_predictions.parquet", prediction_schema
                ) as predictions,
                pq.ParquetWriter(staged / "validation_target.parquet", target_schema) as targets,
                pq.ParquetWriter(staged / "validation_context.parquet", context_schema) as contexts,
            ):
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
                        if any(grouped[p]["target"] for p in PARTITIONS if p != "validation"):
                            raise SplitError(
                                "Se intento evaluar una particion distinta de validation"
                            )
                        rows = grouped["validation"]["target"]
                        if not rows:
                            continue
                        values = [r["trip_duration_minutes"] for r in rows]
                        errors = [abs(v - median) for v in values]
                        sums.append(math.fsum(errors))
                        squares.append(math.fsum(e * e for e in errors))
                        targets.write_table(pa.Table.from_pylist(rows, schema=target_schema))
                        contexts.write_table(
                            pa.Table.from_pylist(
                                grouped["validation"]["context"], schema=context_schema
                            )
                        )
                        predictions.write_table(
                            pa.Table.from_pydict(
                                {
                                    "validation_row_index": list(range(seen, seen + len(rows))),
                                    "predicted_duration_minutes": [median] * len(rows),
                                },
                                schema=prediction_schema,
                            )
                        )
                        seen += len(rows)
                        LOGGER.info("Baseline: %d predicciones validation", seen)
                    LOGGER.info("Validation %04d-%02d terminada", entry["year"], entry["month"])
            if (
                seen < 1
                or counters["rows_seen"] != expected
                or seen != counters["validation"]
                or seen + counters["label_not_available_at_cutoff"] != expected
            ):
                raise SplitError("Cobertura validation no exhaustiva")
            for entry in entries:
                checked()
                if (
                    verify_features(
                        entry["features_directory"],
                        entry["validated_directory"],
                        config=config,
                        data_config=data_config,
                        test_only=test_only,
                    )
                    != entry["verified"]
                ):
                    raise SplitError("Fuente validation cambio durante evaluacion")
            if (
                verify_fit(
                    fit,
                    config=config,
                    data_config=data_config,
                    test_only=test_only,
                    resource_check=checked,
                )
                != initial
                or _sha256(catalog) != catalog_hash
            ):
                raise SplitError("Ajuste/catalogo cambio durante evaluacion")
            model = {**initial["manifest"]["model"], "evaluation_status": "COMPLETE_VALIDATION"}
            model_path = staged / "model.json"
            model_path.write_text(
                json.dumps(model, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
            artifacts = {}
            for path in staged.iterdir():
                with path.open("r+b") as stream:
                    os.fsync(stream.fileno())
                if path.suffix == ".parquet":
                    artifacts[path.name] = describe_parquet(path)
                    if artifacts[path.name]["row_count"] != seen:
                        raise SplitError("Artefactos validation desalineados")
            checked()
            report.update(
                status="BASELINE_TEST_ONLY" if test_only else "BASELINE_REAL",
                evaluation_status="COMPLETE_VALIDATION",
                t15_complete=not test_only,
                configuration=config,
                config_sha256=fingerprint(config),
                source_fit_directory=str(fit),
                source_fit_id=initial["manifest"]["baseline_fit_id"],
                source_fit_manifest_sha256=initial["marker_sha256"],
                source_fit_model_sha256=initial["manifest"]["model_sha256"],
                source_catalog_sha256=catalog_hash,
                inputs=[
                    {
                        **e,
                        "features_directory": str(e["features_directory"]),
                        "validated_directory": str(e["validated_directory"]),
                    }
                    for e in entries
                ],
                counts=dict(counters),
                exclusion_examples=exclusions,
                complete_validation_coverage={(e["year"], e["month"]) for e in entries}
                == validation_months(config),
                coverage="ALL_APPROVED_TRAIN_AND_VALIDATION_ONLY_TEST_REPLAY_SEALED",
                validation_rows=seen,
                validation_logical_sha256=digests["validation"].hexdigest(),
                model=model,
                model_sha256=_sha256(model_path),
                artifacts=artifacts,
                validation_metrics={
                    "mae_minutes": math.fsum(sums) / seen,
                    "rmse_minutes": math.sqrt(math.fsum(squares) / seen),
                },
                pickup_range_utc={k: v.isoformat() for k, v in ranges["validation"].items()},
                resources={
                    "initial": guard.initial,
                    "final": guard.last,
                    "elapsed_seconds": time.monotonic() - started,
                },
                finished_at_utc=utc_now(),
            )
            destination = _under(parent, identifier)
            destination.mkdir(exist_ok=False)
            report["output_directory"] = str(destination)
            for path in staged.iterdir():
                publish_file(path, _under(destination, path.name))
            report["publication_complete"] = True
            publish_manifest(_under(destination, "baseline_manifest.json"), report)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, pa.ArrowException) as error:
        report.update(
            status="FAIL",
            error=str(error),
            t15_complete=False,
            publication_complete=False,
            finished_at_utc=utc_now(),
        )
    publish_manifest(_under(reports, f"{identifier}.json"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit-batch", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/model.yaml"))
    parser.add_argument("--data-config", type=Path, default=Path("configs/data.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/baselines"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/baseline"))
    parser.add_argument("--batch-size", type=int, default=65536)
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    try:
        report = evaluate_fit(
            args.fit_batch,
            args.inputs,
            config_path=args.config,
            data_config_path=args.data_config,
            output_dir=args.output_dir,
            report_dir=args.report_dir,
            batch_size=args.batch_size,
            test_only=args.test_only,
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Evaluacion fallida: {error}\n")
    print(json.dumps(report))
    if report["status"] == "FAIL":
        parser.exit(1)


if __name__ == "__main__":
    main()
