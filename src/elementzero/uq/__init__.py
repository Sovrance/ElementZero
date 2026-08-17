"""WO-201 — predictive-uncertainty calibration (protocol v2.0.0).

Doctrine 7: an uncalibrated model is not scored. Calibration is the EZ-B004
gate that runs before any scored benchmark, not a column in the results table.

The v1 series reported coverage_90 = coverage_95 = 1.000 for every GP row of
every epoch. That was not success; it was a predictive sigma roughly three
orders of magnitude too wide, which cannot be seen from two coverage points but
is obvious from the coverage curve this package reports. See
`reports/v2/sigma_defect.json` for the committed reproduction.

Thresholds live in `protocol/acceptance_matrix.json` and are mirrored as module
constants in `elementzero.uq.calibration`. Changing either requires a protocol
version bump, never an in-place edit.
"""

from elementzero.uq.calibration import (
    CALIBRATION_MODULE_VERSION,
    CalibrationReport,
    ConformalSigmaScaler,
    calibration_report,
    classify_dispersion,
    coverage_curve,
    crps_gaussian,
    empirical_coverage,
    nlpd_gaussian,
    pit_ks,
    pit_values,
    z_scores,
)

__all__ = [
    "CALIBRATION_MODULE_VERSION",
    "CalibrationReport",
    "ConformalSigmaScaler",
    "calibration_report",
    "classify_dispersion",
    "coverage_curve",
    "crps_gaussian",
    "empirical_coverage",
    "nlpd_gaussian",
    "pit_ks",
    "pit_values",
    "z_scores",
]
