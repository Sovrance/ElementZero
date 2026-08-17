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

PREREG_ID = "ez-wo15b-skyrme-massfit-prereg-v3"

SUPERSEDES = "ez-wo15b-skyrme-massfit-prereg-v2"
SUPERSEDE_REASON = (
    "Two instrument defects, both found before any objective evaluation ran "
    "and both corrected on mechanical grounds rather than on results.\n\n"
    "v1 declared the pairing box as (-500, -150), which excluded its own "
    "starting point: WO-15's REFIT_STRICT fit drove CpV0_1 to -140, on that "
    "earlier fit's box edge. The first sensitivity run refused the baseline "
    "and aborted before any solve completed. v2 corrected the box to "
    "(-500, -100), still enforcing attractive pairing.\n\n"
    "v2's sensitivity run then showed all six nuclear-matter parameters "
    "moving binding energy by exactly 0.0 keV while every true coupling "
    "moved it. hfbtho_unedf.f90 explains the exact zeros: use_INM defaults "
    "to .False. and is set .True. only for the UNEDF-family functionals, so "
    "for a (t,x)-defined force like SKM* the nuclear-matter quantities are "
    "outputs computed from the couplings, never inputs. Writing them into "
    "hfbtho_FUNCTIONAL.dat is inert. The equivalence check in the "
    "READ_FUNCTIONAL qualification could not have caught this: feeding the "
    "solver its own values reproduces its own answer whether or not it "
    "reads them. Only the sensitivity probe distinguishes the two.\n\n"
    "Switching the base to UNEDF0/1/2 would make the nuclear-matter "
    "parameters live, and is refused: those parameterizations are 2010, "
    "2012 and 2014, all post-freeze, so adopting one would trade blind "
    "eligibility — the property under test — for accuracy.\n\n"
    "v2 also probed with a proton-shell-biased set: four of six probes had "
    "magic Z (20, 28, 50, 82), where proton pairing collapses, so CpV0_1 "
    "measured 7.4 keV. That is a statement about the probe set, not about "
    "the parameter. The v3 probe set carries four open-proton-shell "
    "nuclides.\n\n"
    "v3 therefore fits the couplings the solver actually reads — pairing, "
    "surface and spin-orbit — and probes them where they can be seen."
)

# The finding that shapes v3, kept next to the code it constrains.
INM_INERT_FINDING = (
    "ez-wo15b-inm-inert-v1: with functional='SKM*' the HFBTHO build has "
    "use_INM=.False., so RHO_NM, E_NM, K_NM, ASS_NM, LASS_NM and SMASS_NM "
    "supplied through hfbtho_FUNCTIONAL.dat have no effect on the solution. "
    "Measured: exactly 0.0 keV mean change across the probe set for all six, "
    "against 3704 keV for CrDr_0. A fit over them would have wandered "
    "freely and reported convergence"
)

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
    "CpV0_0": (-500.0, -100.0),      # neutron pairing, attractive
    "CpV0_1": (-500.0, -100.0),      # proton pairing, attractive
    "CrdJ_0": (-130.0, -60.0),       # isoscalar spin-orbit
    "CrdJ_1": (-80.0, 20.0),         # isovector spin-orbit
}

# Tiers over the couplings the solver actually consumes, grouped by
# physics rather than by measured strength. Nested, so freezing a tier
# states how many degrees of freedom the calibration set can support.
# The nuclear-matter parameters are excluded because they are inert in
# this build, not because they fitted badly — no fit has been run.
TIER_S1 = ("CpV0_0", "CpV0_1")                       # pairing, WO-15's scope
TIER_S2 = TIER_S1 + ("CrDr_0", "CrDr_1")             # + surface
TIER_S3 = TIER_S2 + ("CrdJ_0", "CrdJ_1")             # + spin-orbit

FITTABLE_PARAMETERS = TIER_S3
INERT_PARAMETERS = (
    "RHO_NM",
    "E_NM",
    "K_NM",
    "ASS_NM",
    "LASS_NM",
    "SMASS_NM",
)

TIERS: dict[str, tuple[str, ...]] = {
    "S1": TIER_S1,
    "S2": TIER_S2,
    "S3": TIER_S3,
}

# The selection rule, fixed here rather than after seeing sensitivities.
# Half the probes have open proton shells. A set weighted toward magic Z
# cannot see proton pairing at all, which is how v2 mismeasured CpV0_1.
SENSITIVITY_PROBE_IDS = (
    "Z20-N20",    # doubly magic
    "Z24-N28",    # open Z, magic N
    "Z44-N56",    # open Z, open N
    "Z50-N70",    # magic Z, open N
    "Z62-N88",    # open Z, open N, deformed
    "Z66-N98",    # open Z, open N, deformed
    "Z82-N126",   # doubly magic
    "Z92-N146",   # open Z, open N, actinide
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


def assert_baseline_in_box() -> None:
    """A preregistration whose own starting point is illegal is a bug.

    Checked at build time so the inconsistency surfaces here rather than
    hours into a solver campaign.
    """
    from elementzero.errors import ProtocolError

    outside = {
        name: (value, PARAMETER_BOUNDS[name])
        for name, value in SKYRME_BASELINE_INM.items()
        if not (
            PARAMETER_BOUNDS[name][0] <= value <= PARAMETER_BOUNDS[name][1]
        )
    }
    if outside:
        raise ProtocolError(
            f"PREREG_BASELINE_OUT_OF_BOX: {outside}; the preregistration "
            "cannot exclude the vector it starts from"
        )


def build_preregistration() -> dict[str, Any]:
    """The hashed stream-A preregistration record."""
    assert_baseline_in_box()
    record = {
        "prereg_id": PREREG_ID,
        "supersedes": SUPERSEDES,
        "supersede_reason": SUPERSEDE_REASON,
        "objective_evaluations_before_supersede": 0,
        "inm_inert_finding": INM_INERT_FINDING,
        "inert_parameters": list(INERT_PARAMETERS),
        "fittable_parameters": list(FITTABLE_PARAMETERS),
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
