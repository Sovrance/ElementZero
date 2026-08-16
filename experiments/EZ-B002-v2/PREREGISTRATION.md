# EZ-B002-v2 — preregistration

State: **QUALIFICATION_ONLY**

QUALIFICATION_ONLY: no evaluated mass table has been read under these protocols. Scoring real hidden truth is a separate later act, allowed only after this synthetic qualification passes, and it may not change a threshold.

## Frozen thresholds

```json
{"best_model_max_MAE_keV":"1.500000000000e+02","best_model_max_calibration_error_90":"1.500000000000e-01","frozen_before":"any v2 qualification scoring and any evaluated-table truth","gate_id":"ez-b002-v2-qualification-gate-v1","rule":"the qualification passes when at least one federation participant reconstructs the withheld regions with pooled MAE at or below best_model_max_MAE_keV while keeping abs(coverage_90 - 0.90) at or below best_model_max_calibration_error_90 on the same targets"}
```

Protocol hash: `117b60ccfbde52a3eef1e5e5acdeae8197275d073d122752a8b75b33500cd686`

Registry hash: `9a9e4c8ac12f6b983c464f8ef7bc8162ebbfa9a305d39f4e60e8cdb9848361ec`

ez-wo12-fixture-novelty-v1: the v2 qualification charts differ from EZ-B002-v1/EZ-B003-v1 (new coefficients, phases, windows; closures moved from N0=50/Z0=28) and from the WO-11 dev fixtures (different coefficients, phases, windows; closures moved from N0=82/Z0=50 to the lead region N0=126/Z0=82).

Running this protocol against an evaluated mass table requires: the synthetic qualification to have passed, every WO-12 section 29 stop condition to be clear, and a new experiment id under this frozen protocol — never an edit of a v1 result.
