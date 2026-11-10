"""Replay separado en prediccion y etiquetas maduras; identidades verificadas."""

import hashlib
import importlib.metadata
import os
import re
from contextlib import ExitStack

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from src.evaluation.metrics import ErrorStore
from src.evaluation.segments import SegmentRows, group_masks
from src.features.schema import FEATURE_COLUMNS
from src.monitoring.drift import feature_array
from src.monitoring.protocol import (
    batches,
    envelope,
    maturity_cutoff,
    month_bounds,
    pinned,
    read_json,
    source_manifest,
    verify_tables,
)
from src.validation.run import _sha256
from src.validation.schema import fingerprint

PREDICTION_CONTEXT = ["validated_row_index", "pickup_datetime_utc", "source_feature_id"]


def time_mask(context, year, month):
    start, end = month_bounds(year, month)
    instants = context.column("pickup_datetime_utc").to_numpy(zero_copy_only=False)
    return (instants >= np.datetime64(start.replace(tzinfo=None), "us")) & (
        instants < np.datetime64(end.replace(tzinfo=None), "us")
    )


def identity_arrays(context):
    if any(context.column(name).null_count for name in PREDICTION_CONTEXT):
        raise ValueError("Identidades de viaje nulas")
    indices = context.column("validated_row_index").to_numpy(zero_copy_only=False)
    identifiers = context.column("source_feature_id").to_pylist()
    if (
        indices.dtype.kind not in "iu"
        or np.any(indices < 0)
        or any(
            not isinstance(value, str)
            or len(value) != 32
            or any(c not in "0123456789abcdef" for c in value)
            for value in identifiers
        )
    ):
        raise ValueError("Identidades de viaje invalidas")
    sources = np.asarray(identifiers, dtype="U32")
    return indices, sources


def check_unique(context, previous):
    indices, sources = identity_arrays(context)
    for source in np.unique(sources):
        selected = indices[sources == source]
        if selected[0] <= previous.get(source, -1) or np.any(np.diff(selected) <= 0):
            raise ValueError("Identidad de viaje repetida o desordenada")
        previous[source] = int(selected[-1])


def frozen_model(config, root):
    """Verificar aprobacion y pesos antes de pickle; nunca ajustar ni registrar."""
    import joblib

    from src.training.champion import read_approval, resolve_champion, verify_evidence

    verify_model_runtime(config, root)
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
    approval_path = pinned(root, config["champion_approval"])
    decision = read_approval(approval_path)
    verify_evidence(decision, root, test_only=False)
    identity = resolve_champion(approval_path, root=root)
    path = pinned(root, config["model"])
    if identity.model_sha256 != config["model"]["sha256"]:
        raise ValueError("Modelo distinto del champion aprobado")
    model = joblib.load(path)
    expected = config["model"]["sha256"]
    from src.features.build import feature_values

    sample = np.asarray([feature_values(payload) for payload in decision["smoke"]["payloads"]])
    direct = model.named_steps["estimator"].predict(model.named_steps["native"].transform(sample))
    if not np.allclose(direct, decision["smoke"]["expected_minutes"], rtol=0, atol=1e-10):
        raise ValueError("Predicciones no coinciden con el smoke aprobado T19")

    def predict(values):
        encoded = model.named_steps["native"].transform(values)
        return model.named_steps["estimator"].predict_with_diagnostics(encoded)

    def verify():
        verify_model_runtime(config, root)
        if _sha256(path) != expected or resolve_champion(approval_path, root=root) != identity:
            raise ValueError("Champion cambio durante el replay")
        pinned(root, config["champion_approval"])

    return (
        predict,
        {
            "name": identity.name,
            "version": identity.version,
            "run_id": identity.run_id,
            "model_sha256": expected,
            "approval_sha256": identity.approval_sha256,
            "frozen_runtime_and_t19_smoke_verified": True,
        },
        verify,
    )


def verify_model_runtime(config, root):
    key = "windows" if os.name == "nt" else "linux"
    path = pinned(root, config["model_runtime_locks"][key])
    versions = re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", path.read_text("utf-8"), re.MULTILINE)
    if not versions:
        raise ValueError("Lock de prediccion vacio")
    for name, expected in versions:
        if importlib.metadata.version(name) != expected:
            raise ValueError(f"Runtime congelado del modelo incompatible: {name}")


