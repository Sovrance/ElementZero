"""WO-15 fit campaign: freeze, lock the objective, refit, seal the artifact.

The order of operations is the scientific content of this module. The
freeze is written first, the objective is locked second, and only then
does a solver run. Nothing downstream can reach back and change either.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.amdc import load_edition
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.physics_backends import (
    HISTORICAL_FROZEN_PARTIAL,
    MODERN_REFERENCE,
    REFIT_STRICT,
)
from elementzero.physics_backends.adapters.hfbtho import (
    BASIS_POLICY,
    gogny_backend,
    skyrme_backend,
)
from elementzero.physics_backends.fit import (
    MAX_EVALUATIONS,
    OPTIMIZER_ID,
    OPTIMIZER_VERSION,
    run_refit,
)
from elementzero.physics_backends.freeze import (
    allowed_training_ids,
    build_freeze,
    select_calibration_ids,
)
from elementzero.physics_backends.objective import build_objective_manifest
from elementzero.physics_backends.provenance import (
    PARAMETERIZATIONS,
    parameterization_admissible,
)

AME1995_RELPATH = "data/amdc/mass_rmd.mas95"
CAMPAIGN_CREATED_AT = "2026-08-16T20:00:00Z"

# Which published parameterization each family starts from. Both predate
# the freeze; the covariant family's only available forces do not, which
# is a finding rather than a choice.
FAMILY_PARAMETERIZATION = {
    "EZ-PHYS-SKYRME-HFB-v1": "SKM*",
    "EZ-PHYS-GOGNY-HFB-v1": "D1S",
    "EZ-PHYS-COVARIANT-RHB-v1": "DD-ME2",
}

PAIRING_DEFINITION = (
    "volume delta pairing, strengths vpair_n / vpair_p in MeV fm^3 with a "
    "60 MeV quasiparticle cutoff and pairing_feature 0.5, as implemented by "
    "HFBTHO's user_pairing path"
)


def training_masses(*, repo_root: str | Path | None = None) -> dict[str, tuple[float, float]]:
    """Training-era masses: AME1995 ground-truth-eligible values only."""
    root = Path(repo_root or REPO_ROOT)
    return {
        o.nuclide_id: (o.mass_excess_keV, o.uncertainty_keV)
        for o in load_edition("AME1995", str(root / AME1995_RELPATH))
        if o.ground_truth_eligible
    }


def prepare_campaign(
    *, repo_root: str | Path | None = None, validation_ids: list[str] | None = None
) -> dict[str, Any]:
    """Freeze plus locked objective — written before any solver call."""
    root = Path(repo_root or REPO_ROOT)
    masses = training_masses(repo_root=root)
    allowed = allowed_training_ids(repo_root=root)
    calibration_ids = select_calibration_ids(masses=masses, allowed=allowed)
    freeze = build_freeze(
        calibration_nuclide_ids=calibration_ids,
        validation_nuclide_ids=sorted(validation_ids or []),
        repo_root=root,
    )
    objective = build_objective_manifest(
        calibration_nuclide_ids=calibration_ids,
        freeze_id=freeze["freeze_id"],
        source_hash=sha256_file(root / AME1995_RELPATH),
    )
    return {
        "freeze": freeze,
        "objective": objective,
        "calibration": {i: masses[i][0] for i in calibration_ids},
        "calibration_uncertainty_keV": {i: masses[i][1] for i in calibration_ids},
    }


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def refit_family(
    *,
    backend_id: str,
    campaign: dict[str, Any],
    work_root: str | Path,
    log_path: str | Path,
    max_workers: int = 2,
    max_evaluations: int = MAX_EVALUATIONS,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Refit one family's pairing sector under the locked objective."""
    parameterization = FAMILY_PARAMETERIZATION[backend_id]
    if backend_id == "EZ-PHYS-SKYRME-HFB-v1":
        backend = skyrme_backend(functional=parameterization, repo_root=repo_root)
    elif backend_id == "EZ-PHYS-GOGNY-HFB-v1":
        backend = gogny_backend(functional=parameterization, repo_root=repo_root)
    else:
        raise ProtocolError(f"{backend_id} has no refittable HFBTHO path")

    started = _now()
    fit = run_refit(
        backend=backend,
        calibration=campaign["calibration"],
        objective_manifest=campaign["objective"],
        work_root=work_root,
        max_evaluations=max_evaluations,
        max_workers=max_workers,
        log_path=log_path,
    )
    completed = _now()
    if fit["best"] is None:
        raise ProtocolError(
            f"{backend_id}: no feasible parameter vector; the family is "
            "PHYSICS_BACKEND_NUMERICALLY_UNSTABLE under this freeze"
        )

    freeze = campaign["freeze"]
    artifact = backend.export_parameter_artifact(
        parameter_names=["vpair_n", "vpair_p"],
        parameter_values=[fit["best"]["vpair_n"], fit["best"]["vpair_p"]],
        parameter_units=["MeV fm^3", "MeV fm^3"],
        pairing_definition=PAIRING_DEFINITION,
        optimizer_id=OPTIMIZER_ID,
        optimizer_version=OPTIMIZER_VERSION,
        objective_manifest_hash=campaign["objective"]["objective_manifest_hash"],
        freeze_id=freeze["freeze_id"],
        training_identity_digest=freeze["allowed_identity_digest"],
        calibration_identity_digest=freeze["calibration_identity_digest"],
        fit_started_at=started,
        fit_completed_at=completed,
        convergence_status=fit["status"],
        objective_value=fit["best"]["objective"],
        covariance_artifact_hash=sha256_hex(
            {"evaluations": [
                {k: e[k] for k in ("vpair_n", "vpair_p", "objective")}
                for e in fit["evaluations"]
            ]}
        ),
        fit_log_hash=fit["fit_log_hash"],
        provenance_class=REFIT_STRICT,
        parameterization_source={
            "base_parameterization": parameterization,
            **PARAMETERIZATIONS[parameterization],
            "freeze_admissible": parameterization_admissible(parameterization),
            "refit_scope": (
                "pairing sector only (vpair_n, vpair_p); the bulk EDF stays "
                "at its published historical values"
            ),
            "provenance_reasoning": (
                "the refitted parameters have exact calibration membership "
                "and consumed AME1995 evidence only, so the pairing sector is "
                "REFIT_STRICT; the underlying "
                f"{parameterization} bulk functional is a pre-freeze "
                "publication with prose-level calibration membership, "
                "recorded here as its own "
                f"{HISTORICAL_FROZEN_PARTIAL} provenance"
            ),
            "base_provenance_class": HISTORICAL_FROZEN_PARTIAL,
        },
    )
    return {"fit": fit, "artifact": artifact, "backend_id": backend_id}


