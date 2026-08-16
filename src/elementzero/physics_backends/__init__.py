"""WO-15 — refittable physics backends and historical physics fits.

ElementZero stops treating a physics model as a table someone else
published and starts controlling the whole chain: source code, build,
functional, parameter vector, optimizer, objective, calibration
membership, freeze date, convergence status, and artifact hash.

A model is not historically blind because its *code* is old. Its fitted
*parameter state* must also be historically admissible — that is the
distinction WO-15 exists to enforce.
"""

from __future__ import annotations

WO15_ID = "WO-15"
REPORTS_RELPATH = "reports/physics_backends/wo15"
BACKEND_DATA_RELPATH = "data/physics_backends"

# Independence groups (WO-15 spec section 3). These are physics classes,
# never wrapper or repository names.
GROUP_SKYRME_HFB = "skyrme_hfb_edf"
GROUP_GOGNY_HFB = "gogny_finite_range_hfb"
GROUP_COVARIANT_RHB = "covariant_rhb_edf"

BACKEND_SKYRME = "EZ-PHYS-SKYRME-HFB-v1"
BACKEND_GOGNY = "EZ-PHYS-GOGNY-HFB-v1"
BACKEND_COVARIANT = "EZ-PHYS-COVARIANT-RHB-v1"

# Fit-provenance classes (spec section 5). Exactly one per artifact.
REFIT_STRICT = "REFIT_STRICT"
HISTORICAL_FROZEN_EXACT = "HISTORICAL_FROZEN_EXACT"
HISTORICAL_FROZEN_PARTIAL = "HISTORICAL_FROZEN_PARTIAL"
MODERN_REFERENCE = "MODERN_REFERENCE"
UNKNOWN_PROVENANCE = "UNKNOWN_PROVENANCE"

PROVENANCE_CLASSES = (
    REFIT_STRICT,
    HISTORICAL_FROZEN_EXACT,
    HISTORICAL_FROZEN_PARTIAL,
    MODERN_REFERENCE,
    UNKNOWN_PROVENANCE,
)

# Backend/family status vocabulary (spec section 27).
PHYSICS_BACKEND_QUALIFIED = "PHYSICS_BACKEND_QUALIFIED"
PHYSICS_BACKEND_REFERENCE_ONLY = "PHYSICS_BACKEND_REFERENCE_ONLY"
PHYSICS_BACKEND_NOT_REFITTABLE = "PHYSICS_BACKEND_NOT_REFITTABLE"
PHYSICS_BACKEND_PROVENANCE_INCOMPLETE = "PHYSICS_BACKEND_PROVENANCE_INCOMPLETE"
PHYSICS_BACKEND_NUMERICALLY_UNSTABLE = "PHYSICS_BACKEND_NUMERICALLY_UNSTABLE"
