"""PIR v0.1 data models (stdlib dataclasses; no Pydantic -- see ADR-PIR-0001).

Models are frozen: an object, once built, never mutates. This is the in-memory
half of the append-only guarantee (hard constraint #1); the store half lives in
:mod:`pir.provenance`.

Each model validates its own invariants at construction and exposes
``to_dict()`` so :mod:`pir.canonical` can content-address it. The heavy,
adjudicated rules live on :class:`Fact`:

* verdict is locked to :class:`pir.types.Verdict` -- a candidate-class label in
  the ``verdict`` field is rejected (hard constraint #3);
* SOUND/HEURISTIC honesty (hard constraint #4): HEURISTIC may not claim E0;
  HEURISTIC at E3/E4 must carry located ``warnings``; SOUND may not assert a
  simulation/proxy-level (E3/E4) fact it cannot certify;
* a DOMAIN- or MEASUREMENT-layer fact must name its declared measurement
  interface (SPEC §2);
* every derived fact carries the full provenance quintet of hard constraint #5.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple

from .canonical import content_id
from .types import (
    ActivityType,
    AgentKind,
    CandidateClass,
    EvidenceLevel,
    FactStatus,
    HypothesisStatus,
    Layer,
    Namespace,
    PassTag,
    PirLevel,
    Verdict,
    ACT_OPS,
    PORT_TYPES,
)


class PIRValidationError(ValueError):
    """Raised when a model violates a substrate invariant."""


def _enum(value, enum_cls, field_name):
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_cls)
        raise PIRValidationError(
            f"{field_name}={value!r} is not in the locked vocabulary "
            f"{{{allowed}}}"
        )


# --------------------------------------------------------------------------- #
# L0 evidence artifact                                                         #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Artifact:
    """Immutable L0 evidence. No theoretical labels, no inferred universal
    claims (hard constraint #7, enforced by the loader / this constructor)."""

    artifact_id: str
    kind: str
    content_hash: str
    acquired_at: str
    namespace: Namespace = Namespace.raw
    format: Optional[str] = None
    apparatus_id: Optional[str] = None
    calibration_route: Optional[List[str]] = None
    declared_resolution: Optional[Dict[str, Any]] = None
    source_uri: Optional[str] = None

    _KINDS = frozenset({
        "DATASET", "PAPER_TABLE", "CALIBRATION", "APPARATUS_MANIFEST",
        "SIMULATION_TRACE", "CERTIFICATE_EXTERNAL",
    })

    def __post_init__(self):
        object.__setattr__(self, "namespace", _enum(self.namespace, Namespace, "namespace"))
        if self.namespace is not Namespace.raw:
            raise PIRValidationError("L0 artifact namespace must be 'raw' (SPEC §2)")
        if self.kind not in self._KINDS:
            raise PIRValidationError(f"artifact kind {self.kind!r} not recognized")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "content_hash": self.content_hash,
            "namespace": self.namespace.value,
            "format": self.format,
            "apparatus_id": self.apparatus_id,
            "calibration_route": self.calibration_route,
            "declared_resolution": self.declared_resolution,
            "source_uri": self.source_uri,
            "acquired_at": self.acquired_at,
        }


# --------------------------------------------------------------------------- #
# L1 operational act                                                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Port:
    name: str
    type: str
    unit: str
    value: Any = None
    uncertainty: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.type not in PORT_TYPES:
            raise PIRValidationError(f"port type {self.type!r} not in typed-port vocabulary")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "type": self.type, "unit": self.unit,
            "value": self.value, "uncertainty": self.uncertainty,
        }


