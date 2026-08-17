"""The training-era residual set a discrepancy model may see.

The dataset is where a blind protocol is won or lost. Every identity in
it is checked against the freeze on the way in, and every identity that
must stay out — WO-14 blind targets, B004 targets, and later the B005
targets — is digested into ``target_exclusion_digest`` so the exclusion
is a recorded fact rather than a claim in a docstring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.model_discrepancy.protocol import (
    ALLOWED_FEATURES,
    FEATURE_POLICY_ID,
    features_for,
)

AME1995_RELPATH = "data/amdc/mass_rmd.mas95"
CHRONOLOGY_RELPATH = "reports/eligibility/wo13/historical_source_chronology.json"
B004_TARGETS_RELPATH = "experiments/EZ-B004-v1/target_manifest.json"

TRAINING_SET_RULE = (
    "ez-wo15b-discrepancy-training-v1: a residual may enter the training "
    "set only when its nuclide is ground-truth-eligible in AME1995, its "
    "solve converged, and its identity is absent from every excluded set. "
    "The excluded identities are digested with the training identities, so "
    "membership is checkable without rerunning a solver"
)


def excluded_identities(*, repo_root: str | Path | None = None) -> dict[str, list[str]]:
    """Every identity a training residual may not come from."""
    import json

    root = Path(repo_root or REPO_ROOT)
    excluded: dict[str, list[str]] = {}

    b004 = root / B004_TARGETS_RELPATH
    if b004.is_file():
        excluded["EZ-B004-v1"] = sorted(
            json.loads(b004.read_text(encoding="utf-8"))["target_nuclide_ids"]
        )

    # WO-14's blind targets are the other set that must never be trained on:
    # they are the evidence that the earlier blind claim was blind.
    for experiment in ("EZ-B002-v2-real-blind", "EZ-B003-v2-real-blind"):
        sealed = root / "results" / experiment / "SEALED_PREDICTIONS.json"
        if not sealed.is_file():
            continue
        payload = json.loads(sealed.read_text(encoding="utf-8"))
        ids = payload.get("target_nuclide_ids") or payload.get("nuclide_ids")
        if ids:
            excluded[experiment] = sorted(ids)
    return dict(sorted(excluded.items()))


def build_training_set(
    *,
    family_id: str,
    freeze_id: str,
    rows: list[dict[str, Any]],
    eligible_ids: set[str],
    excluded: dict[str, list[str]],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """A schema-exact PhysicsDiscrepancyTrainingSet from converged rows.

    ``rows`` carry ``nuclide_id``, ``residual_keV`` (experiment minus raw
    physics) and the solver evidence behind them. Rows are refused, not
    silently dropped, when they fall outside the freeze.
    """
    root = Path(repo_root or REPO_ROOT)
    excluded_flat = {i for ids in excluded.values() for i in ids}

    kept: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: r["nuclide_id"]):
        nuclide_id = row["nuclide_id"]
        if nuclide_id not in eligible_ids:
            raise ProtocolError(
                f"DISCREPANCY_TRAINING_LEAK: {nuclide_id} is not "
                f"ground-truth-eligible in the {freeze_id} freeze. "
                f"{TRAINING_SET_RULE}"
            )
        if nuclide_id in excluded_flat:
            raise ProtocolError(
                f"DISCREPANCY_TRAINING_LEAK: {nuclide_id} is an excluded "
                f"blind identity. {TRAINING_SET_RULE}"
            )
        kept.append(row)

    nuclide_ids = [r["nuclide_id"] for r in kept]
    if len(set(nuclide_ids)) != len(nuclide_ids):
        raise ProtocolError(
            "DISCREPANCY_TRAINING_DUPLICATE: a nuclide appears twice in the "
            "training set; residual weighting would be silently doubled"
        )

    source_hashes = []
    for relpath in (AME1995_RELPATH, CHRONOLOGY_RELPATH):
        path = root / relpath
        if path.is_file():
            source_hashes.append(f"{relpath}:{sha256_file(path)}")

    record = {
        "training_set_id": f"ez-wo15b-discrepancy-training-{family_id}",
        "family_id": family_id,
        "freeze_id": freeze_id,
        "rule": TRAINING_SET_RULE,
        "feature_policy_id": FEATURE_POLICY_ID,
        "feature_names": list(ALLOWED_FEATURES),
        "nuclide_ids": nuclide_ids,
        "n_rows": len(kept),
        "residuals_keV": [float(r["residual_keV"]) for r in kept],
        "rows": kept,
        "source_hashes": sorted(source_hashes),
        "excluded_sets": excluded,
        "target_exclusion_digest": identity_digest(sorted(excluded_flat)),
        "training_identity_digest": identity_digest(nuclide_ids),
    }
    record["training_set_hash"] = sha256_hex(canonical_json(record))
    return record


def design_matrix(
    training_set: dict[str, Any],
) -> tuple[list[list[float]], list[float], list[str]]:
    """Features, targets and feature names, in a fixed column order."""
    from elementzero.data.identity import parse_nuclide_id

    names = list(training_set["feature_names"])
    x_rows: list[list[float]] = []
    for nuclide_id in training_set["nuclide_ids"]:
        z, n = parse_nuclide_id(nuclide_id)
        feats = features_for(z, n)
        x_rows.append([feats[name] for name in names])
    y = [float(v) for v in training_set["residuals_keV"]]
    return x_rows, y, names


__all__ = [
    "AME1995_RELPATH",
    "TRAINING_SET_RULE",
    "build_training_set",
    "design_matrix",
    "excluded_identities",
]
