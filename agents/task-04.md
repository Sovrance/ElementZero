# T04 - Extract Certificate and Degradation Services

## Objective

Turn the generic certificate integrity ideas in `ci/run_all_certified.py` into PEC APIs without importing Global Variables benchmark discovery.

## Extract

Reusable concepts:

```text
canonical scientific content hash
volatile-field policy
certificate integrity verification
degradation comparison
runtime/library version manifest
input artifact hashes
```

Leave these Global Variables-specific concerns behind:

```text
tests/test_b*.py discovery
certificates/ directory assumptions
B13 special-case directories
benchmark subprocess command conventions
```

## Certificate semantics

A hash proves that a certificate body is unchanged. It does NOT prove the scientific claim is correct.

Create a documented certificate version, for example:

```text
PEC-PRED-1
```

A prediction certificate includes at least:

```text
prediction_id
subject_id
observable
knowledge_freeze_id
training_ids_sha256
model_id
model_manifest_sha256
feature_policy_id
prediction_mean
prediction_std
uncertainty_scope
domain_status
source hashes
random seed
```

## Identity policy

Explicitly define whether volatile fields such as `created_at` participate in content identity. The scaffold excludes them. If changing this policy, bump certificate version.

## Degradation tests

Port the spirit of Global Variables CI guard tests:

```text
changed timestamp only -> not degradation
small documented float jitter -> policy-dependent, tested
removed key -> degradation
FORCED -> REJECTED -> degradation
certification true -> false -> degradation
prediction/model identity changed -> degradation
```

Do not allow the degradation comparator to hide meaningful scientific changes behind broad tolerances.

## Global Variables adapter

Update the Global Variables CI runner to import PEC degradation helpers only after PEC tests are green. Keep its manifest format unchanged in this task unless an explicit migration is approved.

## Acceptance

- PEC certificate unit tests pass.
- Existing Global Variables CI guard tests pass.
- Existing committed Global Variables certificates show no unexplained degradation.
