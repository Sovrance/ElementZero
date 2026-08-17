"""EZ-B005-v1: the fresh blind challenge WO-15B is judged on.

B004 asked whether two independent blind-eligible families could produce
sealed, converged, uncertainty-carrying predictions. They could, and the
predictions were poor. B005 asks the harder question: are they now
accurate and calibrated enough to earn WO-16?

Its gates are numeric and preregistered, and they are two-sided —
coverage_90 must land inside [0.80, 0.98], so a model cannot pass by
being vague any more than by being overconfident.
"""

from __future__ import annotations

B005_ID = "EZ-B005-v1"
EXPERIMENT_RELPATH = "experiments/EZ-B005-v1"
RESULTS_RELPATH = "results/EZ-B005-v1"

# Preregistered readiness gates. These are the WO-16 entry conditions and
# are not adjustable after scoring.
MAE_KEV_MAX = 2000.0
COVERAGE90_MIN = 0.80
COVERAGE90_MAX = 0.98
P95_ABS_ERROR_KEV_MAX = 5000.0
S2N_MAE_KEV_MAX = 750.0

MIN_TARGETS_PREFERRED = 30
MIN_TARGETS_EVALUABLE = 20
MIN_Z_REGIONS = 3

RESULT_PASS = "CALIBRATED_MULTI_FAMILY_BLIND_PASS"
RESULT_MIXED = "CALIBRATED_MULTI_FAMILY_BLIND_MIXED"
RESULT_NOT_MET = "CALIBRATED_MULTI_FAMILY_BLIND_NOT_MET"
RESULT_NOT_EVALUABLE = "B005_NOT_EVALUABLE"

RESULT_VOCABULARY = (
    RESULT_PASS,
    RESULT_MIXED,
    RESULT_NOT_MET,
    RESULT_NOT_EVALUABLE,
)

FAMILY_CALIBRATION_PASS = "FAMILY_CALIBRATION_PASS"
FAMILY_CALIBRATION_NOT_MET = "FAMILY_CALIBRATION_NOT_MET"
FAMILY_ACCURACY_PASS = "FAMILY_ACCURACY_PASS"
FAMILY_ACCURACY_NOT_MET = "FAMILY_ACCURACY_NOT_MET"
FAMILY_READINESS_PASS = "FAMILY_BLIND_READINESS_PASS"
FAMILY_READINESS_NOT_MET = "FAMILY_BLIND_READINESS_NOT_MET"

WO16_OPEN = "OPEN"
WO16_CLOSED = "CLOSED"

WO16_GATE_RULE = (
    "ez-wo15b-wo16-gate-v1: WO-16 opens only when B005 scores "
    f"{RESULT_PASS} and at least two independent blind-eligible physics "
    f"families each satisfy MAE <= {MAE_KEV_MAX:.0f} keV, coverage_90 in "
    f"[{COVERAGE90_MIN}, {COVERAGE90_MAX}], and 95th-percentile absolute "
    f"error <= {P95_ABS_ERROR_KEV_MAX:.0f} keV. Discrepancy-corrected "
    "variants inherit their parent's independence group and never add to "
    "the family count. The covariant reference is scored and never counted. "
    "No threshold moves after scoring"
)

__all__ = [
    "B005_ID",
    "COVERAGE90_MAX",
    "COVERAGE90_MIN",
    "EXPERIMENT_RELPATH",
    "FAMILY_ACCURACY_NOT_MET",
    "FAMILY_ACCURACY_PASS",
    "FAMILY_CALIBRATION_NOT_MET",
    "FAMILY_CALIBRATION_PASS",
    "FAMILY_READINESS_NOT_MET",
    "FAMILY_READINESS_PASS",
    "MAE_KEV_MAX",
    "MIN_TARGETS_EVALUABLE",
    "MIN_TARGETS_PREFERRED",
    "MIN_Z_REGIONS",
    "P95_ABS_ERROR_KEV_MAX",
    "RESULTS_RELPATH",
    "RESULT_MIXED",
    "RESULT_NOT_EVALUABLE",
    "RESULT_NOT_MET",
    "RESULT_PASS",
    "RESULT_VOCABULARY",
    "S2N_MAE_KEV_MAX",
    "WO16_CLOSED",
    "WO16_GATE_RULE",
    "WO16_OPEN",
]
