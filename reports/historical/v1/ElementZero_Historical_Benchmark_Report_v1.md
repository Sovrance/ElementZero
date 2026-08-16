# ElementZero Historical Benchmark Report v1

This is a repository record, not a summary for readers who want a headline. Every
number below is read from a committed artifact under `experiments/` and
`results/EZ-B001/`, and the machine-readable form of every table in this file is
`aggregate_metrics.json` next to it.

```text
benchmark_id               = EZ-B001
report_version             = v1
experiment_protocol        = 1.0.0
evidence_protocol          = 0.3.0
protocol_code_digest       = 5c20d931cdef024efe55fdf7bdab04d339e4bd787076385f0a1de36df1660e5f
model_suite_id             = EZ-B001-SUITE-v1
epochs                     = EZ-B001-A, EZ-B001-B, EZ-B001-C
models                     = EZ-SEMF-LS-v1, EZ-GP-DIRECT-v1, EZ-SEMF-GP-RESIDUAL-v1
```

Ranking rule: Every metric is reported for every model in every epoch. No ranking, no best-model label, and no epoch is dropped for behaving badly.

## 1. Research question

Trained only on an earlier AME edition, how accurately and how honestly do the three
frozen EZ-B001 models predict the mass excess of nuclides that only became
ground-truth eligible in the following edition?

The question is deliberately narrow. What this benchmark measures:

- interpolation and extrapolation behaviour on later-edition nuclides
- historical predictive accuracy of the three frozen models
- calibration of the reported predictive intervals
- degradation of error with nearest-training L1 distance
- relative behaviour of the three model families under one protocol

What it does not measure, and what is therefore not claimed anywhere below:

- no claim that a model learned nuclear physics
- no significance test, p-value, or confidence statement that was not preregistered
- no best-model label and no single-metric ranking
- no extrapolation of these results to nuclides outside the scored target sets

Engineering success for this series is protocol integrity. A poor scientific result
is reported, never dropped.

## 2. Protocol and preregistration

Each epoch was preregistered before any later-edition truth was read, sealed, and
only then scored. The preregistration hash covers five JSON files; the prose
statement in `PREREGISTRATION.md` is outside the hash and cannot change a number.

| Experiment | Training | Truth | N | Preregistration hash | Sealed predictions sha256 |
| --- | --- | --- | --- | --- | --- |
| EZ-B001-A | AME2003 | AME2012 | 225 | `3bb01b68dd2d07f4abcc7a2c755332c3a9218b79c9daf900d0c8d9127f756442` | `4b88dc5cbd72c98bdc26a77aad669e653af58bc380d822bdd45c4701f79bdcda` |
| EZ-B001-B | AME2012 | AME2016 | 63 | `007c1a5267d905c14bf9dca3333778048dc6fec09a17aefe3c7f298f58c5219a` | `3f3a922c0f0c3171b67649cb31485ec2bc5dc5eef6df4913032390c025676189` |
| EZ-B001-C | AME2016 | AME2020 | 74 | `e563ce856380f4abc51558f91d74d2135d69d0a3379b8c426f4f6e139f4d6c29` | `b967eb4f06e306770e4e24902dc2273cb94f449944b09988f2fa596253942c35` |

One protocol governs the whole series: same parser and normalizer versions, same
target rule, same model suite, same hyperparameters, same uncertainty method, same
metric definitions. The longitudinal aggregate refuses to mix protocol versions,
model suites, Atlas pins, or protocol code digests, so a mixed series cannot be
published as one benchmark.

Model definitions and hyperparameters were frozen at the moment the first truth
value was scored. A change requires a new protocol version and a complete rerun;
nothing is overwritten.

## 3. Data editions

Raw AME tables are licensed upstream files and stay out of git. Their sha256
values, download URLs, citations, and parse reports are committed instead, which is
what makes the run auditable without the files.

| Edition | Release | File | sha256 | Parsed | Eligible | Estimated | Malformed fraction | Roles |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AME2003 | 2003-12-22 | `mass.mas03` | `33405560376f2adfb190beec44213523ec79149804df94e436d608019a4c70d1` | 3179 | 2228 | 951 | 0 | training in EZ-B001-A |
| AME2012 | 2012-12-01 | `mass.mas12` | `81e887c71c2c54c76caea36fd861b195a7f3eeb77d04b520e05fa97e0eedd7f3` | 3353 | 2438 | 915 | 0 | truth in EZ-B001-A; training in EZ-B001-B |
| AME2016 | 2017-03-01 | `mass16.txt` | `2167f57a2a98331e4649b2dd2b658a9006ed4fba1975729ebfe52a42b4b9218a` | 3436 | 2498 | 938 | 0 | truth in EZ-B001-B; training in EZ-B001-C |
| AME2020 | 2021-03-01 | `mass_1.mas20.txt` | `e8599c6d7f724fac91934e59f1b9de8fb8f63e820f4b39456b790665ed2a3307` | 3558 | 2550 | 1008 | 0 | truth in EZ-B001-C |

Citations and download locations:

- AME2003: G. Audi, A.H. Wapstra, C. Thibault, 'The AME2003 atomic mass evaluation (II). Tables, graphs and references', Nuclear Physics A 729 (2003) 337-676, doi:10.1016/j.nuclphysa.2003.11.003
  - `https://amdc.impcas.ac.cn/masstables/Ame2003/mass.mas03` -> `data/raw/amdc/AME2003/mass.mas03`
- AME2012: M. Wang, G. Audi, A.H. Wapstra, F.G. Kondev, M. MacCormick, X. Xu, B. Pfeiffer, 'The AME2012 atomic mass evaluation (II). Tables, graphs and references', Chinese Physics C 36 (2012) 1603-2014, doi:10.1088/1674-1137/36/12/003
  - `https://amdc.impcas.ac.cn/masstables/Ame2012/mass.mas12` -> `data/raw/amdc/AME2012/mass.mas12`
- AME2016: M. Wang, G. Audi, F.G. Kondev, W.J. Huang, S. Naimi, X. Xu, 'The AME2016 atomic mass evaluation (II). Tables, graphs and references', Chinese Physics C 41 (2017) 030003, doi:10.1088/1674-1137/41/3/030003
  - `https://amdc.impcas.ac.cn/masstables/Ame2016/mass16.txt` -> `data/raw/amdc/AME2016/mass16.txt`
- AME2020: M. Wang, W.J. Huang, F.G. Kondev, G. Audi, S. Naimi, 'The AME2020 atomic mass evaluation (II). Tables, graphs and references', Chinese Physics C 45 (2021) 030003, doi:10.1088/1674-1137/abddaf
  - `https://amdc.impcas.ac.cn/masstables/Ame2020/mass_1.mas20.txt` -> `data/raw/amdc/AME2020/mass_1.mas20.txt`

Parser version `ame-parser-v2`. Every parse report records zero rows with `A != Z + N` and zero duplicate identities.

## 4. Ground-truth eligibility policy

Policy `ez-gt-policy-v1:evaluated_non_estimated_only`: only evaluated, non-estimated AME rows may
act as training truth or as scored truth. An estimated row in the training edition
does not remove a target when the later edition promotes that nuclide to
ground-truth eligible, because that promotion is exactly the historical event the
benchmark measures.

