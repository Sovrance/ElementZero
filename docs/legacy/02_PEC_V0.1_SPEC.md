# Physics Evidence Core v0.1 Specification

## Purpose

Physics Evidence Core (PEC) extracts the reusable epistemic substrate from Global Variables without importing that project's physical conjectures.

## Extraction philosophy

Three categories are used.

### A. Extract with behavior preserved

- canonical content addressing;
- core enums and evidence levels;
- Artifact/Event/Fact/Hypothesis/Intervention/ProvenanceRecord;
- namespace-transform discipline;
- append-only FactStore;
- pass honesty contracts;
- deterministic analyzer runtime.

### B. Generalize during extraction

- `pir.forward`: current implementation is transmon/B9 specific. Replace it in PEC with a domain-neutral KnowledgeFreeze and held-out comparison API. Leave the transmon realization in Global Variables.
- `pir.intervention_search`: keep deterministic discrete scoring in v0.1, but make its API generic. Add probabilistic expected-information-gain later.
- certificate/degradation code: extract from `ci/run_all_certified.py` into a reusable certificate module while retaining the old runner through imports/shims.

### C. Do not extract into PEC

- `pir.domains/*`;
- `pir.symbolic/*` until a later generic symbolic interface is specified;
- Global Variables conjectures;
- atlas promotion rules;
- B1-B13 domain benchmark logic;
- electroweak, gravity, circuit, GNS, QNEC or constants-specific code.

## PEC evidence axes

Preserve two orthogonal coordinates:

```text
PirLevel: representation abstraction
EvidenceLevel: warrant strength
```

Do not derive one from the other.

Recommended nuclear mapping:

```text
L0 = raw source artifact
L1 = measurement/evaluation/normalization event
L2 = derived scientific fact
L3 = hypothesis/model family

E0 = exact theorem/arithmetic
E1 = interval-certified numerical result
E2 = statistical inference with stated coverage
E3 = simulation-conditioned result
E4 = proxy/indirect/extreme extrapolation
```

## Required Zero-Mass extension

Add a domain-distance classification outside the evidence level:

```text
INTERPOLATIVE
LOCAL_EXTRAPOLATION
REGIONAL_EXTRAPOLATION
HISTORICALLY_VALIDATED_EXTRAPOLATION
OUT_OF_DISTRIBUTION
EXTREME_EXTRAPOLATION
```

This MUST remain orthogonal to E0-E4.

## Certificate contract

A certificate is a content-addressed statement binding:

```text
claim/prediction
input source hashes
knowledge cutoff
training identity digest
model identity
model parameters or parameter artifact hash
code version
runtime versions
random seed
uncertainty scope
result
```

A certificate is not a proof merely because it has a hash. The hash proves artifact identity/integrity only.

## Append-only rule

A stored fact or certificate cannot be silently overwritten. Corrections create a new object plus an explicit relation to the superseded object.

## Assumption invalidation

PEC preserves Global Variables' useful rule: if an assumption is invalidated, dependent facts are downgraded transitively rather than deleted.

For Zero-Mass, examples include:

```text
assumption: "AME status parser v1 correctly classified extrapolated records"
assumption: "normalization constants snapshot X used"
assumption: "GP residual is approximately Gaussian"
```

## Measurement-interface separation

Zero-Mass must represent this chain explicitly:

```text
physical nucleus
-> apparatus / experiment
-> raw observation
-> calibration
-> inferred observable
-> evaluated nuclear-data record
-> normalized ML record
```

An evaluated number is never automatically promoted to "direct measurement" without provenance supporting that claim.
