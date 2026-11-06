"""Destino observado solo para segmentos; nunca se devuelve como predictor."""

from collections import Counter
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from src.training.candidate_runtime import read_batches


def choose_routes(counts, *, minimum=1000, maximum=20):
    return [
        int(key)
        for key in sorted(counts, key=lambda key: (-counts[key], key))
        if counts[key] >= minimum
    ][:maximum]


class DestinationRows:
    def __init__(self, parquet):
        self.batches = iter(
            parquet.iter_batches(columns=["DOLocationID"], batch_size=65536, use_threads=False)
        )
        self.start = 0
        self.current = None
        self.previous = -1

    def take(self, indices):
        if not len(indices) or indices[0] <= self.previous or np.any(np.diff(indices) <= 0):
            raise ValueError("Identidades de destino desordenadas o repetidas")
        result = np.empty(len(indices), dtype=np.int64)
        position = 0
        while position < len(indices):
            if self.current is None or indices[position] >= self.start + len(self.current):
                if self.current is not None:
                    self.start += len(self.current)
                batch = next(self.batches, None)
                if batch is None or batch.column(0).null_count:
                    raise ValueError("Destino ausente o fuente incompleta")
                self.current = batch.column(0).to_numpy()
                continue
            if indices[position] < self.start:
                raise ValueError("Indice de destino fuera de cobertura")
            end = int(np.searchsorted(indices, self.start + len(self.current)))
            result[position:end] = self.current[indices[position:end] - self.start]
            position = end
        self.previous = int(indices[-1])
        if np.any((result <= 0) | (result >= 1000)):
            raise ValueError("Destino incompatible con zonas del protocolo")
        return result


class SegmentRows:
    def __init__(self, manifest, partition):
        self.stack = ExitStack()
        self.readers = {}
        config = manifest["configuration"]["partitions"][partition]
        start, end = (config[key][:7] for key in ("start", "end"))
        self.entries = {
            entry["verified"]["feature"]["feature_id"]: entry
            for entry in manifest["inputs"]
            if start <= f"{entry['year']:04}-{entry['month']:02}" < end
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def route_codes(self, values, context):
        identities = np.asarray(context.column(3).to_pylist(), dtype="U32")
        indices = context.column(0).to_numpy()
        destinations = np.empty(len(values), dtype=np.int64)
        for identity in np.unique(identities):
            if identity not in self.entries:
                raise ValueError("Fuente de contexto fuera de la particion autorizada")
            if identity not in self.readers:
                path = Path(self.entries[identity]["validated_directory"]) / "data.parquet"
                parquet = self.stack.enter_context(pq.ParquetFile(path))
                self.readers[identity] = DestinationRows(parquet)
            mask = identities == identity
            destinations[mask] = self.readers[identity].take(indices[mask])
        return values[:, 0] * 1000 + destinations


def route_catalog(source, manifest, guard):
    counts = Counter()
    with SegmentRows(manifest, "validation") as segments:
        for values, _, context in read_batches(source, "validation", guard):
            keys, numbers = np.unique(segments.route_codes(values, context), return_counts=True)
            counts.update(
                {int(key): int(number) for key, number in zip(keys, numbers, strict=True)}
            )
    selected = choose_routes(counts)
    return {
        "selection_scope": "validation_frequency_only",
        "minimum_rows": 1000,
        "maximum_routes": 20,
        "routes": [
            {
                "code": code,
                "origin": code // 1000,
                "destination": code % 1000,
                "validation_rows": counts[code],
            }
            for code in selected
        ],
    }


def group_masks(values, routes, selected):
    masks = {
        f"month_2025_{int(month):02}": values[:, 3] == month for month in np.unique(values[:, 3])
    }
    bands = values[:, 1] // 6
    masks.update({f"band_{int(band)}": bands == band for band in np.unique(bands)})
    for code in selected:
        mask = routes == code
        if mask.any():
            masks[f"route_{code // 1000}_{code % 1000}"] = mask
    masks["route_other"] = ~np.isin(routes, selected)
    return masks
