# WO-09 - Implement EZ-B002 Geographic Nuclear-Chart Holdout

Priority: NEXT RESEARCH GATE
Repository: ElementZero
Depends on: WO-08
Blocks: WO-10

## Objective

Test whether ElementZero can extrapolate into deliberately removed contiguous regions of the known nuclear chart.

EZ-B001 asks:

    could the model predict later historical knowledge?

EZ-B002 asks:

    can the model reconstruct a known region
    when all truth in that region is withheld?

This is the first direct rehearsal for prediction into unknown territory.

## New benchmark

    benchmark_id = EZ-B002
    title = Geographic Nuclear-Chart Holdout

Recommended protocol version:

    1.0.0

## New modules

    src/elementzero/benchmark/b002_prepare.py
    src/elementzero/benchmark/b002_freeze.py
    src/elementzero/benchmark/b002_predict.py
    src/elementzero/benchmark/b002_finalize.py
    src/elementzero/benchmark/b002_score.py
    src/elementzero/benchmark/regions.py

Schemas:

    schemas/geographic_region.schema.json
    schemas/geographic_split_manifest.schema.json

Tests:

    tests/unit/test_b002_regions.py
    tests/leakage/test_b002_leakage.py
    tests/integration/test_synthetic_b002.py
    tests/integration/test_reproducibility_b002.py

## 1. Data snapshot

Initial benchmark should use one frozen evaluated mass snapshot.

Recommended initial source:

    AME2020

Use only:

    ground_truth_eligible == True

Record exact raw source hash.

Do not combine editions in B002 v1.

## 2. Region definition

Support explicit region objects:

Rectangle:

    type = "rectangle"
    z_min
    z_max
    n_min
    n_max

Isotopic segment:

    type = "isotopic"
    Z
    n_min
    n_max

Isotonic segment:

    type = "isotonic"
    N
    z_min
    z_max

The first production benchmark should use rectangles.

## 3. Region-generation policy

Do not hand-pick only regions that models reconstruct well.

Implement a deterministic candidate generator.

Recommended process:

1. create candidate fixed-size Z/N windows,
2. retain windows with at least MIN_TARGETS eligible nuclei,
3. retain windows with training support around at least two sides,
4. sort deterministically,
5. choose a preregistered number spanning light/medium/heavy Z bands.

The exact selected region manifest is frozen before model scoring.

Store:

    experiments/EZ-B002-v1/regions.json

## 4. Leakage rule

For a given region:

    targets =
        all eligible nuclei inside region

    training =
        all eligible nuclei outside region

No target mass can enter:

    fitting
    feature construction
    hyperparameter tuning
    uncertainty calibration

Target identities Z/N/A are allowed.

## 5. Distance-to-boundary

For each held-out target compute:

    nearest_training_L1 =
        min(abs(Z_t-Z_r) + abs(N_t-N_r))

This becomes the primary extrapolation-depth coordinate.

Report errors by depth.

## 6. Model suite

Start with the exact models from the historical benchmark:

    EZ-SEMF-LS-v1
    EZ-GP-DIRECT-v1
    EZ-SEMF-GP-RESIDUAL-v1

Additional serious mass models may be added only under a versioned B002 protocol.

Do not remove weak baselines.

## 7. Freeze structure

Create one KnowledgeFreeze per:

    region x model-suite data split

The split digest must include:

    source hash
    region manifest hash
    training identity digest
    target identity digest
    feature policy hash

## 8. Metrics

Primary:

    MAE
    MedAE
    RMSE
    NLPD
    coverage_90
    coverage_95
    calibration_error_90
    calibration_error_95

Diagnostics:

    metrics by nearest_training_L1
    metrics by region
    metrics by model
    worst-region error
    calibration vs depth

## 9. No accuracy pass/fail yet

B002 v1 is characterization.

Engineering PASS means:

    masking is correct
    leakage absent
    outputs calibrated/scored
    results reproducible

Do not define a "successful extrapolator" threshold after seeing the results.

A later protocol may preregister a scientific threshold.

## 10. Synthetic region test

Before real AME data, build a synthetic smooth nuclear-like surface with a hidden rectangular block.

Verify:

    target values are unavailable during fit
    region identities remain available
    distance metric is correct
    deeper points have larger L1 distance
    sealing/scoring mirrors EZ-B001

## 11. Atlas evidence

Reuse the same evidence graph:

    dataset
      ->
    geographic split/freeze
      ->
    model fit
      ->
    prediction set
      ->
    finalization
      ->
    truth dataset
      ->
    validation

Region manifest hash is part of the freeze and ModelFitFact.

## Required tests

    test_rectangle_membership
    test_region_targets_excluded_from_training
    test_region_manifest_hash_stable
    test_distance_to_training
    test_target_truth_in_features_rejected
    test_all_models_same_region
    test_region_results_reproducible
    test_empty_or_unsupported_region_rejected
    test_aggregate_reports_all_regions

## Acceptance gates

PASS only if:

- regions are deterministic and preregistered,
- target truth is entirely absent during fit,
- distance-to-training is correct,
- every model sees identical splits,
- outputs are sealed before scoring,
- all selected regions are reported,
- results reproduce.

## Stop conditions

STOP if:

- regions are changed after seeing performance,
- only easy regions are retained,
- target values enter normalization statistics,
- hyperparameters are tuned against hidden-region truth.
