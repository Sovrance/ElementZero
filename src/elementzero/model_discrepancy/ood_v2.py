"""Out-of-domain classification v2 (WO-15B stream D).

WO-15's uncertainty was silent about *where* a prediction sat relative
to the evidence that produced it. A target two neutrons past the
training lattice and one forty neutrons past it were reported the same
way. This policy makes that distance explicit and versioned, and freezes
it before B005 is scored so the classes cannot be redrawn to flatter a
result.

The signals are deliberately cheap and identity-based, with one
exception: the discrepancy posterior variance, which is a property of
the fitted GP and therefore of training-era evidence only.
"""

from __future__ import annotations

from typing import Any

OOD_POLICY_ID = "ez-wo15b-ood-v2"

IN_DOMAIN = "IN_DOMAIN"
LOCAL_EXTRAPOLATION = "LOCAL_EXTRAPOLATION"
REGIONAL_EXTRAPOLATION = "REGIONAL_EXTRAPOLATION"
EXTREME_EXTRAPOLATION = "EXTREME_EXTRAPOLATION"

OOD_CLASSES = (
    IN_DOMAIN,
    LOCAL_EXTRAPOLATION,
    REGIONAL_EXTRAPOLATION,
    EXTREME_EXTRAPOLATION,
)

# Thresholds on L1 lattice distance to the nearest training nuclide.
# Frozen with the policy; changing them changes the policy id.
LOCAL_MAX_L1 = 2
REGIONAL_MAX_L1 = 8

# Local density is counted inside this L1 radius.
DENSITY_RADIUS_L1 = 6
SPARSE_DENSITY = 3

OOD_POLICY = (
    f"{OOD_POLICY_ID}: a target is {IN_DOMAIN} when a training nuclide sits "
    f"within L1 distance {LOCAL_MAX_L1} and the training density within "
    f"radius {DENSITY_RADIUS_L1} is above {SPARSE_DENSITY}; "
    f"{LOCAL_EXTRAPOLATION} within {LOCAL_MAX_L1}; {REGIONAL_EXTRAPOLATION} "
    f"within {REGIONAL_MAX_L1}; {EXTREME_EXTRAPOLATION} beyond that. Signals "
    "are nearest training lattice distance, local training density, "
    "discrepancy posterior variance and cross-family disagreement. All are "
    "computed from identity and training-era evidence; none consults truth"
)


def classify(
    *,
    z: int,
    n: int,
    training_zn: list[tuple[int, int]],
    posterior_std_keV: float | None = None,
    disagreement_keV: float | None = None,
) -> dict[str, Any]:
    """One target's domain class plus the signals behind it."""
    if not training_zn:
        return {
            "ood_class": EXTREME_EXTRAPOLATION,
            "nearest_training_L1": None,
            "local_training_density": 0,
            "posterior_std_keV": posterior_std_keV,
            "cross_family_disagreement_keV": disagreement_keV,
            "policy_id": OOD_POLICY_ID,
            "reason": "no training lattice",
        }
    distances = [abs(z - tz) + abs(n - tn) for tz, tn in training_zn]
    nearest = min(distances)
    density = sum(1 for d in distances if d <= DENSITY_RADIUS_L1)

    if nearest <= LOCAL_MAX_L1 and density > SPARSE_DENSITY:
        ood = IN_DOMAIN
    elif nearest <= LOCAL_MAX_L1:
        ood = LOCAL_EXTRAPOLATION
    elif nearest <= REGIONAL_MAX_L1:
        ood = REGIONAL_EXTRAPOLATION
    else:
        ood = EXTREME_EXTRAPOLATION
    return {
        "ood_class": ood,
        "nearest_training_L1": nearest,
        "local_training_density": density,
        "posterior_std_keV": posterior_std_keV,
        "cross_family_disagreement_keV": disagreement_keV,
        "policy_id": OOD_POLICY_ID,
    }


__all__ = [
    "DENSITY_RADIUS_L1",
    "EXTREME_EXTRAPOLATION",
    "IN_DOMAIN",
    "LOCAL_EXTRAPOLATION",
    "LOCAL_MAX_L1",
    "OOD_CLASSES",
    "OOD_POLICY",
    "OOD_POLICY_ID",
    "REGIONAL_EXTRAPOLATION",
    "REGIONAL_MAX_L1",
    "classify",
]
