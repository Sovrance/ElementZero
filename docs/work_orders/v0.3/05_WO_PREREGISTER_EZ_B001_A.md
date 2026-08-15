# WO-05 - Preregister EZ-B001-A Before Any Historical Scoring

Priority: CRITICAL
Repository: ElementZero
Depends on: WO-01, WO-02, WO-03, WO-04
Blocks: WO-06

## Objective

Create an immutable preregistration for the first real ElementZero experiment:

    EZ-B001-A
    training = AME2003
    later truth = AME2012

The preregistration freezes the protocol BEFORE any historical truth is scored.

## New repository structure

Create:

    experiments/EZ-B001-A/
        PREREGISTRATION.md
        protocol.json
        source_manifest.json
        target_policy.json
        model_suite.json
        metrics_policy.json
        PREREGISTRATION_SHA256

Do not place later truth values in these files.

## 1. Protocol identity

Required:

    benchmark_family = "EZ-B001"
    experiment_id = "EZ-B001-A"
    protocol_version = "1.0.0"

Training:

    edition = "AME2003"

Truth:

    edition = "AME2012"

## 2. Target rule

Normative rule:

    training_eligible_ids =
        AME2003 rows with ground_truth_eligible == True

    target_ids =
        AME2012 rows with ground_truth_eligible == True
        minus training_eligible_ids

Important:

An AME2003 estimated row does NOT remove a target if the corresponding AME2012 row becomes eligible.

Target manifest exposed to prediction contains only:

    nuclide_id
    Z
    N
    A

## 3. Source hashes

source_manifest.json records:

    AME2003 raw SHA-256
    AME2012 raw SHA-256
    official source URLs
    parser version
    normalizer version

The AME2012 source hash MUST be copied into the freeze as a forbidden source hash.

The prediction process may know the hash.

It may not read the truth contents.

## 4. Model suite

Freeze exactly:

    EZ-SEMF-LS-v1
    EZ-GP-DIRECT-v1
    EZ-SEMF-GP-RESIDUAL-v1

Record for each model:

    model_id
    code implementation path
    hyperparameters
    random_state
    feature list
    uncertainty method

Current feature policy:

    Z
    N
    A

Forbidden in EZ-B001 v1:

    later truth values
    magic-number-distance features
    shell labels
    future-edition derived features

## 5. Primary metrics

Freeze:

    MAE_keV
    MedAE_keV
    RMSE_keV
    NLPD
    coverage_90
    coverage_95
    calibration_error_90
    calibration_error_95

Secondary diagnostic:

    error vs nearest_training_L1

No metric can be added after scoring and then described as preregistered.

Additional post-hoc analyses are allowed only if labeled POST_HOC.

## 6. No model tuning after scoring

The protocol must say:

    Once any AME2012 truth values are scored,
    model definitions and hyperparameters are frozen for
    EZ-B001-A protocol 1.0.0.

If a change is desired:

    create protocol 1.1.0 or 2.0.0
    rerun the complete experiment
    preserve the old result

Do not overwrite.

## 7. Prediction workspace isolation

The prediction execution SHOULD occur in a workspace that does not contain the AME2012 truth file.

Recommended:

Preparation workspace:

    has AME2003 + AME2012
    emits identity-only targets
    emits AME2012 SHA-256

Prediction workspace:

    has AME2003
    has targets.json
    has preregistration
    DOES NOT have mass.mas12

Scoring workspace:

    receives sealed predictions
    receives mass.mas12 only after finalization

This is stronger than trusting code not to open a visible file.

## 8. Hash the preregistration

Create a canonical hash over:

    protocol.json
    source_manifest.json
    target_policy.json
    model_suite.json
    metrics_policy.json

Write:

    PREREGISTRATION_SHA256

Then commit the preregistration before prediction.

Recommended git tag:

    ez-b001-a-preregistered-v1

## 9. Add CLI support for forbidden hashes

Current freeze_training supports forbidden_source_hashes programmatically, but the CLI does not expose them.

Add one of:

    --forbidden-source-hash <sha256>
    repeated as needed

or:

    --protocol experiments/EZ-B001-A/protocol.json

Preferred: protocol file.

The freeze must include the AME2012 raw hash as forbidden.

## 10. Automated prereg validation

Add:

    elementzero benchmark validate-preregistration
        --experiment experiments/EZ-B001-A

Checks:

    all hashes present
    source hashes are 64 hex chars
    Atlas SHA is immutable
    ElementZero commit captured
    model suite recognized
    metrics recognized
    target manifest contains identities only
    truth source hash is forbidden
    no truth-bearing fields in prereg target payload

## Required tests

    test_preregistration_hash_stable
    test_truth_hash_is_forbidden
    test_model_suite_exactly_three_models
    test_target_policy_preserves_old_estimated_targets
    test_preregistration_contains_no_truth_values
    test_mutable_atlas_ref_rejected
    test_unknown_metric_rejected
    test_unknown_model_rejected

## Acceptance gates

PASS only if:

- preregistration exists before prediction,
- git commit and Atlas SHA are fixed,
- later source hash is forbidden,
- model/metric policies are frozen,
- target rule is unambiguous,
- later truth values are absent from prediction inputs,
- prereg hash is reproducible.

## Stop conditions

DO NOT START WO-06 if:

- WO-01 through WO-04 are not merged,
- official AME parser fixtures are not green,
- AME2012 raw hash is not forbidden,
- the model suite was tuned using AME2012 scores.
