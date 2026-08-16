# WO-11 — Evidence Adjudication Report

Work order: WO-11
Input release: elementzero-validation-ladder-v0.3
Baseline commit: 9baee722c49296e681cf53da63f31a36bb6ab2f6
Verdict: **FRONTIER_MODEL_RERUN_JUSTIFIED**

All numbers in this report are derived from the committed, sealed v1
artifacts and from WO-11 control/development runs. The v1 experiments
are synthetic-chart software evidence; nothing here is a statement
about real nuclei, and nothing here changes a frozen v1 result.

## 1. Frozen evidence baseline

| experiment | sealed predictions unchanged | checksums verify | status |
| --- | --- | --- | --- |
| EZ-B001-A | True | True | scored |
| EZ-B001-B | True | True | scored |
| EZ-B001-C | True | True | scored |
| EZ-B002-v1 | True | True | ENGINEERING_PASS_CHARACTERIZATION |
| EZ-B003-v1 | True | True | CRITERION_NOT_MET_ALL_BASELINES |

EZ-B003-v1 frozen criterion: `ez-b003-rediscovery-criterion-v1` (digest `e4a2787b6a640f3c…`), verdicts: EZ-GP-DIRECT-v1 = CRITERION_NOT_MET, EZ-SEMF-GP-RESIDUAL-v1 = CRITERION_NOT_MET, EZ-SEMF-LS-v1 = CRITERION_NOT_MET

EZ-B002-v1 froze no accuracy criterion: v1 is characterization, and the
observed weaknesses below are adjudicated without inventing one.

## 2. Replay verification

- EZ-B002-v1: **PASS** — 9/9 metric files byte-identical, aggregates identical after volatile evidence ids are stripped, except the documented defect b002-worst-region-string-ranking-v1 (EZ-GP-DIRECT-v1) (strict byte level: 171/175 files; the rest are raw-float Atlas fact payloads that move by one ULP on a different libm, plus any files under documented defects).
- EZ-B003-v1: **PASS** — 6/6 metric files byte-identical, aggregates identical after volatile evidence ids are stripped (strict byte level: all 124 regenerated files identical).

Replay re-runs only the frozen scoring stage on the sealed predictions with a fit tripwire armed; a replay that needed model.fit() would raise ProtocolError instead of reproducing.

## 3. EZ-B002 failure decomposition

| failure id | model | check | observed | frozen threshold | primary class | secondary | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WO11-F-B002-EZ-SEMF-LS-v1-undercoverage | EZ-SEMF-LS-v1 | ez-b002-v1-no-accuracy-threshold | 0.448 | none frozen | UNCERTAINTY_UNDERCOVERAGE | MODEL_BIAS | HIGH |
| WO11-F-B002-EZ-GP-DIRECT-v1-bias | EZ-GP-DIRECT-v1 | ez-b002-v1-no-accuracy-threshold | 1470.461 | none frozen | MODEL_BIAS | HYPERPARAMETER_SENSITIVITY | HIGH |
| WO11-F-B002-EZ-GP-DIRECT-v1-overcoverage | EZ-GP-DIRECT-v1 | ez-b002-v1-no-accuracy-threshold | 1.000 | none frozen | UNCERTAINTY_OVERCOVERAGE | HYPERPARAMETER_SENSITIVITY | HIGH |
| WO11-F-B002-EZ-SEMF-GP-RESIDUAL-v1-overcoverage | EZ-SEMF-GP-RESIDUAL-v1 | ez-b002-v1-no-accuracy-threshold | 1.000 | none frozen | UNCERTAINTY_OVERCOVERAGE | HYPERPARAMETER_SENSITIVITY | HIGH |

## 4. EZ-B003 failure decomposition

