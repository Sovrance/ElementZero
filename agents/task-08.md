# T08 - Create Zero-Mass Element v0.2 Package

## Objective

Create the nuclear-domain package that depends on PEC but not on Global Variables.

## Minimum modules

```text
zero_mass_element/
  data_model.py
  io.py
  physics.py
  models/
    semf.py
    gp_residual.py
  benchmark/
    b001.py
  metrics.py
  cli.py
```

Use the scaffold as executable reference, then harden it.

## Data model

Canonical nuclide identity:

```text
A = Z + N
nuclide_id = "Z{Z}-N{N}"
```

Reject inconsistent A or ID at construction.

## Normalized data contract

Implement `schemas/nuclear_observation.schema.json`. Preserve:

```text
raw source hash
source edition
release date
raw evaluator status
normalized ground_truth_eligible flag
normalizer version
raw source line or source span where practical
```

## SEMF implementation

Implement and test the ASCII equation in `docs/01_ZME_V0.2_ENGINEERING_SPEC.md`. Refit coefficients per historical snapshot.

Unit tests must cover:

```text
design matrix terms
pairing sign
mass-excess <-> binding-energy round trip
coefficient determinism
```

## GP residual model

Preprocessing is training-only. Store scaler parameters and kernel after fit in model manifest.

Never fit scaler or hyperparameters using later truth.

GP optimizer may optimize marginal likelihood on old training data. If using cross-validation, folds must be entirely within old training data.

## CLI

Allowed v0.2 commands:

```text
b001-prepare-targets
b001
validation/report commands
```

Do not expose a normal Z=154 prediction command in this release.

## Acceptance

Package tests pass in a clean env with PEC installed. CLI help clearly labels target preparation as UNBLINDED benchmark preparation.
