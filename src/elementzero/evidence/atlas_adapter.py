"""Thin Atlas PIR adapter.

All ElementZero production code must reach Atlas PIR through this module.
Do not import Atlas research/benchmark packages (b1_*, b4_*, generator, ...).

The evidence graph this adapter builds for EZ-B001 (WO-02):

    RawSourceArtifact
          |
          v
    TrainingDatasetFact
          |
          v
    KnowledgeFreezeFact
          |
          v
    ModelFitFact
          |
          +---------------------+
          v                     v
    PredictionFact  ...   PredictionFact
          \\                     /
           v                   v
             PredictionSetFact
                    |
                    v
             FinalizationFact
                    |
                    +------------------+
                    v                  v
             TruthDatasetFact     PredictionSetFact
                    \\                 /
                     v               v
                       ValidationFact

Persisted Atlas bundles use Atlas' own canonical JSON (pir.canonical), not the
ElementZero ``.12e`` float policy, so a rehydrated fact re-derives the exact
Atlas content ID it was stored under.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
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
    Verdict,
    Warning_,
    forward,
    intervention_search,
)
from pir.canonical import canonical_json as atlas_canonical_json

from elementzero.atlas_pin import atlas_pir_ref
from elementzero.data.observations import MassObservation
from elementzero.evidence.hashing import content_id, sha256_hex
from elementzero.identity_meta import elementzero_commit

NUCLEAR_MASS_INTERFACE = "mi:nuclear_atomic_mass_excess"
PREDICTION_WARNING = (
    "Model prediction; uncertainty is conditioned on model and training freeze "
    "and is not direct experimental evidence."
)
MODEL_FIT_WARNING = (
    "Model fit is conditioned on the frozen training corpus, the feature policy, "
    "and the fixed random state; it is not experimental evidence."
)
PREDICTION_SET_WARNING = (
    "Aggregate of model predictions; the set inherits the model conditioning of "
    "every prediction it summarizes."
)
ADAPTER_VERSION = "0.3.0"
SOUND_ANALYZER_ID = "elementzero.evidence.normalize"
HEURISTIC_ANALYZER_ID = "elementzero.models.predict"

# Persisted Atlas bundle layout inside a run directory.
ATLAS_DIRNAME = "atlas"
ATLAS_BUNDLE_FILES = {
    "predict": {
        "artifacts": "artifacts.json",
        "events": "events.json",
        "facts": "facts.json",
        "provenance": "provenance.json",
    },
    "finalize": {
        "facts": "finalization_facts.json",
        "provenance": "finalization_provenance.json",
    },
    "score": {
        "facts": "scoring_facts.json",
        "provenance": "scoring_provenance.json",
    },
}

# Cross-namespace transform for freeze-constrained predictions.
# Observation facts live in `domain`; predictions live in `analyst`.
PREDICT_TRANSFORM_NAME = "ez.domain_to_analyst_prediction"
PREDICT_TRANSFORM_SIGNATURE = (
    "domain->analyst via freeze-constrained nuclear mass prediction"
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_source_uri(path: str | Path) -> str:
    """Machine-independent source URI for a sealed artifact record.

    An absolute path is machine layout, not evidence: two clean runs of the same
    protocol in different directories must produce byte-identical Atlas bundles.
    The immutable identity of the input stays in ``Artifact.content_hash``.
    """
    return f"file:{Path(path).name}"


def compute_fact_id(
    content: Mapping[str, Any],
    analyzer: AnalyzerRef,
    *,
    depends_on_facts: Sequence[str] = (),
    assumptions: Sequence[str] = (),
) -> str:
    """Content-address a fact from the exact skeleton it will be stored with.

    Every ElementZero fact ID is derivable from its persisted content, analyzer,
    dependencies, and assumptions; a rehydrated fact therefore re-derives the ID
    it was stored under (see tests/unit/test_atlas_contract.py).
    """
    return Fact.compute_id(
        dict(content),
        analyzer,
        depends_on_facts=list(depends_on_facts),
        assumptions=list(assumptions),
    )


def _sound_analyzer() -> AnalyzerRef:
    return AnalyzerRef(id=SOUND_ANALYZER_ID, version=ADAPTER_VERSION, tag=PassTag.SOUND)


def _heuristic_analyzer() -> AnalyzerRef:
    return AnalyzerRef(id=HEURISTIC_ANALYZER_ID, version=ADAPTER_VERSION, tag=PassTag.HEURISTIC)


def _namespace_transform(from_ns: Namespace, to_ns: Namespace):
    from pir import NamespaceTransform

    if from_ns is Namespace.domain and to_ns is Namespace.analyst:
        name, signature = PREDICT_TRANSFORM_NAME, PREDICT_TRANSFORM_SIGNATURE
    else:
        name = f"ez.{from_ns.value}_to_{to_ns.value}"
        signature = f"{from_ns.value}->{to_ns.value} via freeze-constrained EZ-B001 analysis"
    return NamespaceTransform(
        name=name,
        from_namespace=from_ns,
        to_namespace=to_ns,
        type_signature=signature,
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
        assumptions = (f"src:{observation.raw_source_hash}",)
        fact = Fact(
            fact_id=compute_fact_id(content, analyzer, assumptions=assumptions),
            pir_level=PirLevel.L2,
            evidence_level=evidence,
            layer=Layer.MEASUREMENT,
            namespace=Namespace.domain,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            assumptions=assumptions,
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

    def training_dataset_fact(
        self,
        *,
        artifact: Artifact,
        edition_id: str,
        raw_source_hash: str,
        normalized_table_hash: str,
        training_identity_digest: str,
        training_count: int,
        normalizer_version: str,
        parser_version: str,
        ground_truth_policy: str,
        event: Event | None = None,
        status: str | FactStatus = FactStatus.SUPPORTED,
    ) -> Fact:
        """Aggregate identity of the exact training corpus.

        The corpus is named by hashes and digests; the individual data rows stay
        in the raw artifact instead of being copied into the fact content.
        """
        analyzer = _sound_analyzer()
        content = {
            "kind": "nuclear_training_dataset",
            "edition_id": edition_id,
            "raw_source_hash": raw_source_hash,
            "normalized_table_hash": normalized_table_hash,
            "training_identity_digest": training_identity_digest,
            "training_count": int(training_count),
            "normalizer_version": normalizer_version,
            "parser_version": parser_version,
            "ground_truth_policy": ground_truth_policy,
        }
        assumptions = (f"src:{raw_source_hash}",)
        return Fact(
            fact_id=compute_fact_id(content, analyzer, assumptions=assumptions),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E2,
            layer=Layer.DOMAIN,
            namespace=Namespace.domain,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            assumptions=assumptions,
            source_spans=(
                {
                    "artifact_id": artifact.artifact_id,
                    "span": f"training_corpus:{training_identity_digest}",
                    "event_id": event.event_id if event else None,
                },
            ),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
        )

    def knowledge_freeze_fact(
        self,
        *,
        freeze_id: str,
        cutoff_date: str,
        allowed_source_hashes: Sequence[str],
        forbidden_source_hashes: Sequence[str],
        allowed_edition_ids: Sequence[str],
        training_identity_digest: str,
        feature_policy_id: str,
        feature_policy_hash: str,
        training_dataset_fact_id: str,
        atlas_pir_ref: str | None = None,
        elementzero_commit: str | None = None,
        status: str | FactStatus = FactStatus.SUPPORTED,
    ) -> Fact:
        analyzer = _sound_analyzer()
        content = {
            "kind": "nuclear_knowledge_freeze",
            "freeze_id": freeze_id,
            "cutoff_date": cutoff_date,
            "allowed_source_hashes": list(allowed_source_hashes),
            "forbidden_source_hashes": list(forbidden_source_hashes),
            "allowed_edition_ids": list(allowed_edition_ids),
            "training_identity_digest": training_identity_digest,
            "feature_policy_id": feature_policy_id,
            "feature_policy_hash": feature_policy_hash,
            "atlas_pir_ref": atlas_pir_ref or self.atlas_pir_ref,
            "elementzero_commit": elementzero_commit or self.elementzero_commit,
        }
        depends_on = (training_dataset_fact_id,)
        assumptions = (f"freeze:{freeze_id}",)
        return Fact(
            fact_id=compute_fact_id(
                content, analyzer, depends_on_facts=depends_on, assumptions=assumptions
            ),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E2,
            layer=Layer.DOMAIN,
            namespace=Namespace.domain,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            depends_on_facts=depends_on,
            assumptions=assumptions,
            source_spans=({"artifact_id": freeze_id, "span": "knowledge_freeze"},),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
        )

    def model_fit_fact(
        self,
        *,
        model_id: str,
        model_manifest_hash: str,
        freeze_id: str,
        training_identity_digest: str,
        fitted_nuclide_count: int,
        feature_policy_id: str,
        random_state: int,
        runtime_versions: Mapping[str, str],
        knowledge_freeze_fact_id: str,
        training_dataset_fact_id: str,
        uncertainty_method: str | None = None,
        status: str | FactStatus = FactStatus.UNRESOLVED,
    ) -> Fact:
        """Model-conditioned fit result: E3, HEURISTIC, warned."""
        analyzer = _heuristic_analyzer()
        content = {
            "kind": "nuclear_mass_model_fit",
            "model_id": model_id,
            "model_manifest_hash": model_manifest_hash,
            "freeze_id": freeze_id,
            "training_identity_digest": training_identity_digest,
            "fitted_nuclide_count": int(fitted_nuclide_count),
            "feature_policy_id": feature_policy_id,
            "random_state": int(random_state),
            "runtime_versions": dict(runtime_versions),
            "uncertainty_method": uncertainty_method,
        }
        depends_on = (knowledge_freeze_fact_id, training_dataset_fact_id)
        assumptions = (f"freeze:{freeze_id}", f"model:{model_id}")
        return Fact(
            fact_id=compute_fact_id(
                content, analyzer, depends_on_facts=depends_on, assumptions=assumptions
            ),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E3,
            layer=Layer.DOMAIN,
            namespace=Namespace.analyst,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            depends_on_facts=depends_on,
            assumptions=assumptions,
            source_spans=({"artifact_id": model_manifest_hash, "span": f"fit:{model_id}"},),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=(Warning_(location=f"model_fit:{model_id}", message=MODEL_FIT_WARNING),),
        )

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
        model_fit_fact_id: str,
        std_keV: float | None = None,
        uncertainty_method: str | None = None,
        status: str | FactStatus = FactStatus.UNRESOLVED,
        evidence_level: str | EvidenceLevel = EvidenceLevel.E3,
    ) -> Fact:
        """One prediction, lineage-anchored to the model fit, not to one datum."""
        analyzer = _heuristic_analyzer()
        content = {
            "kind": "nuclear_mass_prediction",
            "nuclide_id": nuclide_id,
            "Z": z,
            "N": n,
            "A": a,
            "mass_excess_keV": prediction_keV,
            "std_keV": std_keV,
            "uncertainty_method": uncertainty_method,
            "intervals": {k: list(v) for k, v in intervals.items()},
            "model_id": model_id,
            "freeze_id": freeze_id,
            "observable": NUCLEAR_MASS_INTERFACE,
        }
        depends_on = (model_fit_fact_id,)
        assumptions = (f"freeze:{freeze_id}", f"model:{model_id}")
        fact = Fact(
            fact_id=compute_fact_id(
                content, analyzer, depends_on_facts=depends_on, assumptions=assumptions
            ),
            pir_level=PirLevel.L2,
            evidence_level=evidence_level,
            layer=Layer.DOMAIN,
            namespace=Namespace.analyst,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            depends_on_facts=depends_on,
            assumptions=assumptions,
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

    def prediction_set_fact(
        self,
        *,
        model_id: str,
        freeze_id: str,
        target_identity_digest: str,
        n_predictions: int,
        predictions_file_hash: str,
        certificates_file_hash: str,
        prediction_fact_ids: Sequence[str],
        status: str | FactStatus = FactStatus.UNRESOLVED,
    ) -> Fact:
        """Compact aggregate the validation stage can depend on."""
        analyzer = _heuristic_analyzer()
        content = {
            "kind": "nuclear_mass_prediction_set",
            "model_id": model_id,
            "freeze_id": freeze_id,
            "target_identity_digest": target_identity_digest,
            "n_predictions": int(n_predictions),
            "predictions_file_hash": predictions_file_hash,
            "certificates_file_hash": certificates_file_hash,
        }
        depends_on = tuple(sorted(set(prediction_fact_ids)))
        if not depends_on:
            raise ValueError("a prediction set must aggregate at least one prediction fact")
        assumptions = (f"freeze:{freeze_id}", f"model:{model_id}")
        return Fact(
            fact_id=compute_fact_id(
                content, analyzer, depends_on_facts=depends_on, assumptions=assumptions
            ),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E3,
            layer=Layer.DOMAIN,
            namespace=Namespace.analyst,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            depends_on_facts=depends_on,
            assumptions=assumptions,
            source_spans=(
                {"artifact_id": predictions_file_hash, "span": f"prediction_set:{model_id}"},
            ),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=(
                Warning_(
                    location=f"prediction_set:{model_id}",
                    message=PREDICTION_SET_WARNING,
                ),
            ),
        )

    def finalization_fact(
        self,
        *,
        run_id: str,
        finalization_marker_hash: str,
        sealed_artifact_hashes: Mapping[str, str],
        finalization_timestamp: str,
        prediction_set_fact_id: str,
        status: str | FactStatus = FactStatus.SUPPORTED,
    ) -> Fact:
        """Sealing record. SOUND, and free of any truth value by construction."""
        analyzer = _sound_analyzer()
        content = {
            "kind": "nuclear_prediction_finalization",
            "run_id": run_id,
            "finalization_marker_hash": finalization_marker_hash,
            "sealed_artifact_hashes": dict(sealed_artifact_hashes),
            "finalization_timestamp": finalization_timestamp,
        }
        depends_on = (prediction_set_fact_id,)
        assumptions = (f"finalization:{finalization_marker_hash}",)
        return Fact(
            fact_id=compute_fact_id(
                content, analyzer, depends_on_facts=depends_on, assumptions=assumptions
            ),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E2,
            layer=Layer.DOMAIN,
            namespace=Namespace.analyst,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            depends_on_facts=depends_on,
            assumptions=assumptions,
            source_spans=({"artifact_id": run_id, "span": "LEDGER_FINALIZED"},),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
        )

    def truth_dataset_fact(
        self,
        *,
        artifact: Artifact,
        truth_edition_id: str,
        truth_source_hash: str,
        normalized_truth_hash: str,
        target_identity_digest: str,
        truth_count: int,
        parser_version: str,
        ground_truth_policy: str,
        event: Event | None = None,
        status: str | FactStatus = FactStatus.SUPPORTED,
    ) -> Fact:
        """Later-edition truth corpus. Created only after finalization is verified."""
        analyzer = _sound_analyzer()
        content = {
            "kind": "nuclear_truth_dataset",
            "truth_edition_id": truth_edition_id,
            "truth_source_hash": truth_source_hash,
            "normalized_truth_hash": normalized_truth_hash,
            "target_identity_digest": target_identity_digest,
            "truth_count": int(truth_count),
            "parser_version": parser_version,
            "ground_truth_policy": ground_truth_policy,
        }
        assumptions = (f"src:{truth_source_hash}",)
        return Fact(
            fact_id=compute_fact_id(content, analyzer, assumptions=assumptions),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E2,
            layer=Layer.MEASUREMENT,
            namespace=Namespace.domain,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            assumptions=assumptions,
            source_spans=(
                {
                    "artifact_id": artifact.artifact_id,
                    "span": f"truth_corpus:{target_identity_digest}",
                    "event_id": event.event_id if event else None,
                },
            ),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
        )

    def validation_fact(
        self,
        *,
        benchmark_id: str,
        metrics: Mapping[str, Any],
        run_id: str,
        prediction_set_fact_id: str,
        finalization_fact_id: str,
        truth_dataset_fact_id: str,
        protocol_version: str,
        model_id: str,
        truth_source_hash: str,
        finalization_marker_hash: str,
        status: str | FactStatus = FactStatus.SUPPORTED,
    ) -> Fact:
        analyzer = _sound_analyzer()
        content = {
            "kind": "nuclear_benchmark_validation",
            "benchmark_id": benchmark_id,
            "protocol_version": protocol_version,
            "model_id": model_id,
            "run_id": run_id,
            "metrics": dict(metrics),
            "truth_source_hash": truth_source_hash,
            "finalization_marker_hash": finalization_marker_hash,
        }
        depends_on = (
            prediction_set_fact_id,
            finalization_fact_id,
            truth_dataset_fact_id,
        )
        assumptions = (f"benchmark:{benchmark_id}", f"src:{truth_source_hash}")
        fact = Fact(
            fact_id=compute_fact_id(
                content, analyzer, depends_on_facts=depends_on, assumptions=assumptions
            ),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E2,
            layer=Layer.DOMAIN,
            namespace=Namespace.analyst,
            status=status,
            analyzer=analyzer,
            content=content,
            created_at=self.created_at,
            depends_on_facts=depends_on,
            assumptions=assumptions,
            source_spans=({"artifact_id": run_id, "span": "score"},),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
        )
        return fact

    def rehydrate(self, payloads: Iterable[Mapping[str, Any]]) -> list[Fact]:
        """Rebuild persisted facts into this adapter's store, parents first."""
        facts = rehydrate_facts_from_dicts(payloads)
        for fact in facts:
            self.append_fact(fact)
        return facts

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