| Experiment | training_eligible_ids | target_ids |
| --- | --- | --- |
| EZ-B001-A | AME2003 rows with ground_truth_eligible == True | AME2012 rows with ground_truth_eligible == True minus training_eligible_ids |
| EZ-B001-B | AME2012 rows with ground_truth_eligible == True | AME2016 rows with ground_truth_eligible == True minus training_eligible_ids |
| EZ-B001-C | AME2016 rows with ground_truth_eligible == True | AME2020 rows with ground_truth_eligible == True minus training_eligible_ids |

Preregistered wording of the estimated-row rule, per epoch:

- EZ-B001-A: An AME2003 estimated row does not remove a target when the corresponding AME2012 row becomes ground-truth eligible.
- EZ-B001-B: An AME2012 estimated row does not remove a target when the corresponding AME2016 row becomes ground-truth eligible.
- EZ-B001-C: An AME2016 estimated row does not remove a target when the corresponding AME2020 row becomes ground-truth eligible.

## 5. Leakage controls

Controls, in the order they take effect:

- the preregistration declares the later-edition sha256 forbidden and the training
  sha256 as the only allowed source
- the target manifest handed to prediction carries identities only (Z, N, A and `nuclide_id`); any other field is a leakage error
- the KnowledgeFreeze pins the training identities, the normalized table hash, and
  the feature policy, and carries the forbidden hash with it
- prediction runs in a throwaway workspace that is checked by a filesystem preflight
  over truth file names and truth content hashes, before and after prediction
- the prediction ledger is finalized, and the experiment-level seal is committed,
  before any truth file is opened
- scoring refuses to run when a finalization marker changed after the seal

### 5.1 Atlas evidence summary

```text
source
  ->
normalized dataset
  ->
freeze
  ->
model fit
  ->
prediction set
  ->
finalization
  ->
truth
  ->
validation
```

Each stage above is a recorded Atlas PIR fact, not a prose claim. The chain per
epoch:

| Experiment | Prediction set fact ids | Truth dataset fact ids | Validation fact ids |
| --- | --- | --- | --- |
| EZ-B001-A | `fct_sha256_909b47080fa6f9fd`, `fct_sha256_79fb1df9e1488d19`, `fct_sha256_d3bd7c6b1c71f343` | `fct_sha256_7afb37e64bcb4c89` | `fct_sha256_ed85a960ad11a29b`, `fct_sha256_591b1cf473db4af5`, `fct_sha256_dfd8879e2a804c42` |
| EZ-B001-B | `fct_sha256_0a89be4c985cfc25`, `fct_sha256_dc9687805c36793f`, `fct_sha256_37e3f502d7fed56f` | `fct_sha256_da7042f82d42d8ea` | `fct_sha256_06b54556845672e1`, `fct_sha256_c28480f147afb9d6`, `fct_sha256_ac27410d75275da0` |
| EZ-B001-C | `fct_sha256_4f0d0f56be861ca9`, `fct_sha256_82a45d6bb8e28403`, `fct_sha256_437d30a4616afe33` | `fct_sha256_a50e0319df8ebd46` | `fct_sha256_3786ad5b4d368f59`, `fct_sha256_94a72e9738e63521`, `fct_sha256_bb770fd9a3e30f32` |

Code identity of the sealed series:

```text
atlas_repository     = https://github.com/Sovrance/Atlas
atlas_pir_ref        = 31d76d094f1206e64a6920da4775d0a684618357
protocol_code_digest = 5c20d931cdef024efe55fdf7bdab04d339e4bd787076385f0a1de36df1660e5f
```

| Experiment | elementzero_commit | atlas_pir_ref |
| --- | --- | --- |
| EZ-B001-A | `c9774a7f7d5cd578274610e916954c9c85560899` | `31d76d094f1206e64a6920da4775d0a684618357` |
| EZ-B001-B | `7a3fc69056f5e6405a37032a60c5886e7cb84c77` | `31d76d094f1206e64a6920da4775d0a684618357` |
| EZ-B001-C | `bf43d00ceebb9c779f78889a61217a9e928e6c71` | `31d76d094f1206e64a6920da4775d0a684618357` |

The commit SHA is lineage. The enforced gate is `protocol_code_digest`, a hash over
the parser, physics, model, metric, evidence, and leakage-control sources: adding a
report generator cannot invalidate a sealed experiment, and editing a model or a
metric does.

## 6. Model definitions

Model suite `EZ-B001-SUITE-v1`, frozen and ordered. Features: Z, N, A.

| Model | Implementation | Estimator | random_state |
| --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | `src/elementzero/models/gp_residual.py::SEMFLeastSquaresModel` | ordinary least squares on the five SEMF terms | 0 |
| EZ-GP-DIRECT-v1 | `src/elementzero/models/gp_residual.py::GPDirectModel` | sklearn.gaussian_process.GaussianProcessRegressor | 0 |
| EZ-SEMF-GP-RESIDUAL-v1 | `src/elementzero/models/gp_residual.py::SEMFGPResidualModel` | SEMF least squares plus GaussianProcessRegressor on the residual | 0 |

Hyperparameters exactly as preregistered. Numbers appear in the 12-digit canonical
form the committed preregistration stores (ADR-0002).

- EZ-SEMF-LS-v1:
  - estimator = ordinary least squares on the five SEMF terms
  - regularization = None
  - terms = ['volume', 'surface', 'coulomb', 'asymmetry', 'pairing']
- EZ-GP-DIRECT-v1:
  - estimator = sklearn.gaussian_process.GaussianProcessRegressor
  - kernel:
    - constant_value = 1.000000000000e+06
    - constant_value_bounds = fixed
    - expression = ConstantKernel(c) * RBF(length_scale) + WhiteKernel(noise_level)
    - kind = fixed_sum_kernel
    - length_scale = 8.000000000000e+00
    - length_scale_bounds = fixed
    - noise_level = 1.000000000000e+04
    - noise_level_bounds = fixed
    - normalize_y = True
    - optimizer = None
  - regression_target = mass excess of the training edition
- EZ-SEMF-GP-RESIDUAL-v1:
  - estimator = SEMF least squares plus GaussianProcessRegressor on the residual
  - kernel:
    - constant_value = 1.000000000000e+06
    - constant_value_bounds = fixed
    - expression = ConstantKernel(c) * RBF(length_scale) + WhiteKernel(noise_level)
    - kind = fixed_sum_kernel
    - length_scale = 8.000000000000e+00
    - length_scale_bounds = fixed
    - noise_level = 1.000000000000e+04
    - noise_level_bounds = fixed
    - normalize_y = True
    - optimizer = None
  - regression_target = observed minus SEMF residual of the training edition

Forbidden features in EZ-B001 v1: later truth values; magic-number-distance features; shell labels; future-edition derived features.

## 7. Uncertainty definitions

Every model reports a Gaussian predictive distribution, and sigma is taken from the
sealed prediction file. It is never reconstructed from truth or from rounded
intervals.

| Model | Uncertainty method | Predictive distribution |
| --- | --- | --- |
| EZ-SEMF-LS-v1 | global training residual standard deviation | gaussian |
| EZ-GP-DIRECT-v1 | GaussianProcessRegressor return_std | gaussian |
| EZ-SEMF-GP-RESIDUAL-v1 | GaussianProcessRegressor return_std | gaussian |

```text
predictive_distribution = gaussian
z_90                    = 1.64485
z_95                    = 1.95996
sigma_source            = sealed prediction file; sigma is never reconstructed from truth or from rounded intervals
```