class PredictionRows:
    """Unir por identidad sin depender de limites de row groups de Parquet."""

    def __init__(self, parquet):
        self.stream = iter(parquet.iter_batches(batch_size=4096, use_threads=False))
        self.pending = None

    def take(self, count):
        pieces = []
        while count:
            if self.pending is None:
                self.pending = next(self.stream, None)
            if self.pending is None:
                raise ValueError("Predicciones incompletas")
            size = min(count, self.pending.num_rows)
            pieces.append(self.pending.slice(0, size))
            self.pending = self.pending.slice(size) if size < self.pending.num_rows else None
            count -= size
        return pa.Table.from_batches(pieces).combine_chunks()

    def has_remaining(self):
        return self.pending is not None or next(self.stream, None) is not None


def verify_segment_sources(root, manifest, year, month):
    from src.monitoring.protocol import inside

    for entry in manifest["inputs"]:
        if (entry["year"], entry["month"]) != (year, month):
            continue
        folder = inside(root, entry["validated_directory"])
        marker = folder / "validation.json"
        if _sha256(marker) != entry["verified"]["feature"]["validation_manifest_sha256"]:
            raise ValueError("Linaje de destinos validado alterado")
        report = read_json(marker)
        path = folder / "data.parquet"
        if _sha256(path) != report["output"]["sha256"] or not report["data_quality_approved"]:
            raise ValueError("Destinos no corresponden a la fuente aprobada")


def make_predictions(config, root, guard, year, month, output, predict, identity):
    directory, manifest = source_manifest(config, root)
    test_only = config["status"] == "TEST_ONLY"
    verify_tables(
        directory, manifest, "monitoring_replay", ("features", "context"), test_only=test_only
    )
    schema = pa.schema(
        [(name, pa.int64()) for name in FEATURE_COLUMNS]
        + [
            ("validated_row_index", pa.int64()),
            ("pickup_datetime_utc", pa.timestamp("us", "UTC")),
            ("source_feature_id", pa.string()),
            ("partition_row_index", pa.int64()),
            ("predicted_duration_minutes", pa.float64()),
        ],
        metadata={
            b"scope": config["status"].encode(),
            b"model_sha256": identity["model_sha256"].encode(),
            b"split_sha256": config["split"]["sha256"].encode(),
            b"prediction_features": fingerprint(list(FEATURE_COLUMNS)).encode(),
        },
    )
    if output.exists():
        raise ValueError("No sobrescribir predicciones")
    count = scanned = clipped = 0
    previous = {}
    digest = hashlib.sha256()
    with pq.ParquetWriter(output, schema) as writer:
        for features, context in batches(
            directory,
            "monitoring_replay",
            ("features", "context"),
            guard,
            batch_size=4096,
            context_columns=PREDICTION_CONTEXT,
        ):
            mask = time_mask(context, year, month)
            offset = scanned
            scanned += features.num_rows
            if not mask.any():
                continue
            features, context = features.filter(mask), context.filter(mask)
            values = feature_array(features)
            if np.any(values[:, 3] != month):
                raise ValueError("Calendario de features no coincide con cohorte UTC/NY")
            check_unique(context, previous)
            predicted, changed = predict(values)
            predicted = np.asarray(predicted, dtype=np.float64)
            if predicted.shape != (len(values),) or not np.all(
                np.isfinite(predicted) & (predicted >= 1 / 60) & (predicted <= 180)
            ):
                raise ValueError("Predicciones fuera de contrato")
            indices = np.flatnonzero(mask).astype(np.int64) + offset
            arrays = [*features.columns, *context.columns, pa.array(indices), pa.array(predicted)]
            writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
            digest.update(indices.astype("<i8").tobytes())
            count += len(predicted)
            clipped += int(changed)
    if scanned != manifest["partitions"]["monitoring_replay"]["rows"] or not count:
        raise ValueError("Prediccion mensual vacia/no exhaustiva")
    verify_tables(
        directory, manifest, "monitoring_replay", ("features", "context"), test_only=test_only
    )
    return {
        **envelope(config),
        "path": str(output.relative_to(root)),
        "sha256": _sha256(output),
        "rows": count,
        "source_rows_scanned": scanned,
        "partition_indices_sha256": digest.hexdigest(),
        "clipped_predictions": clipped,
        "model": identity,
        "labels_read_for_prediction": False,
        "year": year,
        "month": month,
    }