# --------------------------------------------------------------------------- #
# Rehydration (WO-02 section 11)                                              #
# --------------------------------------------------------------------------- #
# Atlas PIR v0.1 ships Fact.to_dict but no Fact.from_dict. The inverse lives
# here, inside the single allowed Atlas boundary module, instead of copying the
# Atlas evidence model into ElementZero.


def analyzer_ref_from_dict(payload: Mapping[str, Any]) -> AnalyzerRef:
    return AnalyzerRef(
        id=payload["id"],
        version=payload["version"],
        tag=PassTag(payload["tag"]),
    )


def fact_from_dict(payload: Mapping[str, Any]) -> Fact:
    """Inverse of ``pir.Fact.to_dict``, enums included."""
    verdict = payload.get("verdict")
    return Fact(
        fact_id=payload["fact_id"],
        pir_level=PirLevel(payload["pir_level"]),
        evidence_level=EvidenceLevel(payload["evidence_level"]),
        layer=Layer(payload["layer"]),
        namespace=Namespace(payload["namespace"]),
        status=FactStatus(payload["status"]),
        analyzer=analyzer_ref_from_dict(payload["analyzer"]),
        content=dict(payload["content"]),
        created_at=payload["created_at"],
        depends_on_facts=tuple(payload.get("depends_on_facts", ())),
        assumptions=tuple(payload.get("assumptions", ())),
        source_spans=tuple(dict(span) for span in payload.get("source_spans", ())),
        measurement_interface=tuple(payload.get("measurement_interface", ())),
        warnings=tuple(
            Warning_(location=w["location"], message=w["message"])
            for w in payload.get("warnings", ())
        ),
        verdict=verdict if verdict is None else Verdict(verdict),
        witness=payload.get("witness"),
        impossibility_certificate=payload.get("impossibility_certificate"),
        similarity=payload.get("similarity"),
        confidence=payload.get("confidence"),
        correlator=payload.get("correlator"),
    )


