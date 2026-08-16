# WO-12 — Nuclear Model Federation v1

Input commit: ac6152e1c1a23afe7111e8ba2b218e4487e4ec65
WO-11 verdict consumed: FRONTIER_MODEL_RERUN_JUSTIFIED
Qualification status: **PASS**

All qualification numbers below are synthetic-mechanics evidence on the frozen WO-12 charts. Physics tables are expected to disagree with a toy surface; their rows demonstrate coverage, disagreement, and combination mechanics, not physics accuracy. Nothing here reads an evaluated mass table.

## 1. Federation roster

Models: 10 — independence groups: 6 (liquid_drop_baseline, macroscopic_microscopic_frdm, model_combination, residual_ml, skyrme_edf_bskg, statistical_gp)

| participant | role | independence group | license |
| --- | --- | --- | --- |
| EZ-BSKG3-TABLE-v1 | PHYSICS_BACKBONE | skyrme_edf_bskg | APPROVED |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | RESIDUAL_CHALLENGER | residual_ml | internal |
| EZ-FED-UNIFORM-ENSEMBLE-v1 | COMBINER | model_combination | internal |
| EZ-FED-VALIDATION-WEIGHTED-v1 | COMBINER | model_combination | internal |
| EZ-FRDM95-TABLE-v1 | PHYSICS_BACKBONE | macroscopic_microscopic_frdm | APPROVED |
| EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | RESIDUAL_CHALLENGER | residual_ml | internal |
| EZ-GP-DIRECT-v1 | CONTROL | statistical_gp | internal |
| EZ-GP-OPTIMIZED-CONTROL-v1 | CONTROL | statistical_gp | internal |
| EZ-SEMF-GP-RESIDUAL-v1 | CONTROL | statistical_gp | internal |
| EZ-SEMF-LS-v1 | CONTROL | liquid_drop_baseline | internal |

BSkG5 and FRDM2012 remain the preferred backbones; both are BLOCKED_AVAILABILITY in this environment, so the families participate through BSkG3 (BRUSLIB) and FRDM95 (IAEA RIPL-3) under the documented fallback ladders in candidate_review.json.

## 2. WO-11 prerequisites

1. SATISFIED: EZ-B002-v2 and EZ-B003-v2 exist as new QUALIFICATION_ONLY protocols with frozen thresholds; no v1 artifact was touched.
2. SATISFIED: the three v1 baselines are registered CONTROL participants and are never removed.
3. SATISFIED with documented fallback: BSkG5 and BSkG4 tables are BLOCKED_AVAILABILITY in this environment, so the Brussels Skyrme-EDF family participates through the publicly hosted BSkG3 table (PHYSICS_BACKBONE, skyrme_edf_bskg).
4. SATISFIED with documented fallback: FRDM2012's canonical host is unreachable, so the macroscopic-microscopic family participates through the IAEA RIPL-3 FRDM95 table; the combination layer (uniform, validation-weighted, EBMA-compatible) is implemented.
5. SATISFIED: residual/ML models exist only in RESIDUAL_CHALLENGER roles; no ML model is a source of truth.
6. SATISFIED: EZ-GP-OPTIMIZED-CONTROL-v1 is registered with frozen hyperparameters (ez-wo12-gp-optimized-control-v1).
7. ADDRESSED: predictive uncertainty is decomposed (within/residual/disagreement) and calibrated per model in the qualification; the frozen v2 gates enforce honesty (the BSkG3 residual variant and the optimized GP both fail v2 checks on calibration alone, which shows the clause has teeth).
8. SATISFIED: every v2 threshold is frozen in this commit from synthetic mechanics and WO-11 oracle behavior, before any evaluated-table truth.
9. SATISFIED: runtime.lock.json records interpreter, array stack, BLAS/LAPACK identity, OS, and architecture.
10. SATISFIED: every external table carries a source/license manifest; the registry gate excludes anything not APPROVED.
11. SATISFIED: fit/calibration/benchmark identity digests are persisted and disjointness is asserted per split; the discovery feature firewall stays active in every shell run.

v0.3 tag closeout: `elementzero-validation-ladder-v0.3` at `9baee722c492…` (PUSHED_BY_MAINTAINER).

## 3. EZ-B002-v2 qualification

Status: **PASS** — gate: pooled MAE <= 150 keV with calibration error <= 0.15; qualifying: EZ-SEMF-GP-RESIDUAL-v1