def evaluate_predictions(config, root, guard, prediction, scratch, *, labels_available=True):
    if any(prediction.get(key) != value for key, value in envelope(config).items()):
        raise ValueError("Predicciones de otro split o configuracion")
    path = pinned(root, prediction)
    expected = prediction["rows"]
    result = {
        "status": "NOT_AVAILABLE",
        "expected_rows": expected,
        "observed_label_rows": 0,
        "pending_label_rows": expected,
        "coverage_ratio": 0.0,
        "metrics": None,
        "label_cutoff_utc": maturity_cutoff(prediction["year"], prediction["month"]).isoformat(),
        "publication_availability": "NOT_ASSERTED_RETROSPECTIVE_EVENT_TIME_ONLY",
        "retraining_decision": "NOT_EVALUATED_T32",
    }
    if not labels_available:
        result["reason"] = "LABELS_NOT_PROVIDED"
        return result
    directory, manifest = source_manifest(config, root)
    test_only = config["status"] == "TEST_ONLY"
    verify_tables(
        directory, manifest, "monitoring_replay", ("target", "context"), test_only=test_only
    )
    evaluation = read_json(pinned(root, config["validation_evaluation"]))
    routes = evaluation["route_catalog"]
    if routes["selection_scope"] != "validation_frequency_only":
        raise ValueError("Rutas no congeladas con validacion")
    selected = [row["code"] for row in routes["routes"]]
    verify_segment_sources(root, manifest, prediction["year"], prediction["month"])
    store = ErrorStore(scratch)
    matched = observed = scanned = 0
    previous = {}
    with ExitStack() as stack:
        parquet = stack.enter_context(pq.ParquetFile(path))
        segments = stack.enter_context(SegmentRows(manifest, "monitoring_replay"))
        predictions = PredictionRows(parquet)
        for target, context in batches(
            directory, "monitoring_replay", ("target", "context"), guard, batch_size=4096
        ):
            mask = time_mask(context, prediction["year"], prediction["month"])
            offset = scanned
            scanned += target.num_rows
            if not mask.any():
                continue
            predicted = predictions.take(int(mask.sum()))
            context, target = context.filter(mask), target.filter(mask)
            check_unique(context, previous)
            indices, sources = identity_arrays(context)
            other_indices, other_sources = identity_arrays(predicted)
            if (
                not np.array_equal(indices, other_indices)
                or not np.array_equal(sources, other_sources)
                or not np.array_equal(
                    predicted.column("partition_row_index").to_numpy(),
                    np.flatnonzero(mask) + offset,
                )
                or not predicted.column("pickup_datetime_utc")
                .combine_chunks()
                .equals(context.column("pickup_datetime_utc"))
            ):
                raise ValueError("Predicciones/etiquetas no corresponden a las mismas identidades")
            matched += len(indices)
            y = target.column(0).to_numpy(zero_copy_only=False)
            event = context.column("label_event_datetime_utc").to_numpy(zero_copy_only=False)
            cutoff = maturity_cutoff(prediction["year"], prediction["month"])
            available = (
                np.isfinite(y)
                & ~np.isnat(event)
                & (event <= np.datetime64(cutoff.replace(tzinfo=None), "us"))
            )
            if not available.any():
                continue
            y = y[available]
            if np.any((y <= 0) | (y > 180)):
                raise ValueError("Etiqueta fuera del contrato aprobado")
            values = np.column_stack(
                [predicted.column(name).to_numpy() for name in FEATURE_COLUMNS]
            )
            values, context = values[available], context.filter(available)
            prediction_values = predicted.column("predicted_duration_minutes").to_numpy()[available]
            codes = segments.route_codes(values, context)
            store.add(y, prediction_values, group_masks(values, codes, selected))
            observed += len(y)
        if predictions.has_remaining() or matched != expected:
            raise ValueError("Predicciones/etiquetas sin cobertura exacta")
    if scanned != manifest["partitions"]["monitoring_replay"]["rows"]:
        raise ValueError("Lectura de etiquetas incompleta")
    metrics = store.results(resource_check=guard.check) if observed else None
    result.update(
        status="OBSERVED"
        if observed == expected
        else "PARTIAL_LABELS"
        if observed
        else "NOT_AVAILABLE",
        observed_label_rows=observed,
        pending_label_rows=expected - observed,
        coverage_ratio=observed / expected,
        metrics=metrics,
        validation_mae_minutes=evaluation["metrics"]["all"]["mae_minutes"],
        mae_ratio_to_frozen_validation=None
        if not observed
        else metrics["all"]["mae_minutes"] / evaluation["metrics"]["all"]["mae_minutes"],
    )
    verify_tables(
        directory, manifest, "monitoring_replay", ("target", "context"), test_only=test_only
    )
    verify_segment_sources(root, manifest, prediction["year"], prediction["month"])
    pinned(root, prediction)
    return result
