"""Domain-neutral historical prediction and held-out comparison primitives."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional, Tuple
from .canonical import sha256_hex, content_id

class LeakageViolation(RuntimeError):
    pass

@dataclass(frozen=True)
class KnowledgeFreeze:
    freeze_id: str
    cutoff_date: str
    allowed_source_hashes: Tuple[str, ...]
    training_ids: FrozenSet[str]
    forbidden_source_hashes: Tuple[str, ...] = ()
    feature_policy_id: str = "unspecified"

    @property
    def training_ids_sha256(self) -> str:
        return sha256_hex(sorted(self.training_ids))

    def assert_training_id(self, subject_id: str) -> None:
        if subject_id not in self.training_ids:
            raise LeakageViolation(f"{subject_id} is not in the frozen training identity set")

    def assert_target_is_held_out(self, subject_id: str) -> None:
        if subject_id in self.training_ids:
            raise LeakageViolation(f"target {subject_id} appears in training_ids")

@dataclass(frozen=True)
class PredictionRecord:
    subject_id: str
    observable: str
    mean: float
    std: Optional[float]
    model_id: str
    freeze_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def prediction_id(self) -> str:
        return content_id("pred", self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {"subject_id":self.subject_id,"observable":self.observable,"mean":self.mean,
                "std":self.std,"model_id":self.model_id,"freeze_id":self.freeze_id,
                "metadata":self.metadata}

@dataclass(frozen=True)
class HeldOutObservation:
    subject_id: str
    observable: str
    value: float
    source_hash: str
    source_edition: str

@dataclass(frozen=True)
class ResidualComparison:
    prediction_id: str
    subject_id: str
    predicted: float
    held_out: float
    residual: float
    held_out_reused_in_fit: bool
    provenance: Dict[str, Any]

    def to_dict(self):
        return self.__dict__.copy()

def compare_held_out(prediction: PredictionRecord, truth: HeldOutObservation,
                     freeze: KnowledgeFreeze) -> ResidualComparison:
    if prediction.freeze_id != freeze.freeze_id:
        raise LeakageViolation("prediction freeze_id does not match supplied KnowledgeFreeze")
    if prediction.subject_id != truth.subject_id or prediction.observable != truth.observable:
        raise ValueError("prediction/truth identity mismatch")
    freeze.assert_target_is_held_out(truth.subject_id)
    if truth.source_hash in freeze.allowed_source_hashes:
        raise LeakageViolation("held-out truth source is in allowed training sources")
    return ResidualComparison(
        prediction_id=prediction.prediction_id, subject_id=truth.subject_id,
        predicted=prediction.mean, held_out=truth.value,
        residual=abs(prediction.mean-truth.value), held_out_reused_in_fit=False,
        provenance={"knowledge_freeze_id":freeze.freeze_id,
                    "training_ids_sha256":freeze.training_ids_sha256,
                    "truth_source_hash":truth.source_hash,
                    "truth_source_edition":truth.source_edition})
