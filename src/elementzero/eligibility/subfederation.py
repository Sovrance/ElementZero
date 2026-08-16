"""Target-specific strict-blind subfederation (WO-13 spec sections 14-15).

For each target, retain only the contributors whose lineage is blind to
that target under the benchmark's allowed blind claim types, preserve
independence groups, reject everything else, and record exactly who
remained. Residual variants are never counted as independent physics
families — Tier 2 cannot be faked with wrappers.
"""

from __future__ import annotations

from typing import Any

from elementzero.eligibility.claim_types import (
    BLIND_CLAIM_TYPES,
    HISTORICAL_BLIND,
    STRICT_BLIND,
    worst_claim,
)
from elementzero.eligibility.model_training_provenance import (
    BASELINE_MODEL_IDS,
    PHYSICS_TABLE_MODEL_IDS,
)
from elementzero.errors import ProtocolError

SUBFEDERATION_RULE = (
    "ez-wo13-subfederation-v1: per target, retain only contributors whose "
    "claim type is an allowed blind type with strict-gate-eligible "
    "provenance; recompute combination weights from allowed training-era "
    "evidence only; persist the exact contributor list. Nonblind and "
    "unknown-provenance contributors are rejected, never reweighted to "
    "near-zero."
)

COMBINER_POLICY = (
    "ez-wo13-blind-combiner-v1: uniform weights over the eligible blind "
    "contributors are persisted at preregistration; validation weights, if "
    "used, are learned at seal time from the freeze-controlled calibration "
    "split of allowed training-era evidence only, and the fitted weights "
    "are persisted next to the sealed run"
)

# Gate tiers (spec section 15).
TIER_CONTROL = "CONTROL_BLIND_EVALUABLE"
TIER_PHYSICS = "PHYSICS_BLIND_EVALUABLE"
TIER_FEDERATED = "FEDERATED_BLIND_EVALUABLE"
NOT_EVALUABLE = "REAL_BLIND_GATE_NOT_EVALUABLE"

TIER_RULE = (
    "ez-wo13-blind-tiers-v1: Tier 0 = at least one blind refittable "
    "baseline (CONTROL_BLIND_EVALUABLE); Tier 1 = at least one blind "
    "global physics backbone (PHYSICS_BLIND_EVALUABLE); Tier 2 = at least "
    "two blind physics independence groups (FEDERATED_BLIND_EVALUABLE). "
    "Residual variants of one base are not independent physics families "
    "and never count toward Tier 1 or 2."
)


def build_subfederation(
    *,
    target_id: str,
    matrix_records: list[dict[str, Any]],
    allowed_claim_types: tuple[str, ...] = (STRICT_BLIND, HISTORICAL_BLIND),
) -> dict[str, Any]:
    """The strict-blind subfederation manifest entry for one target."""
    for claim in allowed_claim_types:
        if claim not in BLIND_CLAIM_TYPES:
            raise ProtocolError(
                f"{claim} is not a blind claim type; a strict-blind "
                "subfederation may only admit STRICT_BLIND/HISTORICAL_BLIND"
            )
    records = [r for r in matrix_records if r["nuclide_id"] == target_id]
    if not records:
        raise ProtocolError(f"no eligibility records for target {target_id}")
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda r: r["model_id"]):
        admitted = (
            record["claim_type"] in allowed_claim_types
            and record["strict_gate_eligible"]
        )
        (eligible if admitted else excluded).append(record)
    eligible_ids = [r["model_id"] for r in eligible]
    groups = sorted({r["independence_group"] for r in eligible})
    physics_groups = sorted(
        {
            r["independence_group"]
            for r in eligible
            if r["model_id"] in PHYSICS_TABLE_MODEL_IDS
        }
    )
    weights = (
        {m: 1.0 / len(eligible_ids) for m in eligible_ids} if eligible_ids else {}
    )
    entry: dict[str, Any] = {
        "target_id": target_id,
        "eligible_models": eligible_ids,
        "excluded_models": [
            {"model_id": r["model_id"], "claim_type": r["claim_type"]}
            for r in excluded
        ],
        "eligible_independence_groups": groups,
        "eligible_physics_independence_groups": physics_groups,
        "combiner_policy": COMBINER_POLICY,
        "weights": weights,
        "gate_evaluable": bool(eligible_ids),
    }
    if eligible_ids:
        entry["resulting_claim_type"] = worst_claim(
            *(r["claim_type"] for r in eligible)
        )
    tier = target_tier(entry)
    entry["tier"] = tier
    return entry


def target_tier(entry: dict[str, Any]) -> str:
    """The highest blind gate tier this target's subfederation supports."""
    if not entry["eligible_models"]:
        return NOT_EVALUABLE
    n_physics = len(entry["eligible_physics_independence_groups"])
    if n_physics >= 2:
        return TIER_FEDERATED
    if n_physics == 1:
        return TIER_PHYSICS
    if any(m in BASELINE_MODEL_IDS for m in entry["eligible_models"]):
        return TIER_CONTROL
    return NOT_EVALUABLE


_TIER_ORDER = (NOT_EVALUABLE, TIER_CONTROL, TIER_PHYSICS, TIER_FEDERATED)


def benchmark_blind_status(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-target tiers into one honest benchmark status.

    The benchmark status is the highest tier available on at least one
    preregistered target, reported next to the per-tier target counts so a
    single lucky target can never masquerade as broad coverage.
    """
    counts = {tier: 0 for tier in _TIER_ORDER}
    for entry in entries:
        counts[entry["tier"]] += 1
    best = NOT_EVALUABLE
    for tier in _TIER_ORDER:
        if counts[tier]:
            best = tier
    return {
        "rule": TIER_RULE,
        "status": best,
        "n_targets": len(entries),
        "targets_by_tier": counts,
    }


def build_manifest(
    *,
    experiment_id: str,
    matrix: dict[str, Any],
    allowed_claim_types: tuple[str, ...] = (STRICT_BLIND, HISTORICAL_BLIND),
) -> dict[str, Any]:
    """Subfederation manifest for every target of one experiment."""
    target_ids = sorted({r["nuclide_id"] for r in matrix["records"]})
    entries = [
        build_subfederation(
            target_id=target_id,
            matrix_records=matrix["records"],
            allowed_claim_types=allowed_claim_types,
        )
        for target_id in target_ids
    ]
    return {
        "work_order": "WO-13",
        "rule": SUBFEDERATION_RULE,
        "experiment_id": experiment_id,
        "allowed_claim_types": list(allowed_claim_types),
        "targets": entries,
        "benchmark_blind_status": benchmark_blind_status(entries),
    }
