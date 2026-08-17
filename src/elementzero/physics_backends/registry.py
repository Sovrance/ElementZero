"""The WO-15 backend roster and its qualification verdicts.

Qualification here means engineering: the source is pinned, the build is
reproducible, the golden case reproduces, convergence is recorded, and
the parameter artifact is immutable. It deliberately says nothing about
predictive accuracy — that is B004's job, and conflating the two is the
mistake this whole work order exists to prevent.
"""

from __future__ import annotations

from typing import Any

from elementzero.physics_backends import (
    BACKEND_COVARIANT,
    BACKEND_GOGNY,
    BACKEND_SKYRME,
    GROUP_COVARIANT_RHB,
    GROUP_GOGNY_HFB,
    GROUP_SKYRME_HFB,
    PHYSICS_BACKEND_NOT_REFITTABLE,
    PHYSICS_BACKEND_NUMERICALLY_UNSTABLE,
    PHYSICS_BACKEND_QUALIFIED,
    PHYSICS_BACKEND_REFERENCE_ONLY,
)
from elementzero.physics_backends.provenance import (
    BACKEND_SOLVER,
    PARAMETERIZATIONS,
    parameterization_admissible,
)

ROSTER: dict[str, dict[str, Any]] = {
    BACKEND_SKYRME: {
        "backend_id": BACKEND_SKYRME,
        "physics_family": GROUP_SKYRME_HFB,
        "functional_class": "skyrme_zero_range_edf",
        "interaction_or_lagrangian_class": (
            "zero-range Skyrme effective interaction with density-dependent "
            "term and zero-range spin-orbit"
        ),
        "solver": "HFBTHO",
        "parameterization": "SKM*",
        "refittable": True,
        "refit_scope": "pairing sector (vpair_n, vpair_p)",
    },
    BACKEND_GOGNY: {
        "backend_id": BACKEND_GOGNY,
        "physics_family": GROUP_GOGNY_HFB,
        "functional_class": "gogny_finite_range",
        "interaction_or_lagrangian_class": (
            "finite-range Gogny interaction: two Gaussian central terms with "
            "density-dependent and spin-orbit components"
        ),
        "solver": "HFBTHO",
        "parameterization": "D1S",
        "refittable": True,
        "refit_scope": "pairing sector (vpair_n, vpair_p)",
    },
    BACKEND_COVARIANT: {
        "backend_id": BACKEND_COVARIANT,
        "physics_family": GROUP_COVARIANT_RHB,
        "functional_class": "covariant_meson_exchange",
        "interaction_or_lagrangian_class": (
            "relativistic Lagrangian with density-dependent meson-nucleon "
            "couplings (sigma, omega, rho) and separable pairing"
        ),
        "solver": "DIRHB",
        "parameterization": "DD-ME2",
        "refittable": False,
        "refit_scope": "none",
    },
}


def qualification_status(
    *,
    backend_id: str,
    source_verified: bool,
    build_verified: bool,
    golden_reproduced: bool,
    any_converged: bool,
) -> dict[str, Any]:
    """One family's engineering verdict, with the reason attached."""
    entry = ROSTER[backend_id]
    parameterization = entry["parameterization"]
    admissible = parameterization_admissible(parameterization)

    if not (source_verified and build_verified):
        status = "BACKEND_BUILD_FAILURE"
        reason = "source hash or build manifest did not verify"
    elif not golden_reproduced:
        status = "BACKEND_PROVENANCE_FAILURE"
        reason = "the upstream golden case did not reproduce"
    elif not any_converged:
        status = PHYSICS_BACKEND_NUMERICALLY_UNSTABLE
        reason = "the solver produced no converged result on the target set"
    elif not admissible:
        status = PHYSICS_BACKEND_REFERENCE_ONLY
        reason = (
            f"{parameterization} was published in "
            f"{PARAMETERIZATIONS[parameterization]['publication_year']}, after "
            "the freeze; the backend is reproducible but its parameter state "
            "is not historically admissible"
        )
    elif not entry["refittable"]:
        status = PHYSICS_BACKEND_NOT_REFITTABLE
        reason = "no parameter sector can be refit without editing upstream source"
    else:
        status = PHYSICS_BACKEND_QUALIFIED
        reason = (
            "source pinned, build reproducible, golden case reproduced, "
            "convergence recorded, parameters refit under the freeze with "
            "exact calibration membership"
        )
    return {
        "backend_id": backend_id,
        "physics_family": entry["physics_family"],
        "solver": BACKEND_SOLVER[backend_id],
        "parameterization": parameterization,
        "parameterization_year": PARAMETERIZATIONS[parameterization][
            "publication_year"
        ],
        "freeze_admissible_parameterization": admissible,
        "refittable": entry["refittable"],
        "source_verified": source_verified,
        "build_verified": build_verified,
        "golden_reproduced": golden_reproduced,
        "status": status,
        "reason": reason,
        "qualification_scope": (
            "engineering only: provenance, reproducibility, and convergence. "
            "This status makes no claim about predictive accuracy"
        ),
    }