| failure id | model | check | observed | frozen threshold | primary class | secondary | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WO11-F-B003-EZ-GP-DIRECT-v1-rank_1_fraction | EZ-GP-DIRECT-v1 | rank_1_fraction | 0.400 | 0.500 | MODEL_BIAS | HYPERPARAMETER_SENSITIVITY | HIGH |
| WO11-F-B003-EZ-GP-DIRECT-v1-top_k_fraction | EZ-GP-DIRECT-v1 | top_k_fraction | 0.514 | 0.750 | MODEL_BIAS | HYPERPARAMETER_SENSITIVITY | HIGH |
| WO11-F-B003-EZ-SEMF-GP-RESIDUAL-v1-rank_1_fraction | EZ-SEMF-GP-RESIDUAL-v1 | rank_1_fraction | 0.086 | 0.500 | MODEL_BIAS | HYPERPARAMETER_SENSITIVITY | HIGH |
| WO11-F-B003-EZ-SEMF-LS-v1-calibration_error_90 | EZ-SEMF-LS-v1 | calibration_error_90 | 0.225 | 0.150 | UNCERTAINTY_UNDERCOVERAGE | MODEL_BIAS | HIGH |
| WO11-F-B003-EZ-SEMF-LS-v1-rank_1_fraction | EZ-SEMF-LS-v1 | rank_1_fraction | 0.200 | 0.500 | MODEL_BIAS | — | HIGH |
| WO11-F-B003-EZ-SEMF-LS-v1-sign_fraction | EZ-SEMF-LS-v1 | sign_fraction | 0.400 | 0.750 | MODEL_BIAS | — | HIGH |
| WO11-F-B003-EZ-SEMF-LS-v1-top_k_fraction | EZ-SEMF-LS-v1 | top_k_fraction | 0.286 | 0.750 | MODEL_BIAS | — | HIGH |

## 5. Calibration diagnostics

| benchmark | model | mean(z) | std(z) | abs(z)<=1 | abs(z)<=1.645 | abs(z)<=1.96 | abs(z)>3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B002-v1 | EZ-GP-DIRECT-v1 | -0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| EZ-B002-v1 | EZ-SEMF-GP-RESIDUAL-v1 | -0.001 | 0.001 | 1.000 | 1.000 | 1.000 | 0.000 |
| EZ-B002-v1 | EZ-SEMF-LS-v1 | -1.590 | 0.545 | 0.155 | 0.448 | 0.707 | 0.000 |
| EZ-B003-v1 | EZ-GP-DIRECT-v1 | -0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| EZ-B003-v1 | EZ-SEMF-GP-RESIDUAL-v1 | -0.003 | 0.002 | 1.000 | 1.000 | 1.000 | 0.000 |
| EZ-B003-v1 | EZ-SEMF-LS-v1 | -1.074 | 0.963 | 0.292 | 0.675 | 0.867 | 0.000 |

Readout: the GP models are drastically overdispersed (std(z) near 0:
reported sigma is orders of magnitude wider than realized error), so
their intervals are uninformative rather than dishonest. SEMF-LS is
biased (mean(z) near -1.6 on EZ-B002): its misses come from a shifted
mean, not a narrow sigma. These are diagnostics, not causal proof.

## 6. Extrapolation-depth diagnostics

| benchmark | model | bucket | n | MAE (keV) | coverage 90 |
| --- | --- | --- | --- | --- | --- |
| EZ-B002-v1 | EZ-GP-DIRECT-v1 | d=1 | 27 | 1491.447 | 1.000 |
| EZ-B002-v1 | EZ-GP-DIRECT-v1 | d=2 | 26 | 1320.719 | 1.000 |
| EZ-B002-v1 | EZ-GP-DIRECT-v1 | d=3-4 | 5 | 2135.800 | 1.000 |
| EZ-B002-v1 | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 27 | 36.241 | 1.000 |
| EZ-B002-v1 | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 26 | 40.093 | 1.000 |
| EZ-B002-v1 | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 5 | 27.880 | 1.000 |
| EZ-B002-v1 | EZ-SEMF-LS-v1 | d=1 | 27 | 784.540 | 0.444 |
| EZ-B002-v1 | EZ-SEMF-LS-v1 | d=2 | 26 | 809.999 | 0.500 |
| EZ-B002-v1 | EZ-SEMF-LS-v1 | d=3-4 | 5 | 999.009 | 0.200 |
| EZ-B003-v1 | EZ-GP-DIRECT-v1 | d=1 | 76 | 893.089 | 1.000 |
| EZ-B003-v1 | EZ-GP-DIRECT-v1 | d=2 | 44 | 1331.995 | 1.000 |
| EZ-B003-v1 | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 76 | 354.693 | 1.000 |
| EZ-B003-v1 | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 44 | 929.107 | 1.000 |
| EZ-B003-v1 | EZ-SEMF-LS-v1 | d=1 | 76 | 2375.772 | 0.776 |
| EZ-B003-v1 | EZ-SEMF-LS-v1 | d=2 | 44 | 2835.420 | 0.500 |

