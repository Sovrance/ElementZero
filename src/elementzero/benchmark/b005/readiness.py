"""Family readiness and the WO-16 gate (WO-15B v0.5.2 §4, §11, §12, §15).

The distinction this module exists to hold is between a family that was
measured and missed a bar, and a family that could not be measured at
all. WO-15 collapsed those: the covariant family's coverage_90 read 0.00
as though it were a failed calibration, when in truth every one of its
uncertainty probes had failed and there was nothing to calibrate.

So calibration has three outcomes, not two. NOT_MET means the intervals
were real and wrong. NOT_EVALUABLE means the intervals were never
established. Reporting the second as the first would overstate what the
evidence says, in the direction that makes the programme look more
tested than it is.
"""

from __future__ import annotations

from typing import Any

from elementzero.benchmark.b005 import (
    COVERAGE90_MAX,
    COVERAGE90_MIN,
    FAMILY_ACCURACY_NOT_MET,
    FAMILY_ACCURACY_PASS,
    FAMILY_CALIBRATION_NOT_MET,
    FAMILY_CALIBRATION_PASS,
    FAMILY_READINESS_NOT_MET,
    FAMILY_READINESS_PASS,
    MAE_KEV_MAX,
    P95_ABS_ERROR_KEV_MAX,
    RESULT_MIXED,
    RESULT_NOT_EVALUABLE,
    RESULT_NOT_MET,
    RESULT_PASS,
    S2N_MAE_KEV_MAX,
    WO16_CLOSED,
    WO16_GATE_RULE,
    WO16_OPEN,
)

SIGMA_VALID_FRACTION_MIN = 0.90

FAMILY_CALIBRATION_NOT_EVALUABLE = "FAMILY_CALIBRATION_NOT_EVALUABLE"
FAMILY_POINT_SCORE_AVAILABLE = "FAMILY_POINT_SCORE_AVAILABLE"
FAMILY_SIGMA_PROVENANCE_PASS = "FAMILY_SIGMA_PROVENANCE_PASS"
FAMILY_SIGMA_PROVENANCE_NOT_MET = "FAMILY_SIGMA_PROVENANCE_NOT_MET"

# The B004 retrospective label. DD-ME2's point predictions stand; its
# coverage number never described its calibration.
NOT_EVALUABLE_FROM_INVALID_PROBE_SIGMA = (
    "NOT_EVALUABLE_FROM_INVALID_PROBE_SIGMA"
)

CALIBRATION_ELIGIBILITY_RULE = (
    f"ez-wo15b-calibration-eligibility-v1: a family's calibration is scored "
    f"only when at least {SIGMA_VALID_FRACTION_MIN:.0%} of its mass rows "
    "carry total_predictive.valid_for_calibration_scoring. Below that the "
    f"family reports {FAMILY_POINT_SCORE_AVAILABLE} and "
    f"{FAMILY_CALIBRATION_NOT_EVALUABLE} — never "
    f"{FAMILY_CALIBRATION_NOT_MET}, because intervals that were never "
    "established cannot have failed"
)

STRUCTURAL_GATE_NOT_EVALUABLE = "STRUCTURAL_GATE_NOT_EVALUABLE"