@dataclass(frozen=True)
class Event:
    """One act-op grounded in an L0 artifact (PirLevel L1)."""

    event_id: str
    op: str
    artifact_id: str
    ports: Tuple[Port, ...] = ()
    timing: Dict[str, Any] = field(default_factory=dict)
    assumptions: Tuple[str, ...] = ()
    apparatus_id: Optional[str] = None
    calibration_route: Optional[List[str]] = None
    source_spans: Tuple[Dict[str, Any], ...] = ()

    def __post_init__(self):
        if self.op not in ACT_OPS:
            raise PIRValidationError(f"op {self.op!r} not in act-op family")
        object.__setattr__(self, "ports", tuple(self.ports))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "source_spans", tuple(self.source_spans))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id, "op": self.op,
            "artifact_id": self.artifact_id,
            "ports": [p.to_dict() for p in self.ports],
            "timing": self.timing,
            "apparatus_id": self.apparatus_id,
            "calibration_route": self.calibration_route,
            "assumptions": list(self.assumptions),
            "source_spans": [dict(s) for s in self.source_spans],
        }


# --------------------------------------------------------------------------- #
# analyzer stamp                                                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AnalyzerRef:
    id: str
    version: str
    tag: PassTag

    def __post_init__(self):
        object.__setattr__(self, "tag", _enum(self.tag, PassTag, "analyzer.tag"))

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "version": self.version, "tag": self.tag.value}


@dataclass(frozen=True)
class Warning_:
    location: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {"location": self.location, "message": self.message}


