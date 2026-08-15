# ElementZero Engineering Work Orders 01-10 v0.3

Status: IMPLEMENTATION HANDOFF
Date: 2026-08-15
Input repository reviewed: ElementZero-main.zip
Canonical Python package: elementzero
Canonical upstream evidence substrate: Sovrance/Atlas PIR
Primary near-term objective: produce the first defensible historical nuclear-mass prediction result.

## Governing rule

Do not add new speculative nuclear architecture until Work Orders 01-08 are complete.

The next phase is not "design more." It is:

    make the data correct
    -> make the evidence graph complete
    -> make scoring scientifically adequate
    -> make Atlas a clean upstream dependency
    -> preregister EZ-B001-A
    -> run and seal predictions
    -> repeat the historical epochs
    -> publish the benchmark honestly
    -> begin geographic extrapolation
    -> begin hidden-shell rediscovery

## Dependency graph

    WO-01 Data correctness
          |
          +--------+
          |        |
          v        v
    WO-02 Evidence graph
    WO-03 Scoring/UQ
          |        |
          +---+----+
              |
              v
    WO-04 Atlas upstream packaging
              |
              v
    WO-05 Preregister EZ-B001-A
              |
              v
    WO-06 Run 2003 -> 2012
              |
              v
    WO-07 Run 2012 -> 2016 -> 2020
              |
              v
    WO-08 Historical Benchmark Report
              |
              v
    WO-09 EZ-B002 Geographic Holdout
              |
              v
    WO-10 EZ-B003 Hidden Shell Challenge

WO-02 and WO-03 may be implemented in parallel after WO-01 if they do not edit the same files.
WO-05 MUST NOT begin until WO-01 through WO-04 are merged and green.
WO-06 MUST NOT score truth before predictions have been finalized and sealed.

## Current repository observations that drive these work orders

The reviewed repository already contains:

- src/elementzero/data/amdc edition adapters
- ElementZero -> Atlas adapter
- KnowledgeFreeze
- identity-only target manifests
- blind prediction stage
- ledger finalization stage
- separate scoring stage
- leakage tests
- reproducibility tests
- SEMF least-squares model
- direct Gaussian process model
- SEMF + GP residual model
- GitHub Actions CI

Important gaps found during review:

1. AME2020 uses a different fixed-width numeric format from AME2003/2012/2016.
2. Current record semantics overstate "experimental" when a row is merely non-estimated in an evaluated mass table.
3. prepare_targets subtracts every old-edition identity, including old estimated rows; this removes a scientifically important target class.
4. Prediction facts currently depend on only the first observation fact rather than a compact model-fit lineage object.
5. Validation facts are created without a complete persisted dependency chain to predictions, truth, and finalization.
6. Scoring is currently MAE/RMSE/90% coverage/95% coverage only.
7. Atlas PIR is pinned, but ElementZero uses a temporary packaging overlay because the reviewed Atlas baseline has no root install metadata.
8. VERSION and several legacy documents still contain old Zero-Mass Element / Physics Evidence Core names.

## PR policy

Use one work order per PR unless the work order explicitly requires an upstream Atlas PR plus a downstream ElementZero PR.

Every PR must include:

- implementation
- tests
- updated schemas if required
- migration note
- no unexplained generated files
- exact commands used to validate the change

Do not combine performance tuning with protocol changes.

## Scientific result policy

A bad model result is not an engineering failure.

Engineering passes when:

- the protocol is correct,
- leakage is prevented,
- provenance is complete,
- results reproduce,
- uncertainty is scored honestly.

Do not modify a model after seeing a scored historical epoch and then report the modified result under the same preregistration.

If a protocol or model changes after scoring, bump the protocol version and rerun ALL comparable epochs.

## ASCII-first math

Normative equations in these work orders are plain ASCII.

Examples:

    A = Z + N

    residual = observed_mass - physics_mass

    predicted_mass = physics_mass + predicted_residual

    RMSE = sqrt(mean((prediction - truth)^2))

No implementation decision depends on rendered LaTeX.
