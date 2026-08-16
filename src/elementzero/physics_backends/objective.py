"""PhysicsFitObjectiveManifest — the optimization target, locked first.

"Do not silently invent an optimization target" (spec section 12). The
manifest is written and hashed before the first solver call, and the fit
driver refuses to run against an objective whose hash it was not given.
"""

from __future__ import annotations

from typing import Any

from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_hex

OBJECTIVE_ID = "ez-wo15-mass-objective-v1"

WEIGHT_POLICY = (
    "uniform weight per calibration nuclide: the training-era measurement "
    "uncertainties of the selected set are all at or below 50 keV, so an "
    "inverse-variance weighting would concentrate the fit on a handful of "
    "the most precisely measured nuclides without a physics reason. Uniform "
    "weighting is declared here rather than discovered later"
)

INCLUSION_RULE = (
    "a calibration nuclide contributes to the objective only when the "
    "solver converged for it under the preregistered basis policy. A "
    "nonconverged calibration point is recorded and excluded — never "
    "replaced by a penalty value chosen after seeing the fit behave"
)

NONCONVERGENCE_PENALTY_RULE = (
    "if fewer than min_converged_fraction of the calibration set converges "
    "for a trial parameter vector, that vector is rejected as infeasible "
    "with a fixed sentinel objective declared here in advance, so the "
    "optimizer cannot be steered by a tuned penalty"
)

MIN_CONVERGED_FRACTION = 0.75
INFEASIBLE_OBJECTIVE = 1.0e9


def build_objective_manifest(
    *,
    calibration_nuclide_ids: list[str],
    freeze_id: str,
    source_hash: str,
) -> dict[str, Any]:
    """The locked objective for a WO-15 mass refit."""
    manifest = {
        "objective_id": OBJECTIVE_ID,
        "description": (
            "root-mean-square residual between the solver's computed atomic "
            "mass excess and the training-era measured mass excess over the "
            "frozen calibration set"
        ),
        "observables": [
            {
                "observable": "atomic_mass_excess_keV",
                "unit": "keV",
                "uncertainty_treatment": (
                    "training-era measurement uncertainty is recorded per "
                    "nuclide but does not enter the weight (see weight_policy)"
                ),
                "weight_policy": WEIGHT_POLICY,
                "inclusion_rule": INCLUSION_RULE,
                "source_hash": source_hash,
            }
        ],
        "loss": "sqrt(mean((computed_keV - measured_keV)^2))",
        "regularization": "none",
        "min_converged_fraction": MIN_CONVERGED_FRACTION,
        "infeasible_objective": INFEASIBLE_OBJECTIVE,
        "nonconvergence_penalty_rule": NONCONVERGENCE_PENALTY_RULE,
        "freeze_id": freeze_id,
        "calibration_nuclide_ids": sorted(calibration_nuclide_ids),
        "n_calibration": len(calibration_nuclide_ids),
        "locked_before_fitting": True,
    }
    manifest["objective_manifest_hash"] = sha256_hex(manifest)
    return manifest


def assert_objective_locked(
    manifest: dict[str, Any], *, expected_hash: str
) -> None:
    payload = {k: v for k, v in manifest.items() if k != "objective_manifest_hash"}
    if sha256_hex(payload) != expected_hash:
        raise ProtocolError(
            "HISTORICAL_FIT_INTEGRITY_FAILURE: the objective manifest changed "
            "after it was locked"
        )
