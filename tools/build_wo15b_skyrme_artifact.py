#!/usr/bin/env python3
"""Seal the refit Skyrme vector as an immutable parameter artifact.

The vector is the one the optimizer held when its budget ran out. It is
recorded with the tier that produced it, the fit log hash, and the same
freeze and objective the WO-15 fit used, so the two Skyrme artifacts are
directly comparable and the difference between them is exactly the three
extra couplings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elementzero.evidence.hashing import canonical_json, sha256_hex  # noqa: E402
from elementzero.physics_backends import (  # noqa: E402
    BACKEND_SKYRME,
    REFIT_STRICT,
)
from elementzero.physics_backends.artifact import (  # noqa: E402
    build_parameter_artifact,
)
from elementzero.physics_backends.skyrme_hfb import (  # noqa: E402
    BASELINE_SOURCE,
    SKYRME_BASELINE_INM,
    UPSTREAM_PATCH,
)
from elementzero.physics_backends.skyrme_hfb.prereg import PREREG_ID  # noqa: E402

READINESS = Path("reports/readiness/wo15b")
FITS = Path("reports/physics_backends/wo15/fits")
OUT = READINESS / "parameter_artifact_EZ-PHYS-SKYRME-HFB-v2.json"

UNITS = {
    "CpV0_0": "MeV fm^3",
    "CpV0_1": "MeV fm^3",
    "CrDr_0": "MeV fm^5",
    "CrDr_1": "MeV fm^5",
    "CrdJ_0": "MeV fm^5",
    "CrdJ_1": "MeV fm^5",
}


def main() -> int:
    refit = json.loads((READINESS / "skyrme_refit.json").read_text(encoding="utf-8"))
    tier = json.loads(
        (READINESS / "skyrme_tier_freeze.json").read_text(encoding="utf-8")
    )
    qual = json.loads(
        (READINESS / "skyrme_readfunc_qualification.json").read_text(encoding="utf-8")
    )
    freeze = json.loads(
        (FITS / "historical_fit_freeze.json").read_text(encoding="utf-8")
    )
    objective = json.loads(
        (FITS / "objective_manifest.json").read_text(encoding="utf-8")
    )
    old = json.loads(
        (FITS / f"parameter_artifact_{BACKEND_SKYRME}.json").read_text(
            encoding="utf-8"
        )
    )

    if refit["best_point"] is None:
        print("the refit produced no feasible point; the baseline stands")
        return 1

    # The full vector: refit values where fitted, baseline elsewhere. The
    # inert nuclear-matter entries are deliberately absent — recording
    # them would imply they were fitted.
    fitted = {k: float(v) for k, v in refit["best_point"].items()}
    values = {**{k: SKYRME_BASELINE_INM[k] for k in UNITS}, **fitted}
    names = sorted(values)

    artifact = build_parameter_artifact(
        backend_id="EZ-PHYS-SKYRME-HFB-v2",
        physics_family="skyrme_hfb_edf",
        solver_name="HFBTHO",
        solver_version=old["solver_version"],
        solver_source_hash=old["solver_source_hash"],
        build_manifest_hash=qual["binary_sha256"],
        parameter_names=names,
        parameter_values=[values[n] for n in names],
        parameter_units=[UNITS[n] for n in names],
        pairing_definition=old["pairing_definition"],
        basis_policy=old["basis_policy"],
        optimizer_id="ez-wo15b-nelder-mead-nd-v1",
        optimizer_version="1",
        objective_manifest_hash=objective["objective_manifest_hash"],
        freeze_id=freeze["freeze_id"],
        training_identity_digest=freeze["allowed_identity_digest"],
        calibration_identity_digest=freeze["calibration_identity_digest"],
        fit_started_at="2026-08-17T06:31:00Z",
        fit_completed_at="2026-08-17T09:40:00Z",
        convergence_status=refit["status"],
        objective_value=float(refit["best_objective_keV"]),
        covariance_artifact_hash="",
        fit_log_hash=refit["fit_log_hash"],
        provenance_class=REFIT_STRICT,
        parameterization_source={
            "base_parameterization": "SKM*",
            "publication_year": 1982,
            "baseline_source": BASELINE_SOURCE,
            "upstream_patch": UPSTREAM_PATCH,
            "prereg_id": PREREG_ID,
            "frozen_tier": tier["selected_tier"],
            "fitted_parameters": sorted(fitted),
            "held_at_baseline": sorted(set(UNITS) - set(fitted)),
            "supersedes_artifact": old["artifact_id"],
            "note": (
                "fitted over the identifiable, non-collinear subset; the "
                "nuclear-matter parameters are absent because HFBTHO does "
                "not read them for a (t,x)-defined force"
            ),
        },
    )
    OUT.write_text(canonical_json(artifact) + "\n", encoding="utf-8")
    print(f"artifact_id {artifact['artifact_id']}")
    print(f"objective   {artifact['objective_value']} keV")
    print(f"fitted      {sorted(fitted)}")
    print(f"wrote {OUT}")
    print(f"digest {sha256_hex(canonical_json(artifact))[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
