"""Residual-model eligibility inheritance (WO-13 spec section 13).

The resulting eligibility is the WORST status of base model, residual fit,
calibration, and hyperparameter selection. A blind GP residual cannot
repair a nonblind base into blindness.
"""

from __future__ import annotations

from typing import Any

from elementzero.eligibility.claim_types import (
    CONFIDENCE_EXACT,
    STRICT_BLIND,
    strict_gate_eligible,
    weakest_confidence,
    worst_claim,
)
from elementzero.eligibility.model_training_provenance import BASE_MODEL_OF
from elementzero.errors import ProtocolError

RESIDUAL_INHERITANCE_RULE = (
    "ez-wo13-residual-inheritance-v1: residual eligibility = worst(base "
    "model, residual fit, calibration, hyperparameter selection); the "
    "freeze-controlled residual lineage is STRICT_BLIND on its own, so the "
    "result is exactly the base model's status — a blind correction never "
    "erases nonblind base provenance"
)


def residual_record(
    *, model_id: str, base_record: dict[str, Any]
) -> dict[str, Any]:
    if model_id not in BASE_MODEL_OF:
        raise ProtocolError(f"{model_id} is not a registered residual wrapper")
    if BASE_MODEL_OF[model_id] != base_record["model_id"]:
        raise ProtocolError(
            f"{model_id} inherits from {BASE_MODEL_OF[model_id]}, not "
            f"{base_record['model_id']}"
        )
    # The residual GP, its calibration split, and its frozen hyperparameter
    # configuration are all controlled by the sealed KnowledgeFreeze:
    # STRICT_BLIND with EXACT confidence on their own.
    claim = worst_claim(base_record["claim_type"], STRICT_BLIND)
    confidence = weakest_confidence(
        base_record["provenance_confidence"], CONFIDENCE_EXACT
    )
    record = dict(base_record)
    record.update(
        model_id=model_id,
        independence_group="residual_ml",
        residual_fit_overlap=False,
        calibration_overlap=False,
        hyperparameter_overlap=False,
        claim_type=claim,
        provenance_confidence=confidence,
        strict_gate_eligible=strict_gate_eligible(claim, confidence),
        eligibility_reason=(
            f"inherited: worst of base model ({base_record['model_id']}: "
            f"{base_record['claim_type']}) and the freeze-controlled "
            "residual fit, calibration split, and frozen hyperparameters "
            f"(all STRICT_BLIND). {RESIDUAL_INHERITANCE_RULE}"
        ),
        evidence_sources=sorted(
            set(base_record["evidence_sources"])
            | {"ez-wo12-residual-gp-v1 frozen configuration"}
        ),
    )
    return record
