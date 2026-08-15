import pytest

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import GROUND_TRUTH_POLICY, MassObservation
from elementzero.evidence.atlas_adapter import (
    MODEL_FIT_WARNING,
    NUCLEAR_MASS_INTERFACE,
    PREDICTION_WARNING,
    PUBLIC_PIR_SYMBOLS,
    AtlasEvidenceAdapter,
)

TRAINING_DIGEST = "aa" * 32
RAW_SOURCE_HASH = "ab" * 32
TABLE_HASH = "ba" * 32


def _obs(*, estimated: bool = False) -> MassObservation:
    return MassObservation(
        nuclide=NuclideIdentity.from_zn(8, 8),
        mass_excess_keV=-4737.0,
        uncertainty_keV=0.1,
        source_edition="AME2003",
        source_release_date="2003-12-22",
        source_record_status="evaluated_estimated" if estimated else "evaluated_non_estimated",
        raw_source_hash=RAW_SOURCE_HASH,
    )


def _graph(adapter: AtlasEvidenceAdapter, *, n_predictions: int = 2) -> dict:
    """Build the full WO-02 lineage in memory."""
    artifact = adapter.source_artifact(
        b"AME synthetic bytes",
        source_uri="file://old.mas03",
        acquired_at="2003-12-22T00:00:00Z",
    )
    event = adapter.observation_event(artifact)
    training = adapter.training_dataset_fact(
        artifact=artifact,
        edition_id="AME2003",
        raw_source_hash=RAW_SOURCE_HASH,
        normalized_table_hash=TABLE_HASH,
        training_identity_digest=TRAINING_DIGEST,
        training_count=10,
        normalizer_version="ez-norm-v2",
        parser_version="ame-parser-v2",
        ground_truth_policy=GROUND_TRUTH_POLICY,
        event=event,
    )
    adapter.append_fact(training)
    freeze = adapter.knowledge_freeze_fact(
        freeze_id="frz_test",
        cutoff_date="2003-12-22",
        allowed_source_hashes=(RAW_SOURCE_HASH,),
        forbidden_source_hashes=(),
        allowed_edition_ids=("AME2003",),
        training_identity_digest=TRAINING_DIGEST,
        feature_policy_id="ez-b001-identity-zn-v1",
        feature_policy_hash="cc" * 32,
        training_dataset_fact_id=training.fact_id,
    )
    adapter.append_fact(freeze)
    fit = adapter.model_fit_fact(
        model_id="EZ-SEMF-GP-RESIDUAL-v1",
        model_manifest_hash="dd" * 32,
        freeze_id="frz_test",
        training_identity_digest=TRAINING_DIGEST,
        fitted_nuclide_count=10,
        feature_policy_id="ez-b001-identity-zn-v1",
        random_state=0,
        runtime_versions={"numpy": "2.0.0"},
        knowledge_freeze_fact_id=freeze.fact_id,
        training_dataset_fact_id=training.fact_id,
        uncertainty_method="GaussianProcessRegressor return_std",
    )
    adapter.append_fact(fit)
    predictions = []
    for index in range(n_predictions):
        pred = adapter.prediction_fact(
            nuclide_id=f"Z18-N{19 + index}",
            z=18,
            n=19 + index,
            a=37 + index,
            prediction_keV=-30000.0 - index,
            intervals={"p90": [-31000.0, -29000.0], "p95": [-31500.0, -28500.0]},
            model_id="EZ-SEMF-GP-RESIDUAL-v1",
            freeze_id="frz_test",
            model_fit_fact_id=fit.fact_id,
            std_keV=500.0,
            uncertainty_method="GaussianProcessRegressor return_std",
        )
        adapter.append_fact(pred)
        predictions.append(pred)
    prediction_set = adapter.prediction_set_fact(
        model_id="EZ-SEMF-GP-RESIDUAL-v1",
        freeze_id="frz_test",
        target_identity_digest="ee" * 32,
        n_predictions=len(predictions),
        predictions_file_hash="11" * 32,
        certificates_file_hash="22" * 32,
        prediction_fact_ids=[p.fact_id for p in predictions],
    )
    adapter.append_fact(prediction_set)
    finalization = adapter.finalization_fact(
        run_id="prediction",
        finalization_marker_hash="33" * 32,
        sealed_artifact_hashes={"predictions": "11" * 32},
        finalization_timestamp="2026-08-15T00:00:00Z",
        prediction_set_fact_id=prediction_set.fact_id,
    )
    adapter.append_fact(finalization)
    return {
        "artifact": artifact,
        "event": event,
        "training": training,
        "freeze": freeze,
        "fit": fit,
        "predictions": predictions,
        "prediction_set": prediction_set,
        "finalization": finalization,
    }


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
    assert len(adapter.store) == 1


def test_training_dataset_fact_has_exact_digest():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    graph = _graph(adapter)
    training = graph["training"]
    content = training.content
    assert content["training_identity_digest"] == TRAINING_DIGEST
    assert content["raw_source_hash"] == RAW_SOURCE_HASH
    assert content["normalized_table_hash"] == TABLE_HASH
    assert content["training_count"] == 10
    assert content["parser_version"] == "ame-parser-v2"
    assert content["ground_truth_policy"] == GROUND_TRUTH_POLICY
    # The corpus is named by digests, never carried row by row.
    assert "mass_excess_keV" not in content
    assert "training_nuclide_ids" not in content
    assert training.evidence_level.value == "E2"
    assert training.namespace.value == "domain"
    assert training.analyzer.tag.value == "SOUND"
    assert training.source_spans[0]["artifact_id"] == graph["artifact"].artifact_id
    assert f"src:{RAW_SOURCE_HASH}" in training.assumptions


