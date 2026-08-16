"""Claim adjudication records (WO-14 spec section 14).

Every scored run produces one schema-exact ClaimAdjudication record. The
adjudication is where scope discipline is enforced in data: B002 blind
evidence is CONTROL_BLIND_GEOGRAPHIC and can never become physics
validation; reconstruction scopes never grant blind credit.
"""

from __future__ import annotations

from typing import Any

from elementzero.errors import ProtocolError
from elementzero.real_validation.protocol import (
    B002_BLIND_PROHIBITED_SCOPES,
    SCOPE_CONTROL_BLIND_GEOGRAPHIC,
    SCOPE_FULL_BLIND_SHELL_REDISCOVERY,
    SCOPE_PHYSICS_BLIND_EDGE_STRUCTURE,
    SCOPE_PHYSICS_BLIND_MASS_EDGE,
    SCOPE_RECONSTRUCTION_GEOGRAPHIC,
    SCOPE_RECONSTRUCTION_SHELL_STRUCTURE,
    TRACK_BLIND,
    TRACK_RECONSTRUCTION,
)

ALLOWED_SCOPES = (
    SCOPE_CONTROL_BLIND_GEOGRAPHIC,
    SCOPE_RECONSTRUCTION_GEOGRAPHIC,
    SCOPE_PHYSICS_BLIND_MASS_EDGE,
    SCOPE_PHYSICS_BLIND_EDGE_STRUCTURE,
    SCOPE_FULL_BLIND_SHELL_REDISCOVERY,
    SCOPE_RECONSTRUCTION_SHELL_STRUCTURE,
)

_RECON_SCOPES = (
    SCOPE_RECONSTRUCTION_GEOGRAPHIC,
    SCOPE_RECONSTRUCTION_SHELL_STRUCTURE,
)


def build_adjudication(
    *,
    experiment_id: str,
    run_id: str,
    benchmark_id: str,
    claim_track: str,
    prediction_seal_hash: str,
    eligible_model_ids: list[str],
    excluded_model_ids: list[str],
    physics_independence_groups: list[str],
    claim_type: str,
    scientific_scope: str,
    inherited_criterion_status: str,
    blind_gate_status: str,
    visual_stage_permission: str,
    next_gate: str,
) -> dict[str, Any]:
    if scientific_scope not in ALLOWED_SCOPES:
        raise ProtocolError(f"unknown scientific scope {scientific_scope!r}")
    if scientific_scope in B002_BLIND_PROHIBITED_SCOPES:
        raise ProtocolError(
            f"{scientific_scope} is a prohibited claim; control-only "
            "evidence never becomes physics validation"
        )
    if claim_track == TRACK_RECONSTRUCTION and scientific_scope not in _RECON_SCOPES:
        raise ProtocolError(
            "a reconstruction run may only adjudicate reconstruction scopes"
        )
    if claim_track == TRACK_BLIND and scientific_scope in _RECON_SCOPES:
        raise ProtocolError("a blind run never adjudicates a reconstruction scope")
    if (
        experiment_id.startswith("EZ-B002")
        and claim_track == TRACK_BLIND
        and scientific_scope != SCOPE_CONTROL_BLIND_GEOGRAPHIC
    ):
        raise ProtocolError(
            "B002 REAL-BLIND is control-only: zero blind physics groups "
            "means CONTROL_BLIND_GEOGRAPHIC is the only admissible scope"
        )
    if (
        scientific_scope == SCOPE_FULL_BLIND_SHELL_REDISCOVERY
        and blind_gate_status != "FULL_SHELL_BLIND_CRITERION_MET"
    ):
        raise ProtocolError(
            "FULL_BLIND_SHELL_REDISCOVERY requires the full-shell blind "
            "criterion to be independently met by the audited blind track"
        )
    return {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "benchmark_id": benchmark_id,
        "claim_track": claim_track,
        "prediction_seal_hash": prediction_seal_hash,
        "eligible_model_ids": sorted(eligible_model_ids),
        "excluded_model_ids": sorted(excluded_model_ids),
        "physics_independence_groups": sorted(physics_independence_groups),
        "claim_type": claim_type,
        "scientific_scope": scientific_scope,
        "inherited_criterion_status": inherited_criterion_status,
        "blind_gate_status": blind_gate_status,
        "visual_stage_permission": visual_stage_permission,
        "next_gate": next_gate,
    }