Descriptive slopes (no significance claim; v1 depth reaches only L1 = 3): EZ-B002-v1/EZ-GP-DIRECT-v1: 116.7 keV per L1 step; EZ-B002-v1/EZ-SEMF-GP-RESIDUAL-v1: -0.8 keV per L1 step; EZ-B002-v1/EZ-SEMF-LS-v1: 73.1 keV per L1 step; EZ-B003-v1/EZ-GP-DIRECT-v1: 438.9 keV per L1 step; EZ-B003-v1/EZ-SEMF-GP-RESIDUAL-v1: 574.4 keV per L1 step; EZ-B003-v1/EZ-SEMF-LS-v1: 459.6 keV per L1 step.

Depth effects exist but are shallow and cannot explain failures that
are already present at L1 = 1, so EXTRAPOLATION_DEPTH stays a
secondary, not primary, cause at these depths.

## 7. Benchmark oracle controls

Overall control status: **PASS**

| EZ-B002 control | MAE (keV) | coverage 90 |
| --- | --- | --- |
| EZ-CONTROL-EXACT-ORACLE-v1 | 0.000 | 1.000 |
| EZ-CONTROL-NOISY-ORACLE-200KEV-v1 | 153.083 | 0.914 |
| EZ-CONTROL-WEAK-QUADRATIC-v1 | 1607.213 | 0.828 |

| EZ-B003 control | verdict | sign | top-3 | rank-1 | cal. error |
| --- | --- | --- | --- | --- | --- |
| EZ-CONTROL-NOISY-ORACLE-200KEV-v1 | CRITERION_MET | 1.000 | 1.000 | 1.000 | 0.008 |
| EZ-CONTROL-NOISY-ORACLE-2MEV-v1 | CRITERION_MET | 0.943 | 0.829 | 0.714 | 0.008 |
| EZ-CONTROL-SHELL-AWARE-ORACLE-v1 | CRITERION_MET | 1.000 | 1.000 | 1.000 | 0.100 |
| EZ-CONTROL-WEAK-QUADRATIC-v1 | CRITERION_NOT_MET | 0.657 | 0.229 | 0.171 | 0.075 |

Threshold sensitivity: 200 keV of unstructured noise → CRITERION_MET; 2000 keV → CRITERION_MET. Even 2 MeV of *random* mass error keeps the criterion met, while the
baselines fail with sub-MeV *smooth structured* error: the criterion
punishes the inability to localize a discontinuity, not error
magnitude, so the v1 failures are not a knife-edge threshold effect.

## 8. Feature ablations (development fixtures only)

- EZ-B002-dev: baseline MAE 413.0 keV; max MAE change across feature policies 7.8%.
- EZ-B003-dev: baseline MAE 1200.6 keV; max MAE change across feature policies 18.1%.

Dev shell localization (rank-1 fraction) by feature policy: dev-zna-parity-isospin-local-v1 = 0.000, dev-zna-parity-isospin-v1 = 0.000, dev-zna-parity-v1 = 0.000, dev-zna-v1 = 0.000.

Adding parity, isospin, and local coordinate features moves mass MAE
by under twenty percent and leaves localization at zero: with this
model family, FEATURE_INSUFFICIENCY is not the dominant cause.

## 9. Hyperparameter sensitivity (development fixtures only)

