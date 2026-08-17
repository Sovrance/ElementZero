"""Physics family independence adjudication (WO-15 INDEPENDENCE_POLICY).

Independence is a scientific property, not a repository property. A
different wrapper, container, language, or solver for the *same*
functional buys nothing. A residual or emulator on top of a base buys
nothing. What counts is a different functional class with its own
parameter vector, neither derived from the other, and no shared
post-freeze target truth used for selection.

This module also refuses to hide the uncomfortable case: two families
running through one solver build share a numerical implementation. That
is recorded on the adjudication, not omitted because it is inconvenient.
"""

from __future__ import annotations

from typing import Any

from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_hex
from elementzero.physics_backends import (
    HISTORICAL_FROZEN_EXACT,
    HISTORICAL_FROZEN_PARTIAL,
    MODERN_REFERENCE,
    REFIT_STRICT,
    UNKNOWN_PROVENANCE,
)

INDEPENDENT = "INDEPENDENT"
NOT_INDEPENDENT = "NOT_INDEPENDENT"
UNRESOLVED = "UNRESOLVED"

VERDICTS = (INDEPENDENT, NOT_INDEPENDENT, UNRESOLVED)

# Provenance classes that may carry a blind claim at all. PARTIAL is
# admitted only through the explicit date adjudication below, exactly as
# WO-13 admitted FRDM95 on targets unknown in AME1995.
BLIND_CAPABLE_CLASSES = (
    REFIT_STRICT,
    HISTORICAL_FROZEN_EXACT,
    HISTORICAL_FROZEN_PARTIAL,
)

NEVER_INDEPENDENT_REASONS = {
    "residual_variant": (
        "a GP or neural residual on a base model is a correction to that "
        "base, not a second physics family"
    ),
    "emulator": (
        "an emulator reproduces its parent's physics faster; it inherits "
        "the parent's family and never creates a new one"
    ),
    "same_functional_different_solver": (
        "the same functional class solved by different code is one physics "
        "family; solver difference is a numerics check, not independence"
    ),
    "reparameterized_same_class": (
        "a different parameter vector within the same functional class, "
        "derived from the other family's fit, is not independent"
    ),
}

INDEPENDENCE_RULE = (
    "ez-wo15-independence-v1: two backends are independent physics families "
    "only when the functional/interaction class differs, the parameter "
    "vectors differ and neither is derived from the other, neither is a "
    "residual or emulator of the other, and no shared post-freeze target "
    "truth selected either of them. A shared solver implementation does not "
    "by itself deny independence, but it is a correlated-numerics caveat "
    "that is recorded on both adjudications"
)

BLIND_DATE_ADJUDICATION_RULE = (
    "ez-wo15-blind-date-adjudication-v1: a HISTORICAL_FROZEN_PARTIAL "
    "parameterization is blind-eligible for a target only when the "
    "parameterization was published before the freeze cutoff AND the target "
    "was not present in the frozen snapshot. Publication date bounds what "
    "could have entered the fit even when the exact calibration list is "
    "prose; this is the same adjudication WO-13 applied to FRDM95, and it "
    "never upgrades a post-freeze parameterization"
)


def build_adjudication(
    *,
    group_id: str,
    functional_class: str,
    interaction_or_lagrangian_class: str,
    solver: str,
    parameter_artifact: str,
    fit_freeze: str,
    shared_training_data: list[str],
    shared_parameters: list[str],
    derived_from_family: str | None,
    residual_parent: str | None,
    provenance_class: str,
    parameterization_year: int,
    freeze_year: int,
    shared_solver_with: list[str] | None = None,
) -> dict[str, Any]:
    """One schema-exact PhysicsIndependenceAdjudication."""
    reasons: list[str] = []
    verdict = INDEPENDENT

    if residual_parent:
        verdict = NOT_INDEPENDENT
        reasons.append(NEVER_INDEPENDENT_REASONS["residual_variant"])
    if derived_from_family:
        verdict = NOT_INDEPENDENT
        reasons.append(NEVER_INDEPENDENT_REASONS["reparameterized_same_class"])
    if shared_parameters:
        verdict = NOT_INDEPENDENT
        reasons.append(
            f"shares fitted parameters {sorted(shared_parameters)} with "
            "another family"
        )

    blind_eligible = (
        provenance_class in BLIND_CAPABLE_CLASSES
        and parameterization_year < freeze_year
    )
    if provenance_class == MODERN_REFERENCE:
        reasons.append(
            "post-freeze parameterization: reference and reconstruction only, "
            "never a blind physics contributor"
        )
    elif provenance_class == UNKNOWN_PROVENANCE:
        reasons.append("provenance cannot be established; not blind eligible")
    elif blind_eligible:
        reasons.append(
            f"parameterization published {parameterization_year}, before the "
            f"{freeze_year} freeze; {BLIND_DATE_ADJUDICATION_RULE}"
        )

    if shared_solver_with:
        reasons.append(
            "correlated-numerics caveat: shares a solver implementation with "
            f"{sorted(shared_solver_with)}. The functional classes differ, so "
            "the physics is independent, but a shared basis/solver means "
            "numerical errors are not independent. A second implementation "
            "would strengthen this claim"
        )

    record = {
        "group_id": group_id,
        "functional_class": functional_class,
        "interaction_or_lagrangian_class": interaction_or_lagrangian_class,
        "solver": solver,
        "parameter_artifact": parameter_artifact,
        "fit_freeze": fit_freeze,
        "shared_training_data": sorted(shared_training_data),
        "shared_parameters": sorted(shared_parameters),
        "derived_from_family": derived_from_family,
        "residual_parent": residual_parent,
        "provenance_class": provenance_class,
        "shared_solver_with": sorted(shared_solver_with or []),
        "independence_verdict": verdict,
        "blind_eligible": bool(blind_eligible and verdict == INDEPENDENT),
        "reason": " | ".join(reasons) if reasons else INDEPENDENCE_RULE,
        "rule": INDEPENDENCE_RULE,
    }
    if record["independence_verdict"] not in VERDICTS:
        raise ProtocolError("unknown independence verdict")
    record["adjudication_hash"] = sha256_hex(record)
    return record


def count_blind_families(records: list[dict[str, Any]]) -> dict[str, Any]:
    """The two-family gate, counted over raw physics families only."""
    blind = [
        r
        for r in records
        if r["blind_eligible"] and r["independence_verdict"] == INDEPENDENT
    ]
    groups = sorted({r["group_id"] for r in blind})
    n = len(groups)
    status = {
        0: "ZERO_BLIND_PHYSICS_FAMILIES",
        1: "ONE_BLIND_PHYSICS_FAMILY",
        2: "TWO_BLIND_PHYSICS_FAMILIES",
    }.get(n, "THREE_BLIND_PHYSICS_FAMILIES")
    return {
        "n_blind_independent_families": n,
        "blind_independent_groups": groups,
        "status": status,
        "gate_met": n >= 2,
        "counting_rule": (
            "counted over raw physics families; residual variants, "
            "emulators, and combiners never add to this number"
        ),
        "rule": INDEPENDENCE_RULE,
    }