# --------------------------------------------------------------------------- #
# L2 structural fact                                                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Fact:
    """Append-only derived fact carrying BOTH orthogonal coordinates."""

    fact_id: str
    pir_level: PirLevel
    evidence_level: EvidenceLevel
    layer: Layer
    namespace: Namespace
    status: FactStatus
    analyzer: AnalyzerRef
    content: Dict[str, Any]
    created_at: str
    depends_on_facts: Tuple[str, ...] = ()
    assumptions: Tuple[str, ...] = ()
    source_spans: Tuple[Dict[str, Any], ...] = ()
    measurement_interface: Tuple[str, ...] = ()
    warnings: Tuple[Warning_, ...] = ()
    verdict: Optional[Verdict] = None
    witness: Optional[Dict[str, Any]] = None
    impossibility_certificate: Optional[Dict[str, Any]] = None
    similarity: Optional[float] = None
    confidence: Optional[float] = None
    correlator: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "pir_level", _enum(self.pir_level, PirLevel, "pir_level"))
        object.__setattr__(self, "evidence_level", _enum(self.evidence_level, EvidenceLevel, "evidence_level"))
        object.__setattr__(self, "layer", _enum(self.layer, Layer, "layer"))
        object.__setattr__(self, "namespace", _enum(self.namespace, Namespace, "namespace"))
        object.__setattr__(self, "status", _enum(self.status, FactStatus, "status"))
        object.__setattr__(self, "depends_on_facts", tuple(self.depends_on_facts))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "source_spans", tuple(self.source_spans))
        object.__setattr__(self, "measurement_interface", tuple(self.measurement_interface))
        object.__setattr__(self, "warnings", tuple(self.warnings))

        # Verdict lock (hard constraint #3): a candidate-class label here is a
        # violation, with a message that names the correct home.
        if self.verdict is not None:
            if isinstance(self.verdict, CandidateClass) or (
                isinstance(self.verdict, str) and self.verdict in {c.value for c in CandidateClass}
            ):
                raise PIRValidationError(
                    f"candidate-class label {self.verdict!r} is taxonomy, not a "
                    "verdict; put it on hypothesis.candidate_class "
                    "(hard constraint #3 / ADJUDICATION #24)"
                )
            object.__setattr__(self, "verdict", _enum(self.verdict, Verdict, "verdict"))

        # SOUND/HEURISTIC honesty (hard constraint #4).
        tag = self.analyzer.tag
        e = self.evidence_level
        if tag is PassTag.HEURISTIC and e is EvidenceLevel.E0:
            raise PIRValidationError(
                "a HEURISTIC pass cannot assert an E0 (exact) fact -- E0 is a "
                "soundness claim (hard constraint #4)"
            )
        if tag is PassTag.SOUND and e in (EvidenceLevel.E3, EvidenceLevel.E4):
            raise PIRValidationError(
                "a SOUND pass may not assert a simulation/proxy-level "
                f"({e.value}) fact it cannot certify (hard constraint #4)"
            )
        if tag is PassTag.HEURISTIC and e in (EvidenceLevel.E3, EvidenceLevel.E4) and not self.warnings:
            raise PIRValidationError(
                f"a HEURISTIC {e.value} fact must carry a non-empty, located "
                "warnings[] (hard constraint #4, Ghidra WARNING pattern)"
            )

        # Measurement-interface requirement (SPEC §2 / required negative test).
        if self.layer in (Layer.DOMAIN, Layer.MEASUREMENT) and not self.measurement_interface:
            raise PIRValidationError(
                f"a {self.layer.value}-layer fact must declare its measurement "
                "interface (calibration route / apparatus); none given (SPEC §2)"
            )

        # Similarity/confidence discipline (BinDiff): if either is set, the
        # correlator (matching algorithm identity) is mandatory.
        if (self.similarity is not None or self.confidence is not None) and not self.correlator:
            raise PIRValidationError(
                "similarity/confidence require a named correlator "
                "(similarity and confidence are separate numbers)"
            )

    # ---- provenance quintet completeness (hard constraint #5) ------------- #
    def missing_provenance(self) -> List[str]:
        """Report which of the mandatory provenance carriers are absent.

        A *derived* fact (one with dependencies, i.e. not a bare loader fact)
        must carry analyzer id+version, dependency IDs, assumption taint, source
        spans, evidence level, pir level, layer, namespace, and status. The
        dataclass types already force the coordinate fields to be present; this
        reports the list-valued carriers that a derived fact must not leave
        empty."""
        missing = []
        if not self.analyzer.id or not self.analyzer.version:
            missing.append("analyzer.id/version")
        if not self.source_spans:
            missing.append("source_spans")
        return missing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "pir_level": self.pir_level.value,
            "evidence_level": self.evidence_level.value,
            "layer": self.layer.value,
            "namespace": self.namespace.value,
            "status": self.status.value,
            "verdict": self.verdict.value if self.verdict else None,
            "analyzer": self.analyzer.to_dict(),
            "warnings": [w.to_dict() for w in self.warnings],
            "depends_on_facts": list(self.depends_on_facts),
            "assumptions": list(self.assumptions),
            "source_spans": [dict(s) for s in self.source_spans],
            "measurement_interface": list(self.measurement_interface),
            "content": self.content,
            "witness": self.witness,
            "impossibility_certificate": self.impossibility_certificate,
            "similarity": self.similarity,
            "confidence": self.confidence,
            "correlator": self.correlator,
            "created_at": self.created_at,
        }

    def with_status(self, status: FactStatus) -> "Fact":
        """Return a NEW fact with a changed status (never mutates in place)."""
        return replace(self, status=status)

    @staticmethod
    def compute_id(content: Dict[str, Any], analyzer: AnalyzerRef,
                   depends_on_facts=(), assumptions=(), prefix: str = "fct") -> str:
        """Content-address a fact by its content + provenance skeleton."""
        return content_id(prefix, {
            "content": content,
            "analyzer": analyzer.to_dict(),
            "depends_on_facts": list(depends_on_facts),
            "assumptions": list(assumptions),
        })