| model | MAE (keV) | RMSE (keV) | coverage 90 | cal. error 90 |
| --- | --- | --- | --- | --- |
| EZ-BSKG3-TABLE-v1 | 6785.657 | 7565.378 | 0.033 | 0.867 |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 446.349 | 635.735 | 0.767 | 0.133 |
| EZ-FED-UNIFORM-ENSEMBLE-v1 | 3429.803 | 3797.188 | 1.000 | 0.100 |
| EZ-FED-VALIDATION-WEIGHTED-v1 | 443.964 | 588.576 | 0.867 | 0.033 |
| EZ-FRDM95-TABLE-v1 | 6908.157 | 7523.175 | 0.017 | 0.883 |
| EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | 539.133 | 730.129 | 0.683 | 0.217 |
| EZ-GP-DIRECT-v1 | 1496.771 | 2077.569 | 1.000 | 0.100 |
| EZ-GP-OPTIMIZED-CONTROL-v1 | 10.281 | 12.538 | 0.683 | 0.217 |
| EZ-SEMF-GP-RESIDUAL-v1 | 57.567 | 75.663 | 1.000 | 0.100 |
| EZ-SEMF-LS-v1 | 407.559 | 465.220 | 0.867 | 0.033 |

## 4. EZ-B003-v2 qualification

Status: **PASS** — evaluable closures: neutron-N126, proton-Z82 (7 reported NOT_EVALUABLE); models meeting the frozen criterion: EZ-FED-VALIDATION-WEIGHTED-v1, EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1

| model | verdict | sign | top-3 | rank-1 | cal. error |
| --- | --- | --- | --- | --- | --- |
| EZ-BSKG3-TABLE-v1 | CRITERION_NOT_MET | 0.000 | 0.000 | 0.000 | 0.900 |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | CRITERION_NOT_MET | 1.000 | 1.000 | 0.978 | 0.400 |
| EZ-FED-UNIFORM-ENSEMBLE-v1 | CRITERION_NOT_MET | 0.000 | 0.000 | 0.000 | 0.100 |
| EZ-FED-VALIDATION-WEIGHTED-v1 | CRITERION_MET | 1.000 | 1.000 | 1.000 | 0.057 |
| EZ-FRDM95-TABLE-v1 | CRITERION_NOT_MET | 0.000 | 0.000 | 0.000 | 0.900 |
| EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | CRITERION_MET | 1.000 | 1.000 | 1.000 | 0.016 |
| EZ-GP-DIRECT-v1 | CRITERION_NOT_MET | 0.826 | 0.391 | 0.174 | 0.100 |
| EZ-GP-OPTIMIZED-CONTROL-v1 | CRITERION_NOT_MET | 1.000 | 0.978 | 0.870 | 0.320 |
| EZ-SEMF-GP-RESIDUAL-v1 | CRITERION_NOT_MET | 0.978 | 0.609 | 0.152 | 0.100 |
| EZ-SEMF-LS-v1 | CRITERION_NOT_MET | 0.217 | 0.152 | 0.109 | 0.168 |

Reading: the FRDM95-backed residual challenger and the validation-weighted combiner meet the frozen criterion with rank-1 = 1.0 — the physics table carries the kink, the GP corrects the smooth offset — which is precisely the WO-11-diagnosed failure mode repaired. Every pure smooth-prior baseline still fails structure, exactly as in v1. The calibration clause keeps its teeth: the BSkG3-backed residual variant localizes almost perfectly (rank-1 0.978) and still fails on dishonest uncertainty, and the equal-weight ensemble fails structure outright, which is why the validation-weighted combiner exists.

## 5. Uncertainty and disagreement

ez-wo12-uncertainty-decomposition-v1: predictive_std**2 = within_model_std**2 + residual_std**2 + model_disagreement_std**2. Table models report their empirical rms as within_model_std; residual-corrected models report the correction-GP posterior sigma as residual_std (the base sigma is replaced, not added); combiners report the weighted within-component sigma as within_model_std and the between-component spread as model_disagreement_std. Components that do not apply are exactly zero, never silently folded elsewhere.

Per-model decomposition means and z-statistics are committed in calibration_report.json and synthetic_qualification.json; disagreement by depth (std and MAD over available predictions) is committed per benchmark. High agreement is not proof of correctness; high disagreement is evidence of epistemic uncertainty.

## 6. Stop conditions and next gate

evaluated-table EZ-B002-v2 / EZ-B003-v2 runs stay blocked until this synthetic qualification passes and every stop condition of WO-12 section 29 is clear

A failed qualification would be preserved honestly; this one passed, so the next gate is the evaluated-table EZ-B002-v2 / EZ-B003-v2 runs under the frozen protocols, with new experiment ids and no threshold edits.
