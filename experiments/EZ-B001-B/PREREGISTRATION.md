# Preregistration — EZ-B001-B

Protocol version: 1.0.0
Evidence protocol version: 0.3.0
Benchmark family: EZ-B001
Preregistration hash: `007c1a5267d905c14bf9dca3333778048dc6fec09a17aefe3c7f298f58c5219a`

This document is prose. Every load-bearing value lives in the five JSON
files that the preregistration hash covers. Editing this file cannot change
a number, a hash, or a policy.

## 1. Research question

Trained only on AME2012, how accurately and how honestly do the
three frozen EZ-B001 models predict the mass excess of nuclides that only
became ground-truth eligible in AME2016?

Engineering success is protocol integrity, not low error.

## 2. Protocol identity

```text
benchmark_family = EZ-B001
experiment_id    = EZ-B001-B
protocol_version = 1.0.0
training edition = AME2012
truth edition    = AME2016
```

## 3. Sources

| Role | Edition | File | sha256 |
| --- | --- | --- | --- |
| training | AME2012 | `data/raw/amdc/AME2012/mass.mas12` | `81e887c71c2c54c76caea36fd861b195a7f3eeb77d04b520e05fa97e0eedd7f3` |
| later truth | AME2016 | `data/raw/amdc/AME2016/mass16.txt` | `2167f57a2a98331e4649b2dd2b658a9006ed4fba1975729ebfe52a42b4b9218a` |

Training citation: M. Wang, G. Audi, A.H. Wapstra, F.G. Kondev, M. MacCormick, X. Xu, B. Pfeiffer, 'The AME2012 atomic mass evaluation (II). Tables, graphs and references', Chinese Physics C 36 (2012) 1603-2014, doi:10.1088/1674-1137/36/12/003

Later-edition citation: M. Wang, G. Audi, F.G. Kondev, W.J. Huang, S. Naimi, X. Xu, 'The AME2016 atomic mass evaluation (II). Tables, graphs and references', Chinese Physics C 41 (2017) 030003, doi:10.1088/1674-1137/41/3/030003

Training URL: https://amdc.impcas.ac.cn/masstables/Ame2012/mass.mas12

Later-edition URL: https://amdc.impcas.ac.cn/masstables/Ame2016/mass16.txt

Raw tables stay gitignored. The prediction process may know the later-edition
hash; it may not read the later-edition contents.

## 4. Target rule

```text
training_eligible_ids = AME2012 rows with ground_truth_eligible == True
target_ids            = AME2016 rows with ground_truth_eligible == True minus training_eligible_ids
```

An AME2012 estimated row does not remove a target when the corresponding AME2016 row becomes ground-truth eligible.

The target manifest exposed to prediction contains exactly A, N, Z, nuclide_id.

## 5. Ground-truth eligibility

`ez-gt-policy-v1:evaluated_non_estimated_only`: only evaluated, non-estimated AME rows
may act as training truth or as scored truth.

## 6. Leakage controls

- allowed source hashes: `81e887c71c2c54c76caea36fd861b195a7f3eeb77d04b520e05fa97e0eedd7f3`
- forbidden source hashes: `2167f57a2a98331e4649b2dd2b658a9006ed4fba1975729ebfe52a42b4b9218a`
- identity-only target manifest, validated on load
- KnowledgeFreeze pins training identities, normalized table hash, and feature policy
- prediction ledger is finalized before any truth unlock
- the prediction workspace is checked by a filesystem preflight over truth file
  names and truth content hashes

## 7. Model suite

| model_id | implementation | random_state | uncertainty |
| --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | `src/elementzero/models/gp_residual.py::SEMFLeastSquaresModel` | 0 | global training residual standard deviation |
| EZ-GP-DIRECT-v1 | `src/elementzero/models/gp_residual.py::GPDirectModel` | 0 | GaussianProcessRegressor return_std |
| EZ-SEMF-GP-RESIDUAL-v1 | `src/elementzero/models/gp_residual.py::SEMFGPResidualModel` | 0 | GaussianProcessRegressor return_std |

Features: Z, N, A.

Forbidden in EZ-B001 v1: later truth values; magic-number-distance features; shell labels; future-edition derived features.

## 8. Metrics

Primary: MAE_keV, MedAE_keV, RMSE_keV, NLPD, coverage_90, coverage_95, calibration_error_90, calibration_error_95.

Secondary diagnostics: error vs nearest_training_L1, metrics per L1 distance bucket, metrics per Z band.

No metric may be added after scoring and then described as preregistered. Additional analyses are allowed only when labelled POST_HOC.

## 9. No model tuning after scoring

Once any truth value of the later edition is scored, model definitions and hyperparameters are frozen for this experiment at protocol 1.0.0. A desired change requires a new protocol version (1.1.0 or 2.0.0), a complete rerun, and preservation of the old result. Nothing is overwritten.

## 10. Code identity

```text
atlas_pir_ref        = 31d76d094f1206e64a6920da4775d0a684618357
elementzero_commit   = 2518e07da14764d67db51115d67066358928f464
protocol_code_policy = ez-b001-protocol-code-v1
protocol_code_digest = 5c20d931cdef024efe55fdf7bdab04d339e4bd787076385f0a1de36df1660e5f
```

The commit SHA is lineage. The enforced gate is `protocol_code_digest`, a
hash over the parser, physics, model, metric, evidence, and leakage-control
source files (`src/elementzero/experiments/protocol_code.py`). Adding a
report generator cannot silently invalidate a sealed experiment, and editing
a model or a metric definitely does.

Atlas packaging runs under the approved exception in
`docs/migrations/WO-04-atlas-packaging-exception.md`; the pin is immutable.

## 11. Preregistration hash rule

```text
ez-prereg-hash-v1: sha256 of canonical JSON of the name-sorted [{name, sha256(file bytes)}] list of protocol.json, source_manifest.json, target_policy.json, model_suite.json, metrics_policy.json
```

`PREREGISTRATION_SHA256` holds the resulting digest and is recomputable
with `elementzero benchmark validate-preregistration`.