## 8. Metrics

Metrics policy `ez-b001-metrics-policy-v1`. The `status` column is the whole
point of this table: a quantity is either preregistered or it is labelled
`POST_HOC`. Nothing is described as preregistered after the fact.

| Quantity | Definition | status |
| --- | --- | --- |
| MAE_keV | mean(abs(error_i)) | preregistered |
| MedAE_keV | median(abs(error_i)) | preregistered |
| RMSE_keV | sqrt(mean(error_i^2)) | preregistered |
| NLPD | mean(0.5*log(2*pi*sigma_i^2) + 0.5*((truth_i - prediction_i)/sigma_i)^2) | preregistered |
| coverage_90 | fraction of targets inside the reported 90 percent interval | preregistered |
| coverage_95 | fraction of targets inside the reported 95 percent interval | preregistered |
| calibration_error_90 | abs(coverage_90 - 0.90) | preregistered |
| calibration_error_95 | abs(coverage_95 - 0.95) | preregistered |
| metric_delta_first_to_last_epoch | last-epoch metric minus first-epoch metric, per model | POST_HOC |
| calibration_delta_first_to_last_epoch | last-epoch coverage or calibration error minus the first-epoch value | POST_HOC |
| mae_non_decreasing_with_distance | whether MAE is monotonic across the populated distance buckets | POST_HOC |
| mean_predictive_sigma_keV | mean of the sealed per-target sigma | POST_HOC |
| rmse_over_mean_predictive_sigma | RMSE divided by the mean sealed sigma | POST_HOC |
| coverage_gap_below_nominal | max(nominal coverage - observed coverage, 0) | POST_HOC |
| known_failure_screen | screening rules that select rows for section 15; thresholds calibration_tolerance = 0.05, sigma_understatement_ratio = 2 | POST_HOC |

Preregistered secondary diagnostics: error vs nearest_training_L1, metrics per L1 distance bucket, metrics per Z band.

No metric may be added after scoring and then described as preregistered. Additional analyses are allowed only when labelled POST_HOC.

Definitions in ASCII, exactly as preregistered:

```text
MAE_keV               = mean(abs(error_i))
MedAE_keV             = median(abs(error_i))
NLPD                  = mean(0.5*log(2*pi*sigma_i^2) + 0.5*((truth_i - prediction_i)/sigma_i)^2)
RMSE_keV              = sqrt(mean(error_i^2))
calibration_error_90  = abs(coverage_90 - 0.90)
calibration_error_95  = abs(coverage_95 - 0.95)
coverage_90           = fraction of targets inside the reported 90 percent interval
coverage_95           = fraction of targets inside the reported 95 percent interval
error_i               = prediction_i - truth_i
```

## 9. EZ-B001-A results

AME2003 is the only training source; AME2012 is the scored truth. 225 nuclides became ground-truth eligible in AME2012 and are scored for all three models.

```text
experiment_id              = EZ-B001-A
n_targets                  = 225
freeze_id                  = frz_d1ee8dd2efa4dc85
preregistration_hash       = 3bb01b68dd2d07f4abcc7a2c755332c3a9218b79c9daf900d0c8d9127f756442
sealed_predictions_sha256  = 4b88dc5cbd72c98bdc26a77aad669e653af58bc380d822bdd45c4701f79bdcda
target_identity_digest     = 724a4865a2ad67fa6ee0872c4b038f16eca8dac31b1e1628e16a538e3e54087d
training_source_sha256     = 33405560376f2adfb190beec44213523ec79149804df94e436d608019a4c70d1
truth_source_sha256        = 81e887c71c2c54c76caea36fd861b195a7f3eeb77d04b520e05fa97e0eedd7f3
seal_state                 = PREDICTIONS_SEALED_TRUTH_LOCKED
```

### 9.1 Primary metrics

| Experiment | Model | N | MAE | MedAE | RMSE | NLPD | Cov90 | Cov95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | 225 | 3393.29 | 2269.58 | 4934.89 | 10.077 | 0.822222 | 0.848889 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | 225 | 2012.21 | 1392.97 | 4868.76 | 16.329 | 1 | 1 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | 225 | 510.998 | 294.001 | 827.689 | 13.8519 | 1 | 1 |

### 9.2 Calibration

| Experiment | Model | CalErr90 | CalErr95 |
| --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | 0.0777778 | 0.101111 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | 0.1 | 0.05 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | 0.1 | 0.05 |

### 9.3 Error versus nearest-training L1 distance

Distance policy `ez-b001-l1-distance-buckets-v1`. An empty bucket is reported with N = 0 rather than dropped.

| Experiment | Model | DistanceBucket | N | MAE | RMSE | NLPD |
| --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=1 | 170 | 3246.09 | 4915.95 | 10.0694 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=2 | 46 | 3931.71 | 5162.37 | 10.1715 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=3-4 | 8 | 3544.02 | 4172.34 | 9.79154 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d>=5 | 1 | 2443.4 | 2443.4 | 9.3213 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=1 | 170 | 1388.11 | 1747.97 | 16.2823 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=2 | 46 | 2228.24 | 2712.19 | 16.4067 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=3-4 | 8 | 7752.72 | 14773 | 16.6917 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d>=5 | 1 | 52248 | 52248 | 17.7918 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 170 | 530.332 | 881.466 | 13.8052 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 46 | 476.592 | 666.912 | 13.9296 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 8 | 301.204 | 412.082 | 14.2146 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 1 | 485.233 | 485.233 | 15.3147 |

### 9.4 Metrics per Z band (preregistered secondary diagnostic)

| Experiment | Model | Region | N | MAE | RMSE | NLPD | MeanIsospinAsymmetry |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | light | 13 | 12340.7 | 14029.7 | 17.1678 | 0.346989 |
| EZ-B001-A | EZ-SEMF-LS-v1 | medium | 76 | 2157.48 | 2731.68 | 9.38263 | 0.152792 |
| EZ-B001-A | EZ-SEMF-LS-v1 | heavy | 75 | 2600.38 | 3637.02 | 9.61967 | 0.147597 |
| EZ-B001-A | EZ-SEMF-LS-v1 | very_heavy | 61 | 4001.04 | 4724.24 | 9.99339 | 0.201846 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | light | 13 | 2412.4 | 3267.25 | 16.3019 | 0.346989 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | medium | 76 | 1849.83 | 2235.21 | 16.3068 | 0.152792 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | heavy | 75 | 1206.11 | 1484.09 | 16.2907 | 0.147597 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | very_heavy | 61 | 3120.33 | 8730.86 | 16.4096 | 0.201846 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | light | 13 | 2220.74 | 2583.75 | 13.8248 | 0.346989 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | medium | 76 | 645.931 | 810.998 | 13.8297 | 0.152792 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | heavy | 75 | 337.91 | 424.029 | 13.8136 | 0.147597 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | very_heavy | 61 | 191.327 | 252.32 | 13.9325 | 0.201846 |

Figures: `figures/predicted_vs_truth_EZ-B001-A.svg`, `figures/abs_error_vs_distance_EZ-B001-A.svg`.

Validation fact ids: EZ-GP-DIRECT-v1 = `fct_sha256_ed85a960ad11a29b`, EZ-SEMF-GP-RESIDUAL-v1 = `fct_sha256_591b1cf473db4af5`, EZ-SEMF-LS-v1 = `fct_sha256_dfd8879e2a804c42`.

