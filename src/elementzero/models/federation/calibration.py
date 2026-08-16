"""Calibration splits and calibration metrics (WO-12 sections 13, 14, 17).

The three identity sets of every v2 qualification:

    fit_ids           observations models may fit on
    calibration_ids   held-out training observations used only to learn
                      ensemble weights / check sigma quality
    benchmark_target_ids   the hidden targets

Required invariants, asserted rather than assumed:

    fit_ids         ∩ benchmark_target_ids = ∅
    calibration_ids ∩ benchmark_target_ids = ∅
    fit_ids         ∩ calibration_ids     = ∅

All three sets are persisted as identity digests.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from typing import Any

from elementzero.data.observations import MassObservation
from elementzero.errors import LeakageError
from elementzero.evidence.freezes import identity_digest

CALIBRATION_SPLIT_POLICY_ID = "ez-wo12-calibration-split-v1"
CALIBRATION_SPLIT_RULE = (
    f"{CALIBRATION_SPLIT_POLICY_ID}: training observations are sorted by "
    "nuclide_id; every fifth (index % 5 == 0) forms the calibration set, the "
    "rest form the fit set. Deterministic, identity-only, and fixed before "
    "any qualification is scored."
)


def split_fit_calibration(
    observations: Sequence[MassObservation],
) -> tuple[list[MassObservation], list[MassObservation]]:
    ordered = sorted(observations, key=lambda o: o.nuclide_id)
    fit = [o for i, o in enumerate(ordered) if i % 5 != 0]
    calibration = [o for i, o in enumerate(ordered) if i % 5 == 0]
    return fit, calibration


def assert_split_disjoint(
    *,
    fit_ids: Sequence[str],
    calibration_ids: Sequence[str],
    benchmark_target_ids: Sequence[str],
) -> dict[str, Any]:
    fit, calibration, targets = set(fit_ids), set(calibration_ids), set(benchmark_target_ids)
    leaks = {
        "fit ∩ benchmark": sorted(fit & targets),
        "calibration ∩ benchmark": sorted(calibration & targets),
        "fit ∩ calibration": sorted(fit & calibration),
    }
    bad = {k: v for k, v in leaks.items() if v}
    if bad:
        raise LeakageError(f"calibration split leaks identities: {bad}")
    return {
        "split_policy_id": CALIBRATION_SPLIT_POLICY_ID,
        "split_rule": CALIBRATION_SPLIT_RULE,
        "fit_identity_digest": identity_digest(sorted(fit)),
        "calibration_identity_digest": identity_digest(sorted(calibration)),
        "benchmark_target_identity_digest": identity_digest(sorted(targets)),
        "n_fit": len(fit),
        "n_calibration": len(calibration),
        "n_benchmark_targets": len(targets),
    }


# --------------------------------------------------------------------------- #
# Calibration metrics                                                         #
# --------------------------------------------------------------------------- #

UNCERTAINTY_DECOMPOSITION_RULE = (
    "ez-wo12-uncertainty-decomposition-v1: predictive_std**2 = "
    "within_model_std**2 + residual_std**2 + model_disagreement_std**2. "
    "Table models report their empirical rms as within_model_std; residual-"
    "corrected models report the correction-GP posterior sigma as "
    "residual_std (the base sigma is replaced, not added); combiners report "
    "the weighted within-component sigma as within_model_std and the "
    "between-component spread as model_disagreement_std. Components that do "
    "not apply are exactly zero, never silently folded elsewhere."
)

# An informative sigma keeps standardized residuals within this band; far
# outside it the interval is either dishonest (>>1) or uninformative (<<1).
INFORMATIVE_STD_Z_RANGE = (1.0 / 3.0, 3.0)


def calibration_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """z-statistics for rows carrying prediction_keV / truth_keV / std_keV."""
    if not rows:
        return {"n": 0}
    z_values = [
        (float(r["truth_keV"]) - float(r["prediction_keV"])) / float(r["std_keV"])
        for r in rows
    ]
    n = len(z_values)
    std_z = statistics.pstdev(z_values) if n > 1 else 0.0
    lo, hi = INFORMATIVE_STD_Z_RANGE
    return {
        "n": n,
        "mean_z": statistics.fmean(z_values),
        "std_z": std_z,
        "fraction_abs_z_le_1": sum(1 for z in z_values if abs(z) <= 1.0) / n,
        "fraction_abs_z_le_1p645": sum(1 for z in z_values if abs(z) <= 1.645) / n,
        "fraction_abs_z_le_1p96": sum(1 for z in z_values if abs(z) <= 1.96) / n,
        "fraction_abs_z_gt_3": sum(1 for z in z_values if abs(z) > 3.0) / n,
        "coverage_90": sum(1 for z in z_values if abs(z) <= 1.6448536269514722) / n,
        "coverage_95": sum(1 for z in z_values if abs(z) <= 1.959963984540054) / n,
        "informative_std_z_range": list(INFORMATIVE_STD_Z_RANGE),
        "sigma_informative": bool(lo <= std_z <= hi) if n > 1 else None,
        "NLPD": statistics.fmean(
            0.5 * math.log(2.0 * math.pi * float(r["std_keV"]) ** 2)
            + 0.5
            * ((float(r["truth_keV"]) - float(r["prediction_keV"])) / float(r["std_keV"])) ** 2
            for r in rows
        ),
    }
