"""Mediana exacta fuera de memoria; no usa datasets TLC."""

import math

import pyarrow as pa
import pytest

from src.training.baseline import exact_disk_median
from src.training.split import SplitError


def batches(values, size=2):
    return pa.table({"trip_duration_minutes": pa.array(values, type=pa.float64())}).to_batches(
        max_chunksize=size
    )


@pytest.mark.parametrize(
    "values,expected",
    [
        ([9.0, 1.0, 7.0, 3.0], 5.0),
        ([1.0, 1.0, 100.0, 2.0, 3.0], 2.0),
        ([42.0], 42.0),
        ([1.0, 90.0, 2.0, 3.0, 4.0, 5.0], 3.5),
    ],
)
def test_global_median_not_median_of_block_medians(tmp_path, values, expected):
    first = exact_disk_median(batches(values, 1), scratch_dir=tmp_path)
    second = exact_disk_median(batches(values[::-1], 4), scratch_dir=tmp_path)
    assert first["median_minutes"] == second["median_minutes"] == expected
    assert first["train_rows"] == len(values)
    assert first["sqlite_file_peak_bytes"] > 0
    assert not list(tmp_path.glob("median-*"))


@pytest.mark.parametrize("values", [[], [0.0], [-1.0], [None], [math.nan], [math.inf]])
def test_invalid_training_targets_do_not_publish_or_keep_database(tmp_path, values):
    with pytest.raises(SplitError):
        exact_disk_median(batches(values), scratch_dir=tmp_path)
    assert not list(tmp_path.glob("median-*"))


def test_resource_abort_releases_sqlite_and_temporary_directory(tmp_path):
    def fail():
        raise RuntimeError("budget exceeded")

    with pytest.raises(RuntimeError, match="budget"):
        exact_disk_median(batches([1.0, 2.0]), scratch_dir=tmp_path, resource_check=fail)
    assert not list(tmp_path.glob("median-*"))


def test_resource_abort_during_native_sort_is_preserved(tmp_path):
    calls = 0

    def exhausted():
        nonlocal calls
        calls += 1
        if calls >= 4:
            raise RuntimeError("native sort budget")

    values = [float(value) for value in range(20000, 0, -1)]
    with pytest.raises(RuntimeError, match="native sort budget"):
        exact_disk_median(
            batches(values, len(values)), scratch_dir=tmp_path, resource_check=exhausted
        )
    assert not list(tmp_path.glob("median-*"))