## 10. EZ-B001-B results

AME2012 is the only training source; AME2016 is the scored truth. 63 nuclides became ground-truth eligible in AME2016 and are scored for all three models.

```text
experiment_id              = EZ-B001-B
n_targets                  = 63
freeze_id                  = frz_0883fe445515efe7
preregistration_hash       = 007c1a5267d905c14bf9dca3333778048dc6fec09a17aefe3c7f298f58c5219a
sealed_predictions_sha256  = 3f3a922c0f0c3171b67649cb31485ec2bc5dc5eef6df4913032390c025676189
target_identity_digest     = d8c1aa9314c0256ecdbece276f7a154ea4f73c5dd9245288768e3afd12a3a9ec
training_source_sha256     = 81e887c71c2c54c76caea36fd861b195a7f3eeb77d04b520e05fa97e0eedd7f3
truth_source_sha256        = 2167f57a2a98331e4649b2dd2b658a9006ed4fba1975729ebfe52a42b4b9218a
seal_state                 = PREDICTIONS_SEALED_TRUTH_LOCKED
```

### 10.1 Primary metrics

| Experiment | Model | N | MAE | MedAE | RMSE | NLPD | Cov90 | Cov95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-B | EZ-SEMF-LS-v1 | 63 | 3165.85 | 1650.19 | 4874.56 | 10.0168 | 0.809524 | 0.857143 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | 63 | 1767.22 | 1183.77 | 2294.86 | 16.3089 | 1 | 1 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | 63 | 543.412 | 357.596 | 796.271 | 13.8456 | 1 | 1 |

### 10.2 Calibration

| Experiment | Model | CalErr90 | CalErr95 |
| --- | --- | --- | --- |
| EZ-B001-B | EZ-SEMF-LS-v1 | 0.0904762 | 0.0928571 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | 0.1 | 0.05 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | 0.1 | 0.05 |

### 10.3 Error versus nearest-training L1 distance

Distance policy `ez-b001-l1-distance-buckets-v1`. An empty bucket is reported with N = 0 rather than dropped.

| Experiment | Model | DistanceBucket | N | MAE | RMSE | NLPD |
| --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=1 | 57 | 3375.59 | 5088.55 | 10.0975 |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=2 | 6 | 1173.23 | 1872.94 | 9.24974 |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-LS-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=1 | 57 | 1648.65 | 2083.46 | 16.3004 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=2 | 6 | 2893.68 | 3749.58 | 16.3899 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 57 | 525.357 | 759.232 | 13.837 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 6 | 714.927 | 1086.92 | 13.9265 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 0 | n/a | n/a | n/a |

### 10.4 Metrics per Z band (preregistered secondary diagnostic)

| Experiment | Model | Region | N | MAE | RMSE | NLPD | MeanIsospinAsymmetry |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-B | EZ-SEMF-LS-v1 | light | 14 | 6700.71 | 8339.88 | 11.751 | 0.182213 |
| EZ-B001-B | EZ-SEMF-LS-v1 | medium | 24 | 2443.54 | 3509.17 | 9.58326 | 0.208768 |
| EZ-B001-B | EZ-SEMF-LS-v1 | heavy | 7 | 1837.57 | 2880.3 | 9.43108 | 0.210016 |
| EZ-B001-B | EZ-SEMF-LS-v1 | very_heavy | 18 | 1896.13 | 3069.57 | 9.47373 | 0.164391 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | light | 14 | 3291.19 | 3820.81 | 16.3339 | 0.182213 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | medium | 24 | 1365.72 | 1672.54 | 16.3061 | 0.208768 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | heavy | 7 | 674.615 | 857.575 | 16.2685 | 0.210016 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | very_heavy | 18 | 1542.15 | 1749.88 | 16.309 | 0.164391 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | light | 14 | 950.641 | 1132.6 | 13.8705 | 0.182213 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | medium | 24 | 591.194 | 890.414 | 13.8427 | 0.208768 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | heavy | 7 | 225.24 | 300.916 | 13.8051 | 0.210016 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | very_heavy | 18 | 286.702 | 359.321 | 13.8456 | 0.164391 |

Figures: `figures/predicted_vs_truth_EZ-B001-B.svg`, `figures/abs_error_vs_distance_EZ-B001-B.svg`.

Validation fact ids: EZ-GP-DIRECT-v1 = `fct_sha256_06b54556845672e1`, EZ-SEMF-GP-RESIDUAL-v1 = `fct_sha256_c28480f147afb9d6`, EZ-SEMF-LS-v1 = `fct_sha256_ac27410d75275da0`.

## 11. EZ-B001-C results

AME2016 is the only training source; AME2020 is the scored truth. 74 nuclides became ground-truth eligible in AME2020 and are scored for all three models.

```text
experiment_id              = EZ-B001-C
n_targets                  = 74
freeze_id                  = frz_3d3a4532f61e0906
preregistration_hash       = e563ce856380f4abc51558f91d74d2135d69d0a3379b8c426f4f6e139f4d6c29
sealed_predictions_sha256  = b967eb4f06e306770e4e24902dc2273cb94f449944b09988f2fa596253942c35
target_identity_digest     = 9d3e7d5f412d477152e37c15d247dd6f6c35c108c1f1e77e700f87ad4d02d576
training_source_sha256     = 2167f57a2a98331e4649b2dd2b658a9006ed4fba1975729ebfe52a42b4b9218a
truth_source_sha256        = e8599c6d7f724fac91934e59f1b9de8fb8f63e820f4b39456b790665ed2a3307
seal_state                 = PREDICTIONS_SEALED_TRUTH_LOCKED
```

### 11.1 Primary metrics

| Experiment | Model | N | MAE | MedAE | RMSE | NLPD | Cov90 | Cov95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-C | EZ-SEMF-LS-v1 | 74 | 2789.26 | 1561.58 | 5055.12 | 10.0753 | 0.878378 | 0.905405 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | 74 | 1862.71 | 1256.65 | 2746.72 | 16.3463 | 1 | 1 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | 74 | 388.765 | 229.855 | 575.287 | 13.8894 | 1 | 1 |

### 11.2 Calibration

| Experiment | Model | CalErr90 | CalErr95 |
| --- | --- | --- | --- |
| EZ-B001-C | EZ-SEMF-LS-v1 | 0.0216216 | 0.0445946 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | 0.1 | 0.05 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | 0.1 | 0.05 |

### 11.3 Error versus nearest-training L1 distance

Distance policy `ez-b001-l1-distance-buckets-v1`. An empty bucket is reported with N = 0 rather than dropped.

| Experiment | Model | DistanceBucket | N | MAE | RMSE | NLPD |
| --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=1 | 62 | 3177.88 | 5492.1 | 10.2462 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=2 | 10 | 826.636 | 1423.95 | 9.20241 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=3-4 | 2 | 555.315 | 558.653 | 9.13876 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=1 | 62 | 1966.7 | 2891.27 | 16.3196 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=2 | 10 | 1448.88 | 1973.64 | 16.4568 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=3-4 | 2 | 708.032 | 724.588 | 16.6184 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 62 | 416.426 | 609.779 | 13.8628 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 10 | 258.883 | 368.504 | 14 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 2 | 180.711 | 199.054 | 14.1616 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 0 | n/a | n/a | n/a |

### 11.4 Metrics per Z band (preregistered secondary diagnostic)

