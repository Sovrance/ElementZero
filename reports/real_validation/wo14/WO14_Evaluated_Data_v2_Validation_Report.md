# WO-14 — Evaluated Data v2 Validation

Work order status: **ENGINEERING_PASS_SCIENTIFIC_MIXED**

## 1. Input integrity

Every pinned input re-hashed unchanged (13 files), the v1 evidence inventory is unchanged, and the WO-12 registry and protocol hashes match their frozen values.

- WO-12 registry hash: `9a9e4c8ac12f6b983c464f8ef7bc8162ebbfa9a305d39f4e60e8cdb9848361ec`
- WO-12 protocol hash: `117b60ccfbde52a3eef1e5e5acdeae8197275d073d122752a8b75b33500cd686`

## 2. Frozen protocol and threshold confirmation

The inherited thresholds are the frozen EZ-B002-v2 gate and the frozen EZ-B003-v2 rediscovery criterion, hash-asserted at truth unlock on every track. No new real-data threshold was invented; meeting an inherited criterion on real data is labeled INHERITED_SYNTHETIC_QUALIFICATION_CRITERION, never a universal real-world standard.

## 3. B002 REAL-BLIND protocol

60 preregistered targets in 3 regions; roster = the 4 freeze-controlled statistical baselines the committed WO-13 blind subfederation admits. Zero blind physics groups: control-only evidence by construction. Predictions were sealed and committed (commit `10d1bbcbb5efd96bd4fb1b52a04fc885b6abf0c2`) before any truth was read.

## 4. B002 REAL-BLIND results

Status: **CONTROL_BLIND_CRITERION_NOT_MET** — best baseline `EZ-GP-OPTIMIZED-CONTROL-v1`, inherited gate met: False.

| model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | cal_error_90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-GP-DIRECT-v1 | 60 | 1.447726599259e+03 | 1.251771121669e+03 | 1.921475735112e+03 | 1.627894379513e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 |
| EZ-GP-OPTIMIZED-CONTROL-v1 | 60 | 5.474285743684e+02 | 2.900781465000e+02 | 8.355697786694e+02 | 8.480897204656e+00 | 8.000000000000e-01 | 8.333333333333e-01 | 1.000000000000e-01 |
| EZ-SEMF-GP-RESIDUAL-v1 | 60 | 7.419436639270e+02 | 5.400088892650e+02 | 1.006399009282e+03 | 1.381408540744e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 |
| EZ-SEMF-LS-v1 | 60 | 3.834552690030e+03 | 4.066095127991e+03 | 4.143030837558e+03 | 9.762296630099e+00 | 9.500000000000e-01 | 1.000000000000e+00 | 5.000000000000e-02 |

federation_improved_over_baseline: NOT_EVALUABLE_FOR_BLIND_B002

## 5. B002 REAL-RECON results

Status: **B002_RECON_COMPLETE**. Roster = the BSkG3 lineage the committed WO-13 claim facts admit on every target; the FRDM95 lineage is INELIGIBLE_UNKNOWN_PROVENANCE outside its 12 blind targets and no combiner can hide that ineligible contributor.

| model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | cal_error_90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-BSKG3-TABLE-v1 | 60 | 7.585359885000e+02 | 7.073835000000e+02 | 8.917699526573e+02 | 8.293523186680e+00 | 8.666666666667e-01 | 9.166666666667e-01 | 3.333333333333e-02 |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 60 | 4.494064241056e+02 | 3.743301404300e+02 | 5.922048333956e+02 | 8.203891982989e+00 | 7.666666666667e-01 | 8.333333333333e-01 | 1.333333333333e-01 |

- best baseline (cross-referenced from the blind track): `EZ-GP-OPTIMIZED-CONTROL-v1` (MAE 5.474285743684e+02 keV)
- best physics table: `EZ-BSKG3-TABLE-v1` (MAE 7.585359885000e+02 keV)
- best residual physics: `EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1` (MAE 4.494064241056e+02 keV)
- best combined: NOT_RUN_NO_ELIGIBLE_COMBINER
- reconstruction improved over best baseline: True

## 6. B002 claim adjudication

