# WO-02 - Complete Atlas Evidence and Provenance Graph

Priority: HIGH
Repository: ElementZero
Depends on: WO-01
May run in parallel with: WO-03 after WO-01
Blocks: WO-05

## Objective

Replace the current partial Atlas lineage with a compact, complete scientific evidence graph.

Current behavior creates thousands of observation facts, but each prediction depends on only:

    obs_facts[:1]

That is not an honest representation of the model fit.

The fix is NOT to attach thousands of observations to every prediction.

Create aggregate lineage facts.

## Target evidence graph

    RawSourceArtifact
          |
          v
    NormalizedTrainingDatasetFact
          |
          v
    KnowledgeFreezeFact
          |
          v
    ModelFitFact
          |
          +-----------------------+
          |                       |
          v                       v
    PredictionFact ...       PredictionFact
          \                       /
           \                     /
            v                   v
             PredictionSetFact
                    |
                    v
             FinalizationFact
                    |
                    +------------------+
                    |                  |
                    v                  v
             TruthDatasetFact     prediction set
                    \                  /
                     \                /
                      v              v
                       ValidationFact

## Files to modify

    src/elementzero/evidence/atlas_adapter.py
    src/elementzero/evidence/ledger.py
    src/elementzero/evidence/certificates.py
    src/elementzero/evidence/freezes.py
    src/elementzero/benchmark/b001_predict.py
    src/elementzero/benchmark/b001_finalize.py
    src/elementzero/benchmark/b001_score.py

Tests:

    tests/unit/test_atlas_adapter.py
    tests/unit/test_atlas_contract.py
    tests/integration/test_synthetic_b001.py
    tests/integration/test_reproducibility.py
    tests/leakage/test_leakage.py

## 1. Add Atlas adapter factories

Add methods similar to:

    training_dataset_fact(...)
    knowledge_freeze_fact(...)
    model_fit_fact(...)
    prediction_set_fact(...)
    finalization_fact(...)
    truth_dataset_fact(...)
    validation_fact(...)

Exact names may differ, but the graph above is mandatory.

## 2. TrainingDatasetFact

The fact must identify the exact training corpus WITHOUT carrying every datum in its content.

Required content:

    edition_id
    raw_source_hash
    normalized_table_hash
    training_identity_digest
    training_count
    normalizer_version
    parser_version
    ground_truth_policy

Recommended:

    pir_level = L2
    evidence_level = E2
    layer = DOMAIN
    namespace = domain
    analyzer = SOUND

The source span must point to the raw AME Artifact.

## 3. KnowledgeFreezeFact

Required content:

    freeze_id
    cutoff_date
    allowed_source_hashes
    forbidden_source_hashes
    allowed_edition_ids
    training_identity_digest
    feature_policy_id
    feature_policy_hash
    Atlas commit
    ElementZero commit

It depends on TrainingDatasetFact.

## 4. ModelFitFact

This is a model-conditioned result.

Required content:

    model_id
    model_manifest_hash
    freeze_id
    training_identity_digest
    fitted_nuclide_count
    feature_policy_id
    random_state
    runtime_versions

Recommended:

    evidence_level = E3
    analyzer.tag = HEURISTIC
    warnings = non-empty
    namespace = analyst

It depends on KnowledgeFreezeFact and TrainingDatasetFact.

## 5. PredictionFact

Change current behavior:

    depends_on_facts=[first observation]

to:

    depends_on_facts=[model_fit_fact_id]

Each prediction still retains:

    nuclide_id
    Z
    N
    A
    prediction
    uncertainty
    model_id
    freeze_id

## 6. PredictionSetFact

After all predictions are generated, create one aggregate fact containing:

    model_id
    freeze_id
    target_identity_digest
    n_predictions
    predictions_file_hash
    certificates_file_hash

It may depend on all prediction fact IDs.

This is the compact object used by validation.

## 7. FinalizationFact

After LEDGER_FINALIZED is written, record:

    finalization_marker_hash
    sealed_artifact_hashes
    finalization_timestamp
    run_id

The fact must be SOUND and must not contain truth data.

It depends on PredictionSetFact.

## 8. TruthDatasetFact

Created only in the scoring process.

Required content:

    truth_edition_id
    truth_source_hash
    normalized_truth_hash
    target_identity_digest
    truth_count
    parser_version
    ground_truth_policy

It MUST be created after finalization has been verified.

## 9. ValidationFact

Validation must depend on:

    PredictionSetFact
    FinalizationFact
    TruthDatasetFact

Required content:

    benchmark_id
    protocol_version
    model_id
    metrics
    truth_source_hash
    finalization_marker_hash

## 10. Persist Atlas artifacts

The current adapter store is in-memory.

Write deterministic run files:

Prediction phase:

    atlas/artifacts.json
    atlas/events.json
    atlas/facts.json
    atlas/provenance.json

Scoring phase:

    atlas/scoring_facts.json
    atlas/scoring_provenance.json

All files must use canonical JSON and stable ordering.

## 11. Rehydration

Scoring is a separate process.

Implement a supported ElementZero adapter function that rehydrates the minimum Atlas Fact objects needed to validate lineage.

Do not import Atlas benchmark packages.

Do not add a second copied evidence model.

If Atlas lacks Fact.from_dict, implement the conversion inside:

    elementzero/evidence/atlas_adapter.py

and cover it with contract tests.

## 12. Invalidation test

Add a test:

    invalidate the training-source assumption
        ->
    model fit is downgraded
        ->
    predictions are transitively downgraded
        ->
    prediction set is downgraded

This verifies that the graph is not decorative.

## Required tests

    test_training_dataset_fact_has_exact_digest
    test_model_fit_depends_on_freeze
    test_prediction_depends_on_model_fit_not_single_observation
    test_prediction_set_aggregates_predictions
    test_finalization_has_no_truth_dependency
    test_scoring_validation_depends_on_truth_and_finalization
    test_atlas_fact_bundle_round_trip
    test_training_assumption_invalidation_reaches_predictions
    test_full_synthetic_graph_is_acyclic
    test_reproducible_atlas_fact_hashes

Run:

    python -m pytest -q tests/unit/test_atlas_adapter.py
    python -m pytest -q tests/unit/test_atlas_contract.py
    python -m pytest -q tests/integration
    python -m pytest -q tests/leakage
    python -m pytest -q

## Acceptance gates

PASS only if:

- no PredictionFact directly points at only one arbitrary observation,
- exact training corpus is represented by hashes/digests,
- validation lineage reaches prediction + finalization + truth,
- Atlas graph can be reconstructed in scoring,
- invalidation traversal works transitively,
- graph artifacts reproduce bit-for-bit in deterministic runs.

## Stop conditions

STOP if:

- truth becomes accessible during prediction,
- Atlas facts require copying Atlas PIR into ElementZero,
- a model-generated value is promoted to E2 measurement evidence,
- validation can exist without a finalized prediction set.