| Experiment | Model | Region | N | MAE | RMSE | NLPD | MeanIsospinAsymmetry |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-C | EZ-SEMF-LS-v1 | light | 4 | 15757.5 | 17972.7 | 21.1113 | 0.108983 |
| EZ-B001-C | EZ-SEMF-LS-v1 | medium | 27 | 3151.46 | 3845.34 | 9.67578 | 0.143584 |
| EZ-B001-C | EZ-SEMF-LS-v1 | heavy | 23 | 923.478 | 2250.65 | 9.31511 | 0.207953 |
| EZ-B001-C | EZ-SEMF-LS-v1 | very_heavy | 20 | 1852.31 | 2039.54 | 9.28151 | 0.179952 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | light | 4 | 7192.84 | 8609.43 | 16.3359 | 0.108983 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | medium | 27 | 2000.65 | 2359.91 | 16.334 | 0.143584 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | heavy | 23 | 723.985 | 829.031 | 16.3895 | 0.207953 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | very_heavy | 20 | 1919.98 | 2186.6 | 16.3151 | 0.179952 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | light | 4 | 1100.51 | 1157.06 | 13.8791 | 0.108983 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | medium | 27 | 595.085 | 780.032 | 13.8772 | 0.143584 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | heavy | 23 | 221.904 | 290.642 | 13.9327 | 0.207953 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | very_heavy | 20 | 159.776 | 195.522 | 13.8583 | 0.179952 |

Figures: `figures/predicted_vs_truth_EZ-B001-C.svg`, `figures/abs_error_vs_distance_EZ-B001-C.svg`.

Validation fact ids: EZ-GP-DIRECT-v1 = `fct_sha256_3786ad5b4d368f59`, EZ-SEMF-GP-RESIDUAL-v1 = `fct_sha256_94a72e9738e63521`, EZ-SEMF-LS-v1 = `fct_sha256_bb770fd9a3e30f32`.

## 12. Longitudinal comparison

All three epochs and all three models, in one table. No epoch is dropped for
behaving badly and no metric is hidden because another one looks better.

| Experiment | Model | N | MAE | MedAE | RMSE | NLPD | Cov90 | Cov95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | 225 | 3393.29 | 2269.58 | 4934.89 | 10.077 | 0.822222 | 0.848889 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | 225 | 2012.21 | 1392.97 | 4868.76 | 16.329 | 1 | 1 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | 225 | 510.998 | 294.001 | 827.689 | 13.8519 | 1 | 1 |
| EZ-B001-B | EZ-SEMF-LS-v1 | 63 | 3165.85 | 1650.19 | 4874.56 | 10.0168 | 0.809524 | 0.857143 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | 63 | 1767.22 | 1183.77 | 2294.86 | 16.3089 | 1 | 1 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | 63 | 543.412 | 357.596 | 796.271 | 13.8456 | 1 | 1 |
| EZ-B001-C | EZ-SEMF-LS-v1 | 74 | 2789.26 | 1561.58 | 5055.12 | 10.0753 | 0.878378 | 0.905405 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | 74 | 1862.71 | 1256.65 | 2746.72 | 16.3463 | 1 | 1 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | 74 | 388.765 | 229.855 | 575.287 | 13.8894 | 1 | 1 |

Figures: `figures/mae_kev_by_epoch.svg`, `figures/rmse_kev_by_epoch.svg`,
`figures/nlpd_by_epoch.svg`.

### 12.1 POST_HOC drift across epochs

Labelled POST_HOC: cross-epoch deltas were not preregistered as metrics. A
later epoch is not assumed to be better, and a worsening delta is reported as it is.
The three epochs also score different target sets of different sizes, so a delta is
a description of the series, not a controlled comparison.

| Model | Quantity | First epoch | Last epoch | Delta | Direction | status |
| --- | --- | --- | --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | MAE_keV (metric_delta_first_to_last_epoch) | 3393.29 | 2789.26 | -604.024 | decreasing | POST_HOC |
| EZ-SEMF-LS-v1 | MedAE_keV (metric_delta_first_to_last_epoch) | 2269.58 | 1561.58 | -708.005 | decreasing | POST_HOC |
| EZ-SEMF-LS-v1 | RMSE_keV (metric_delta_first_to_last_epoch) | 4934.89 | 5055.12 | 120.228 | increasing | POST_HOC |
| EZ-SEMF-LS-v1 | NLPD (metric_delta_first_to_last_epoch) | 10.077 | 10.0753 | -0.00178076 | decreasing | POST_HOC |
| EZ-SEMF-LS-v1 | coverage_90 (calibration_delta_first_to_last_epoch) | 0.822222 | 0.878378 | 0.0561562 | increasing | POST_HOC |
| EZ-SEMF-LS-v1 | coverage_95 (calibration_delta_first_to_last_epoch) | 0.848889 | 0.905405 | 0.0565165 | increasing | POST_HOC |
| EZ-SEMF-LS-v1 | cal_error_90 (calibration_delta_first_to_last_epoch) | 0.0777778 | 0.0216216 | -0.0561562 | decreasing | POST_HOC |
| EZ-SEMF-LS-v1 | cal_error_95 (calibration_delta_first_to_last_epoch) | 0.101111 | 0.0445946 | -0.0565165 | decreasing | POST_HOC |
| EZ-SEMF-LS-v1 | n_targets (metric_delta_first_to_last_epoch) | 225 | 74 | -151 | decreasing | POST_HOC |
| EZ-GP-DIRECT-v1 | MAE_keV (metric_delta_first_to_last_epoch) | 2012.21 | 1862.71 | -149.502 | decreasing | POST_HOC |
| EZ-GP-DIRECT-v1 | MedAE_keV (metric_delta_first_to_last_epoch) | 1392.97 | 1256.65 | -136.317 | decreasing | POST_HOC |
| EZ-GP-DIRECT-v1 | RMSE_keV (metric_delta_first_to_last_epoch) | 4868.76 | 2746.72 | -2122.04 | decreasing | POST_HOC |
| EZ-GP-DIRECT-v1 | NLPD (metric_delta_first_to_last_epoch) | 16.329 | 16.3463 | 0.0172097 | increasing | POST_HOC |
| EZ-GP-DIRECT-v1 | coverage_90 (calibration_delta_first_to_last_epoch) | 1 | 1 | 0 | flat | POST_HOC |
| EZ-GP-DIRECT-v1 | coverage_95 (calibration_delta_first_to_last_epoch) | 1 | 1 | 0 | flat | POST_HOC |
| EZ-GP-DIRECT-v1 | cal_error_90 (calibration_delta_first_to_last_epoch) | 0.1 | 0.1 | 0 | flat | POST_HOC |
| EZ-GP-DIRECT-v1 | cal_error_95 (calibration_delta_first_to_last_epoch) | 0.05 | 0.05 | 0 | flat | POST_HOC |
| EZ-GP-DIRECT-v1 | n_targets (metric_delta_first_to_last_epoch) | 225 | 74 | -151 | decreasing | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | MAE_keV (metric_delta_first_to_last_epoch) | 510.998 | 388.765 | -122.233 | decreasing | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | MedAE_keV (metric_delta_first_to_last_epoch) | 294.001 | 229.855 | -64.1461 | decreasing | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | RMSE_keV (metric_delta_first_to_last_epoch) | 827.689 | 575.287 | -252.401 | decreasing | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | NLPD (metric_delta_first_to_last_epoch) | 13.8519 | 13.8894 | 0.037542 | increasing | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | coverage_90 (calibration_delta_first_to_last_epoch) | 1 | 1 | 0 | flat | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | coverage_95 (calibration_delta_first_to_last_epoch) | 1 | 1 | 0 | flat | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | cal_error_90 (calibration_delta_first_to_last_epoch) | 0.1 | 0.1 | 0 | flat | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | cal_error_95 (calibration_delta_first_to_last_epoch) | 0.05 | 0.05 | 0 | flat | POST_HOC |
| EZ-SEMF-GP-RESIDUAL-v1 | n_targets (metric_delta_first_to_last_epoch) | 225 | 74 | -151 | decreasing | POST_HOC |

