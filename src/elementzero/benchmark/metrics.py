"""EZ-B001 scoring metrics (ASCII-first).

For predictions mu_i, truth y_i, predictive sigma_i:

    error_i     = mu_i - y_i
    MAE_keV     = mean(abs(error_i))
    MedAE_keV   = median(abs(error_i))
    RMSE_keV    = sqrt(mean(error_i^2))

    NLPD_i      = 0.5*log(2*pi*sigma_i^2) + 0.5*((y_i - mu_i)/sigma_i)^2
    NLPD        = mean(NLPD_i)

    coverage_90 = count(y_i inside interval_90_i) / n
    coverage_95 = count(y_i inside interval_95_i) / n

    cal_error_90 = abs(coverage_90 - 0.90)
    cal_error_95 = abs(coverage_95 - 0.95)

sigma_i comes from the sealed prediction file. It is never reconstructed from
truth and never re-derived from rounded intervals.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from typing import Any

NOMINAL_90 = 0.90
NOMINAL_95 = 0.95

# Metric keys reported for the whole run and for every distance/region group.
GROUP_METRIC_KEYS = (
    "n",
    "MAE_keV",
    "RMSE_keV",
    "coverage_90",
    "coverage_95",
    "NLPD",
)


def mae_keV(predictions: Sequence[float], truth: Sequence[float]) -> float:
    if not predictions:
        raise ValueError("no predictions")
    return sum(abs(p - t) for p, t in zip(predictions, truth)) / len(predictions)


def medae_keV(predictions: Sequence[float], truth: Sequence[float]) -> float:
    if not predictions:
        raise ValueError("no predictions")
    return float(statistics.median([abs(p - t) for p, t in zip(predictions, truth)]))


def rmse_keV(predictions: Sequence[float], truth: Sequence[float]) -> float:
    if not predictions:
        raise ValueError("no predictions")
    return math.sqrt(sum((p - t) ** 2 for p, t in zip(predictions, truth)) / len(predictions))


def gaussian_nlpd_term(*, prediction: float, truth: float, std: float) -> float:
    """One Gaussian negative log predictive density term."""
    if std <= 0.0:
        raise ValueError("predictive std must be positive to score NLPD")
    z = (truth - prediction) / std
    return 0.5 * math.log(2.0 * math.pi * std * std) + 0.5 * z * z


def nlpd(
    predictions: Sequence[float],
    truth: Sequence[float],
    stds: Sequence[float],
) -> float:
    if not predictions:
        raise ValueError("no predictions")
    terms = [
        gaussian_nlpd_term(prediction=p, truth=t, std=s)
        for p, t, s in zip(predictions, truth, stds)
    ]
    return sum(terms) / len(terms)


def coverage(truth: Sequence[float], intervals: Sequence[Sequence[float]]) -> float:
    if not truth:
        raise ValueError("no truth values")
    hits = 0
    for t, interval in zip(truth, intervals):
        lo, hi = float(interval[0]), float(interval[1])
        if lo <= t <= hi:
            hits += 1
    return hits / len(truth)


def calibration_error(observed_coverage: float, nominal: float) -> float:
    """abs(observed - nominal); a poorly calibrated model cannot hide here."""
    return abs(float(observed_coverage) - float(nominal))


def group_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Metrics for one group of scored rows; an empty group reports n = 0."""
    if not rows:
        return {
            "n": 0,
            "MAE_keV": None,
            "RMSE_keV": None,
            "coverage_90": None,
            "coverage_95": None,
            "NLPD": None,
        }
    preds = [float(r["prediction_keV"]) for r in rows]
    truth = [float(r["truth_keV"]) for r in rows]
    stds = [float(r["std_keV"]) for r in rows]
    return {
        "n": len(rows),
        "MAE_keV": mae_keV(preds, truth),
        "RMSE_keV": rmse_keV(preds, truth),
        "coverage_90": coverage(truth, [r["interval_p90"] for r in rows]),
        "coverage_95": coverage(truth, [r["interval_p95"] for r in rows]),
        "NLPD": nlpd(preds, truth, stds),
    }


def score_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    preds = [float(r["prediction_keV"]) for r in rows]
    truth = [float(r["truth_keV"]) for r in rows]
    stds = [float(r["std_keV"]) for r in rows]
    p90 = [r["interval_p90"] for r in rows]
    p95 = [r["interval_p95"] for r in rows]
    cov90 = coverage(truth, p90)
    cov95 = coverage(truth, p95)
    return {
        "n": len(rows),
        "MAE_keV": mae_keV(preds, truth),
        "MedAE_keV": medae_keV(preds, truth),
        "RMSE_keV": rmse_keV(preds, truth),
        "NLPD": nlpd(preds, truth, stds),
        "coverage_90": cov90,
        "coverage_95": cov95,
        "cal_error_90": calibration_error(cov90, NOMINAL_90),
        "cal_error_95": calibration_error(cov95, NOMINAL_95),
    }
