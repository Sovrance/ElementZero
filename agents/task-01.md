# T01 - Baseline and Provenance Freeze

## Objective

Establish an immutable before-state for the supplied Global Variables repository and the Zero-Mass v0.1 baseline. No refactoring begins until this evidence exists.

## Steps

1. Create a clean worktree or clone of Global Variables at the exact supplied revision.
2. Record SHA-256 for the source archive and, if Git metadata exists in the authoritative repository, record commit SHA and branch.
3. Record:

```text
python version
OS/platform
numpy
scipy
mpmath
jsonschema
h5py
```

4. Run the native scientific certification runner:

```bash
python ci/run_all_certified.py --build-dir build/pre-pec-baseline
```

5. Preserve `build/pre-pec-baseline/run_manifest.json` as a release artifact.
6. Run ordinary pytest and record the expected pre-patch failure without changing files:

```bash
python -m pytest -q
```

7. Confirm the failure is the B4 imported `test_event` collection problem described in `docs/legacy/04_GLOBAL_VARIABLES_MIGRATION_AND_PATCH.md`. If the failure differs, stop and investigate snapshot drift.
8. Hash all committed `certificates/*.json` and `b13_cdl/certificates/*.json`.
9. Create `migration/baseline_manifest.json` containing all hashes and environment information.

## Do not

- regenerate/replace committed certificates;
- change dependency versions to make a failure disappear;
- normalize timestamps in the baseline artifacts;
- make any source edit in this task.

## Acceptance

```text
native certified runner = PASS
baseline manifest exists
certificate hashes recorded
ordinary pytest failure captured and explained
working tree unchanged
```

## Deliverable report

State exact source identity, commands, runner signature, number of certified benchmarks, pytest failure text, and any divergence from the bundle review.