- blind: scope `CONTROL_BLIND_GEOGRAPHIC`, claim `STRICT_BLIND`, visual `BADGE_CB_ONLY_NO_STAGE_PROMOTION`
- recon: scope `RECONSTRUCTION_GEOGRAPHIC`, claim `RECONSTRUCTION_REFERENCE`, visual `BADGE_R_ONLY_NO_STAGE_PROMOTION`

## 7. B003 REAL-BLIND eligibility

12 historically blind central targets; one blind physics family (`macroscopic_microscopic_frdm`). The 4 statistical baselines run as freeze-controlled comparators, not independent physics.

Targets: `Z48-N83`, `Z81-N130`, `Z81-N132`, `Z81-N95`, `Z82-N133`, `Z82-N96`, `Z82-N97`, `Z82-N98`, `Z83-N134`, `Z83-N135`, `Z93-N126`, `Z93-N127`

## 8. Derived-observable blindness audit

ez-wo14-derived-blindness-v1: a derived shell observable is blind only when every model-side component mass entering it satisfies the blind policy for the model under test; central-target blindness never propagates to neighbors, and post-seal scoring truth never repairs a model that was fitted on a component's answer

- records: 60
- blind-eligible: 2 (S2n:Z81-N132, S2n:Z82-N98)
- full-shell eligible: 0

## 9. B003 blind mass results

Status: **PHYSICS_BLIND_MASS_CRITERION_NOT_MET** — best blind-family model `EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1`; criterion 1.649095586609e+02 keV MAE vs 1.500000000000e+02 keV allowed (INHERITED_SYNTHETIC_QUALIFICATION_CRITERION).

| model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | cal_error_90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-FRDM95-TABLE-v1 | 12 | 6.345660833333e+02 | 5.950755000000e+02 | 8.096805309861e+02 | 8.124153200076e+00 | 9.166666666667e-01 | 9.166666666667e-01 | 1.666666666667e-02 |
| EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | 12 | 1.649095586609e+02 | 1.176561981465e+02 | 2.240965614477e+02 | 6.929118604149e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 |
| EZ-GP-DIRECT-v1 | 12 | 1.666019002799e+03 | 1.788125366101e+03 | 1.819574153832e+03 | 1.635762505104e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 |
| EZ-GP-OPTIMIZED-CONTROL-v1 | 12 | 3.891218516314e+02 | 3.663867741925e+02 | 4.916878720215e+02 | 7.730865692761e+00 | 9.166666666667e-01 | 1.000000000000e+00 | 1.666666666667e-02 |
| EZ-SEMF-GP-RESIDUAL-v1 | 12 | 3.582865048918e+02 | 3.521192806950e+02 | 4.552589022514e+02 | 1.389644230101e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 |
| EZ-SEMF-LS-v1 | 12 | 2.516158689492e+03 | 2.306294549799e+03 | 3.433332117976e+03 | 9.566325848297e+00 | 9.166666666667e-01 | 9.166666666667e-01 | 1.666666666667e-02 |

## 10. B003 edge-structure results

Status: **PHYSICS_BLIND_EDGE_VALIDATION** over 12 blind-eligible derived rows.

| observable | central | model | predicted MeV | truth MeV | error MeV | sign recovered |
| --- | --- | --- | --- | --- | --- | --- |
| S2n | Z81-N132 | EZ-FRDM95-TABLE-v1 | 7.922636210758e+00 | 8.280826210761e+00 | -3.581900000022e-01 | True |
| S2n | Z81-N132 | EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | 8.324947567200e+00 | 8.280826210761e+00 | 4.412135643906e-02 | True |
| S2n | Z81-N132 | EZ-GP-DIRECT-v1 | 9.271766341784e+00 | 8.280826210761e+00 | 9.909401310235e-01 | True |
| S2n | Z81-N132 | EZ-GP-OPTIMIZED-CONTROL-v1 | 8.922239462778e+00 | 8.280826210761e+00 | 6.414132520179e-01 | True |
| S2n | Z81-N132 | EZ-SEMF-GP-RESIDUAL-v1 | 8.030167506008e+00 | 8.280826210761e+00 | -2.506587047526e-01 | True |
| S2n | Z81-N132 | EZ-SEMF-LS-v1 | 1.080205742695e+01 | 8.280826210761e+00 | 2.521231216192e+00 | True |
| S2n | Z82-N98 | EZ-FRDM95-TABLE-v1 | 2.160263621079e+01 | 2.165707621079e+01 | -5.443999999557e-02 | True |
| S2n | Z82-N98 | EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | 2.150155365001e+01 | 2.165707621079e+01 | -1.555225607794e-01 | True |
| S2n | Z82-N98 | EZ-GP-DIRECT-v1 | 2.021393482856e+01 | 2.165707621079e+01 | -1.443141382222e+00 | True |
| S2n | Z82-N98 | EZ-GP-OPTIMIZED-CONTROL-v1 | 2.132136426756e+01 | 2.165707621079e+01 | -3.357119432249e-01 | True |
| S2n | Z82-N98 | EZ-SEMF-GP-RESIDUAL-v1 | 2.165901200116e+01 | 2.165707621079e+01 | 1.935790376592e-03 | True |
| S2n | Z82-N98 | EZ-SEMF-LS-v1 | 2.252831928961e+01 | 2.165707621079e+01 | 8.712430788291e-01 | True |

