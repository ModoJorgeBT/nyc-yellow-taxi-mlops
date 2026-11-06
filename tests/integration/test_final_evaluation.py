"""Holdout 2026 sintético: cortes, tres modelos congelados y ninguna selección."""

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.evaluation.final_data import prepare_final, read_final_profile
from src.evaluation.final_run import Destinations, evaluate_final, segment_masks
from src.features.artifacts import build_validated_features
from src.training.baseline import run_baseline
from src.training.lightgbm_train import train_lightgbm
from src.training.train import train_candidates
from src.validation.run import _sha256
from src.validation.schema import fingerprint
from tests.fixtures.factory import make_table
from tests.integration.test_candidates import prepared
from tests.integration.test_feature_pipeline import validated_fixture


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("independent-final")
    source, _ = prepared(root / "old", large_train=True)
    trained = train_candidates(
        source, output_dir=root / "sgd", report_dir=root / "sgd-reports", test_only=True
    )
    boosted = train_lightgbm(
        source, output_dir=root / "lgb", report_dir=root / "lgb-reports", test_only=True
    )
    baseline = run_baseline(
        source,
        output_dir=root / "baseline",
        report_dir=root / "baseline-reports",
        scratch_dir=root / "median",
        test_only=True,
    )
    assert all(r["publication_complete"] for r in (trained, boosted, baseline))
    profile = copy.deepcopy(
        json.loads(Path("configs/lightgbm-final-evaluation.yaml").read_text(encoding="utf-8"))
    )
    profile.update(approval_status="TEST_ONLY", fixture_origin="synthetic")
    paths = {
        "sgd": Path(trained["output_directory"]) / "sgd.joblib",
        "lightgbm": Path(boosted["output_directory"]) / "lightgbm.joblib",
        "baseline": Path(baseline["output_directory"]) / "model.json",
    }
    profile["models"] = {
        name: {"path": str(path), "sha256": _sha256(path)} for name, path in paths.items()
    }
    profile["route_catalog"]["routes"] = []
    profile_path = root / "profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    batches = []
    template = make_table()
    base = template.to_pylist()[0]
    for month in (1, 2, 3):
        rows = []
        for i in range(3):
            pickup = datetime(2026, month, 15, 8, i)
            rows.append(
                {
                    **base,
                    "tpep_pickup_datetime": pickup,
                    "tpep_dropoff_datetime": pickup + timedelta(minutes=5 + i),
                }
            )
        if month == 3:
            rows.append(
                {
                    **base,
                    "tpep_pickup_datetime": datetime(2026, 3, 31, 23, 59),
                    "tpep_dropoff_datetime": datetime(2026, 4, 1),
                }
            )
        validated = validated_fixture(
            root / f"new-{month}",
            pa.Table.from_pylist(rows, schema=template.schema),
            year=2026,
            month=month,
        )
        features = build_validated_features(
            validated, processed_dir=root / f"features-{month}", test_only=True
        )
        batches.append(
            {
                "year": 2026,
                "month": month,
                "features_directory": features["output_directory"],
                "validated_directory": str(validated),
            }
        )
    catalog = root / "catalog.json"
    catalog.write_text(json.dumps({"format_version": 1, "batches": batches}))
    return root, source, catalog, profile_path


def test_cohort_cut_exactly_at_april_and_block_size_reproducibility(inputs, tmp_path):
    _, _, catalog, profile = inputs
    results = [
        prepare_final(
            catalog,
            profile_path=profile,
            output_dir=tmp_path / f"out-{size}",
            report_dir=tmp_path / f"reports-{size}",
            test_only=True,
            batch_size=size,
        )
        for size in (2, 65536)
    ]
    for result in results:
        assert result["publication_complete"], result.get("error")
        assert result["rows"] == 9
        assert sum(m["cutoff_excluded"] for m in result["monthly"]) == 1
        assert result["monthly"][-1]["feature_rows"] == 4
        assert not result["models_fitted"] and not result["approved_for_training"]
    assert results[0]["target_sha256"] == results[1]["target_sha256"]
    for name in ("features", "target", "context"):
        tables = [pq.read_table(Path(r["output_directory"]) / f"{name}.parquet") for r in results]
        assert tables[0].equals(tables[1])


