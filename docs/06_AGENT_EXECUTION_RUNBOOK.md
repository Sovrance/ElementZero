# Coding Agent Execution Runbook

## Non-negotiable working rules

1. Work from a clean branch/worktree.
2. Do not modify scientific behavior while extracting infrastructure unless a task explicitly requires it.
3. One task = one reviewable commit when practical.
4. Run the acceptance commands after every task.
5. Never use later nuclear truth to tune a historical benchmark model.
6. Never replace a failing certificate with a regenerated one merely to make CI green.
7. No inferred license. Ask the repository owner if publication licensing is required.
8. Preserve canonical serialization behavior until compatibility tests prove equivalence.
9. All equations in agent-generated docs must include an ASCII representation.
10. Treat Z>118 prediction as locked in this release.

## Branch sequence

Recommended:

```text
chore/gv-packaging-baseline
feat/physics-evidence-core-v0.1
refactor/gv-pec-compat
feat/zme-v0.2-foundation
feat/zme-b001
chore/zme-b001-real-data
```

## Task order

Execute `agents/task_manifest.json`. Summary:

```text
T01 baseline and hash
T02 Global Variables packaging/test patch
T03 PEC core extraction
T04 PEC certificate extraction
T05 PEC generic forward/no-leakage API
T06 PEC intervention API
T07 Global Variables compatibility migration
T08 Zero-Mass v0.2 package foundation
T09 ZME-B001 implementation
T10 official AME ingestion + historical run
T11 release validation and agent-readability audit
```

## T01 commands

```bash
sha256sum "Global-variables-main (2).zip"
python ci/run_all_certified.py
```

Record environment, Python version, dependency versions and manifest signature.

## T02

Apply the provided patch. Do not combine with PEC refactor.

```bash
git apply patches/global_variables_packaging_pytest.patch
python -m pytest -q
python ci/run_all_certified.py
```

Both must be green.

## T03

Create a standalone PEC package under its own repository or top-level workspace package. Port core modules, then run identity compatibility tests before changing Global Variables imports.

Required compatibility test concept:

```text
old_id = old_pir.content_id(payload)
new_id = pec.content_id(payload)
assert old_id == new_id
```

Use many payload forms.

## T04

Extract certificate integrity and degradation comparison from the Global Variables CI runner. Do not extract suite-specific benchmark discovery into PEC.

## T05

Do not copy the B9 transmon predictor into generic PEC. Implement the domain-neutral freeze/prediction/held-out objects supplied in the scaffold.

## T06

Port deterministic intervention ranking. Keep the first API small. Add probabilistic expected information gain only after tests define the semantics.

## T07

Migrate Global Variables through compatibility facades. The old benchmark suite must remain byte-equivalent in its committed certificates except for explicitly reviewed certificate-version migrations.

## T08

Create the Zero-Mass package with no direct dependency on Global Variables. It depends only on PEC and scientific libraries.

## T09

Implement ZME-B001 using normalized snapshots. Complete synthetic smoke tests first.

## T10

Acquire official AME historical source data from the authoritative Atomic Mass Data Center. Store raw source files in an immutable data cache, record SHA-256 and source URL/date, and implement edition-specific normalization. Do not scrape a third-party table as the canonical dataset.

## T11

Run:

```bash
python -m pytest -q
python scripts/validate_bundle.py
```

For the real repository, also run lint/type checks selected by the project and rerun historical experiments twice to verify deterministic scientific artifacts.