def reference_artifact(
    *, backend_id: str, campaign: dict[str, Any], repo_root: str | Path | None = None
) -> dict[str, Any]:
    """A published post-freeze parameterization, labeled MODERN_REFERENCE."""
    from elementzero.physics_backends.adapters.dirhb import dirhb_backend

    parameterization = FAMILY_PARAMETERIZATION[backend_id]
    backend = dirhb_backend(force=parameterization, repo_root=repo_root)
    freeze = campaign["freeze"]
    return {
        "backend_id": backend_id,
        "artifact": backend.export_parameter_artifact(
            parameter_names=["force"],
            parameter_values=[0.0],
            parameter_units=["published parameter set"],
            pairing_definition=(
                "separable / monopole pairing as implemented by the DIRHB "
                "spherical solver for the published force"
            ),
            optimizer_id="none-published-parameterization",
            optimizer_version="n/a",
            objective_manifest_hash=campaign["objective"]["objective_manifest_hash"],
            freeze_id=freeze["freeze_id"],
            training_identity_digest=identity_digest([]),
            calibration_identity_digest=identity_digest([]),
            fit_started_at=CAMPAIGN_CREATED_AT,
            fit_completed_at=CAMPAIGN_CREATED_AT,
            convergence_status="PUBLISHED_PARAMETERIZATION",
            objective_value=None,
            covariance_artifact_hash=sha256_hex({"published": parameterization}),
            fit_log_hash=sha256_hex({"published": parameterization}),
            provenance_class=MODERN_REFERENCE,
            parameterization_source={
                "base_parameterization": parameterization,
                **PARAMETERIZATIONS[parameterization],
                "freeze_admissible": parameterization_admissible(parameterization),
                "refit_scope": "none — published parameterization used as-is",
                "provenance_reasoning": (
                    f"{parameterization} was published in "
                    f"{PARAMETERIZATIONS[parameterization]['publication_year']}, "
                    "after the 1995 freeze. The DIRHB distribution ships no "
                    "pre-freeze force, so the covariant family cannot be made "
                    "historically blind by parameter selection alone. This is "
                    "recorded as MODERN_REFERENCE rather than argued around"
                ),
                "base_provenance_class": MODERN_REFERENCE,
            },
            basis_policy=BASIS_POLICY,
        ),
    }


def write_campaign(dest: str | Path, payload: dict[str, Any]) -> str:
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return sha256_file(path)