def test_final_uses_only_new_cohort_no_fit_and_no_selection(inputs, tmp_path, monkeypatch):
    from src.training.lightgbm_model import BoundedBooster, NativeFeatures
    from src.training.models import BoundedRegressor

    _, old_source, catalog, profile = inputs
    held = prepare_final(
        catalog,
        profile_path=profile,
        output_dir=tmp_path / "held",
        report_dir=tmp_path / "held-reports",
        test_only=True,
    )
    assert held["publication_complete"], held.get("error")
    actual_open = Path.open

    def guarded(path, *args, **kwargs):
        if path.resolve().is_relative_to(old_source):
            pytest.fail("La evaluación final no abre particiones originales")
        return actual_open(path, *args, **kwargs)

    def no_fit(*args, **kwargs):
        pytest.fail("No se ajusta ningún modelo ni vocabulario con el holdout")

    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr(BoundedRegressor, "partial_fit", no_fit)
    monkeypatch.setattr(BoundedBooster, "fit", no_fit)
    monkeypatch.setattr(NativeFeatures, "fit", no_fit)
    result = evaluate_final(
        Path(held["output_directory"]),
        profile_path=profile,
        output_dir=tmp_path / "eval",
        report_dir=tmp_path / "reports",
        test_only=True,
    )
    assert result["publication_complete"], result.get("error")
    assert not any(
        result[key]
        for key in (
            "models_fitted",
            "selection_changed",
            "model_registered",
            "approved_for_serving",
            "original_test_reused",
            "replay_reused",
        )
    )
    assert "recommended_model" not in result
    for name, item in result["results"].items():
        assert item["rows"] == 9 and item["target_sha256"] == held["target_sha256"]
        assert set(k for k in item["metrics"] if k.startswith("month_")) == {
            "month_2026_01",
            "month_2026_02",
            "month_2026_03",
        }
        predicted = (
            pq.read_table(Path(result["output_directory"]) / f"{name}.parquet").column(1).to_numpy()
        )
        y = pq.read_table(Path(held["output_directory"]) / "target.parquet").column(0).to_numpy()
        errors = np.abs(y - predicted)
        assert item["metrics"]["all"]["mae_minutes"] == pytest.approx(errors.mean())
        assert item["metrics"]["all"]["medae_minutes"] == pytest.approx(np.median(errors))
        assert item["metrics"]["all"]["p90_absolute_error_minutes"] == pytest.approx(
            np.quantile(errors, 0.9)
        )
    duplicate = evaluate_final(
        Path(held["output_directory"]),
        profile_path=profile,
        output_dir=tmp_path / "eval",
        report_dir=tmp_path / "reports",
        test_only=True,
    )
    assert duplicate["status"] == "FAIL" and not duplicate["publication_complete"]


def test_missing_month_and_unauthorized_period_are_blocked(inputs, tmp_path):
    _, _, catalog, profile = inputs
    value = json.loads(catalog.read_text())
    value["batches"].pop()
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="tres meses"):
        prepare_final(
            missing,
            profile_path=profile,
            output_dir=tmp_path / "out",
            report_dir=tmp_path / "reports",
            test_only=True,
        )
    value = json.loads(profile.read_text())
    value["period"]["year"] = 2025
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Periodo"):
        read_final_profile(bad, test_only=True)
    with pytest.raises(ValueError, match="distinta"):
        read_final_profile(profile, test_only=False)


def test_heldout_corruption_blocks_before_prediction(inputs, tmp_path):
    _, _, catalog, profile = inputs
    held = prepare_final(
        catalog,
        profile_path=profile,
        output_dir=tmp_path / "held",
        report_dir=tmp_path / "held-reports",
        test_only=True,
    )
    folder = Path(held["output_directory"])
    with (folder / "features.parquet").open("ab") as stream:
        stream.write(b"corrupt")
    result = evaluate_final(
        folder,
        profile_path=profile,
        output_dir=tmp_path / "eval",
        report_dir=tmp_path / "reports",
        test_only=True,
    )
    assert result["status"] == "FAIL" and not result["publication_complete"]
    assert not list((tmp_path / "reports").rglob("reservations/*.json"))


