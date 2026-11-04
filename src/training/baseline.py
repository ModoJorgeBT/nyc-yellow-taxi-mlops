"""T15: mediana global exacta de train en disco; validacion sin acceso a test."""

import argparse
import json
import logging
import math
import os
import sqlite3
import tempfile
import time
import uuid
from contextlib import ExitStack
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from src.ingestion.manifest import describe_parquet, publish_file, publish_manifest, utc_now
from src.training.resources import ResourceGuard, ResourceLimitError
from src.training.split import (
    CONTEXT,
    SCHEMAS,
    SplitError,
    _read_object,
    preparation_budget,
    read_model_config,
    verify_features,
)
from src.validation.run import _sha256, _under
from src.validation.schema import fingerprint, load_config

LOGGER = logging.getLogger(__name__)
BASELINE_POLICY = {
    "approval_status": "APPROVED",
    "kind": "exact_global_train_median",
    "fit_partition": "train",
    "prediction_partition": "validation",
    "quantile_interpolation": "midpoint_for_even_count",
    "test_usage": "sealed_no_baseline_fit_or_selection",
}


def verify_split(directory: Path, *, config: dict, data_config: dict, test_only: bool) -> dict:
    """Verifica solo train/validation; nunca abre artefactos ni fuentes de test/replay."""
    directory = directory.resolve()
    marker = _under(directory, "split_manifest.json")
    marker_hash = _sha256(marker)
    report = _read_object(marker)
    expected = {
        "report_version": 1,
        "status": "SPLIT_TEST_ONLY" if test_only else "SPLIT_REAL",
        "mode": "TEST_ONLY" if test_only else "REAL",
        "publication_complete": True,
        "approved_for_training": False,
        "preprocessor_fitted": False,
    }
    if any(type(report.get(k)) is not type(v) or report[k] != v for k, v in expected.items()):
        raise SplitError("Marcador de particionado incompleto o de otro ambito")
    if (
        directory.name != report.get("split_id")
        or fingerprint(report.get("configuration")) != report.get("config_sha256")
        or report["config_sha256"] != fingerprint(config)
        or (not test_only and report.get("complete_protocol_coverage") is not True)
    ):
        raise SplitError("Identidad/configuracion/cobertura de particionado divergente")
    months = set()
    for entry in report["inputs"]:
        year, month = entry["year"], entry["month"]
        if year != 2024 and not (year == 2025 and month <= 3):
            continue
        if (year, month) in months:
            raise SplitError("Mes de train/validacion repetido")
        months.add((year, month))
        actual = verify_features(
            Path(entry["features_directory"]).resolve(),
            Path(entry["validated_directory"]).resolve(),
            test_only=test_only,
            config=config,
            data_config=data_config,
        )
        if actual != entry["verified"]:
            raise SplitError("Linaje de entrada alterado desde T14")
    if not test_only and months != {(2024, m) for m in range(1, 13)} | {
        (2025, m) for m in (1, 2, 3)
    }:
        raise SplitError("Faltan meses de train/validacion")
    for partition in ("train", "validation"):
        info = report["partitions"][partition]
        if type(info["rows"]) is not int or info["rows"] < 1:
            raise SplitError("Particion vacia")
        for name in ("features", "target", "context"):
            path = _under(directory, partition, f"{name}.parquet")
            actual = describe_parquet(path)
            if actual != info["artifacts"][name] or actual["row_count"] != info["rows"]:
                raise SplitError("Contenido de particion divergente")
            expected_schema = SCHEMAS[name]
            if name == "context":
                expected_schema = CONTEXT.append(pa.field("source_feature_id", pa.string()))
            with pq.ParquetFile(path) as parquet:
                schema = parquet.schema_arrow
            metadata = schema.metadata or {}
            if (
                not schema.equals(expected_schema, check_metadata=False)
                or metadata.get(b"split_scope") != report["mode"].encode()
                or metadata.get(b"approved_for_training") != b"false"
                or (test_only and metadata.get(b"fixture_origin") != b"synthetic")
            ):
                raise SplitError("Esquema/metadata de particion incompatible")
    if _sha256(marker) != marker_hash:
        raise SplitError("Marcador de particionado cambio durante verificacion")
    return {"manifest": report, "marker_sha256": marker_hash}