## 11. Full-shell blind evaluability

**FULL_SHELL_BLIND_NOT_EVALUABLE** — edge validation is not full shell rediscovery: the audited blind-eligible observables cover drip-side S2n edges only, and delta2n/delta2p/local_peak_rank dependencies are nonblind

## 12. B003 REAL-RECON results

Status: **B003_RECON_CRITERION_MET**; models meeting the frozen criterion: EZ-BSKG3-TABLE-v1.

| model_id | verdict | sign | top-k | rank-1 | cal_err_90 |
| --- | --- | --- | --- | --- | --- |
| EZ-BSKG3-TABLE-v1 | CRITERION_MET | 1.000000000000e+00 | 8.734177215190e-01 | 6.708860759494e-01 | 6.889632107023e-02 |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | CRITERION_NOT_MET | 1.000000000000e+00 | 8.924050632911e-01 | 7.405063291139e-01 | 1.859531772575e-01 |

RECONSTRUCTION_CRITERION_MET is reference evidence about known structure; BLIND_REDISCOVERY_CRITERION_MET can only be earned by the BLIND track, which this run is not

## 13. Visual-state effects

- B002 control-blind: badge `CB` only; the primary stage never becomes geographic_holdout_validated from control-only evidence.
- B002/B003 reconstruction: badge `R` only; no stage promotion.
- B003 historical-blind edge: badge `HB` only; shell_rediscovery_validated additionally requires FULL_SHELL_BLIND_CRITERION_MET, which this run did not earn.

## 14. Atlas provenance

Each track carries the chain RealValidationProtocolFact -> EligibilityManifestFact -> BlindSubfederationFact -> PredictionSetFact -> FinalizationFact -> TruthUnlockFact -> ScoreFact -> (DerivedBlindnessFact) -> ClaimAdjudicationFact under reports/real_validation/wo14/atlas.

## 15. Limitations

- One blind physics family only; no second independent family.
- The 12 historical-blind targets are a small post-fit subset around otherwise established shell regions: edge evidence, not shell rediscovery.
- B002 blind evidence is statistical-baseline extrapolation on interior holdouts, not physics validation.
- Reconstruction results are reference descriptions of known structure.
- ez-wo14-no-post-truth-tuning-v1: after REAL-BLIND truth unlock, model definitions, hyperparameters, fit/calibration split, subfederation membership rule, combination rule, uncertainty rule, thresholds, and shell observable definitions are frozen; any change requires a new protocol and a new experiment id

## 16. Allowed claims

- Blind statistical geographic extrapolation on preregistered real holdout regions (control scope).
- One historical-blind global physics family scored on 12 post-1995 targets (mass edge, plus 2 blind S2n edge observables).
- Reconstruction reference quality of the BSkG3 lineage on known geographic regions and known shell structure.

## 17. Prohibited claims

- PHYSICS_BLIND_GEOGRAPHIC_VALIDATION or FEDERATED_BLIND_GEOGRAPHIC_VALIDATION from B002 control-blind evidence.
- FULL_BLIND_SHELL_REDISCOVERY (not evaluable with this target set).
- BLIND_REDISCOVERY_CRITERION_MET from any reconstruction run.
- Any claim about unknown or superheavy elements.

## 18. Next gate

WO-15 Refittable Physics Backends and Historical Physics Fits: at least two independent physics families whose fitting/calibration can exclude benchmark targets; WO-14 alone does not authorize prediction of unknown elements.
