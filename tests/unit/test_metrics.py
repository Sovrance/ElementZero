import math

import pytest

from elementzero.benchmark.metrics import (
    NOMINAL_90,
    NOMINAL_95,
    calibration_error,
    coverage,
    gaussian_nlpd_term,
    group_metrics,
    mae_keV,
    medae_keV,
    nlpd,
    rmse_keV,
    score_rows,
)


def _row(nid, mu, truth, sigma):
    return {
        "nuclide_id": nid,
        "prediction_keV": mu,
        "truth_keV": truth,
        "std_keV": sigma,
        "interval_p90": [mu - 1.6448536269514722 * sigma, mu + 1.6448536269514722 * sigma],
        "interval_p95": [mu - 1.959963984540054 * sigma, mu + 1.959963984540054 * sigma],
    }


def test_point_error_metrics():
    preds = [0.0, 0.0, 0.0, 0.0]
    truth = [1.0, -1.0, 3.0, -9.0]
    assert mae_keV(preds, truth) == pytest.approx((1 + 1 + 3 + 9) / 4)
    assert medae_keV(preds, truth) == pytest.approx(2.0)
    assert rmse_keV(preds, truth) == pytest.approx(math.sqrt((1 + 1 + 9 + 81) / 4))


def test_gaussian_nlpd_known_values():
    # sigma = 1, zero residual: NLPD = 0.5*log(2*pi)
    assert gaussian_nlpd_term(prediction=0.0, truth=0.0, std=1.0) == pytest.approx(
        0.9189385332046727
    )
    # sigma = 1, residual = 1: previous value + 0.5
    assert gaussian_nlpd_term(prediction=0.0, truth=1.0, std=1.0) == pytest.approx(
        1.4189385332046727
    )
    # sigma = 2, zero residual: 0.5*log(2*pi*4)
    assert gaussian_nlpd_term(prediction=5.0, truth=5.0, std=2.0) == pytest.approx(
        0.5 * math.log(2.0 * math.pi * 4.0)
    )
    assert nlpd([0.0, 0.0], [0.0, 1.0], [1.0, 1.0]) == pytest.approx(
        (0.9189385332046727 + 1.4189385332046727) / 2
    )
    with pytest.raises(ValueError):
        gaussian_nlpd_term(prediction=0.0, truth=0.0, std=0.0)


def test_calibration_error():
    assert calibration_error(0.9, NOMINAL_90) == pytest.approx(0.0)
    assert calibration_error(0.5, NOMINAL_90) == pytest.approx(0.4)
    assert calibration_error(1.0, NOMINAL_95) == pytest.approx(0.05)
    assert calibration_error(0.0, NOMINAL_95) == pytest.approx(0.95)


def test_coverage_counts_closed_intervals():
    assert coverage([0.0, 10.0], [[-1.0, 1.0], [-1.0, 1.0]]) == pytest.approx(0.5)
    assert coverage([1.0], [[-1.0, 1.0]]) == pytest.approx(1.0)


def test_score_rows_reports_all_v03_metrics():
    rows = [_row("Z18-N19", 0.0, 1.0, 10.0), _row("Z19-N20", 0.0, -3.0, 10.0)]
    metrics = score_rows(rows)
    assert set(metrics) == {
        "n",
        "MAE_keV",
        "MedAE_keV",
        "RMSE_keV",
        "NLPD",
        "coverage_90",
        "coverage_95",
        "cal_error_90",
        "cal_error_95",
    }
    assert metrics["n"] == 2
    assert metrics["MAE_keV"] == pytest.approx(2.0)
    assert metrics["coverage_90"] == pytest.approx(1.0)
    assert metrics["cal_error_90"] == pytest.approx(0.1)


def test_badly_calibrated_model_is_not_hidden():
    """Tiny sigma buys low RMSE nothing: coverage, NLPD, and calibration all flag it."""
    honest = [_row("Z18-N19", 0.0, 1.0, 10.0), _row("Z19-N20", 0.0, -1.0, 10.0)]
    overconfident = [_row("Z18-N19", 0.0, 1.0, 0.001), _row("Z19-N20", 0.0, -1.0, 0.001)]
    honest_metrics = score_rows(honest)
    bad_metrics = score_rows(overconfident)
    # Identical point accuracy ...
    assert bad_metrics["MAE_keV"] == pytest.approx(honest_metrics["MAE_keV"])
    assert bad_metrics["RMSE_keV"] == pytest.approx(honest_metrics["RMSE_keV"])
    # ... but the uncertainty metrics expose the overconfidence.
    assert bad_metrics["coverage_90"] == pytest.approx(0.0)
    assert bad_metrics["coverage_95"] == pytest.approx(0.0)
    assert bad_metrics["cal_error_90"] == pytest.approx(0.9)
    assert bad_metrics["cal_error_95"] == pytest.approx(0.95)
    assert bad_metrics["NLPD"] > honest_metrics["NLPD"] * 1000


def test_group_metrics_reports_empty_group_as_zero_n():
    empty = group_metrics([])
    assert empty["n"] == 0
    assert empty["MAE_keV"] is None
    assert empty["NLPD"] is None
    filled = group_metrics([_row("Z18-N19", 0.0, 1.0, 10.0)])
    assert filled["n"] == 1
    assert filled["MAE_keV"] == pytest.approx(1.0)