## 13. Error vs extrapolation distance

Distance policy `ez-b001-l1-distance-buckets-v1`; buckets d=1, d=2, d=3-4, d>=5 over `nearest_training_L1`, the L1 lattice
distance from a scored target to the closest training nucleus.

| Experiment | Model | DistanceBucket | N | MAE | RMSE | NLPD |
| --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=1 | 170 | 3246.09 | 4915.95 | 10.0694 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=2 | 46 | 3931.71 | 5162.37 | 10.1715 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=3-4 | 8 | 3544.02 | 4172.34 | 9.79154 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d>=5 | 1 | 2443.4 | 2443.4 | 9.3213 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=1 | 170 | 1388.11 | 1747.97 | 16.2823 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=2 | 46 | 2228.24 | 2712.19 | 16.4067 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=3-4 | 8 | 7752.72 | 14773 | 16.6917 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d>=5 | 1 | 52248 | 52248 | 17.7918 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 170 | 530.332 | 881.466 | 13.8052 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 46 | 476.592 | 666.912 | 13.9296 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 8 | 301.204 | 412.082 | 14.2146 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 1 | 485.233 | 485.233 | 15.3147 |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=1 | 57 | 3375.59 | 5088.55 | 10.0975 |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=2 | 6 | 1173.23 | 1872.94 | 9.24974 |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-LS-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=1 | 57 | 1648.65 | 2083.46 | 16.3004 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=2 | 6 | 2893.68 | 3749.58 | 16.3899 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 57 | 525.357 | 759.232 | 13.837 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 6 | 714.927 | 1086.92 | 13.9265 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=1 | 62 | 3177.88 | 5492.1 | 10.2462 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=2 | 10 | 826.636 | 1423.95 | 9.20241 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=3-4 | 2 | 555.315 | 558.653 | 9.13876 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=1 | 62 | 1966.7 | 2891.27 | 16.3196 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=2 | 10 | 1448.88 | 1973.64 | 16.4568 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=3-4 | 2 | 708.032 | 724.588 | 16.6184 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 62 | 416.426 | 609.779 | 13.8628 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 10 | 258.883 | 368.504 | 14 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 2 | 180.711 | 199.054 | 14.1616 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 0 | n/a | n/a | n/a |

### 13.1 POST_HOC monotonicity screen

Labelled POST_HOC: the preregistration asks for metrics per bucket, not for a
monotonicity claim. `mae_non_decreasing_with_distance` is `null` when fewer than two
buckets are populated.

| Experiment | Model | Populated buckets | mae_non_decreasing_with_distance | status |
| --- | --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=1, d=2, d=3-4, d>=5 | False | POST_HOC |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=1, d=2 | False | POST_HOC |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=1, d=2, d=3-4 | False | POST_HOC |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=1, d=2, d=3-4, d>=5 | True | POST_HOC |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=1, d=2 | True | POST_HOC |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=1, d=2, d=3-4 | False | POST_HOC |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=1, d=2, d=3-4, d>=5 | False | POST_HOC |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=1, d=2 | True | POST_HOC |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=1, d=2, d=3-4 | False | POST_HOC |

Figures: `figures/abs_error_vs_distance_EZ-B001-A.svg` and the equivalent
figure for each epoch.

## 14. Calibration

Coverage is the fraction of scored targets inside the reported interval;
`CalErr` is the absolute distance from the nominal level. Both nominal levels are
reported for every model in every epoch.

| Experiment | Model | CalErr90 | CalErr95 |
| --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | 0.0777778 | 0.101111 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | 0.1 | 0.05 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | 0.1 | 0.05 |
| EZ-B001-B | EZ-SEMF-LS-v1 | 0.0904762 | 0.0928571 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | 0.1 | 0.05 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | 0.1 | 0.05 |
| EZ-B001-C | EZ-SEMF-LS-v1 | 0.0216216 | 0.0445946 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | 0.1 | 0.05 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | 0.1 | 0.05 |

Figures: `figures/coverage_90_by_epoch.svg`, `figures/coverage_95_by_epoch.svg` (nominal levels drawn as reference lines).

### 14.1 POST_HOC interval width against realised error

Labelled POST_HOC. NLPD already penalises a badly sized interval, but it mixes
width and error into one number. The ratio below separates them: above one means the
reported sigma is smaller than the realised error, and well below one means the
interval is far wider than the error it has to cover, which is how a model reaches
coverage 1 and a poor NLPD at the same time.

| Experiment | Model | N | mean_predictive_sigma_keV | rmse_over_mean_predictive_sigma | status |
| --- | --- | --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | 225 | 3487.45 | 1.41504 | POST_HOC |
| EZ-B001-A | EZ-GP-DIRECT-v1 | 225 | 5.01708e+06 | 0.000970435 | POST_HOC |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | 225 | 421350 | 0.00196437 | POST_HOC |
| EZ-B001-B | EZ-SEMF-LS-v1 | 63 | 3633.51 | 1.34156 | POST_HOC |
| EZ-B001-B | EZ-GP-DIRECT-v1 | 63 | 4.8369e+06 | 0.000474449 | POST_HOC |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | 63 | 411840 | 0.00193345 | POST_HOC |
| EZ-B001-C | EZ-SEMF-LS-v1 | 74 | 3671.09 | 1.37701 | POST_HOC |
| EZ-B001-C | EZ-GP-DIRECT-v1 | 74 | 5.02956e+06 | 0.000546115 | POST_HOC |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | 74 | 431074 | 0.00133454 | POST_HOC |

## 15. Model failures

Failures stay in the record. Every row below is also present, unchanged, in the
tables above and in `aggregate_metrics.json`; this section only points at them.

The screen itself is POST_HOC (`known_failure_screen`), with a calibration
tolerance of 0.05 and a sigma ratio bound of
2 in both directions. Changing a threshold changes
which rows are listed here; it cannot change a metric.

