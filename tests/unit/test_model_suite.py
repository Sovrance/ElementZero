import pytest

from elementzero.benchmark.model_suite import (
    COMPARISON_COLUMNS,
    MODEL_SUITE_ID,
    RANKING_RULE,
    SUITE_MODEL_IDS,
    build_comparison,
    comparison_markdown,
    model_suite_manifest,
    suite_manifest_hash,
)
from elementzero.errors import ProtocolError


def _report(model_id, *, mae, medae, rmse, nlpd_value, cov90, cov95):
    return {
        "model_id": model_id,
        "run_id": model_id,
        "freeze_id": "frz_shared",
        "truth_source_hash": "ab" * 32,
        "validation_fact_id": f"fct_{model_id}",
        "metrics": {
            "n": 3,
            "MAE_keV": mae,
            "MedAE_keV": medae,
            "RMSE_keV": rmse,
            "NLPD": nlpd_value,
            "coverage_90": cov90,
            "coverage_95": cov95,
            "cal_error_90": abs(cov90 - 0.90),
            "cal_error_95": abs(cov95 - 0.95),
            "distance_buckets": {"d=1": {"n": 0}},
            "regions": {"light": {"n": 3}},
        },
    }


def _reports():
    return [
        _report("EZ-SEMF-LS-v1", mae=900.0, medae=880.0, rmse=1000.0, nlpd_value=1e6,
                cov90=0.0, cov95=0.0),
        _report("EZ-GP-DIRECT-v1", mae=14000.0, medae=13500.0, rmse=15000.0, nlpd_value=16.0,
                cov90=1.0, cov95=1.0),
        _report("EZ-SEMF-GP-RESIDUAL-v1", mae=500.0, medae=480.0, rmse=600.0, nlpd_value=42.0,
                cov90=0.9, cov95=0.95),
    ]


def test_model_suite_manifest_is_frozen_and_ordered():
    manifest = model_suite_manifest()
    assert manifest["model_suite_id"] == MODEL_SUITE_ID
    assert manifest["model_ids"] == [
        "EZ-SEMF-LS-v1",
        "EZ-GP-DIRECT-v1",
        "EZ-SEMF-GP-RESIDUAL-v1",
    ]
    assert list(SUITE_MODEL_IDS) == manifest["model_ids"]
    assert manifest["ranking_rule"] == RANKING_RULE
    # The manifest hash is content-addressed and order sensitive.
    assert suite_manifest_hash(manifest) == suite_manifest_hash(model_suite_manifest())
    reordered = model_suite_manifest(
        model_ids=["EZ-GP-DIRECT-v1", "EZ-SEMF-LS-v1", "EZ-SEMF-GP-RESIDUAL-v1"]
    )
    assert suite_manifest_hash(reordered) != suite_manifest_hash(manifest)
    with pytest.raises(ValueError):
        model_suite_manifest(model_ids=["EZ-SEMF-LS-v1", "EZ-SEMF-LS-v1"])


def test_model_comparison_contains_all_models():
    suite = model_suite_manifest()
    comparison = build_comparison(_reports(), suite=suite)
    assert [row["model_id"] for row in comparison["rows"]] == suite["model_ids"]
    assert comparison["columns"] == list(COMPARISON_COLUMNS)
    assert comparison["ranking_rule"] == RANKING_RULE
    for row in comparison["rows"]:
        for column in COMPARISON_COLUMNS:
            assert column in row
    markdown = comparison_markdown(comparison)
    for model_id in suite["model_ids"]:
        assert model_id in markdown
    assert "calibration_error_95" in markdown
    # No model is crowned by a single metric.
    assert "best_model" not in comparison
    assert comparison["ranking_rule"].startswith("none")


def test_model_comparison_refuses_to_drop_a_scored_model():
    suite = model_suite_manifest()
    partial = [r for r in _reports() if r["model_id"] != "EZ-GP-DIRECT-v1"]
    with pytest.raises(ProtocolError):
        build_comparison(partial, suite=suite)


def test_model_comparison_requires_one_freeze_and_one_truth_source():
    reports = _reports()
    reports[1]["freeze_id"] = "frz_other"
    with pytest.raises(ProtocolError):
        build_comparison(reports, suite=model_suite_manifest())
    reports = _reports()
    reports[2]["truth_source_hash"] = "cd" * 32
    with pytest.raises(ProtocolError):
        build_comparison(reports, suite=model_suite_manifest())


def test_badly_calibrated_model_stays_in_the_comparison():
    comparison = build_comparison(_reports(), suite=model_suite_manifest())
    row = next(r for r in comparison["rows"] if r["model_id"] == "EZ-SEMF-LS-v1")
    assert row["coverage_90"] == 0.0
    assert row["calibration_error_90"] == pytest.approx(0.9)
    assert "EZ-SEMF-LS-v1" in comparison_markdown(comparison)