def test_model_fit_depends_on_freeze():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    graph = _graph(adapter)
    fit = graph["fit"]
    assert graph["freeze"].fact_id in fit.depends_on_facts
    assert graph["training"].fact_id in fit.depends_on_facts
    assert graph["training"].fact_id in graph["freeze"].depends_on_facts
    assert fit.evidence_level.value == "E3"
    assert fit.analyzer.tag.value == "HEURISTIC"
    assert fit.warnings and MODEL_FIT_WARNING in fit.warnings[0].message
    assert fit.namespace.value == "analyst"
    assert fit.content["model_manifest_hash"] == "dd" * 32
    assert fit.content["runtime_versions"] == {"numpy": "2.0.0"}


def test_prediction_depends_on_model_fit_not_single_observation():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    graph = _graph(adapter)
    observation = adapter.observation_fact(_obs(), artifact=graph["artifact"])
    for pred in graph["predictions"]:
        assert pred.depends_on_facts == (graph["fit"].fact_id,)
        assert observation.fact_id not in pred.depends_on_facts
        assert pred.warnings and PREDICTION_WARNING in pred.warnings[0].message
        assert pred.content["std_keV"] == 500.0
        assert pred.content["uncertainty_method"] == "GaussianProcessRegressor return_std"


def test_prediction_set_aggregates_predictions():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    graph = _graph(adapter, n_predictions=3)
    prediction_set = graph["prediction_set"]
    assert prediction_set.content["n_predictions"] == 3
    assert set(prediction_set.depends_on_facts) == {p.fact_id for p in graph["predictions"]}
    assert prediction_set.content["predictions_file_hash"] == "11" * 32
    assert prediction_set.content["certificates_file_hash"] == "22" * 32
    assert prediction_set.content["target_identity_digest"] == "ee" * 32


def test_prediction_set_requires_at_least_one_prediction():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    with pytest.raises(ValueError):
        adapter.prediction_set_fact(
            model_id="EZ-SEMF-LS-v1",
            freeze_id="frz_test",
            target_identity_digest="ee" * 32,
            n_predictions=0,
            predictions_file_hash="11" * 32,
            certificates_file_hash="22" * 32,
            prediction_fact_ids=[],
        )


def test_finalization_has_no_truth_dependency():
    from elementzero.data.observations import TRUTH_BEARING_FIELDS

    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    graph = _graph(adapter)
    finalization = graph["finalization"]
    assert finalization.depends_on_facts == (graph["prediction_set"].fact_id,)
    assert finalization.analyzer.tag.value == "SOUND"
    assert finalization.evidence_level.value == "E2"
    assert not TRUTH_BEARING_FIELDS.intersection(finalization.content)
    kinds = {
        adapter.store.get(fid).content["kind"]
        for fid in adapter.store.dependents_of_fact(graph["training"].fact_id)
    }
    assert "nuclear_truth_dataset" not in kinds


def test_scoring_validation_depends_on_truth_and_finalization():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    graph = _graph(adapter)
    truth_artifact = adapter.source_artifact(
        b"AME2020 synthetic truth",
        source_uri="file://later.mas20",
        acquired_at="2021-03-01T00:00:00Z",
    )
    truth = adapter.truth_dataset_fact(
        artifact=truth_artifact,
        truth_edition_id="AME2020",
        truth_source_hash="44" * 32,
        normalized_truth_hash="55" * 32,
        target_identity_digest="ee" * 32,
        truth_count=2,
        parser_version="ame-parser-v2",
        ground_truth_policy=GROUND_TRUTH_POLICY,
    )
    adapter.append_fact(truth)
    validation = adapter.validation_fact(
        benchmark_id="EZ-B001",
        metrics={"n": 2, "MAE_keV": 1.5},
        run_id="prediction",
        prediction_set_fact_id=graph["prediction_set"].fact_id,
        finalization_fact_id=graph["finalization"].fact_id,
        truth_dataset_fact_id=truth.fact_id,
        protocol_version="0.3.0",
        model_id="EZ-SEMF-GP-RESIDUAL-v1",
        truth_source_hash="44" * 32,
        finalization_marker_hash="33" * 32,
    )
    adapter.append_fact(validation)
    assert set(validation.depends_on_facts) == {
        graph["prediction_set"].fact_id,
        graph["finalization"].fact_id,
        truth.fact_id,
    }
    assert validation.content["protocol_version"] == "0.3.0"
    assert validation.content["truth_source_hash"] == "44" * 32
    assert validation.content["finalization_marker_hash"] == "33" * 32
    assert validation.content["model_id"] == "EZ-SEMF-GP-RESIDUAL-v1"
    assert validation.content["metrics"]["MAE_keV"] == 1.5


def test_training_assumption_invalidation_reaches_predictions():
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    graph = _graph(adapter, n_predictions=3)
    affected = adapter.invalidate_assumption(
        f"src:{RAW_SOURCE_HASH}", "training source edition recalled"
    )
    expected = {
        graph["training"].fact_id,
        graph["freeze"].fact_id,
        graph["fit"].fact_id,
        graph["prediction_set"].fact_id,
        *[p.fact_id for p in graph["predictions"]],
    }
    assert expected.issubset(set(affected))
    for fact_id in expected:
        assert adapter.store.get(fact_id).status.value == "DOWNGRADED"


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
