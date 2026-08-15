"""EZ-B001 scoring metrics (ASCII-first).

    MAE_keV  = mean(abs(prediction - truth))
    RMSE_keV = sqrt(mean((prediction - truth)^2))
    coverage_90 = count(truth inside 90_percent_interval) / n
    coverage_95 = count(truth inside 95_percent_interval) / n
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


def mae_keV(predictions: Sequence[float], truth: Sequence[float]) -> float:
    if not predictions:
        raise ValueError("no predictions")
    return sum(abs(p - t) for p, t in zip(predictions, truth)) / len(predictions)


def rmse_keV(predictions: Sequence[float], truth: Sequence[float]) -> float:
    if not predictions:
        raise ValueError("no predictions")
    return math.sqrt(sum((p - t) ** 2 for p, t in zip(predictions, truth)) / len(predictions))


def coverage(truth: Sequence[float], intervals: Sequence[Sequence[float]]) -> float:
    if not truth:
        raise ValueError("no truth values")
    hits = 0
    for t, interval in zip(truth, intervals):
        lo, hi = float(interval[0]), float(interval[1])
        if lo <= t <= hi:
            hits += 1
    return hits / len(truth)


def score_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    preds = [float(r["prediction_keV"]) for r in rows]
    truth = [float(r["truth_keV"]) for r in rows]
    p90 = [r["interval_p90"] for r in rows]
    p95 = [r["interval_p95"] for r in rows]
    return {
        "n": len(rows),
        "MAE_keV": mae_keV(preds, truth),
        "RMSE_keV": rmse_keV(preds, truth),
        "coverage_90": coverage(truth, p90),
        "coverage_95": coverage(truth, p95),
    }