| Kind | Experiment | Model | Detail | Severity | Retained | status |
| --- | --- | --- | --- | --- | --- | --- |
| undercoverage_90 | EZ-B001-A | EZ-SEMF-LS-v1 | coverage_90 = 0.822222 is below the nominal 0.9; cal_error_90 = 0.0777778 | outside_calibration_tolerance | True | POST_HOC |
| undercoverage_95 | EZ-B001-A | EZ-SEMF-LS-v1 | coverage_95 = 0.848889 is below the nominal 0.95; cal_error_95 = 0.101111 | outside_calibration_tolerance | True | POST_HOC |
| overcoverage_90 | EZ-B001-A | EZ-GP-DIRECT-v1 | coverage_90 = 1 exceeds the nominal 0.9 by more than 0.05; the reported interval is too wide, and cal_error_90 = 0.1 | outside_calibration_tolerance | True | POST_HOC |
| overcoverage_95 | EZ-B001-A | EZ-GP-DIRECT-v1 | coverage_95 = 1 exceeds the nominal 0.95 by more than 0.05; the reported interval is too wide, and cal_error_95 = 0.05 | within_calibration_tolerance | True | POST_HOC |
| overcoverage_90 | EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | coverage_90 = 1 exceeds the nominal 0.9 by more than 0.05; the reported interval is too wide, and cal_error_90 = 0.1 | outside_calibration_tolerance | True | POST_HOC |
| overcoverage_95 | EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | coverage_95 = 1 exceeds the nominal 0.95 by more than 0.05; the reported interval is too wide, and cal_error_95 = 0.05 | within_calibration_tolerance | True | POST_HOC |
| undercoverage_90 | EZ-B001-B | EZ-SEMF-LS-v1 | coverage_90 = 0.809524 is below the nominal 0.9; cal_error_90 = 0.0904762 | outside_calibration_tolerance | True | POST_HOC |
| undercoverage_95 | EZ-B001-B | EZ-SEMF-LS-v1 | coverage_95 = 0.857143 is below the nominal 0.95; cal_error_95 = 0.0928571 | outside_calibration_tolerance | True | POST_HOC |
| overcoverage_90 | EZ-B001-B | EZ-GP-DIRECT-v1 | coverage_90 = 1 exceeds the nominal 0.9 by more than 0.05; the reported interval is too wide, and cal_error_90 = 0.1 | outside_calibration_tolerance | True | POST_HOC |
| overcoverage_95 | EZ-B001-B | EZ-GP-DIRECT-v1 | coverage_95 = 1 exceeds the nominal 0.95 by more than 0.05; the reported interval is too wide, and cal_error_95 = 0.05 | within_calibration_tolerance | True | POST_HOC |
| overcoverage_90 | EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | coverage_90 = 1 exceeds the nominal 0.9 by more than 0.05; the reported interval is too wide, and cal_error_90 = 0.1 | outside_calibration_tolerance | True | POST_HOC |
| overcoverage_95 | EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | coverage_95 = 1 exceeds the nominal 0.95 by more than 0.05; the reported interval is too wide, and cal_error_95 = 0.05 | within_calibration_tolerance | True | POST_HOC |
| undercoverage_90 | EZ-B001-C | EZ-SEMF-LS-v1 | coverage_90 = 0.878378 is below the nominal 0.9; cal_error_90 = 0.0216216 | within_calibration_tolerance | True | POST_HOC |
| undercoverage_95 | EZ-B001-C | EZ-SEMF-LS-v1 | coverage_95 = 0.905405 is below the nominal 0.95; cal_error_95 = 0.0445946 | within_calibration_tolerance | True | POST_HOC |
| overcoverage_90 | EZ-B001-C | EZ-GP-DIRECT-v1 | coverage_90 = 1 exceeds the nominal 0.9 by more than 0.05; the reported interval is too wide, and cal_error_90 = 0.1 | outside_calibration_tolerance | True | POST_HOC |
| overcoverage_95 | EZ-B001-C | EZ-GP-DIRECT-v1 | coverage_95 = 1 exceeds the nominal 0.95 by more than 0.05; the reported interval is too wide, and cal_error_95 = 0.05 | within_calibration_tolerance | True | POST_HOC |
| overcoverage_90 | EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | coverage_90 = 1 exceeds the nominal 0.9 by more than 0.05; the reported interval is too wide, and cal_error_90 = 0.1 | outside_calibration_tolerance | True | POST_HOC |
| overcoverage_95 | EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | coverage_95 = 1 exceeds the nominal 0.95 by more than 0.05; the reported interval is too wide, and cal_error_95 = 0.05 | within_calibration_tolerance | True | POST_HOC |
| predictive_sigma_overstates_error | EZ-B001-A | EZ-GP-DIRECT-v1 | RMSE is 0.000970435 times the mean reported sigma (5.01708e+06 keV) | outside_calibration_tolerance | True | POST_HOC |
| predictive_sigma_overstates_error | EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | RMSE is 0.00196437 times the mean reported sigma (421350 keV) | outside_calibration_tolerance | True | POST_HOC |
| predictive_sigma_overstates_error | EZ-B001-B | EZ-GP-DIRECT-v1 | RMSE is 0.000474449 times the mean reported sigma (4.8369e+06 keV) | outside_calibration_tolerance | True | POST_HOC |
| predictive_sigma_overstates_error | EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | RMSE is 0.00193345 times the mean reported sigma (411840 keV) | outside_calibration_tolerance | True | POST_HOC |
| predictive_sigma_overstates_error | EZ-B001-C | EZ-GP-DIRECT-v1 | RMSE is 0.000546115 times the mean reported sigma (5.02956e+06 keV) | outside_calibration_tolerance | True | POST_HOC |
| predictive_sigma_overstates_error | EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | RMSE is 0.00133454 times the mean reported sigma (431074 keV) | outside_calibration_tolerance | True | POST_HOC |
| error_not_non_decreasing_with_distance | EZ-B001-A | EZ-SEMF-LS-v1 | MAE over the populated buckets (d=1 = 3246.09, d=2 = 3931.71, d=3-4 = 3544.02, d>=5 = 2443.4) is not monotonic in distance | diagnostic | True | POST_HOC |
| error_not_non_decreasing_with_distance | EZ-B001-B | EZ-SEMF-LS-v1 | MAE over the populated buckets (d=1 = 3375.59, d=2 = 1173.23) is not monotonic in distance | diagnostic | True | POST_HOC |
| error_not_non_decreasing_with_distance | EZ-B001-C | EZ-SEMF-LS-v1 | MAE over the populated buckets (d=1 = 3177.88, d=2 = 826.636, d=3-4 = 555.315) is not monotonic in distance | diagnostic | True | POST_HOC |
| metric_worsens_across_epochs | EZ-B001-A -> EZ-B001-C | EZ-SEMF-LS-v1 | RMSE_keV moved from 4934.89 to 5055.12 (delta 120.228) | diagnostic | True | POST_HOC |
| error_not_non_decreasing_with_distance | EZ-B001-C | EZ-GP-DIRECT-v1 | MAE over the populated buckets (d=1 = 1966.7, d=2 = 1448.88, d=3-4 = 708.032) is not monotonic in distance | diagnostic | True | POST_HOC |
| metric_worsens_across_epochs | EZ-B001-A -> EZ-B001-C | EZ-GP-DIRECT-v1 | NLPD moved from 16.329 to 16.3463 (delta 0.0172097) | diagnostic | True | POST_HOC |
| error_not_non_decreasing_with_distance | EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | MAE over the populated buckets (d=1 = 530.332, d=2 = 476.592, d=3-4 = 301.204, d>=5 = 485.233) is not monotonic in distance | diagnostic | True | POST_HOC |
| error_not_non_decreasing_with_distance | EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | MAE over the populated buckets (d=1 = 416.426, d=2 = 258.883, d=3-4 = 180.711) is not monotonic in distance | diagnostic | True | POST_HOC |
| metric_worsens_across_epochs | EZ-B001-A -> EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | NLPD moved from 13.8519 to 13.8894 (delta 0.037542) | diagnostic | True | POST_HOC |

