import pytest

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.evidence.atlas_adapter import (
    NUCLEAR_MASS_INTERFACE,
    PREDICTION_WARNING,
    PUBLIC_PIR_SYMBOLS,
    AtlasEvidenceAdapter,
)


def _obs(*, estimated: bool = False) -> MassObservation:
    return MassObservation(
        nuclide=NuclideIdentity.from_zn(8, 8),
        mass_excess_keV=-4737.0,
        uncertainty_keV=0.1,
        source_edition="AME2003",
        source_release_date="2003-12-22",
        source_record_status="evaluated_estimated" if estimated else "evaluated_non_estimated",
        raw_source_hash="ab" * 32,
    )


def test_adapter_persists_artifact_fact_provenance_downgrade_and_ranking():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    artifact = adapter.source_artifact(
        b"AME synthetic bytes",
        source_uri="file://old.mas03",
        acquired_at="2003-12-22T00:00:00Z",
    )
    assert artifact.kind == "DATASET"
    assert artifact.namespace.value == "raw"
    event = adapter.observation_event(artifact)
    fact = adapter.observation_fact(_obs(), artifact=artifact, event=event)
    assert fact.measurement_interface == (NUCLEAR_MASS_INTERFACE,)
    assert fact.evidence_level.value == "E2"
    adapter.append_fact(fact)
    adapter.append_provenance(
        entity=fact.fact_id,
        activity_type="LOWER",
        used=(artifact.artifact_id,),
        generated=(fact.fact_id,),
    )
    pred = adapter.prediction_fact(
        nuclide_id="Z18-N19",
        z=18,
        n=19,
        a=37,
        prediction_keV=-30000.0,
        intervals={"p90": [-31000.0, -29000.0]},
        model_id="EZ-SEMF-GP-RESIDUAL-v1",
        freeze_id="frz_test",
        depends_on_facts=(fact.fact_id,),
    )
    assert pred.warnings
    assert PREDICTION_WARNING in pred.warnings[0].message
    adapter.append_fact(pred)
    adapter.append_provenance(
        entity=pred.fact_id,
        activity_type="ANALYZE",
        used=(fact.fact_id,),
        generated=(pred.fact_id,),
    )
    affected = adapter.invalidate_assumption(f"src:{_obs().raw_source_hash}", "source recalled")
    assert fact.fact_id in affected
    ranking = adapter.rank_interventions(
        [
            {
                "id": "measure-Z18-N19",
                "kind": "PERTURBATION",
                "cost": 1.0,
                "predicted_outcomes": {"h_semf": "low", "h_gp": "high"},
            },
            {
                "id": "scale-sweep",
                "kind": "SCALE_SWEEP",
                "cost": 2.0,
                "predicted_outcomes": {"h_semf": "same", "h_gp": "same"},
            },
        ],
        ["h_semf", "h_gp"],
    )
    assert ranking["verdict"] == "DISCRIMINATOR_FOUND"
    assert ranking["best"]["intervention_id"] == "measure-Z18-N19"
    assert adapter.store.provenance()
    assert len(adapter.store) == 2


def test_heuristic_prediction_without_warning_is_rejected():
    from pir import AnalyzerRef, Fact, PIRValidationError, Warning_

    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    with pytest.raises(PIRValidationError):
        Fact(
            fact_id="bad",
            pir_level="L2",
            evidence_level="E3",
            layer="DOMAIN",
            namespace="analyst",
            status="UNRESOLVED",
            analyzer=AnalyzerRef(id="x", version="0.2.0", tag="HEURISTIC"),
            content={"k": 1},
            created_at="2026-08-15T00:00:00Z",
            source_spans=({"artifact_id": "a", "span": "s"},),
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=(),
        )
    # Control: the same fact is legal once a located warning is present.
    Fact(
        fact_id="ok",
        pir_level="L2",
        evidence_level="E3",
        layer="DOMAIN",
        namespace="analyst",
        status="UNRESOLVED",
        analyzer=AnalyzerRef(id="x", version="0.2.0", tag="HEURISTIC"),
        content={"k": 1},
        created_at="2026-08-15T00:00:00Z",
        source_spans=({"artifact_id": "a", "span": "s"},),
        measurement_interface=(NUCLEAR_MASS_INTERFACE,),
        warnings=(Warning_(location="prediction:Z1-N1", message=PREDICTION_WARNING),),
    )
    assert "Fact" in PUBLIC_PIR_SYMBOLS
    assert adapter.identity()["atlas_pir_ref"]


def test_estimated_observation_is_not_promoted_to_e2():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    artifact = adapter.source_artifact(b"x", source_uri="file://x", acquired_at="2003-12-22T00:00:00Z")
    fact = adapter.observation_fact(_obs(estimated=True), artifact=artifact)
    assert fact.evidence_level.value == "E4"
    assert fact.warnings
