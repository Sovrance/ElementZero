"""Derived shell-observable blindness audit (WO-14 spec sections 8-9).

The 12 historical-blind central targets do not automatically make the
derived shell observables blind: S2n/S2p/delta2n/delta2p and the local
peak rank consume neighbor masses, and a model that was fitted on a
neighbor's truth is not blind for that component. Every derived
observable gets a DerivedBlindnessRecord naming its components and each
model's per-component claim; FULL_BLIND_SHELL_REDISCOVERY is permitted
only when every model-side input satisfies the blind policy. Known
post-seal scoring truth never repairs a model that was trained on the
answer.
"""

from __future__ import annotations

from typing import Any

from elementzero.data.identity import parse_nuclide_id
from elementzero.eligibility.claim_types import (
    HISTORICAL_BLIND,
    INELIGIBLE_UNKNOWN_PROVENANCE,
    NONBLIND_REFERENCE,
    STRICT_BLIND,
    worst_claim,
)
from elementzero.eligibility.historical_sources import SourceChronology

DERIVED_OBSERVABLES = ("S2n", "S2p", "delta2n", "delta2p", "local_peak_rank")

DERIVED_BLINDNESS_RULE = (
    "ez-wo14-derived-blindness-v1: a derived shell observable is blind only "
    "when every model-side component mass entering it satisfies the blind "
    "policy for the model under test; central-target blindness never "
    "propagates to neighbors, and post-seal scoring truth never repairs a "
    "model that was fitted on a component's answer"
)


def _nid(z: int, n: int) -> str:
    return f"Z{z}-N{n}"


def component_ids(observable: str, nuclide_id: str, *, chain_window: int = 4):
    """Model-side mass components of one derived observable."""
    z, n = parse_nuclide_id(nuclide_id)
    if observable == "S2n":
        return [_nid(z, n - 2), _nid(z, n)]
    if observable == "S2p":
        return [_nid(z - 2, n), _nid(z, n)]
    if observable == "delta2n":
        return [_nid(z, n - 2), _nid(z, n), _nid(z, n + 2)]
    if observable == "delta2p":
        return [_nid(z - 2, n), _nid(z, n), _nid(z + 2, n)]
    if observable == "local_peak_rank":
        # The rank compares delta2n along the isotopic chain: every chain
        # member's delta2n enters, so the component set is the chain window
        # with its +-2 halo. This breadth is exactly why full-shell
        # rediscovery is so hard to claim blind.
        return [
            _nid(z, m)
            for m in range(n - 2 * chain_window - 2, n + 2 * chain_window + 3, 2)
            if m >= 0
        ]
    raise ValueError(f"unknown derived observable {observable!r}")


def component_claim(
    *,
    model_id: str,
    component_id: str,
    blind_targets: frozenset[str],
    chronology: SourceChronology,
) -> str:
    """One model's blindness claim for one component mass.

    FRDM95 (frozen table): HISTORICAL_BLIND only where the component was
    not even a parsed record in AME1995. Refittable lineages (baselines and
    the FRDM residual wrapper) are STRICT_BLIND only for components the
    sealed freeze excluded from fitting — i.e. the 12 blind targets
    themselves; every other component's truth sat in their training corpus.
    """
    if model_id == "EZ-FRDM95-TABLE-v1":
        if not chronology.was_target_known_by(component_id, "AME1995"):
            return HISTORICAL_BLIND
        return INELIGIBLE_UNKNOWN_PROVENANCE
    if model_id == "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1":
        base = component_claim(
            model_id="EZ-FRDM95-TABLE-v1",
            component_id=component_id,
            blind_targets=blind_targets,
            chronology=chronology,
        )
        residual = (
            STRICT_BLIND if component_id in blind_targets else NONBLIND_REFERENCE
        )
        return worst_claim(base, residual)
    # Refittable baselines: the freeze excluded exactly the blind targets.
    if component_id in blind_targets:
        return STRICT_BLIND
    return NONBLIND_REFERENCE


def build_records(
    *,
    blind_target_ids: list[str],
    model_ids: list[str],
    chronology: SourceChronology,
    truth_available: frozenset[str],
) -> list[dict[str, Any]]:
    """One DerivedBlindnessRecord per (observable, central target)."""
    blind_targets = frozenset(blind_target_ids)
    records: list[dict[str, Any]] = []
    for nuclide_id in sorted(blind_target_ids):
        for observable in DERIVED_OBSERVABLES:
            components = component_ids(observable, nuclide_id)
            claims = {
                model_id: {
                    component: component_claim(
                        model_id=model_id,
                        component_id=component,
                        blind_targets=blind_targets,
                        chronology=chronology,
                    )
                    for component in components
                }
                for model_id in sorted(model_ids)
            }
            # Truth values are needed for every component to score the
            # observable at all (post-seal unlock; scoring only).
            truth_missing = [c for c in components if c not in truth_available]
            per_model_blind = {
                model_id: all(
                    claim in (STRICT_BLIND, HISTORICAL_BLIND)
                    for claim in per_component.values()
                )
                for model_id, per_component in claims.items()
            }
            all_blind = all(per_model_blind.values()) and not truth_missing
            worst = worst_claim(
                *(
                    claim
                    for per_component in claims.values()
                    for claim in per_component.values()
                )
            )
            if truth_missing:
                reason = (
                    f"truth is not evaluated evidence for {truth_missing}; "
                    "the observable cannot be scored at all"
                )
            elif all_blind:
                reason = (
                    "every model-side component satisfies the blind policy "
                    "for every model under test"
                )
            else:
                nonblind = sorted(
                    {
                        component
                        for per_component in claims.values()
                        for component, claim in per_component.items()
                        if claim not in (STRICT_BLIND, HISTORICAL_BLIND)
                    }
                )
                reason = (
                    f"components {nonblind} carry nonblind or unknown model "
                    "lineage; central-target blindness does not propagate to "
                    "neighbors"
                )
            records.append(
                {
                    "derived_observable_id": f"{observable}:{nuclide_id}",
                    "observable": observable,
                    "central_nuclide_id": nuclide_id,
                    "component_nuclide_ids": components,
                    "component_model_claim_types": claims,
                    "truth_dependency_ids": components,
                    "model_dependency_ids": components,
                    "all_model_inputs_blind_eligible": all_blind,
                    "claim_type": worst,
                    "full_shell_gate_eligible": (
                        all_blind and observable in ("delta2n", "delta2p", "local_peak_rank")
                    ),
                    "reason": reason,
                }
            )
    return records


def audit_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """The honest bottom line of the dependency audit."""
    eligible = [r for r in records if r["all_model_inputs_blind_eligible"]]
    full_shell = [r for r in records if r["full_shell_gate_eligible"]]
    by_observable: dict[str, dict[str, int]] = {}
    for record in records:
        entry = by_observable.setdefault(
            record["observable"], {"total": 0, "blind_eligible": 0}
        )
        entry["total"] += 1
        if record["all_model_inputs_blind_eligible"]:
            entry["blind_eligible"] += 1
    return {
        "rule": DERIVED_BLINDNESS_RULE,
        "n_records": len(records),
        "n_blind_eligible": len(eligible),
        "n_full_shell_eligible": len(full_shell),
        "by_observable": by_observable,
        "blind_eligible_ids": sorted(
            r["derived_observable_id"] for r in eligible
        ),
        "full_shell_blind_evaluable": bool(full_shell),
        "edge_structure_evaluable": bool(
            [r for r in eligible if r["observable"] in ("S2n", "S2p")]
        ),
    }