def test_unknown_destination_stays_in_other_group(tmp_path):
    file = tmp_path / "validated"
    file.mkdir()
    pq.write_table(
        pa.table({"DOLocationID": pa.array([None, 237], type=pa.int64())}), file / "data.parquet"
    )
    identity = "a" * 32
    entries = [
        {"verified": {"feature": {"feature_id": identity}}, "validated_directory": str(file)}
    ]
    context = pa.record_batch(
        [pa.array([0, 1]), pa.array([1, 1]), pa.array([2, 2]), pa.array([identity, identity])],
        names=["i", "p", "l", "id"],
    )
    X = np.array([[161, 8, 1, 1, 1, 0], [161, 9, 1, 1, 1, 0]])
    with Destinations(entries, [161, 237]) as reader:
        codes, unknown = reader.codes(X, context)
    assert unknown == 1
    masks = segment_masks(X, codes, [161237], year=2026)
    np.testing.assert_array_equal(masks["route_other"], [True, False])
    assert "month_2026_01" in masks and not any(k.startswith("month_2025") for k in masks)


def test_resource_failure_retry_preserves_first_reservation_and_models(
    inputs, tmp_path, monkeypatch
):
    from src.evaluation import final_run
    from src.training.resources import ResourceLimitError

    _, _, catalog, profile_path = inputs
    held = prepare_final(
        catalog,
        profile_path=profile_path,
        output_dir=tmp_path / "held",
        report_dir=tmp_path / "held-reports",
        test_only=True,
    )
    source = Path(held["output_directory"])
    original_check = final_run.CandidateGuard.check
    starts = []

    def fail_third(self, *, start=False):
        if start:
            starts.append(True)
            if len(starts) == 4:
                raise ResourceLimitError("D-02: available_ram_bytes=1; limite=8589934592")
        return original_check(self, start=start)

    monkeypatch.setattr(final_run.CandidateGuard, "check", fail_third)
    failed = evaluate_final(
        source,
        profile_path=profile_path,
        output_dir=tmp_path / "eval",
        report_dir=tmp_path / "reports",
        test_only=True,
    )
    assert failed["status"] == "FAIL" and failed["completed_candidates"] == ["baseline", "sgd"]
    failed_path = tmp_path / "reports" / "_test_only" / f"{failed['evaluation_id']}.json"
    reservation = next((tmp_path / "reports").rglob("reservations/*.json"))
    initial_sha = _sha256(reservation)
    profile = json.loads(profile_path.read_text())
    hashes = {name: _sha256(Path(info["path"])) for name, info in profile["models"].items()}
    configuration = {
        "approval_status": "TEST_ONLY",
        "fixture_origin": "synthetic",
        "scope": "frozen_independent_final_inference_only",
        "base_profile_sha256": fingerprint(profile),
        "holdout_manifest_sha256": _sha256(source / "holdout_manifest.json"),
        "failed_report_sha256": _sha256(failed_path),
        "resources": json.loads(Path("configs/lightgbm-final-resources.yaml").read_text())[
            "resources"
        ],
    }
    review = tmp_path / "review.json"
    review.write_text(json.dumps(configuration))
    monkeypatch.setattr(final_run.CandidateGuard, "check", original_check)
    retried = evaluate_final(
        source,
        profile_path=profile_path,
        output_dir=tmp_path / "eval",
        report_dir=tmp_path / "reports",
        test_only=True,
        resource_review_path=review,
        retry_of=failed_path,
    )
    assert retried["publication_complete"], retried.get("error")
    assert retried["retry_of"]["evaluation_id"] == failed["evaluation_id"]
    assert retried["effective_evaluation_resources"]["process_rss_limit_gib"] == 2
    assert len(list((tmp_path / "reports").rglob("reservations/*.json"))) == 2
    assert _sha256(reservation) == initial_sha
    assert hashes == {name: _sha256(Path(info["path"])) for name, info in profile["models"].items()}
    duplicate = evaluate_final(
        source,
        profile_path=profile_path,
        output_dir=tmp_path / "eval",
        report_dir=tmp_path / "reports",
        test_only=True,
        resource_review_path=review,
        retry_of=failed_path,
    )
    assert duplicate["status"] == "FAIL" and not duplicate["publication_complete"]
