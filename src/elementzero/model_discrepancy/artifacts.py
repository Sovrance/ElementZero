"""Immutable artifacts for the discrepancy and calibration stages.

Same discipline as the WO-15 parameter artifact: the id *is* the digest
of the content, so an artifact that has been edited no longer answers to
its own name. The B005 unlock re-checks every one of these before truth
is read.
"""

from __future__ import annotations

from typing import Any

from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.model_discrepancy.protocol import (
    FEATURE_POLICY_ID,
    FIT_METHOD,
    MODEL_TYPE_GP,
)
from elementzero.readiness import CHILD_FAMILY_RULE

# The uncertainty components a calibrated family must carry separately.
# Naming them in the artifact is what makes "no post-blind scalar sigma
# inflation" checkable: an inflated sigma has no component to point at.
REQUIRED_UNCERTAINTY_COMPONENTS = (
    "numerical",
    "parameter",
    "model_discrepancy",
)
SEPARATE_NOT_IN_SIGMA = ("cross_family_disagreement",)


def build_discrepancy_artifact(
    *,
    family_id: str,
    independence_group: str,
    training_set: dict[str, Any],
    hyperparameters: dict[str, Any],
    cv_metrics: dict[str, float],
    feature_names: list[str],
    scaling: dict[str, list[float]],
) -> dict[str, Any]:
    """A schema-exact, content-addressed DiscrepancyModelArtifact."""
    record = {
        "family_id": family_id,
        "independence_group": independence_group,
        "counts_as_independent_family": False,
        "child_family_rule": CHILD_FAMILY_RULE,
        "model_type": MODEL_TYPE_GP,
        "kernel": "RBF + white noise, zero mean",
        "fit_method": FIT_METHOD,
        "feature_policy_id": FEATURE_POLICY_ID,
        "feature_names": list(feature_names),
        "feature_scaling": scaling,
        "hyperparameters": dict(sorted(hyperparameters.items())),
        "training_set_hash": training_set["training_set_hash"],
        "training_identity_digest": training_set["training_identity_digest"],
        "target_exclusion_digest": training_set["target_exclusion_digest"],
        "n_training_rows": training_set["n_rows"],
        "cv_metrics": dict(sorted(cv_metrics.items())),
    }
    digest = sha256_hex(canonical_json(record))
    record["artifact_hash"] = digest
    record["artifact_id"] = f"ez-wo15b-discrepancy-{family_id}-{digest[:12]}"
    return record


def build_calibration_artifact(
    *,
    family_id: str,
    independence_group: str,
    raw_parameter_artifact: str,
    discrepancy_artifact: dict[str, Any],
    training_set: dict[str, Any],
    calibration_set_hash: str,
    training_coverage: dict[str, Any] | None,
    cv_coverage: dict[str, float],
    provenance_class: str,
    blind_eligible: bool,
) -> dict[str, Any]:
    """A schema-exact, content-addressed FamilyCalibrationArtifact."""
    record = {
        "family_id": family_id,
        "independence_group": independence_group,
        "provenance_class": provenance_class,
        "blind_eligible": blind_eligible,
        "raw_parameter_artifact": raw_parameter_artifact,
        "discrepancy_artifact": discrepancy_artifact["artifact_id"],
        "discrepancy_artifact_hash": discrepancy_artifact["artifact_hash"],
        "training_set_hash": training_set["training_set_hash"],
        "calibration_set_hash": calibration_set_hash,
        "uncertainty_components": list(REQUIRED_UNCERTAINTY_COMPONENTS),
        "components_reported_separately": list(SEPARATE_NOT_IN_SIGMA),
        "training_coverage": training_coverage,
        "cv_coverage": dict(sorted(cv_coverage.items())),
    }
    digest = sha256_hex(canonical_json(record))
    record["artifact_hash"] = digest
    record["calibration_artifact_id"] = (
        f"ez-wo15b-calibration-{family_id}-{digest[:12]}"
    )
    return record


def assert_artifact_unchanged(artifact: dict[str, Any], *, kind: str) -> None:
    """Re-derive the digest; an edited artifact fails its own name."""
    id_key = (
        "calibration_artifact_id" if kind == "calibration" else "artifact_id"
    )
    stripped = {
        k: v
        for k, v in artifact.items()
        if k not in ("artifact_hash", id_key)
    }
    digest = sha256_hex(canonical_json(stripped))
    if digest != artifact["artifact_hash"]:
        raise ProtocolError(
            f"WO15B_ARTIFACT_MUTATED: {kind} artifact "
            f"{artifact.get(id_key)} now hashes {digest}, recorded "
            f"{artifact['artifact_hash']}"
        )


def assert_components_present(artifact: dict[str, Any]) -> None:
    """Every declared uncertainty component must actually be named."""
    missing = sorted(
        set(REQUIRED_UNCERTAINTY_COMPONENTS)
        - set(artifact.get("uncertainty_components", []))
    )
    if missing:
        raise ProtocolError(
            f"WO15B_UNCERTAINTY_INCOMPLETE: {artifact.get('family_id')} does "
            f"not carry {missing}; a sigma without a named component is a "
            "scalar, not a decomposition"
        )
    overlap = sorted(
        set(SEPARATE_NOT_IN_SIGMA) & set(artifact["uncertainty_components"])
    )
    if overlap:
        raise ProtocolError(
            f"WO15B_DISAGREEMENT_ABSORBED: {overlap} must be reported "
            "separately, never inside a family's own sigma"
        )


__all__ = [
    "REQUIRED_UNCERTAINTY_COMPONENTS",
    "SEPARATE_NOT_IN_SIGMA",
    "assert_artifact_unchanged",
    "assert_components_present",
    "build_calibration_artifact",
    "build_discrepancy_artifact",
]