def rehydrate_facts_from_dicts(payloads: Iterable[Mapping[str, Any]]) -> list[Fact]:
    """Rebuild Fact objects in dependency order (parents before children).

    The order matters because ``FactStore.add_fact`` refuses a fact whose
    parents are not present yet, which is how the append-only store keeps a
    fact from depending on the future.
    """
    facts = {}
    for payload in payloads:
        fact = fact_from_dict(payload)
        facts[fact.fact_id] = fact
    ordered: list[Fact] = []
    emitted: set[str] = set()
    remaining = sorted(facts)
    while remaining:
        ready = [
            fid
            for fid in remaining
            if all(parent in emitted or parent not in facts for parent in facts[fid].depends_on_facts)
        ]
        if not ready:
            raise ValueError(f"persisted Atlas facts contain a dependency cycle: {remaining}")
        for fid in ready:
            ordered.append(facts[fid])
            emitted.add(fid)
        remaining = [fid for fid in remaining if fid not in emitted]
    return ordered


def provenance_record_from_dict(payload: Mapping[str, Any]) -> ProvenanceRecord:
    return ProvenanceRecord(
        record_id=payload["record_id"],
        entity=payload["entity"],
        activity=dict(payload["activity"]),
        agent=dict(payload["agent"]),
        used=tuple(payload.get("used", ())),
        generated=tuple(payload.get("generated", ())),
        created_at=payload["created_at"],
        cross_namespace_transform=payload.get("cross_namespace_transform"),
    )


