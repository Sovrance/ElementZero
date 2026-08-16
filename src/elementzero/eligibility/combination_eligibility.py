"""Combiner eligibility inheritance (WO-13 spec section 13).

A combiner inherits the worst eligibility of every contributor that can
carry nonzero weight. No combiner may convert nonblind evidence into blind
evidence, and a contributor with unknown provenance poisons the whole
combination — unknown is not permission.
"""

from __future__ import annotations

from typing import Any

from elementzero.eligibility.claim_types import (
    BLIND_CLAIM_TYPES,
    INELIGIBLE_UNKNOWN_PROVENANCE,
    PARTIALLY_BLIND,
    strict_gate_eligible,
    weakest_confidence,
    worst_claim,
)
from elementzero.eligibility.model_training_provenance import COMBINER_COMPONENTS
from elementzero.errors import ProtocolError

COMBINER_INHERITANCE_RULE = (
    "ez-wo13-combiner-inheritance-v1: a combiner inherits the worst "
    "contributor eligibility over every contributor that can carry nonzero "
    "weight; a mixed blind/nonblind panel is PARTIALLY_BLIND at best, an "
    "unknown-provenance contributor makes the combination ineligible, and "
    "no weighting scheme converts nonblind evidence into blind evidence"
)


def combiner_record(
    *, model_id: str, contributor_records: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if model_id not in COMBINER_COMPONENTS:
        raise ProtocolError(f"{model_id} is not a registered combiner")
    expected = set(COMBINER_COMPONENTS[model_id])
    if set(contributor_records) != expected:
        raise ProtocolError(
            f"{model_id} contributor records {sorted(contributor_records)} "
            f"do not match the registered components {sorted(expected)}"
        )
    claims = {m: r["claim_type"] for m, r in sorted(contributor_records.items())}
    worst = worst_claim(*claims.values())
    blind = sorted(m for m, c in claims.items() if c in BLIND_CLAIM_TYPES)
    nonblind = sorted(m for m, c in claims.items() if c not in BLIND_CLAIM_TYPES)
    # Mixed panels: PARTIALLY_BLIND unless something worse (unknown
    # provenance) already poisons the combination.
    if blind and nonblind and worst != INELIGIBLE_UNKNOWN_PROVENANCE:
        claim = worst_claim(PARTIALLY_BLIND, worst)
    else:
        claim = worst
    confidence = weakest_confidence(
        *(r["provenance_confidence"] for r in contributor_records.values())
    )
    template = next(iter(sorted(contributor_records.items())))[1]
    record = dict(template)
    record.update(
        model_id=model_id,
        independence_group="model_combination",
        base_fit_overlap=any(
            r["base_fit_overlap"] is True for r in contributor_records.values()
        )
        or (
            None
            if any(
                r["base_fit_overlap"] is None for r in contributor_records.values()
            )
            else False
        ),
        residual_fit_overlap=False,
        calibration_overlap=False,
        hyperparameter_overlap=False,
        # Weights are learned from the freeze-controlled calibration split:
        # the target itself never enters the weighting. Nonblindness arrives
        # through contributors, which is exactly what this record shows.
        combination_weight_overlap=False,
        target_known_at_cutoff=None,
        exact_fit_membership=None,
        fit_cutoff_date=None,
        claim_type=claim,
        provenance_confidence=confidence,
        strict_gate_eligible=strict_gate_eligible(claim, confidence),
        eligibility_reason=(
            f"inherited: worst contributor status over {claims}; "
            f"blind contributors {blind or 'none'}, non-blind contributors "
            f"{nonblind or 'none'}. {COMBINER_INHERITANCE_RULE}"
        ),
        evidence_sources=sorted(
            {
                source
                for r in contributor_records.values()
                for source in r["evidence_sources"]
            }
        ),
    )
    return record
