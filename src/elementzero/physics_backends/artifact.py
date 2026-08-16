"""PhysicsParameterArtifact — the immutable record of a fitted state.

An artifact answers, for one physics family: exactly which parameters,
produced by which optimizer against which objective, over exactly which
nuclides, under which freeze, with which solver build. Once B004 is
preregistered the artifact is frozen; a changed parameter is a new
artifact with a new id, never an edit.
"""

from __future__ import annotations

from typing import Any

from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_hex
from elementzero.identity_meta import elementzero_commit
from elementzero.physics_backends import PROVENANCE_CLASSES

REQUIRED_FIELDS = (
    "artifact_id",
    "backend_id",
    "physics_family",
    "solver_name",
    "solver_version",
    "solver_source_hash",
    "build_manifest_hash",
    "parameter_names",
    "parameter_values",
    "freeze_id",
    "training_identity_digest",
    "calibration_identity_digest",
    "convergence_status",
    "fit_log_hash",
    "provenance_class",
    "elementzero_commit",
)

IMMUTABILITY_RULE = (
    "ez-wo15-artifact-immutable-v1: a parameter artifact is immutable from "
    "B004 preregistration onward. Its id is the digest of its own content, "
    "so any change to a parameter, objective, membership, or build produces "
    "a different id — an edit in place is not representable"
)


def build_parameter_artifact(
    *,
    backend_id: str,
    physics_family: str,
    solver_name: str,
    solver_version: str,
    solver_source_hash: str,
    build_manifest_hash: str,
    parameter_names: list[str],
    parameter_values: list[float],
    parameter_units: list[str],
    pairing_definition: str,
    basis_policy: str,
    optimizer_id: str,
    optimizer_version: str,
    objective_manifest_hash: str,
    freeze_id: str,
    training_identity_digest: str,
    calibration_identity_digest: str,
    fit_started_at: str,
    fit_completed_at: str,
    convergence_status: str,
    objective_value: float | None,
    covariance_artifact_hash: str,
    fit_log_hash: str,
    provenance_class: str,
    parameterization_source: dict[str, Any],
) -> dict[str, Any]:
    if provenance_class not in PROVENANCE_CLASSES:
        raise ProtocolError(f"unknown provenance class {provenance_class!r}")
    if len(parameter_names) != len(parameter_values):
        raise ProtocolError("parameter names and values must correspond")
    payload = {
        "backend_id": backend_id,
        "physics_family": physics_family,
        "solver_name": solver_name,
        "solver_version": solver_version,
        "solver_source_hash": solver_source_hash,
        "build_manifest_hash": build_manifest_hash,
        "parameter_names": list(parameter_names),
        "parameter_values": [float(v) for v in parameter_values],
        "parameter_units": list(parameter_units),
        "pairing_definition": pairing_definition,
        "basis_policy": basis_policy,
        "optimizer_id": optimizer_id,
        "optimizer_version": optimizer_version,
        "objective_manifest_hash": objective_manifest_hash,
        "freeze_id": freeze_id,
        "training_identity_digest": training_identity_digest,
        "calibration_identity_digest": calibration_identity_digest,
        "fit_started_at": fit_started_at,
        "fit_completed_at": fit_completed_at,
        "convergence_status": convergence_status,
        "objective_value": objective_value,
        "covariance_artifact_hash": covariance_artifact_hash,
        "fit_log_hash": fit_log_hash,
        "provenance_class": provenance_class,
        "parameterization_source": parameterization_source,
        "elementzero_commit": elementzero_commit(),
        "immutability_rule": IMMUTABILITY_RULE,
    }
    payload["artifact_id"] = sha256_hex(payload)[:32]
    missing = [f for f in REQUIRED_FIELDS if f not in payload]
    if missing:
        raise ProtocolError(f"parameter artifact is missing {missing}")
    return payload


def assert_artifact_unchanged(
    artifact: dict[str, Any], *, expected_id: str
) -> None:
    """Recompute the content digest; an edited artifact cannot pass."""
    payload = {k: v for k, v in artifact.items() if k != "artifact_id"}
    recomputed = sha256_hex(payload)[:32]
    if recomputed != expected_id or artifact["artifact_id"] != expected_id:
        raise ProtocolError(
            f"parameter artifact {artifact.get('artifact_id')} does not match "
            f"the sealed id {expected_id}; {IMMUTABILITY_RULE}"
        )