# --------------------------------------------------------------------------- #
# Deterministic bundle persistence (WO-02 section 10)                         #
# --------------------------------------------------------------------------- #


def atlas_bundle_dir(run_dir: str | Path) -> Path:
    return Path(run_dir) / ATLAS_DIRNAME


def _write_atlas_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = atlas_canonical_json(payload)
    path.write_text(text + "\n", encoding="utf-8")
    return sha256_hex(text.encode("utf-8"))


def write_atlas_bundle(
    run_dir: str | Path,
    *,
    stage: str,
    facts: Sequence[Fact],
    provenance: Sequence[ProvenanceRecord] = (),
    artifacts: Sequence[Artifact] = (),
    events: Sequence[Event] = (),
) -> dict[str, str]:
    """Persist one stage of the Atlas graph; returns file name -> sha256.

    Facts are ordered by fact ID and provenance by record ID so a deterministic
    run reproduces the bundle bit for bit.
    """
    if stage not in ATLAS_BUNDLE_FILES:
        raise ValueError(f"unknown Atlas bundle stage {stage!r}")
    names = ATLAS_BUNDLE_FILES[stage]
    dest = atlas_bundle_dir(run_dir)
    payloads: dict[str, Any] = {
        "facts": [f.to_dict() for f in sorted(facts, key=lambda f: f.fact_id)],
        "provenance": [
            r.to_dict() for r in sorted(provenance, key=lambda r: (r.record_id, r.entity))
        ],
    }
    if "artifacts" in names:
        payloads["artifacts"] = [
            a.to_dict() for a in sorted(artifacts, key=lambda a: a.artifact_id)
        ]
    if "events" in names:
        payloads["events"] = [e.to_dict() for e in sorted(events, key=lambda e: e.event_id)]
    hashes = {}
    for key, filename in names.items():
        hashes[filename] = _write_atlas_json(dest / filename, payloads[key])
    return hashes


def atlas_bundle_paths(run_dir: str | Path, *, stage: str) -> dict[str, Path]:
    if stage not in ATLAS_BUNDLE_FILES:
        raise ValueError(f"unknown Atlas bundle stage {stage!r}")
    dest = atlas_bundle_dir(run_dir)
    return {key: dest / name for key, name in ATLAS_BUNDLE_FILES[stage].items()}


def atlas_bundle_exists(run_dir: str | Path, *, stage: str) -> bool:
    return all(path.is_file() for path in atlas_bundle_paths(run_dir, stage=stage).values())


def read_atlas_facts(run_dir: str | Path, *, stage: str = "predict") -> list[dict[str, Any]]:
    """Read one persisted stage's fact payloads without rebuilding objects."""
    import json

    path = atlas_bundle_paths(run_dir, stage=stage)["facts"]
    return json.loads(path.read_text(encoding="utf-8"))


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
    "Verdict",
    "Warning_",
    "forward",
    "intervention_search",
)
