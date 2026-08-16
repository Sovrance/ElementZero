"""HistoricalPhysicsFitFreeze — what the fit was allowed to see.

The freeze is the whole argument. A fitted model is historically blind on
a target because the freeze provably excluded that target's evidence, not
because the parameterization feels old.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT, atlas_pir_ref
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import sha256_hex
from elementzero.identity_meta import elementzero_commit
from elementzero.physics_backends.provenance import FIT_FREEZE_CUTOFF

FREEZE_ID = "ez-wo15-historical-fit-freeze-v1"
CHRONOLOGY_RELPATH = "reports/eligibility/wo13/historical_source_chronology.json"

# WO-14's committed truth is the thing a WO-15 fit must never touch.
WO14_TRUTH_ARTIFACTS = (
    "results/EZ-B002-v2-real-blind/aggregate.json",
    "results/EZ-B002-v2-real-recon/aggregate.json",
    "results/EZ-B003-v2-real-blind/mass_results.json",
    "results/EZ-B003-v2-real-blind/derived_results.json",
    "results/EZ-B003-v2-real-recon/closure_results.json",
)

FREEZE_RULE = (
    "ez-wo15-freeze-v1: fitting may consume only ground-truth-eligible "
    "masses present in the AME1995 snapshot. Every later edition, every "
    "WO-14 scored result, and every B004 target is forbidden — not by "
    "convention but by membership: the allowed identity set is enumerated "
    "and digested, and the forbidden sets are digested alongside it"
)

# The calibration selection rule is preregistered and deterministic. It
# uses identity and training-era mass only — never a model residual,
# never a WO-14 error table.
CALIBRATION_RULE_ID = "ez-wo15-calibration-selection-v1"
CALIBRATION_BANDS = ((16, 60), (60, 110), (110, 160), (160, 240))
CALIBRATION_PER_BAND = 3
CALIBRATION_RULE = (
    f"{CALIBRATION_RULE_ID}: from the AME1995 ground-truth-eligible "
    "even-even nuclides, take the "
    f"{CALIBRATION_PER_BAND} nuclides closest to the centre of each mass "
    f"band {CALIBRATION_BANDS} whose proton and neutron numbers are both "
    "even and whose measured uncertainty is at most 50 keV, ordered by "
    "(|A - band centre|, Z, N). Selection consumes identity, training-era "
    "mass, and training-era uncertainty only"
)


def _chronology(repo_root: Path) -> dict[str, Any]:
    path = repo_root / CHRONOLOGY_RELPATH
    if not path.is_file():
        raise ProtocolError(f"{path} is missing; WO-13 chronology is required")
    return json.loads(path.read_text(encoding="utf-8"))


def allowed_training_ids(*, repo_root: str | Path | None = None) -> list[str]:
    """Every AME1995 ground-truth-eligible nuclide id, sorted."""
    root = Path(repo_root or REPO_ROOT)
    payload = _chronology(root)
    return sorted(payload["sources"]["AME1995"]["eligible_nuclide_ids"])


def select_calibration_ids(
    *,
    masses: dict[str, tuple[float, float]],
    allowed: list[str],
) -> list[str]:
    """Apply CALIBRATION_RULE deterministically.

    ``masses`` maps nuclide id to (mass_excess_keV, uncertainty_keV) from
    the training-era snapshot.
    """
    chosen: list[str] = []
    for low, high in CALIBRATION_BANDS:
        centre = (low + high) / 2.0
        candidates = []
        for nuclide_id in allowed:
            z, n = parse_nuclide_id(nuclide_id)
            a = z + n
            if z % 2 or n % 2 or z < 8 or not (low <= a < high):
                continue
            entry = masses.get(nuclide_id)
            if entry is None or entry[1] > 50.0:
                continue
            candidates.append((abs(a - centre), z, n, nuclide_id))
        candidates.sort()
        chosen.extend(c[3] for c in candidates[:CALIBRATION_PER_BAND])
    return sorted(chosen)


def build_freeze(
    *,
    calibration_nuclide_ids: list[str],
    validation_nuclide_ids: list[str],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """The committed freeze record (spec section 7)."""
    root = Path(repo_root or REPO_ROOT)
    payload = _chronology(root)
    allowed = allowed_training_ids(repo_root=root)
    unknown = [i for i in calibration_nuclide_ids if i not in set(allowed)]
    if unknown:
        raise ProtocolError(
            f"calibration nuclides {unknown} are not freeze-admissible; the "
            "fit cannot see them"
        )

    forbidden_hashes = {}
    for relpath in WO14_TRUTH_ARTIFACTS:
        path = root / relpath
        if path.is_file():
            from elementzero.evidence.hashing import sha256_file

            forbidden_hashes[relpath] = sha256_file(path)

    freeze = {
        "freeze_id": FREEZE_ID,
        "cutoff_date": FIT_FREEZE_CUTOFF,
        "source_publication_cutoff": FIT_FREEZE_CUTOFF,
        "allowed_dataset_hashes": {
            "AME1995": payload["sources"]["AME1995"]["raw_sha256"],
        },
        "forbidden_dataset_hashes": {
            edition: payload["sources"][edition]["raw_sha256"]
            for edition in ("AME2003", "AME2012", "AME2016", "AME2020")
        },
        "wo14_truth_forbidden_hashes": dict(sorted(forbidden_hashes.items())),
        "n_allowed_nuclides": len(allowed),
        "allowed_identity_digest": identity_digest(allowed),
        "calibration_nuclide_ids": sorted(calibration_nuclide_ids),
        "calibration_identity_digest": identity_digest(calibration_nuclide_ids),
        "validation_nuclide_ids": sorted(validation_nuclide_ids),
        "validation_identity_digest": identity_digest(validation_nuclide_ids),
        "observable_manifest": ["atomic_mass_excess_keV"],
        "physics_constraints_manifest": [
            "spherical ground state only",
            "even-even nuclides only (EVEN_EVEN_ONLY)",
            "no constraint on deformation beyond the preregistered basis",
        ],
        "calibration_rule": CALIBRATION_RULE,
        "rule": FREEZE_RULE,
        "elementzero_commit": elementzero_commit(),
        "atlas_pir_ref": atlas_pir_ref(),
    }
    freeze["freeze_hash"] = sha256_hex(freeze)
    return freeze


def assert_no_forbidden_membership(
    *, freeze: dict[str, Any], used_ids: list[str]
) -> None:
    """Every nuclide a fit consumed must be inside the freeze."""
    allowed = set(freeze["calibration_nuclide_ids"])
    leaked = sorted(set(used_ids) - allowed)
    if leaked:
        raise ProtocolError(
            f"HISTORICAL_FIT_INTEGRITY_FAILURE: the fit consumed {leaked}, "
            "which the freeze does not admit"
        )
