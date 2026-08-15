# WO-07 - Repeat Historical Epochs Without Changing the Rules

Priority: HIGH
Repository: ElementZero
Depends on: WO-06
Blocks: WO-08

## Objective

Repeat the exact historical protocol across later AME transitions to test whether ElementZero's behavior is consistent across time.

Experiments:

    EZ-B001-B
    AME2012 -> AME2016

    EZ-B001-C
    AME2016 -> AME2020

## Governing rule

Do not tune the v1 model suite using EZ-B001-A scores and then call B/C comparable v1 results.

For direct comparability, B and C use:

    same parser semantics
    same feature policy
    same three model implementations
    same hyperparameters
    same metric definitions
    same target eligibility rule
    same evidence graph
    same sealing process

Only source edition and target identities change.

## 1. Clone the preregistration structure

Create:

    experiments/EZ-B001-B/
    experiments/EZ-B001-C/

Each gets its own:

    PREREGISTRATION.md
    protocol.json
    source_manifest.json
    target_policy.json
    model_suite.json
    metrics_policy.json
    PREREGISTRATION_SHA256

B:

    training edition = AME2012
    truth edition = AME2016

C:

    training edition = AME2016
    truth edition = AME2020

## 2. Protocol-version compatibility

If ANY of these changed after A:

    parser semantics
    target rule
    model code
    model hyperparameters
    feature policy
    uncertainty method
    metric definitions

then do NOT run B/C as protocol 1.0.0.

Instead:

    bump protocol version
    rerun A under the new version
    then run B and C

Never compare mixed protocol versions as one benchmark series.

## 3. Target policy remains the same

For each epoch:

    training_eligible_ids =
        earlier edition eligible ids

    target_ids =
        later edition eligible ids
        minus training_eligible_ids

Earlier estimated rows remain valid later targets when they become eligible.

## 4. Run and seal independently

Use the exact WO-06 sequence for B and C.

Required tags:

    ez-b001-b-preregistered-v1
    ez-b001-b-predictions-sealed-v1

    ez-b001-c-preregistered-v1
    ez-b001-c-predictions-sealed-v1

Do not use one experiment's truth in another experiment's prediction process.

## 5. Aggregate longitudinal result

After A, B, C are scored, create:

    results/EZ-B001/aggregate_v1.json
    results/EZ-B001/aggregate_v1.md

Required rows:

    experiment_id
    training_edition
    truth_edition
    model_id
    n
    MAE
    MedAE
    RMSE
    NLPD
    coverage_90
    coverage_95
    cal_error_90
    cal_error_95

Also aggregate error by nearest-training distance.

## 6. Stability diagnostics

For each model evaluate:

    metric drift across epochs
    calibration drift
    target-count drift
    error-vs-distance trend

Do not assume later epochs must improve.

If performance worsens, report it.

## 7. Reproducibility replay

Add a replay command:

    elementzero benchmark replay
        --experiment EZ-B001-B

The command reconstructs metrics from:

    sealed predictions
    immutable truth source
    manifests

without refitting.

The replay output must match the committed metrics hashes.

## 8. Historical source citation

Every experiment report must cite the corresponding AME publications, not only the electronic files.

Source URLs/hashes remain in the data manifest for reproducibility.

## Required tests

    test_b_target_policy
    test_c_target_policy
    test_protocol_version_mismatch_rejected
    test_all_epochs_use_same_model_suite
    test_aggregate_contains_all_3x3_rows
    test_replay_matches_committed_metrics
    test_epoch_truth_hash_forbidden_during_prediction
    test_no_cross_epoch_target_leakage

## Acceptance gates

PASS only if:

- A, B, C share one explicit protocol version,
- any protocol change caused A to be rerun,
- every model is present in every epoch,
- each epoch has its own prereg and seal,
- aggregate report includes all results,
- replay is deterministic.

## Stop conditions

STOP and bump protocol if:

- any model is tuned after A scoring,
- any metric changes meaning,
- AME2020 parser behavior changes,
- one epoch uses a different target eligibility rule.