def exact_disk_median(batches, *, scratch_dir: Path, resource_check=None) -> dict:
    """Orden numerico exacto SQLite, no medianas de bloques ni cuantiles aproximados."""
    scratch_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with tempfile.TemporaryDirectory(prefix="median-", dir=scratch_dir) as owned:
        db_path = Path(owned) / "labels.sqlite"
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("PRAGMA cache_size=-16384")
            connection.execute("PRAGMA temp_store=FILE")
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("PRAGMA threads=1")
            connection.execute("CREATE TABLE labels (value REAL NOT NULL)")
            for batch in batches:
                if resource_check:
                    resource_check()
                values = batch.column(0).to_pylist()
                if any(type(v) is not float or not math.isfinite(v) or v <= 0 for v in values):
                    raise SplitError("Train contiene etiquetas no positivas/finitas")
                connection.executemany("INSERT INTO labels VALUES (?)", ((v,) for v in values))
                connection.commit()
                count += len(values)
                LOGGER.info("Mediana exacta: %d etiquetas train incorporadas", count)
                if resource_check:
                    resource_check()
            if not count:
                raise SplitError("Train vacio")
            if resource_check:
                resource_check()

            # El callback tambien permite cancelar durante la ordenacion/consulta larga.
            interrupted = []

            def progress():
                try:
                    if resource_check:
                        resource_check()
                except Exception as error:
                    interrupted.append(error)
                    return 1
                return 0

            connection.set_progress_handler(progress, 100000)
            LOGGER.info("Mediana exacta: ordenando %d etiquetas en disco", count)
            try:
                connection.execute("CREATE INDEX by_value ON labels(value)")
                middle = connection.execute(
                    "SELECT value FROM labels ORDER BY value LIMIT ? OFFSET ?",
                    (2 if count % 2 == 0 else 1, (count - 1) // 2),
                ).fetchall()
            except sqlite3.Error:
                if interrupted:
                    raise interrupted[0] from None
                raise
            result = {
                "train_rows": count,
                "median_minutes": middle[0][0] + (middle[-1][0] - middle[0][0]) / 2,
                "sqlite_file_peak_bytes": db_path.stat().st_size,
                "method": "exact_sqlite_order_statistic_midpoint_if_even",
            }
            if resource_check:
                resource_check()
            return result
        finally:
            connection.close()


def run_baseline(
    split_directory: Path,
    *,
    config_path: Path = Path("configs/model.yaml"),
    data_config_path: Path = Path("configs/data.yaml"),
    output_dir: Path = Path("data/processed/baselines"),
    report_dir: Path = Path("reports/baseline"),
    scratch_dir: Path = Path(".cache/baseline"),
    batch_size: int = 65536,
    test_only: bool = False,
) -> dict:
    if type(test_only) is not bool or type(batch_size) is not int or not 1 <= batch_size <= 65536:
        raise SplitError("Modo o tamano de bloque incompatible")
    source, output, reports, scratch = [
        Path(p).resolve() for p in (split_directory, output_dir, report_dir, scratch_dir)
    ]
    roots = (source, output, reports, scratch)
    if any(
        a.is_relative_to(b) or b.is_relative_to(a)
        for i, a in enumerate(roots)
        for b in roots[i + 1 :]
    ):
        raise SplitError("Entradas, salidas, reportes y scratch deben estar separados")
    baseline_id = uuid.uuid4().hex
    scopes = ("_test_only",) if test_only else ()
    reports = _under(reports, *scopes)
    reports.mkdir(parents=True, exist_ok=True)
    report = {
        "report_version": 1,
        "baseline_id": baseline_id,
        "status": "FAIL",
        "mode": "TEST_ONLY" if test_only else "REAL",
        "started_at_utc": utc_now(),
        "fit_partition": "train",
        "prediction_partition": "validation",
        "test_accessed": False,
        "approved_for_serving": False,
        "model_registered": False,
        "publication_complete": False,
        "output_directory": None,
    }
    try:
        config = read_model_config(Path(config_path))
        if config.get("baseline") != BASELINE_POLICY:
            raise SplitError("Baseline no aprobado")
        data_config = load_config(Path(data_config_path))
        output.mkdir(parents=True, exist_ok=True)
        guard = ResourceGuard(preparation_budget(config), output, test_only=test_only)
        guard.check(start=True)
        started = time.monotonic()

        def checked():
            guard.check()
            if time.monotonic() - started > config["resources"]["candidate_timeout_seconds"]:
                raise ResourceLimitError("Baseline excedio dos horas")

        initial = verify_split(source, config=config, data_config=data_config, test_only=test_only)
        manifest = initial["manifest"]
        parent = _under(output, *scopes)
        parent.mkdir(parents=True, exist_ok=True)
        with (
            tempfile.TemporaryDirectory(prefix=".baseline-", dir=parent) as owned,
            ExitStack() as stack,
            threadpool_limits(limits=4),
        ):
            staged = Path(owned)
            train = stack.enter_context(pq.ParquetFile(_under(source, "train", "target.parquet")))
            learned = exact_disk_median(
                train.iter_batches(batch_size=batch_size, use_threads=False),
                scratch_dir=scratch,
                resource_check=checked,
            )
            if learned["train_rows"] != manifest["partitions"]["train"]["rows"]:
                raise SplitError("Escaneo de train incompleto")
            median = learned["median_minutes"]
            schema = pa.schema(
                [
                    ("validation_row_index", pa.int64()),
                    ("predicted_duration_minutes", pa.float64()),
                ],
                metadata={
                    b"baseline_scope": report["mode"].encode(),
                    b"approved_for_serving": b"false",
                },
            )
            validation = stack.enter_context(
                pq.ParquetFile(_under(source, "validation", "target.parquet"))
            )
            seen, sums, squared = 0, [], []
            with pq.ParquetWriter(staged / "validation_predictions.parquet", schema) as writer:
                for batch in validation.iter_batches(batch_size=batch_size, use_threads=False):
                    checked()
                    values = batch.column(0).to_pylist()
                    if any(type(v) is not float or not math.isfinite(v) or v <= 0 for v in values):
                        raise SplitError("Validacion contiene etiquetas invalidas")
                    errors = [abs(value - median) for value in values]
                    sums.append(math.fsum(errors))
                    squared.append(math.fsum(error * error for error in errors))
                    writer.write_table(
                        pa.Table.from_pydict(
                            {
                                "validation_row_index": list(range(seen, seen + len(values))),
                                "predicted_duration_minutes": [median] * len(values),
                            },
                            schema=schema,
                        )
                    )
                    seen += len(values)
                    LOGGER.info("Baseline: %d predicciones de validacion", seen)
            if seen != manifest["partitions"]["validation"]["rows"]:
                raise SplitError("Escaneo de validacion incompleto")
            if (
                verify_split(source, config=config, data_config=data_config, test_only=test_only)
                != initial
            ):
                raise SplitError("Particiones cambiaron durante baseline")
            model = {
                "kind": "exact_global_train_median",
                "prediction_minutes": median,
                "train_rows": learned["train_rows"],
                "train_target_sha256": manifest["partitions"]["train"]["artifacts"]["target"][
                    "sha256"
                ],
            }
            model_path = staged / "model.json"
            model_path.write_text(
                json.dumps(model, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
            for name in ("model.json", "validation_predictions.parquet"):
                with (staged / name).open("r+b") as stream:
                    os.fsync(stream.fileno())
            checked()
            report.update(
                status="BASELINE_TEST_ONLY" if test_only else "BASELINE_REAL",
                source_split_id=manifest["split_id"],
                source_split_manifest_sha256=initial["marker_sha256"],
                configuration=config,
                config_sha256=fingerprint(config),
                learned=learned,
                model=model,
                model_sha256=_sha256(model_path),
                validation_rows=seen,
                validation_metrics={
                    "mae_minutes": math.fsum(sums) / seen,
                    "rmse_minutes": math.sqrt(math.fsum(squared) / seen),
                },
                predictions=describe_parquet(staged / "validation_predictions.parquet"),
                resources={
                    "initial": guard.initial,
                    "final": guard.last,
                    "elapsed_seconds": time.monotonic() - started,
                },
                finished_at_utc=utc_now(),
            )
            destination = _under(parent, baseline_id)
            destination.mkdir(exist_ok=False)
            report["output_directory"] = str(destination)
            for name in ("model.json", "validation_predictions.parquet"):
                publish_file(staged / name, _under(destination, name))
            report["publication_complete"] = True
            publish_manifest(_under(destination, "baseline_manifest.json"), report)
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
            status="FAIL", error=str(error), publication_complete=False, finished_at_utc=utc_now()
        )
    publish_manifest(_under(reports, f"{baseline_id}.json"), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-batch", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/model.yaml"))
    parser.add_argument("--data-config", type=Path, default=Path("configs/data.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/baselines"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/baseline"))
    parser.add_argument("--scratch-dir", type=Path, default=Path(".cache/baseline"))
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    try:
        report = run_baseline(
            args.split_batch,
            config_path=args.config,
            data_config_path=args.data_config,
            output_dir=args.output_dir,
            report_dir=args.report_dir,
            scratch_dir=args.scratch_dir,
            test_only=args.test_only,
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Baseline fallido: {error}\n")
    print(json.dumps(report))
    if report["status"] == "FAIL":
        parser.exit(1)


if __name__ == "__main__":
    main()
