# T05 - Generalize Forward Validation and No-Leakage API

## Objective

Replace the Global Variables B9-specific `pir.forward` concept with a domain-neutral historical-prediction contract in PEC.

## Important separation

Do not move this transmon-specific equation into generic PEC:

```text
E01 = sqrt(8 * EJ * EC) - EC
```

It remains Global Variables domain code.

PEC instead owns:

```text
KnowledgeFreeze
PredictionRecord
HeldOutObservation
ResidualComparison
PredictionLedger state
LeakageViolation
```

## KnowledgeFreeze

Must bind:

```text
cutoff date
allowed source hashes
forbidden source hashes
training subject IDs
feature policy ID
```

Training ID digest must be deterministic over sorted IDs.

## Ledger state machine

Implement explicit states, not an informal file marker in production:

```text
OPEN
PREDICTIONS_FINALIZED
TRUTH_UNLOCKED
SCORED
```

Allowed transitions:

```text
OPEN -> PREDICTIONS_FINALIZED
PREDICTIONS_FINALIZED -> TRUTH_UNLOCKED
TRUTH_UNLOCKED -> SCORED
```

Any other transition raises `BenchmarkStateError` or PEC equivalent.

## No-leakage design

The fit API gets training records only. A target manifest may carry identity metadata:

```text
nuclide_id
Z
N
A
```

It may NOT carry truth values or later-value uncertainty/status fields.

Later truth is parsed only after predictions are finalized.

File hashing of the later source before prediction is permitted because it binds the artifact without semantically exposing target values. Document this distinction.

## Negative tests

Required:

```text
target appears in training IDs -> fail
target manifest contains mass_excess_keV -> fail
truth source included in allowed training sources -> fail
truth unlock while ledger OPEN -> fail
score before truth unlock -> fail
prediction freeze ID mismatch -> fail
```

## Acceptance

All PEC tests pass and a tiny fake-domain example demonstrates a blind prediction followed by later truth unlock.
