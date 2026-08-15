"""Thin Atlas PIR adapter.

All ElementZero production code must reach Atlas PIR through this module.
Do not import Atlas research/benchmark packages (b1_*, b4_*, generator, ...).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from pir import (
    AnalyzerRef,
    Artifact,
    Event,
    EvidenceLevel,
    Fact,
    FactStatus,
    FactStore,
    Hypothesis,
    HypothesisStatus,
    Intervention,
    Layer,
    Namespace,
    PassTag,
    PirLevel,
    Port,
    ProvenanceRecord,
    Warning_,
    forward,
    intervention_search,
)

from elementzero.atlas_pin import atlas_pir_ref
from elementzero.data.observations import MassObservation
from elementzero.evidence.hashing import content_id, sha256_hex
from elementzero.identity_meta import elementzero_commit

NUCLEAR_MASS_INTERFACE = "mi:nuclear_atomic_mass_excess"
PREDICTION_WARNING = (
    "Model prediction; uncertainty is conditioned on model and training freeze "
    "and is not direct experimental evidence."
)
ADAPTER_VERSION = "0.2.0"
SOUND_ANALYZER_ID = "elementzero.evidence.normalize"
HEURISTIC_ANALYZER_ID = "elementzero.models.predict"

# Cross-namespace transform for freeze-constrained predictions.
# Observation facts live in `domain`; predictions live in `analyst`.
PREDICT_TRANSFORM_NAME = "ez.domain_to_analyst_prediction"
PREDICT_TRANSFORM_SIGNATURE = (
    "domain->analyst via freeze-constrained nuclear mass prediction"
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sound_analyzer() -> AnalyzerRef:
    return AnalyzerRef(id=SOUND_ANALYZER_ID, version=ADAPTER_VERSION, tag=PassTag.SOUND)


def _heuristic_analyzer() -> AnalyzerRef:
    return AnalyzerRef(id=HEURISTIC_ANALYZER_ID, version=ADAPTER_VERSION, tag=PassTag.HEURISTIC)


def _namespace_transform(from_ns: Namespace, to_ns: Namespace):
    from pir import NamespaceTransform

    return NamespaceTransform(
        name=PREDICT_TRANSFORM_NAME,
        from_namespace=from_ns,
        to_namespace=to_ns,
        type_signature=PREDICT_TRANSFORM_SIGNATURE,
    )


class AtlasEvidenceAdapter:
    """ElementZero boundary over Atlas PIR v0.1."""

    def __init__(
        self,
        store: FactStore | None = None,
        *,
        created_at: str | None = None,
        atlas_ref: str | None = None,
        ez_commit: str | None = None,
    ) -> None:
        self.store = store or FactStore()
        self.created_at = created_at or utc_now()
        self.atlas_pir_ref = atlas_ref or atlas_pir_ref()
        self.elementzero_commit = ez_commit or elementzero_commit()
        self.artifacts: dict[str, Artifact] = {}
        self.events: dict[str, Event] = {}
        self.hypotheses: dict[str, Hypothesis] = {}

    def source_artifact(
        self,
        raw_bytes: bytes,
        *,
        source_uri: str,
        acquired_at: str,
        format: str = "ame-mass-table",
        artifact_id: str | None = None,
    ) -> Artifact:
        digest = sha256_hex(raw_bytes)
        artifact = Artifact(
            artifact_id=artifact_id or content_id("art", digest),
            kind="DATASET",
            content_hash=digest,
            acquired_at=acquired_at,
            namespace=Namespace.raw,
            format=format,
            source_uri=source_uri,
        )
        self.artifacts[artifact.artifact_id] = artifact
        return artifact

    def observation_event(
        self,
        artifact: Artifact,
        *,
        event_id: str | None = None,
        op: str = "RECORD",
    ) -> Event:
        event = Event(
            event_id=event_id or content_id("evt", artifact.artifact_id),
            op=op,
            artifact_id=artifact.artifact_id,
            ports=(Port(name="atomic_mass_excess", type="Observable", unit="keV"),),
        )
        self.events[event.event_id] = event
        return event

    def observation_fact(
        self,
        observation: MassObservation,
        *,
        artifact: Artifact,
        event: Event | None = None,
        status: str | FactStatus = FactStatus.SUPPORTED,
    ) -> Fact:
        if not observation.ground_truth_eligible:
            # Extrapolated/model-derived source rows stay E4 and must not be
            # presented as experimental truth.
            evidence = EvidenceLevel.E4
            tag = PassTag.HEURISTIC
            warnings = (
                Warning_(
                    location=f"observation:{observation.nuclide_id}",
                    message=(
                        "Source record is extrapolated or estimated; not promoted "
                        "to experimental ground truth."
                    ),
                ),
            )
            analyzer = AnalyzerRef(id=SOUND_ANALYZER_ID, version=ADAPTER_VERSION, tag=tag)
        else:
            evidence = EvidenceLevel.E2
            warnings = ()
            analyzer = _sound_analyzer()
        content = {
            "kind": "nuclear_mass_observation",
            "nuclide_id": observation.nuclide_id,
            "Z": observation.Z,
            "N": observation.N,
            "A": observation.A,
            "mass_excess_keV": observation.mass_excess_keV,
            "uncertainty_keV": observation.uncertainty_keV,
            "source_edition": observation.source_edition,
            "source_record_status": observation.source_record_status,
            "ground_truth_eligible": observation.ground_truth_eligible,
        }
        fact = Fact(
            fact_id=Fact.compute_id(content, analyzer, assumptions=(observation.raw_source_hash,)),
            pir_level=PirLevel.L2,
            evidence_level=evidence,
            layer=Layer.MEASUREMENT,
            namespace=Namespace.domain,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            assumptions=(f"src:{observation.raw_source_hash}",),
            source_spans=(
                {
                    "artifact_id": artifact.artifact_id,
                    "span": f"nuclide:{observation.nuclide_id}",
                    "event_id": event.event_id if event else None,
                },
            ),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=warnings,
        )
        return fact

    def prediction_fact(
        self,
        *,
        nuclide_id: str,
        z: int,
        n: int,
        a: int,
        prediction_keV: float,
        intervals: Mapping[str, Sequence[float]],
        model_id: str,
        freeze_id: str,
        depends_on_facts: Sequence[str],
        status: str | FactStatus = FactStatus.UNRESOLVED,
        evidence_level: str | EvidenceLevel = EvidenceLevel.E3,
    ) -> Fact:
        analyzer = _heuristic_analyzer()
        content = {
            "kind": "nuclear_mass_prediction",
            "nuclide_id": nuclide_id,
            "Z": z,
            "N": n,
            "A": a,
            "mass_excess_keV": prediction_keV,
            "intervals": {k: list(v) for k, v in intervals.items()},
            "model_id": model_id,
            "freeze_id": freeze_id,
            "observable": NUCLEAR_MASS_INTERFACE,
        }
        fact = Fact(
            fact_id=Fact.compute_id(content, analyzer, depends_on_facts=depends_on_facts),
            pir_level=PirLevel.L2,
            evidence_level=evidence_level,
            layer=Layer.DOMAIN,
            namespace=Namespace.analyst,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            depends_on_facts=tuple(depends_on_facts),
            assumptions=(f"freeze:{freeze_id}", f"model:{model_id}"),
            source_spans=({"artifact_id": freeze_id, "span": f"predict:{nuclide_id}"},),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=(
                Warning_(
                    location=f"prediction:{nuclide_id}",
                    message=PREDICTION_WARNING,
                ),
            ),
        )
        return fact

    def validation_fact(
        self,
        *,
        benchmark_id: str,
        metrics: Mapping[str, Any],
        depends_on_facts: Sequence[str],
        run_id: str,
    ) -> Fact:
        analyzer = _sound_analyzer()
        content = {
            "kind": "nuclear_benchmark_validation",
            "benchmark_id": benchmark_id,
            "run_id": run_id,
            "metrics": dict(metrics),
        }
        fact = Fact(
            fact_id=Fact.compute_id(content, analyzer, depends_on_facts=depends_on_facts),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E2,
            layer=Layer.DOMAIN,
            namespace=Namespace.analyst,
            status=FactStatus.SUPPORTED,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            depends_on_facts=tuple(depends_on_facts),
            assumptions=(f"benchmark:{benchmark_id}",),
            source_spans=({"artifact_id": run_id, "span": "score"},),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
        )
        return fact

    def append_fact(
        self,
        fact: Fact,
        *,
        parent_namespaces: Mapping[str, Namespace] | None = None,
    ) -> Fact:
        edge_transforms = {}
        for parent_id in fact.depends_on_facts:
            parent = self.store.get(parent_id)
            if parent.namespace != fact.namespace:
                edge_transforms[parent_id] = _namespace_transform(parent.namespace, fact.namespace)
        return self.store.add_fact(fact, edge_transforms=edge_transforms or None)

    def append_provenance(
        self,
        *,
        entity: str,
        activity_type: str,
        agent_kind: str = "ANALYZER",
        agent_id: str = SOUND_ANALYZER_ID,
        used: Sequence[str] = (),
        generated: Sequence[str] = (),
        activity_id: str | None = None,
    ) -> ProvenanceRecord:
        record = ProvenanceRecord(
            record_id=content_id("prov", {"entity": entity, "used": list(used), "gen": list(generated)}),
            entity=entity,
            activity={"id": activity_id or content_id("act", entity), "type": activity_type},
            agent={"id": agent_id, "kind": agent_kind},
            used=tuple(used),
            generated=tuple(generated),
            created_at=self.created_at,
        )
        return self.store.add_provenance(record)

    def invalidate_assumption(self, assumption_id: str, reason: str) -> list[str]:
        return self.store.invalidate_assumption(assumption_id, reason)

    def model_hypothesis(self, *, family: str, hypothesis_id: str | None = None) -> Hypothesis:
        hyp = Hypothesis(
            hypothesis_id=hypothesis_id or content_id("hyp", family),
            family=family,
            status=HypothesisStatus.ACTIVE,
        )
        self.hypotheses[hyp.hypothesis_id] = hyp
        return hyp

    def rank_interventions(
        self,
        interventions: Sequence[Mapping[str, Any]] | Sequence[Any],
        hypothesis_ids: Sequence[str],
    ) -> dict[str, Any]:
        admissible = []
        for item in interventions:
            if hasattr(item, "predicted_outcomes") and hasattr(item, "id"):
                admissible.append(item)
                continue
            kind = item.get("kind", "PERTURBATION")
            if kind not in Intervention._KINDS:
                # Closest generic kinds; do not invent nuclear-only enum values.
                kind = "PERTURBATION"
            admissible.append(
                intervention_search.AdmissibleIntervention(
                    id=item["id"],
                    kind=kind,
                    cost=float(item.get("cost", 1.0)),
                    predicted_outcomes=dict(item.get("predicted_outcomes", {})),
                    assumptions=tuple(item.get("assumptions", ())),
                )
            )
        return intervention_search.search(list(admissible), list(hypothesis_ids))

    def nuclear_intervention(
        self,
        *,
        intervention_id: str,
        target: str,
        kind: str = "PERTURBATION",
        parameters: Mapping[str, Any] | None = None,
    ) -> Intervention:
        if kind not in Intervention._KINDS:
            kind = "PERTURBATION"
        return Intervention(
            intervention_id=intervention_id,
            kind=kind,
            target=target,
            admissible=True,
            parameters=dict(parameters or {}),
        )

    def identity(self) -> dict[str, str]:
        return {
            "atlas_repository": "https://github.com/Sovrance/Atlas",
            "atlas_pir_ref": self.atlas_pir_ref,
            "elementzero_commit": self.elementzero_commit,
            "adapter_version": ADAPTER_VERSION,
        }


# Re-export the Atlas modules the adapter is allowed to wrap. Callers that
# need forward recompilation still go through this module.
forward_recompile = forward
intervention_search_api = intervention_search

PUBLIC_PIR_SYMBOLS = (
    "AnalyzerRef",
    "Artifact",
    "Event",
    "Fact",
    "FactStore",
    "Hypothesis",
    "Intervention",
    "ProvenanceRecord",
    "Warning_",
    "forward",
    "intervention_search",
)
