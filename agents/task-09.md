# T09 - Implement ZME-B001

## Objective

Implement the first combined reproducible historical nuclear-mass prediction experiment.

## Stage 0: benchmark preparation

This stage may inspect both historical and later normalized snapshots solely to construct an identity-only target manifest.

Output fields allowed per target:

```text
nuclide_id
Z
N
A
```

Forbidden:

```text
mass_excess_keV
uncertainty_keV
later record status
any derived value using the later target mass
```

The target manifest records hashes of old and later snapshots so it cannot silently be reused against different data.

## Stage 1: blind fit

Read old snapshot. Select only old records eligible under the versioned ground-truth policy.

Create PEC KnowledgeFreeze and fit:

```text
ZME-SEMF-LS-v1
ZME-SEMF-GP-RESIDUAL-v1
```

Fit every preprocessing transform on training rows only.

## Stage 2: blind prediction

Read target identity manifest. Predict mass excess for each target without parsing later truth values.

Write:

```text
model_manifest.json
predictions.json or predictions.jsonl
prediction certificates
prediction ledger finalization artifact
```

Finalize ledger state.

## Stage 3: truth unlock

Only after finalization parse later normalized truth. Match by canonical nuclide ID, validate later ground-truth eligibility, then compare.

## Stage 4: scoring

Produce:

```text
MAE_keV
RMSE_keV
median absolute error
coverage 68/90/95
mean interval width
error versus training-support distance
```

Add NLPD if Gaussian density implementation is numerically safe.

## Stage 5: baseline comparison

Score SEMF alone and SEMF+GP separately. The residual model does not pass merely because it exists. Report difference with confidence/bootstrap analysis computed only from fixed test predictions after scoring.

## Stage 6: deterministic rerun

Run the exact benchmark twice in fresh output directories. Non-volatile scientific artifacts must match by hash.

If scikit-learn optimizer behavior is platform-sensitive, record platform/library version and define reproducibility tolerance rather than silently changing certificate identity.

## Leakage attack tests

Build malicious fixtures for every forbidden channel listed in the B001 spec. Tests must fail closed.

## Acceptance

Synthetic smoke run passes software gates. This does NOT authorize scientific claims. Scientific activation waits for T10 official AME ingestion.
