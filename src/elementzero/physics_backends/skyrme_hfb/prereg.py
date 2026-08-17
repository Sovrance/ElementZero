"""Stream A preregistration: what may be fitted, and how much compute.

Written and hashed before the first sensitivity solve runs. The point is
that the tier is chosen by a rule fixed in advance rather than by which
subset happened to fit best — the failure mode that turns a refit into
an exercise in finding the parameters that flatter a benchmark.

Bounds are physical, not convenience. Each is a range within which the
functional remains a sane nuclear-matter description; a fit that wants
to leave the box is telling you the functional form is wrong, which is
information worth keeping rather than a bound worth widening. WO-15
learned that the hard way when the pairing fit sat on its box edge and
the honest move was to report it, not to open the box.
"""

from __future__ import annotations

from typing import Any

from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.physics_backends.skyrme_hfb import (
    BASELINE_SOURCE,
    INM_PARAMETER_NAMES,
    SKYRME_BASELINE_INM,
    UPSTREAM_PATCH,
)

PREREG_ID = "ez-wo15b-skyrme-massfit-prereg-v1"

# Physical bounds. Empirical ranges from the nuclear-matter literature,
# deliberately generous at the edges but finite everywhere.
PARAMETER_BOUNDS: dict[str, tuple[float, float]] = {
    "RHO_NM": (0.145, 0.175),        # fm^-3, saturation density
    "E_NM": (-16.5, -15.0),          # MeV per nucleon
    "K_NM": (180.0, 270.0),          # MeV, incompressibility
    "ASS_NM": (28.0, 36.0),          # MeV, symmetry energy
    "LASS_NM": (20.0, 90.0),         # MeV, symmetry-energy slope
    "SMASS_NM": (0.80, 1.40),        # isoscalar effective mass ratio
    "CrDr_0": (-100.0, -40.0),       # isoscalar surface
    "CrDr_1": (-40.0, 60.0),         # isovector surface
    "CpV0_0": (-500.0, -150.0),      # neutron pairing
    "CpV0_1": (-500.0, -150.0),      # proton pairing
    "CrdJ_0": (-130.0, -60.0),       # isoscalar spin-orbit
    "CrdJ_1": (-80.0, 20.0),         # isovector spin-orbit
}

# Tier definitions. S1 through S3 are nested, so freezing a tier is a
# statement about how many degrees of freedom the data can support.
TIER_S1 = ("CpV0_0", "CpV0_1", "E_NM", "ASS_NM")
TIER_S2 = TIER_S1 + ("K_NM", "LASS_NM", "SMASS_NM")
TIER_S3 = TIER_S2 + ("CrDr_0", "CrDr_1", "CrdJ_0", "RHO_NM")

TIERS: dict[str, tuple[str, ...]] = {
    "S1": TIER_S1,
    "S2": TIER_S2,
    "S3": TIER_S3,
}

# The selection rule, fixed here rather than after seeing sensitivities.
SENSITIVITY_PROBE_IDS = (
    "Z20-N20",
    "Z28-N32",
    "Z50-N70",
    "Z62-N88",
    "Z82-N126",
    "Z92-N146",
)
RELATIVE_STEP = 0.02
IDENTIFIABILITY_MIN_KEV = 50.0
CORRELATION_MAX = 0.98

TIER_SELECTION_RULE = (
    f"{PREREG_ID}-tier-rule: a parameter is identifiable when a "
    f"{RELATIVE_STEP:.0%} step inside its bounds moves the mean binding "
    f"energy of the probe set by at least {IDENTIFIABILITY_MIN_KEV} keV. The "
    "largest nested tier whose parameters are all identifiable, and whose "
    "sensitivity vectors are not pairwise collinear above "
    f"{CORRELATION_MAX}, is frozen. Ties go to the smaller tier: fewer "
    "degrees of freedom is the conservative error"
)

# Compute budget, in solver calls, fixed before the optimizer starts.
MAX_OBJECTIVE_EVALUATIONS = 60
CALIBRATION_TIMEOUT_S = 1800
BUDGET_RULE = (
    f"{PREREG_ID}-budget: the refit may spend at most "
    f"{MAX_OBJECTIVE_EVALUATIONS} objective evaluations. Exhausting the "
    "budget is a recorded outcome (FIT_BUDGET_EXHAUSTED), not a reason to "
    "extend it, and the parameter vector at exhaustion is the one that ships"
)

OBJECTIVE_RULE = (
    f"{PREREG_ID}-objective: root-mean-square mass-excess residual in keV "
    "over the frozen AME1995 calibration set, equally weighted. A "
    "non-converged solve contributes a fixed infeasible penalty rather than "
    "being dropped, so the optimizer cannot improve the objective by "
    "steering into regions where the solver quietly fails"
)
INFEASIBLE_PENALTY_KEV = 1e9
MIN_CONVERGED_FRACTION = 0.75

PHYSICAL_CONSTRAINTS = (
    "every parameter stays inside its declared bound; a bound is never "
    "widened after seeing a fit",
    "pairing strengths stay negative (attractive)",
    "isoscalar effective mass stays positive",
    "a vector that leaves the box is rejected before the solver runs",
)


def build_preregistration() -> dict[str, Any]:
    """The hashed stream-A preregistration record."""
    record = {
        "prereg_id": PREREG_ID,
        "baseline_source": BASELINE_SOURCE,
        "upstream_patch": UPSTREAM_PATCH,
        "parameter_names": list(INM_PARAMETER_NAMES),
        "baseline_vector": dict(sorted(SKYRME_BASELINE_INM.items())),
        "bounds": {k: list(v) for k, v in sorted(PARAMETER_BOUNDS.items())},
        "tiers": {name: list(params) for name, params in sorted(TIERS.items())},
        "tier_selection_rule": TIER_SELECTION_RULE,
        "sensitivity_probe_ids": list(SENSITIVITY_PROBE_IDS),
        "relative_step": RELATIVE_STEP,
        "identifiability_min_keV": IDENTIFIABILITY_MIN_KEV,
        "correlation_max": CORRELATION_MAX,
        "objective_rule": OBJECTIVE_RULE,
        "infeasible_penalty_keV": INFEASIBLE_PENALTY_KEV,
        "min_converged_fraction": MIN_CONVERGED_FRACTION,
        "budget_rule": BUDGET_RULE,
        "max_objective_evaluations": MAX_OBJECTIVE_EVALUATIONS,
        "physical_constraints": list(PHYSICAL_CONSTRAINTS),
        "truth_policy": (
            "the calibration set is the WO-15 AME1995 freeze. WO-14 truth, "
            "B004 truth and B005 truth are forbidden at every step"
        ),
    }
    record["prereg_hash"] = sha256_hex(canonical_json(record))
    return record


def within_bounds(values: dict[str, float]) -> bool:
    for name, value in values.items():
        low, high = PARAMETER_BOUNDS[name]
        if not (low <= value <= high):
            return False
    return True


__all__ = [
    "BUDGET_RULE",
    "CALIBRATION_TIMEOUT_S",
    "CORRELATION_MAX",
    "IDENTIFIABILITY_MIN_KEV",
    "INFEASIBLE_PENALTY_KEV",
    "MAX_OBJECTIVE_EVALUATIONS",
    "MIN_CONVERGED_FRACTION",
    "OBJECTIVE_RULE",
    "PARAMETER_BOUNDS",
    "PREREG_ID",
    "RELATIVE_STEP",
    "SENSITIVITY_PROBE_IDS",
    "TIERS",
    "TIER_SELECTION_RULE",
    "build_preregistration",
    "within_bounds",
]