# --------------------------------------------------------------------------- #
# L3 candidate grammar / hypothesis                                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    family: str
    status: HypothesisStatus
    derived_from_facts: Tuple[str, ...] = ()
    assumptions: Tuple[str, ...] = ()
    candidate_class: Optional[Tuple[CandidateClass, ...]] = None
    equivalence_class_id: Optional[str] = None
    compatibility: Tuple[Dict[str, Any], ...] = ()
    distinguishing_interventions: Tuple[Dict[str, Any], ...] = ()
    fingerprint_full: Optional[str] = None
    fingerprint_specific: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "status", _enum(self.status, HypothesisStatus, "status"))
        object.__setattr__(self, "derived_from_facts", tuple(self.derived_from_facts))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "compatibility", tuple(self.compatibility))
        object.__setattr__(self, "distinguishing_interventions", tuple(self.distinguishing_interventions))
        if self.candidate_class is not None:
            cc = tuple(_enum(c, CandidateClass, "candidate_class") for c in self.candidate_class)
            object.__setattr__(self, "candidate_class", cc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "family": self.family,
            "candidate_class": [c.value for c in self.candidate_class] if self.candidate_class else None,
            "status": self.status.value,
            "equivalence_class_id": self.equivalence_class_id,
            "compatibility": [dict(c) for c in self.compatibility],
            "distinguishing_interventions": [dict(d) for d in self.distinguishing_interventions],
            "fingerprint_full": self.fingerprint_full,
            "fingerprint_specific": self.fingerprint_specific,
            "derived_from_facts": list(self.derived_from_facts),
            "assumptions": list(self.assumptions),
        }


# --------------------------------------------------------------------------- #
# declared intervention                                                        #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Intervention:
    intervention_id: str
    kind: str
    target: str
    admissible: bool
    assumptions: Tuple[str, ...] = ()
    parameters: Dict[str, Any] = field(default_factory=dict)
    cost_estimate: Optional[Dict[str, Any]] = None
    feasibility: Optional[Dict[str, Any]] = None
    objective_scores: Optional[Dict[str, Any]] = None
    predicted_outcomes: Tuple[Dict[str, Any], ...] = ()
    status: str = "PROPOSED"

    _KINDS = frozenset({
        "APPARATUS_SWAP", "BOUNDARY_CHANGE", "TIMING_PERMUTATION",
        "LOOP_DEFORMATION", "SOURCE_DETECTOR_EXCHANGE", "SCALE_SWEEP",
        "PERTURBATION", "COUPLING_CHANGE", "GEOMETRY_CHANGE",
        "TEMPERATURE_CHANGE", "PREPARATION_REORDER",
    })
    _STATUS = frozenset({"PROPOSED", "EXECUTED", "RETIRED"})

    def __post_init__(self):
        if self.kind not in self._KINDS:
            raise PIRValidationError(f"intervention kind {self.kind!r} not recognized")
        if self.status not in self._STATUS:
            raise PIRValidationError(f"intervention status {self.status!r} not recognized")
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "predicted_outcomes", tuple(self.predicted_outcomes))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "kind": self.kind,
            "target": self.target,
            "parameters": self.parameters,
            "admissible": self.admissible,
            "cost_estimate": self.cost_estimate,
            "feasibility": self.feasibility,
            "objective_scores": self.objective_scores,
            "predicted_outcomes": [dict(p) for p in self.predicted_outcomes],
            "assumptions": list(self.assumptions),
            "status": self.status,
        }


# --------------------------------------------------------------------------- #
# provenance record (PROV-O core)                                             #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProvenanceRecord:
    record_id: str
    entity: str
    activity: Dict[str, Any]
    agent: Dict[str, Any]
    used: Tuple[str, ...]
    generated: Tuple[str, ...]
    created_at: str
    cross_namespace_transform: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        _enum(self.activity.get("type"), ActivityType, "activity.type")
        _enum(self.agent.get("kind"), AgentKind, "agent.kind")
        object.__setattr__(self, "used", tuple(self.used))
        object.__setattr__(self, "generated", tuple(self.generated))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "entity": self.entity,
            "activity": self.activity,
            "agent": self.agent,
            "used": list(self.used),
            "generated": list(self.generated),
            "cross_namespace_transform": self.cross_namespace_transform,
            "created_at": self.created_at,
        }
