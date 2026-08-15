# T10 - Official AME Historical Ingestion and Real ZME-B001 Runs

## Objective

Replace synthetic smoke data with authoritative historical mass-evaluation snapshots and execute the first real Time-Machine benchmarks.

## Source authority

Use the Atomic Mass Data Center as canonical source:

```text
https://www-nds.iaea.org/amdc/
```

Acquire the historical editions required by the benchmark and their format/readme documentation.

## Raw data policy

For every downloaded source file:

```text
save bytes unchanged
record source URI
record acquisition timestamp
record edition
record SHA-256
record local immutable artifact ID
```

Never manually edit a raw file.

## Parser development

AME formats/flags can differ by edition. Implement edition-specific parsers behind one normalized interface.

For each edition, commit parser fixtures copied from a small number of official source lines where redistribution is permitted; otherwise store line hashes/locations and use local test assets according to source terms.

Tests must demonstrate at least:

```text
one direct/eligible measurement classification
one extrapolated/non-eligible classification
one uncertainty parse
one nuclide identity parse
```

Do not guess flag semantics. Use edition documentation.

## Ground-truth policy review

Create a human-reviewable document:

```text
data/policies/AME2003-GT-v1.md
...
```

It states exactly which raw statuses become `ground_truth_eligible=true` and why.

## Historical checkpoint runs

Execute separately:

```text
2003 -> 2012
2012 -> 2016
2016 -> 2020
```

Primary track: DISCOVERY_HOLDOUT.
Secondary revision track may be run but reported separately.

## Pre-registration

Before scoring each real checkpoint, freeze:

```text
target identity manifest
feature policy
model IDs
kernel family
metrics
gates
random seeds
```

Do not alter them in response to test performance. Any changed method becomes a new benchmark version.

## Report

For each checkpoint include:

```text
number of train nuclides
number of targets
SEMF metrics
SEMF+GP metrics
coverage
calibration plot data
error vs distance
largest misses
model uncertainty vs actual error
source/policy hashes
```

Large misses are scientifically useful. Do not remove them as outliers unless a predeclared data-integrity rule is triggered.

## Acceptance

A real B001 release artifact is self-contained enough that another agent can reproduce it from the raw source hashes, code commit, dependency lock and run manifest.
