"""Numerical convergence as evidence (WO-15 spec section 13).

A solver result is not a valid prediction merely because a process exits
zero. Every solve produces a PhysicsConvergenceRecord, and a record whose
``converged`` is false never becomes a number.
"""

from __future__ import annotations

from typing import Any

from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_hex

FAILURE_NONE = "NONE"
FAILURE_NONCONVERGED = "NONCONVERGED"
FAILURE_NUMERICAL_INSTABILITY = "NUMERICAL_INSTABILITY"
FAILURE_UNSUPPORTED_NUCLIDE = "UNSUPPORTED_NUCLIDE"
FAILURE_INVALID_OUTPUT = "INVALID_OUTPUT"
FAILURE_RESOURCE_FAILURE = "RESOURCE_FAILURE"

FAILURE_CLASSES = (
    FAILURE_NONE,
    FAILURE_NONCONVERGED,
    FAILURE_NUMERICAL_INSTABILITY,
    FAILURE_UNSUPPORTED_NUCLIDE,
    FAILURE_INVALID_OUTPUT,
    FAILURE_RESOURCE_FAILURE,
)

CONVERGENCE_RULE = (
    "ez-wo15-convergence-v1: a prediction exists only when the solver "
    "reported self-consistent convergence within the preregistered "
    "iteration and accuracy policy AND the parsed output is physically "
    "well-formed. Exit status alone proves nothing; NaN, missing energy, "
    "or an iteration-limit stop is a failure class, never a value."
)


def build_record(
    *,
    nuclide_id: str,
    backend_id: str,
    parameter_artifact_id: str,
    converged: bool,
    iterations: int,
    basis_policy: str,
    retry_count: int,
    failure_class: str,
    output_hash: str,
    energy_delta: float | None = None,
    constraint_residuals: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One schema-exact PhysicsConvergenceRecord."""
    if failure_class not in FAILURE_CLASSES:
        raise ProtocolError(f"unknown failure class {failure_class!r}")
    if converged and failure_class != FAILURE_NONE:
        raise ProtocolError(
            f"{nuclide_id}: a converged solve cannot carry failure class "
            f"{failure_class}"
        )
    if not converged and failure_class == FAILURE_NONE:
        raise ProtocolError(
            f"{nuclide_id}: a nonconverged solve must name its failure class"
        )
    record = {
        "nuclide_id": nuclide_id,
        "backend_id": backend_id,
        "parameter_artifact_id": parameter_artifact_id,
        "converged": bool(converged),
        "iterations": int(iterations),
        "energy_delta": energy_delta,
        "constraint_residuals": constraint_residuals or {},
        "basis_policy": basis_policy,
        "retry_count": int(retry_count),
        "failure_class": failure_class,
        "output_hash": output_hash,
        "rule": CONVERGENCE_RULE,
    }
    if detail:
        record["detail"] = detail
    record["convergence_record_id"] = sha256_hex(record)[:32]
    return record


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Coverage of one campaign, reported exactly (spec section 14)."""
    by_class: dict[str, int] = {}
    for record in records:
        key = record["failure_class"]
        by_class[key] = by_class.get(key, 0) + 1
    converged = [r for r in records if r["converged"]]
    return {
        "n_records": len(records),
        "n_converged": len(converged),
        "coverage_fraction": (len(converged) / len(records)) if records else None,
        "by_failure_class": dict(sorted(by_class.items())),
        "nonconverged_nuclide_ids": sorted(
            r["nuclide_id"] for r in records if not r["converged"]
        ),
        "rule": CONVERGENCE_RULE,
    }