def assess_family(
    *,
    family_id: str,
    independence_group: str,
    blind_eligible: bool,
    metrics: dict[str, Any] | None,
    sigma_summary: dict[str, Any],
    coverage_90_sigma_valid: float | None,
) -> dict[str, Any]:
    """One family against the frozen gates, with three-way calibration."""
    fraction = float(sigma_summary.get("sigma_valid_fraction") or 0.0)
    sigma_status = (
        FAMILY_SIGMA_PROVENANCE_PASS
        if fraction >= SIGMA_VALID_FRACTION_MIN
        else FAMILY_SIGMA_PROVENANCE_NOT_MET
    )

    if not metrics:
        accuracy_status = FAMILY_ACCURACY_NOT_MET
        catastrophic_pass = False
    else:
        mae = float(metrics.get("MAE_keV") or float("inf"))
        p95 = float(metrics.get("p95_abs_error_keV") or float("inf"))
        accuracy_status = (
            FAMILY_ACCURACY_PASS if mae <= MAE_KEV_MAX else FAMILY_ACCURACY_NOT_MET
        )
        catastrophic_pass = p95 <= P95_ABS_ERROR_KEV_MAX

    # Calibration is only *judged* when it was measurable.
    if sigma_status == FAMILY_SIGMA_PROVENANCE_NOT_MET:
        calibration_status = FAMILY_CALIBRATION_NOT_EVALUABLE
        point_status = FAMILY_POINT_SCORE_AVAILABLE if metrics else None
    elif coverage_90_sigma_valid is None:
        calibration_status = FAMILY_CALIBRATION_NOT_EVALUABLE
        point_status = FAMILY_POINT_SCORE_AVAILABLE if metrics else None
    else:
        inside = COVERAGE90_MIN <= coverage_90_sigma_valid <= COVERAGE90_MAX
        calibration_status = (
            FAMILY_CALIBRATION_PASS if inside else FAMILY_CALIBRATION_NOT_MET
        )
        point_status = None

    readiness = (
        FAMILY_READINESS_PASS
        if (
            accuracy_status == FAMILY_ACCURACY_PASS
            and sigma_status == FAMILY_SIGMA_PROVENANCE_PASS
            and calibration_status == FAMILY_CALIBRATION_PASS
            and catastrophic_pass
        )
        else FAMILY_READINESS_NOT_MET
    )
    return {
        "family_id": family_id,
        "independence_group": independence_group,
        "blind_eligible": blind_eligible,
        "sigma_valid_fraction": fraction,
        "sigma_provenance_status": sigma_status,
        "point_accuracy_status": accuracy_status,
        "point_score_status": point_status,
        "calibration_status": calibration_status,
        "coverage_90_sigma_valid": coverage_90_sigma_valid,
        "catastrophic_error_pass": catastrophic_pass,
        "readiness_status": readiness,
        "eligibility_rule": CALIBRATION_ELIGIBILITY_RULE,
    }


def adjudicate(
    *,
    families: list[dict[str, Any]],
    n_targets: int,
    evaluable: bool,
    s2n_mae_keV: float | None = None,
    integrity_failures: list[str] | None = None,
) -> dict[str, Any]:
    """The B005 result and the WO-16 gate, on frozen thresholds."""
    from elementzero.benchmark.b005 import RESULT_VOCABULARY

    if integrity_failures:
        return {
            "result": "B005_INTEGRITY_FAILURE",
            "integrity_failures": sorted(integrity_failures),
            "qualifying_blind_physics_families": [],
            "wo16_gate": WO16_CLOSED,
            "wo16_gate_rule": WO16_GATE_RULE,
        }

    # Only blind-eligible families count, and only one per independence
    # group: a discrepancy child shares its parent's group by design.
    passing_groups = sorted(
        {
            f["independence_group"]
            for f in families
            if f["blind_eligible"]
            and f["readiness_status"] == FAMILY_READINESS_PASS
        }
    )
    if not evaluable:
        result = RESULT_NOT_EVALUABLE
    elif len(passing_groups) >= 2:
        result = RESULT_PASS
    elif passing_groups:
        result = RESULT_MIXED
    else:
        result = RESULT_NOT_MET
    assert result in RESULT_VOCABULARY

    if s2n_mae_keV is None:
        structural = STRUCTURAL_GATE_NOT_EVALUABLE
    else:
        structural = (
            "STRUCTURAL_GATE_PASS"
            if s2n_mae_keV <= S2N_MAE_KEV_MAX
            else "STRUCTURAL_GATE_NOT_MET"
        )

    return {
        "result": result,
        "n_targets": n_targets,
        "qualifying_blind_physics_families": passing_groups,
        "structural_gate": structural,
        "s2n_mae_keV": s2n_mae_keV,
        "wo16_gate": WO16_OPEN if result == RESULT_PASS else WO16_CLOSED,
        "wo16_gate_rule": WO16_GATE_RULE,
        "families": families,
    }


__all__ = [
    "CALIBRATION_ELIGIBILITY_RULE",
    "FAMILY_CALIBRATION_NOT_EVALUABLE",
    "FAMILY_POINT_SCORE_AVAILABLE",
    "FAMILY_SIGMA_PROVENANCE_NOT_MET",
    "FAMILY_SIGMA_PROVENANCE_PASS",
    "NOT_EVALUABLE_FROM_INVALID_PROBE_SIGMA",
    "SIGMA_VALID_FRACTION_MIN",
    "STRUCTURAL_GATE_NOT_EVALUABLE",
    "adjudicate",
    "assess_family",
]