| fixture | variant | MAE (keV) | shell rank-1 |
| --- | --- | --- | --- |
| EZ-B002-dev | hp-baseline | 412.972 | n/a |
| EZ-B002-dev | hp-direct-formulation | 2520.895 | n/a |
| EZ-B002-dev | hp-length-scale-2 | 573.423 | n/a |
| EZ-B002-dev | hp-length-scale-32 | 399.652 | n/a |
| EZ-B002-dev | hp-no-normalize-y | 412.972 | n/a |
| EZ-B002-dev | hp-noise-1e2 | 462.162 | n/a |
| EZ-B002-dev | hp-noise-1e6 | 400.518 | n/a |
| EZ-B002-dev | hp-optimized-restarts-2 | 9.603 | n/a |
| EZ-B003-dev | hp-baseline | 1200.606 | 0.000 |
| EZ-B003-dev | hp-direct-formulation | 3452.617 | 0.105 |
| EZ-B003-dev | hp-length-scale-2 | 630.684 | 0.000 |
| EZ-B003-dev | hp-length-scale-32 | 3004.821 | 0.000 |
| EZ-B003-dev | hp-no-normalize-y | 1200.611 | 0.000 |
| EZ-B003-dev | hp-noise-1e2 | 929.346 | 0.000 |
| EZ-B003-dev | hp-noise-1e6 | 2867.404 | 0.000 |
| EZ-B003-dev | hp-optimized-restarts-2 | 326.651 | 0.579 |

The family is highly configuration-sensitive: on EZ-B002-dev the
optimizer-enabled variant drops MAE from hundreds of keV to under
10 keV, and on EZ-B003-dev it is the only variant with non-zero
rank-1 localization from the smooth-kernel grid. The frozen v1
fixed-kernel configuration understates what even this family can do,
which is recorded as HYPERPARAMETER_SENSITIVITY evidence — and it
was preregistered, so the v1 results stand as they are.

## 10. Model-family diagnosis

- EZ-SEMF-LS-v1: structurally unable to express a shell discontinuity
  (no shell term); resolves H0 where truth resolves H1; global sigma
  cannot absorb its structured bias (undercoverage on both benchmarks).
- EZ-GP-DIRECT-v1: physics-free mean function reverts toward the
  training mean inside holdouts (MAE ~40x the residual model on
  EZ-B002-v1); smooth kernel smears the indicator spike; sigma
  overdispersed to the point of being uninformative.
- EZ-SEMF-GP-RESIDUAL-v1: best mass surface of the three and recovers
  the *presence* of the injected gap (sign 1.0, top-3 0.8) but not its
  *location* (rank-1 0.086): a squared-exponential prior has no kink
  bias. This is the physically expected failure of a smooth
  interpolator on a discontinuity.

Primary failure classes: EZ-B002: MODEL_BIAS, UNCERTAINTY_OVERCOVERAGE, UNCERTAINTY_UNDERCOVERAGE; EZ-B003: MODEL_BIAS, UNCERTAINTY_UNDERCOVERAGE.

## 11. Frontier-model candidate registry

| candidate | class | role | independence group | status |
| --- | --- | --- | --- | --- |
| BSKG4 | microscopic global EDF mass model | PHYSICS_BACKBONE | brussels-skyrme-edf | CANDIDATE |
| BSKG5 | microscopic global EDF mass model | PHYSICS_BACKBONE | brussels-skyrme-edf | RESEARCH |
| BAYES-GP-EXTRAP-2018 | statistical residual correction with UQ | UQ_CHALLENGER | bayesian-mass-uq | CANDIDATE |
| EBMA-2024 | multi-model combination with UQ | MODEL_COMBINATION | bayesian-mass-uq | CANDIDATE |
| CNN-WS4 | ML residual model over a macroscopic-microscopic base | RESIDUAL_CHALLENGER | ml-residual-networks | RESEARCH |
| GPR-NN-2025 | ML mass regression with GP components | RESIDUAL_CHALLENGER | ml-residual-networks | RESEARCH |
| MTGP-2025 | ML multi-observable regression with UQ | RESIDUAL_CHALLENGER | ml-multitask-gp | RESEARCH |

