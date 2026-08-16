# WO-13 — Real-Data Blindness, Eligibility, and Claim Integrity

Status: **PHYSICS_BLIND_EVALUABLE**
B002 blind status: **CONTROL_BLIND_EVALUABLE**
B003 blind status: **PHYSICS_BLIND_EVALUABLE**
Blind physics independence groups: macroscopic_microscopic_frdm

Core rule: a target hidden from ElementZero is not automatically blind to an imported physics table.

## 1. Immutable inputs

WO-12 registry hash: `9a9e4c8ac12f6b983c464f8ef7bc8162ebbfa9a305d39f4e60e8cdb9848361ec`

Frozen v2 thresholds re-hashed and asserted unchanged; v1 inventory re-verified. ez-wo13-threshold-inheritance-v1: the frozen v2 qualification thresholds are inherited as qualification criteria, hashed and asserted unchanged; passing them on real data is NOT a validated real-world performance standard unless a separate preregistration justifies that claim before scoring, and no new real-data threshold may be invented after looking at real results

## 2. Three separate facts

- protocol_qualified (B002): True
- federation_improved_over_baseline (B002): False — best baseline EZ-GP-OPTIMIZED-CONTROL-v1 at 10.3 keV, best physics EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 at 446.3 keV, best combined EZ-FED-VALIDATION-WEIGHTED-v1 at 444.0 keV
- B003: structure_localization_improved=True, calibration_improved=True, federation_criterion_met=True, blind_claim_eligible=True

Protocol PASS is not the same as frontier-model improvement, and reconstruction is not rediscovery.

## 3. Claim-aware sections (never one mixed leaderboard)

ez-wo13-claim-sections-v1: never one mixed leaderboard. Section A: strict/historical blind; B: partially blind; C: nonblind reference; D: reconstruction reference; E: ineligible/unknown provenance. Metrics can be identical across sections; claims cannot.

### EZ-B002-v2-real-blind

- **A_STRICT_HISTORICAL_BLIND**
  - EZ-GP-DIRECT-v1: 60 targets
  - EZ-GP-OPTIMIZED-CONTROL-v1: 60 targets
  - EZ-SEMF-GP-RESIDUAL-v1: 60 targets
  - EZ-SEMF-LS-v1: 60 targets
- **C_NONBLIND_REFERENCE**
  - EZ-BSKG3-TABLE-v1: 60 targets
  - EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1: 60 targets
- **E_INELIGIBLE_UNKNOWN**
  - EZ-FED-UNIFORM-ENSEMBLE-v1: 60 targets
  - EZ-FED-VALIDATION-WEIGHTED-v1: 60 targets
  - EZ-FRDM95-TABLE-v1: 60 targets
  - EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1: 60 targets

Blind gate: **CONTROL_BLIND_EVALUABLE** over 60 targets ({'REAL_BLIND_GATE_NOT_EVALUABLE': 0, 'CONTROL_BLIND_EVALUABLE': 60, 'PHYSICS_BLIND_EVALUABLE': 0, 'FEDERATED_BLIND_EVALUABLE': 0}).

### EZ-B003-v2-real-blind

- **A_STRICT_HISTORICAL_BLIND**
  - EZ-FRDM95-TABLE-v1: 12 targets
  - EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1: 12 targets
  - EZ-GP-DIRECT-v1: 548 targets
  - EZ-GP-OPTIMIZED-CONTROL-v1: 548 targets
  - EZ-SEMF-GP-RESIDUAL-v1: 548 targets
  - EZ-SEMF-LS-v1: 548 targets
- **C_NONBLIND_REFERENCE**
  - EZ-BSKG3-TABLE-v1: 548 targets
  - EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1: 548 targets
  - EZ-FED-UNIFORM-ENSEMBLE-v1: 12 targets
  - EZ-FED-VALIDATION-WEIGHTED-v1: 12 targets
- **E_INELIGIBLE_UNKNOWN**
  - EZ-FED-UNIFORM-ENSEMBLE-v1: 536 targets
  - EZ-FED-VALIDATION-WEIGHTED-v1: 536 targets
  - EZ-FRDM95-TABLE-v1: 536 targets
  - EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1: 536 targets

Blind gate: **PHYSICS_BLIND_EVALUABLE** over 548 targets ({'REAL_BLIND_GATE_NOT_EVALUABLE': 0, 'CONTROL_BLIND_EVALUABLE': 536, 'PHYSICS_BLIND_EVALUABLE': 12, 'FEDERATED_BLIND_EVALUABLE': 0}).

## 4. Honest boundaries

- BSkG3 against AME2020 defaults NONBLIND_REFERENCE; a blind GP residual cannot repair a nonblind base into blindness.
- FRDM95 fit membership is unknown for every target already known by AME1995: INELIGIBLE_UNKNOWN_PROVENANCE, never assumed blind.
- Combiners inherit their worst contributor; nonblind evidence is excluded from strict-blind subfederations, never reweighted away.
- Residual variants are not independent physics families; Tier 2 is not faked with wrappers.
- REAL_BLIND_GATE_NOT_EVALUABLE is an acceptable, honest result.

## 5. Next gate

WO-14 — Execute Evaluated-Data v2 Validation with separate REAL-BLIND and REAL-RECON result tracks; fewer than two blind physics families remain, so frontier physics claims additionally require Refittable Physics Backends / Historical Physics Model Builds — the blind definition is not weakened to compensate
