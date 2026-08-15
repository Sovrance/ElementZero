# ZME-B001: Historical Nuclear Mass Prediction

## Scientific question

Can Zero-Mass Element predict nuclear masses that were not available to the model at a historical cutoff, with uncertainty estimates that remain calibrated as the model moves away from known nuclei?

## Primary benchmark track

`DISCOVERY_HOLDOUT`

Training world:

```text
AME2003 records eligible under policy AME2003-GT-v1
```

Evaluation world:

```text
later-edition records that become ground-truth eligible after the cutoff
and were not ground-truth eligible in the training world
```

The implementation must also support later checkpoint pairs:

```text
AME2003 -> AME2012
AME2012 -> AME2016
AME2016 -> AME2020
```

Do not pool those into one training run. Each pair is a separate historical knowledge freeze.

## Secondary track

`REVISION_HOLDOUT` may compare improved later values for nuclides already known at the old cutoff. Report it separately because it is not the same as predicting a previously unavailable target.

## Ground-truth policy

The AME input format contains evaluator flags and distinctions that must be parsed from the official edition documentation. The agent must implement an edition-specific parser and tests using real source lines.

Policy requirements:

```text
1. Preserve the raw flag/string.
2. Map it to a normalized status using a versioned policy.
3. Never silently erase extrapolation markers.
4. Record policy ID in every normalized row and run certificate.
5. Unit-test at least one measured and one extrapolated source example per edition.
```

## Dataset separation

The benchmark runner receives paths or immutable artifact IDs for:

```text
train_snapshot
later_truth_snapshot
```

The model object receives ONLY training records.

The later truth object is opened only after prediction serialization.

Required execution order:

```text
1. hash both raw/normalized snapshots
2. build KnowledgeFreeze from old snapshot
3. select target IDs from metadata/split manifest
4. fit model using allowed old rows only
5. serialize model manifest
6. predict target identities using Z,N only
7. serialize predictions and prediction certificates
8. close/finalize prediction ledger
9. open later truth values
10. compare and score
11. serialize metrics/calibration report
```

If step 9 occurs before step 7 completes, the run is invalid.

## Target identity versus target value

It is acceptable for the benchmark orchestrator to know that a target nuclide identity exists in the test list. It may know:

```text
Z
N
A
nuclide_id
```

It must not expose later target values, uncertainties, evaluator statuses that encode the answer, or derived values based on them during fit/prediction.

## Baseline model

Use a refit SEMF model first. Coefficients are training-snapshot-specific.

```text
B = X * beta
```

where each row of X contains the five SEMF terms and beta contains fitted coefficients.

Fit via deterministic least squares and record coefficients.

## Residual GP

After SEMF:

```text
r_i = observed_mass_excess_i - semf_mass_excess_i
```

Fit GP on old-snapshot residuals only.

Initial features:

```text
Z
N
A
(N-Z)/A
pairing_sign
```

Standardize features using parameters fit on training data only.

Predicted result:

```text
mass_pred = semf_mass_pred + gp_residual_mean
sigma_pred = gp_residual_std
```

In v0.2, `sigma_pred` is explicitly conditioned on the selected model and kernel. It is not claimed to include full nuclear model-form uncertainty.

## Scoring

Report at least:

```text
n_targets
MAE_keV
RMSE_keV
median_absolute_error_keV
coverage_68
coverage_90
coverage_95
mean_interval_width_90_keV
error_by_nearest_training_distance
```

If Gaussian predictive densities are used, add NLPD.

## Extrapolation distance

Implement at least two transparent distances:

```text
manhattan_ZN = min_train(abs(Z-Z_train) + abs(N-N_train))
scaled_euclidean = min_train(sqrt(((Z-Zt)/sZ)^2 + ((N-Nt)/sN)^2))
```

Use training-derived scale values only.

## Prediction certificate minimum fields

```text
certificate_version
prediction_id
nuclide_id
observable
knowledge_freeze_id
cutoff_date
training_ids_sha256
allowed_source_hashes
model_id
model_manifest_sha256
feature_policy_id
prediction_mean
prediction_std
uncertainty_scope
domain_status
code_version
runtime_manifest_sha256
random_seed
created_at
```

`created_at` is volatile and excluded from scientific identity if that is the established canonical rule. Document the choice.

## Fail-closed leakage tests

Tests must intentionally attempt:

```text
- target ID in training set
- later source hash in allowed sources
- scaler fitted on train+test
- feature table containing target mass-derived column
- prediction comparison before ledger finalization
```

Every attempt must fail with a named exception.

## Synthetic smoke test

The scaffold contains synthetic CSV snapshots. These exist only to test:

- parsing;
- split construction;
- SEMF fitting;
- GP residual prediction;
- certificate generation;
- scoring;
- deterministic reruns.

No scientific result may cite the synthetic fixture.

## Real-data acceptance gate

ZME-B001 is scientifically activated only after agents ingest official AME source files, hash the original files, preserve source lines/flags, and commit a normalized snapshot manifest with reviewable parsing tests.
