# WO-03 - Scientific Scoring, Calibration, and Model Comparison

Priority: HIGH
Repository: ElementZero
Depends on: WO-01
May run in parallel with: WO-02
Blocks: WO-05

## Objective

Upgrade EZ-B001 scoring from a software smoke score to a defensible probabilistic benchmark.

Current metrics:

    MAE
    RMSE
    90% coverage
    95% coverage

Required v0.3 metrics:

    MAE
    median absolute error
    RMSE
    negative log predictive density
    90% coverage
    95% coverage
    90% calibration error
    95% calibration error
    nearest-training distance
    error vs extrapolation distance
    grouped regional summaries

All three existing models must be compared automatically.

## Files to modify

    src/elementzero/models/protocol.py
    src/elementzero/models/gp_residual.py
    src/elementzero/benchmark/metrics.py
    src/elementzero/benchmark/b001_predict.py
    src/elementzero/benchmark/b001_score.py
    src/elementzero/cli.py

New recommended module:

    src/elementzero/benchmark/distance.py
    src/elementzero/benchmark/model_suite.py

Schemas:

    schemas/prediction_certificate.schema.json
    schemas/run_manifest.schema.json

Tests:

    tests/unit/test_gp_residual.py
    tests/integration/test_synthetic_b001.py
    tests/integration/test_reproducibility.py

## 1. Persist predictive standard deviation

The current models compute sigma but discard it after building percentile intervals.

Extend Prediction with:

    std_keV: float

Requirements:

    std_keV > 0 for probabilistic models
    std_keV >= small_epsilon for deterministic baseline wrappers

Every model manifest must state how uncertainty was constructed.

For SEMF:

    std_keV = training residual standard deviation

For GP models:

    std_keV = GP predictive standard deviation

Do not infer sigma from rounded intervals during scoring if the model already computed it.

## 2. Prediction certificate changes

Add:

    predictive_distribution = "gaussian"
    predictive_std_keV
    uncertainty_method

Examples:

SEMF:

    uncertainty_method =
        "global training residual standard deviation"

GP:

    uncertainty_method =
        "GaussianProcessRegressor return_std"

Update schema and tests.

## 3. Normative metrics

For predictions mu_i, truth y_i, sigma_i:

    error_i = mu_i - y_i

    MAE =
        mean(abs(error_i))

    MedAE =
        median(abs(error_i))

    RMSE =
        sqrt(mean(error_i^2))

Gaussian negative log predictive density:

    NLPD_i =
        0.5*log(2*pi*sigma_i^2)
        + 0.5*((y_i - mu_i)/sigma_i)^2

    NLPD =
        mean(NLPD_i)

Coverage:

    coverage_90 =
        count(y_i in interval_90_i) / n

    coverage_95 =
        count(y_i in interval_95_i) / n

Calibration error:

    cal_error_90 =
        abs(coverage_90 - 0.90)

    cal_error_95 =
        abs(coverage_95 - 0.95)

Do not hide poor calibration behind low RMSE.

## 4. Extrapolation distance

Implement a transparent lattice distance from each target to the nearest training nucleus.

Primary metric:

    d_L1(target, train) =
        abs(Z_t - Z_r) + abs(N_t - N_r)

    nearest_training_L1 =
        min over training nuclei

Optional secondary:

    d_L2 =
        sqrt((Z_t-Z_r)^2 + (N_t-N_r)^2)

Persist distance for every scored target.

## 5. Distance buckets

Produce at least:

    d = 1
    d = 2
    d = 3-4
    d >= 5

If a bucket is empty, report n=0 rather than omitting it.

For every nonempty bucket report:

    n
    MAE
    RMSE
    coverage_90
    coverage_95
    NLPD

## 6. Regional summaries

Add fixed, preregistered Z bands.

Recommended v1:

    light:         Z < 20
    medium:        20 <= Z < 50
    heavy:         50 <= Z < 82
    very_heavy:    Z >= 82

Also record isospin asymmetry:

    I = (N - Z) / A

Do not invent a success threshold per band.

## 7. Automatic three-model suite

The existing model IDs are:

    EZ-SEMF-LS-v1
    EZ-GP-DIRECT-v1
    EZ-SEMF-GP-RESIDUAL-v1

Add a model-suite manifest that freezes this ordered set.

Prediction stage must produce separate sealed run directories for each model.

Example:

    runs/EZ-B001-A/
        EZ-SEMF-LS-v1/
        EZ-GP-DIRECT-v1/
        EZ-SEMF-GP-RESIDUAL-v1/

All models use the same:

    KnowledgeFreeze
    targets
    source hashes
    feature policy

## 8. Comparison report

After all model runs are finalized and individually scored, generate:

    model_comparison.json
    model_comparison.md

Minimum columns:

    model_id
    n
    MAE_keV
    MedAE_keV
    RMSE_keV
    NLPD
    coverage_90
    coverage_95
    calibration_error_90
    calibration_error_95

Do not label any model "best" using a single metric.

If a ranking is provided, make the ranking rule explicit and preregistered.

## 9. Reproducibility

All metrics must be deterministic from sealed prediction + truth files.

No bootstrap uncertainty is required in this work order.

If later added, it must use fixed seeds and be separately versioned.

## Required tests

    test_prediction_serializes_std
    test_gaussian_nlpd_known_values
    test_calibration_error
    test_nearest_training_l1
    test_distance_bucket_boundaries
    test_region_boundaries
    test_three_model_suite_same_freeze
    test_model_comparison_contains_all_models
    test_badly_calibrated_model_is_not_hidden
    test_metric_json_reproducible

## Acceptance gates

PASS only if:

- predictive sigma is persisted,
- NLPD is computed directly from mu/sigma,
- distance-to-training is included per target,
- all three models are automatically compared,
- empty groups are explicit,
- scoring is deterministic,
- no performance threshold is used as an engineering gate.

## Stop conditions

STOP if:

- sigma is reconstructed from truth,
- model selection uses later truth before sealing,
- different models use different target sets,
- report silently drops a model with poor results.
