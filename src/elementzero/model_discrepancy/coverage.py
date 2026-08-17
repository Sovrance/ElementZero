"""Calibration metrics, reported by band and by extrapolation distance.

A single coverage number hides the failure that matters. A model can
sit at 0.90 overall while being badly overconfident exactly where it is
extrapolating — which, for a mass model aimed at the frontier, is the
only region anyone cares about. Every metric here is therefore also
reported per Z band and per extrapolation class.
"""

from __future__ import annotations

import math
from typing import Any

Z68 = 0.9944578832097535
Z90 = 1.6448536269514722
Z95 = 1.959963984540054

Z_BANDS = ((8, 40), (40, 70), (70, 100), (100, 140))


def z_band(z: int) -> str:
    for low, high in Z_BANDS:
        if low <= z < high:
            return f"Z{low}-{high}"
    return f"Z{Z_BANDS[-1][1]}+"


def calibration_metrics(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Coverage, calibration error, NLPD and standardized residuals.

    ``rows`` carry ``error_keV`` (prediction minus truth) and
    ``sigma_keV``. A row with a non-positive sigma is a defect, not a
    point to skip: it is counted and reported rather than dropped.
    """
    usable = [r for r in rows if float(r.get("sigma_keV") or 0.0) > 0.0]
    n_bad_sigma = len(rows) - len(usable)
    if not usable:
        return None
    z_scores = [float(r["error_keV"]) / float(r["sigma_keV"]) for r in usable]
    abs_err = sorted(abs(float(r["error_keV"])) for r in usable)
    n = len(z_scores)
    mean_z = sum(z_scores) / n
    var_z = sum((z - mean_z) ** 2 for z in z_scores) / n
    cov68 = sum(1 for z in z_scores if abs(z) <= Z68) / n
    cov90 = sum(1 for z in z_scores if abs(z) <= Z90) / n
    cov95 = sum(1 for z in z_scores if abs(z) <= Z95) / n
    nlpd = sum(
        0.5 * math.log(2.0 * math.pi * float(r["sigma_keV"]) ** 2)
        + 0.5 * (float(r["error_keV"]) / float(r["sigma_keV"])) ** 2
        for r in usable
    ) / n
    return {
        "n": n,
        "n_unusable_sigma": n_bad_sigma,
        "MAE_keV": sum(abs_err) / n,
        "RMSE_keV": math.sqrt(
            sum(float(r["error_keV"]) ** 2 for r in usable) / n
        ),
        "p95_abs_error_keV": _percentile(abs_err, 0.95),
        "max_abs_error_keV": abs_err[-1],
        "coverage_68": cov68,
        "coverage_90": cov90,
        "coverage_95": cov95,
        "calibration_error_90": abs(cov90 - 0.90),
        "NLPD": nlpd,
        "standardized_mean": mean_z,
        "standardized_std": math.sqrt(var_z),
    }


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation percentile on an already-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = int(math.floor(pos))
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac


def by_group(
    rows: list[dict[str, Any]], key: str
) -> dict[str, Any]:
    """Calibration metrics split by one row field."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(key, "UNKNOWN")), []).append(row)
    return {
        name: calibration_metrics(members)
        for name, members in sorted(groups.items())
    }


__all__ = [
    "Z68",
    "Z90",
    "Z95",
    "Z_BANDS",
    "by_group",
    "calibration_metrics",
    "z_band",
]