WO-12 must not choose by leaderboard accuracy alone. Selection weighs independent physics assumptions, global coverage, extrapolation evidence, uncertainty support, access to tables/code, reproducibility, deformation/fission extensibility, computational feasibility, and licensing. ElementZero needs physics diversity more than a monoculture of closely related regressors; note that BSkG4 and BSkG5 share one independence group and count once toward diversity.

## 12. WO-11 verdict

**FRONTIER_MODEL_RERUN_JUSTIFIED**

- the v1 evidence is intact and the sealed replay reproduces it
- oracle controls pass and the weak control fails, so the frozen benchmark mechanics and criterion are sound
- every frozen-criterion failure is attributed with evidence to model capacity, inductive bias, or uncertainty quality

## 13. Exact prerequisites for WO-12

1. Define EZ-B002-v2 and EZ-B003-v2 as new preregistered protocol versions; the v1 results stay frozen and are never relabeled or rerun.
2. Keep EZ-SEMF-LS-v1, EZ-GP-DIRECT-v1, and EZ-SEMF-GP-RESIDUAL-v1 in every WO-12 run as controls; do not replace them.
3. Integrate at least one physics-rich global mass model (Class A: BSkG4 or BSkG5 published tables) as the physics backbone.
4. Add a second, scientifically independent global model family and a Bayesian/ensemble combination layer (Class B) so model-family disagreement becomes measurable.
5. Add residual/ML models (Class C) in challenger roles only; no ML model may be the sole source of truth.
6. Include the optimizer-enabled GP configuration from the WO-11 dev grid as a configuration control: the dev evidence shows the frozen fixed-kernel configuration understates the baseline family.
7. Repair predictive-uncertainty calibration before v2 scoring: v1 GP sigmas are orders of magnitude too wide (std(z) near 0) and the SEMF-LS global sigma cannot absorb structured bias (mean(z) near -1.6).
8. Freeze v2 thresholds on synthetic mechanics before any evaluated-table truth is read, exactly as B003 v1 did.
9. Pin the runtime environment (interpreter minor version and library versions) in the v2 protocol so strict byte replay stays achievable.
10. Complete license and availability review for every candidate before integration; a candidate without traceable publications and data/code stays out of WO-12.
11. Never tune any frontier candidate on EZ-B002/EZ-B003 hidden truth; public training data only, verified through the existing leakage firewalls.

## 14. Deviations / limitations

- The WO-11 handoff described EZ-B002-v1 as `CRITERION_NOT_MET`; the
  frozen v1 record shows that protocol deliberately froze *no* accuracy
  criterion (characterization, engineering PASS). WO-11 adjudicates the
  observed EZ-B002-v1 weaknesses without inventing a threshold after
  the fact, and treats `frozen-threshold failure` as accurate for
  EZ-B003-v1 only.
- Strict byte-level replay (including raw-float Atlas fact payloads) is
  achieved under the recorded interpreter line (CPython 3.12). Under
  3.11 every 12-significant-digit metric and every verdict still
  reproduces exactly; only content-addressed ids over raw IEEE floats
  shift by one ULP. WO-12 should pin the interpreter minor version.
- The committed-seal *refit* reproducibility tests require the recorded
  library stack (numpy 2.4.4, scipy 1.18.0, Python 3.12.3); scipy
  1.18.0 was not installable in the WO-11 environment, so refit
  reproducibility remains verified only in the recording environment.
  This is environment sensitivity of the *fit* path, not of the sealed
  evidence, and it is additional HYPERPARAMETER_SENSITIVITY-adjacent
  evidence for WO-12's environment-pinning prerequisite.
- All v1 evidence is synthetic-chart software evidence. Every
  conclusion here is about protocol and model behavior on those
  synthetic surfaces; none of it is scientific evidence about real
  nuclei, about any real closure, or about any island of stability.
- Dev-fixture results are development diagnostics only and are never
  comparable to v1 numbers.