## 16. Limitations

- The three epochs score different target sets of different sizes. A metric that
  moves between epochs may reflect which nuclides became eligible, not model skill.
- Targets are the nuclides a later edition added, which are systematically further
  from stability and closer to the measurement frontier than an average nucleus.
  Nothing here generalises to interpolation inside well-measured regions.
- Later-edition truth values carry their own experimental uncertainty; the metrics
  above treat them as exact.
- Distance buckets far from the training corpus contain very few targets, so their
  metrics are noisy. They are reported with their N and not smoothed.
- The uncertainty families differ by construction: one model reports a single global
  residual standard deviation, two report a GP posterior standard deviation with
  fixed kernel hyperparameters. Calibration is therefore not compared like for like.
- No significance test was preregistered, so no difference between models or epochs
  in this report is a statistical claim.
- The AME editions are not independent samples: each edition re-evaluates earlier
  measurements, so consecutive epochs share evaluation methodology and correlated
  inputs.

## 17. Deviations from preregistration

| Id | Status | Preregistered | Actual | Changes numbers | Reference |
| --- | --- | --- | --- | --- | --- |
| artifact-layout | disclosed | WO-06 lists runs/<experiment>/<model> and results/<experiment>/<model> | experiments/<experiment>/runs/<model> keeps seal, scoring, and Atlas bundle together | False | `experiments/<experiment>/RUN_MANIFEST.json -> artifact_layout.layout_note` |
| atlas-packaging-overlay | approved exception | Atlas PIR is consumed as a commit-pinned upstream dependency | the pinned Atlas commit is installed through the ensure overlay in tools/ensure_atlas_pir.py; the pin itself is unchanged | False | `docs/migrations/WO-04-atlas-packaging-exception.md` |
| post-hoc-diagnostics | POST_HOC additions, labelled | primary metrics MAE_keV, MedAE_keV, RMSE_keV, NLPD, coverage_90, coverage_95, calibration_error_90, calibration_error_95; secondary diagnostics error vs nearest_training_L1, metrics per L1 distance bucket, metrics per Z band | this report adds the POST_HOC fields metric_delta_first_to_last_epoch, calibration_delta_first_to_last_epoch, mae_non_decreasing_with_distance, mean_predictive_sigma_keV, rmse_over_mean_predictive_sigma, coverage_gap_below_nominal, known_failure_screen | False | `reports/historical/v1/aggregate_metrics.json -> post_hoc` |
| raw-tables-not-committed | disclosed | raw AME tables stay gitignored; hashes, URLs, and parse reports are committed | unchanged; a rebuild without data/raw verifies hashes and skips the truth replay | False | `experiments/<experiment>/source_manifest.json -> raw_files_note` |

No metric was added to the preregistered set after scoring, no model was refit, and
no hyperparameter was changed. The protocol code digest of every epoch still matches
its preregistration, which the committed-experiment test suite checks on every run.

## 18. Reproducibility instructions

```bash
python scripts/reproduce_historical_report.py
```

The script, in order: verifies the committed artifact hashes of every epoch,
validates every preregistration and the protocol code digest, replays scoring from
the sealed predictions against the raw truth table, rebuilds the longitudinal
aggregate, rebuilds this report with its tables and figures, and compares the result
against `SHA256SUMS.txt`.

It never refits a model. Refitting requires the explicit flag:

```bash
python scripts/reproduce_historical_report.py --refit
```

which fits into a scratch directory, never into `experiments/`, and compares the
recomputed metric hashes with the committed ones.

Raw AME tables are not committed. Download them to the declared paths first:

```text
https://amdc.impcas.ac.cn/masstables/Ame2003/mass.mas03
  -> data/raw/amdc/AME2003/mass.mas03  sha256 33405560376f2adfb190beec44213523ec79149804df94e436d608019a4c70d1
https://amdc.impcas.ac.cn/masstables/Ame2012/mass.mas12
  -> data/raw/amdc/AME2012/mass.mas12  sha256 81e887c71c2c54c76caea36fd861b195a7f3eeb77d04b520e05fa97e0eedd7f3
https://amdc.impcas.ac.cn/masstables/Ame2016/mass16.txt
  -> data/raw/amdc/AME2016/mass16.txt  sha256 2167f57a2a98331e4649b2dd2b658a9006ed4fba1975729ebfe52a42b4b9218a
https://amdc.impcas.ac.cn/masstables/Ame2020/mass_1.mas20.txt
  -> data/raw/amdc/AME2020/mass_1.mas20.txt  sha256 e8599c6d7f724fac91934e59f1b9de8fb8f63e820f4b39456b790665ed2a3307
```

Without those files the hash verification, the aggregate rebuild, and the report
rebuild still run; the truth replay reports itself as skipped instead of passing
silently.

## 19. Artifact hashes

`SHA256SUMS.txt` in this directory is a `sha256sum`-compatible manifest of every
generated file, and `artifact_manifest.json` lists every committed input the
generator read, with its hash and its role.

```bash
cd reports/historical/v1 && sha256sum -c SHA256SUMS.txt
```

Load-bearing hashes of the series:

| Experiment | Preregistration | Sealed predictions | Model comparison |
| --- | --- | --- | --- |
| EZ-B001-A | `3bb01b68dd2d07f4abcc7a2c755332c3a9218b79c9daf900d0c8d9127f756442` | `4b88dc5cbd72c98bdc26a77aad669e653af58bc380d822bdd45c4701f79bdcda` | `47a9bb62ad2ae0812d39ede8b1dbfb77b58bcb8c30f84c098203bd4c40514f39` |
| EZ-B001-B | `007c1a5267d905c14bf9dca3333778048dc6fec09a17aefe3c7f298f58c5219a` | `3f3a922c0f0c3171b67649cb31485ec2bc5dc5eef6df4913032390c025676189` | `4cac602f6778639dc9f26eeb545848655fdd366ccd249bef1067be35ef90b319` |
| EZ-B001-C | `e563ce856380f4abc51558f91d74d2135d69d0a3379b8c426f4f6e139f4d6c29` | `b967eb4f06e306770e4e24902dc2273cb94f449944b09988f2fa596253942c35` | `4be265d5d899923964bef82721a928f6dcdf7c491aeb2d454dce55d2034b605a` |

Published aggregate `results/EZ-B001/aggregate_v1.json` sha256 `dee599c663f4bafe0762e7e544523991f8ed0a1610da231b0cc904df0425d1ff`.

```text
atlas_pir_ref        = 31d76d094f1206e64a6920da4775d0a684618357
protocol_code_digest = 5c20d931cdef024efe55fdf7bdab04d339e4bd787076385f0a1de36df1660e5f
```

## 20. Next benchmark decision

Recommended release tag after audit: `elementzero-historical-benchmark-v1`, pointing at a commit that
contains the preregistrations, the sealed hashes, the score outputs, this report,
and the reproduction script.

The next gate is WO-09, EZ-B002 Geographic Nuclear-Chart Holdout: withhold a
contiguous region of the known chart instead of a historical edition, and ask
whether the same three models can reconstruct it. EZ-B002 does not start until
this report exists, the reproduction replay passes, unresolved data or parser issues
are documented, and any protocol change is versioned rather than edited in place.

The machine-readable form of this decision, including the failure list, is
`benchmark_status.json`. It has no single PASS field: engineering status covers
protocol integrity only, and the scientific verdict stays null.
