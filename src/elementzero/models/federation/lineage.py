"""Atlas provenance for federation lineage (WO-12 section 18).

Physics prediction lineage:

    external model table Artifact + KnowledgeFreeze
        -> ModelAdapterFact
        -> ModelPredictionFact

Residual lineage:

    ModelPredictionFact + evaluated residual training set
        -> ResidualModelFitFact
        -> ResidualCorrectedPredictionFact

Combined lineage:

    contributing prediction facts
        -> FederationCombinationFact

Contributors are never flattened into one anonymous model: every combination
fact carries the contributing fact ids, model ids, weights, and independence
groups. Prediction sets are content-addressed as sets (one fact per model per
qualification benchmark) — the per-nuclide sealed prediction facts of the
benchmark pipeline already exist next to these and are not duplicated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# pir types come through the atlas_adapter boundary module: the import
# firewall keeps direct pir imports confined to that one file.
from elementzero.evidence.atlas_adapter import (
    NUCLEAR_MASS_INTERFACE,
    AtlasEvidenceAdapter,
    EvidenceLevel,
    Fact,
    FactStatus,
    Layer,
    Namespace,
    PirLevel,
    Warning_,
    compute_fact_id,
)
from elementzero.evidence.hashing import sha256_hex

MODEL_ADAPTER_FACT_KIND = "federation_model_adapter"
MODEL_PREDICTION_FACT_KIND = "federation_model_prediction_set"
RESIDUAL_FIT_FACT_KIND = "federation_residual_model_fit"
RESIDUAL_PREDICTION_FACT_KIND = "federation_residual_corrected_prediction_set"
COMBINATION_FACT_KIND = "federation_combination"

FEDERATION_LINEAGE_WARNING = (
    "Federation bookkeeping: statements about models and their combination, "
    "conditioned on frozen tables and training freezes. Not experimental "
    "evidence about nuclei."
)


class FederationLineage:
    """Builds the WO-12 fact chain on top of the shared Atlas adapter."""

    def __init__(self, *, created_at: str | None = None) -> None:
        self.adapter = AtlasEvidenceAdapter(created_at=created_at)
        self.facts: list[Fact] = []
        self.provenance: list[Any] = []
        self.artifacts: list[Any] = []

    # -- table artifact + adapter fact ------------------------------------- #

    def table_artifact(self, *, table_path: str | Path, source_url: str):
        raw = Path(table_path).read_bytes()
        artifact = self.adapter.source_artifact(
            raw, source_uri=source_url, acquired_at=self.adapter.created_at
        )
        self.artifacts.append(artifact)
        self.provenance.append(
            self.adapter.append_provenance(
                entity=artifact.artifact_id,
                activity_type="LOAD",
                used=(),
                generated=(artifact.artifact_id,),
            )
        )
        return artifact

    def _analyst_fact(self, content: dict[str, Any], *, assumptions: tuple[str, ...]) -> Fact:
        from elementzero.evidence.atlas_adapter import _heuristic_analyzer

        analyzer = _heuristic_analyzer()
        return Fact(
            fact_id=compute_fact_id(content, analyzer, assumptions=assumptions),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E3,
            layer=Layer.MEASUREMENT,
            namespace=Namespace.analyst,
            status=FactStatus.SUPPORTED,
            analyzer=analyzer,
            content=content,
            created_at=self.adapter.created_at,
            assumptions=assumptions,
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=(
                Warning_(
                    location=f"federation:{content.get('model_id', content['kind'])}",
                    message=FEDERATION_LINEAGE_WARNING,
                ),
            ),
        )

    def model_adapter_fact(
        self,
        *,
        artifact,
        freeze_id: str,
        model_manifest: dict[str, Any],
    ) -> Fact:
        content = {
            "kind": MODEL_ADAPTER_FACT_KIND,
            "model_id": model_manifest["model_id"],
            "independence_group": model_manifest.get("independence_group"),
            "table_raw_sha256": model_manifest.get("table_raw_sha256"),
            "parser_version": model_manifest.get("parser_version"),
            "table_n_rows": model_manifest.get("table_n_rows"),
            "freeze_id": freeze_id,
            "artifact_id": artifact.artifact_id,
            "warning": FEDERATION_LINEAGE_WARNING,
        }
        fact = self._analyst_fact(
            content, assumptions=(f"freeze:{freeze_id}", f"artifact:{artifact.artifact_id}")
        )
        self._record(fact, activity_type="TRANSFORM", used=(artifact.artifact_id,))
        return fact

    def model_prediction_fact(
        self,
        *,
        adapter_fact: Fact | None,
        model_id: str,
        benchmark_id: str,
        prediction_set_digest: str,
        n_predictions: int,
        n_missing: int,
    ) -> Fact:
        content = {
            "kind": MODEL_PREDICTION_FACT_KIND,
            "model_id": model_id,
            "benchmark_id": benchmark_id,
            "prediction_set_digest": prediction_set_digest,
            "n_predictions": n_predictions,
            "n_missing": n_missing,
            "warning": FEDERATION_LINEAGE_WARNING,
        }
        assumptions = (f"model:{model_id}",)
        if adapter_fact is not None:
            assumptions = assumptions + (f"fact:{adapter_fact.fact_id}",)
        fact = self._analyst_fact(content, assumptions=assumptions)
        self._record(
            fact,
            activity_type="ANALYZE",
            used=(adapter_fact.fact_id,) if adapter_fact is not None else (),
        )
        return fact

    def residual_fit_fact(
        self,
        *,
        base_prediction_fact: Fact,
        residual_manifest: dict[str, Any],
        training_identity_digest: str,
    ) -> Fact:
        content = {
            "kind": RESIDUAL_FIT_FACT_KIND,
            "model_id": residual_manifest["model_id"],
            "base_model_id": residual_manifest["base_model_id"],
            "residual_gp_config_id": residual_manifest["residual_gp_config_id"],
            "n_residual_pairs": residual_manifest["n_residual_pairs"],
            "n_skipped_uncovered": residual_manifest["n_skipped_uncovered"],
            "training_identity_digest": training_identity_digest,
            "warning": FEDERATION_LINEAGE_WARNING,
        }
        fact = self._analyst_fact(
            content, assumptions=(f"fact:{base_prediction_fact.fact_id}",)
        )
        self._record(fact, activity_type="ANALYZE", used=(base_prediction_fact.fact_id,))
        return fact

    def residual_prediction_fact(
        self,
        *,
        residual_fit_fact: Fact,
        model_id: str,
        benchmark_id: str,
        prediction_set_digest: str,
        n_predictions: int,
    ) -> Fact:
        content = {
            "kind": RESIDUAL_PREDICTION_FACT_KIND,
            "model_id": model_id,
            "benchmark_id": benchmark_id,
            "prediction_set_digest": prediction_set_digest,
            "n_predictions": n_predictions,
            "warning": FEDERATION_LINEAGE_WARNING,
        }
        fact = self._analyst_fact(content, assumptions=(f"fact:{residual_fit_fact.fact_id}",))
        self._record(fact, activity_type="ANALYZE", used=(residual_fit_fact.fact_id,))
        return fact

    def combination_fact(
        self,
        *,
        combiner_manifest: dict[str, Any],
        benchmark_id: str,
        contributing_facts: dict[str, Fact],
        prediction_set_digest: str,
    ) -> Fact:
        content = {
            "kind": COMBINATION_FACT_KIND,
            "model_id": combiner_manifest["model_id"],
            "benchmark_id": benchmark_id,
            "combination_rule": combiner_manifest["combination_rule"],
            "weights": combiner_manifest["weights"],
            "contributing_model_ids": sorted(contributing_facts),
            "contributing_fact_ids": {
                model_id: fact.fact_id for model_id, fact in sorted(contributing_facts.items())
            },
            "contributing_independence_groups": combiner_manifest[
                "component_independence_groups"
            ],
            "component_source_hashes": combiner_manifest["component_source_hashes"],
            "prediction_set_digest": prediction_set_digest,
            "anonymity_rule": (
                "contributors are never flattened into one anonymous model"
            ),
            "warning": FEDERATION_LINEAGE_WARNING,
        }
        fact = self._analyst_fact(
            content,
            assumptions=tuple(
                f"fact:{f.fact_id}" for _, f in sorted(contributing_facts.items())
            ),
        )
        self._record(
            fact,
            activity_type="ANALYZE",
            used=tuple(f.fact_id for _, f in sorted(contributing_facts.items())),
        )
        return fact

    def _record(self, fact: Fact, *, activity_type: str, used: tuple[str, ...]) -> None:
        self.adapter.append_fact(fact)
        self.facts.append(fact)
        self.provenance.append(
            self.adapter.append_provenance(
                entity=fact.fact_id,
                activity_type=activity_type,
                used=used,
                generated=(fact.fact_id,),
            )
        )

    # -- serialization ------------------------------------------------------ #

    def write_bundle(self, run_dir: str | Path) -> dict[str, str]:
        """Persist the federation graph using the shared predict-stage layout."""
        from elementzero.evidence.atlas_adapter import write_atlas_bundle

        return write_atlas_bundle(
            run_dir,
            stage="predict",
            facts=self.facts,
            provenance=self.provenance,
            artifacts=self.artifacts,
            events=(),
        )


def prediction_set_digest(rows: list[dict[str, Any]]) -> str:
    """Content address of one model's prediction set (sorted by nuclide)."""
    return sha256_hex(sorted(rows, key=lambda r: r["nuclide_id"]))
