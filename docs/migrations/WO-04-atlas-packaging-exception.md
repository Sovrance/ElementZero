# WO-04 exception — Atlas PIR packaging overlay stays temporarily approved

Status: Approved temporary exception
Exception ID: `WO-04-ATLAS-PACKAGING-OVERLAY-EXCEPTION-v1`
Date: 2026-08-15
Work order: `docs/work_orders/v0.3/04_WO_ATLAS_UPSTREAM_PACKAGING.md` (section 8, rollback)

## Decision

WO-04 Part A (the upstream `Sovrance/Atlas` packaging pull request) is **not
merged**. WO-04 section 8 allows exactly two ways forward, and this document
selects the second one:

- the upstream package is clean, **or**
- a formally documented exception approves the immutable overlay.

This document is that exception. It unblocks WO-05 and everything downstream of
it (WO-06, WO-07, WO-08) without moving ElementZero onto a mutable Atlas ref.

## Pin

```text
atlas_repository = https://github.com/Sovrance/Atlas
atlas_pir_ref    = 31d76d094f1206e64a6920da4775d0a684618357
distribution     = sovrance-atlas-pir
python_import    = pir
```

The pin is unchanged by this exception. `atlas.lock.json`,
`pyproject.toml [project.dependencies]`, and
`pyproject.toml [tool.elementzero.atlas]` all still carry the same
40-character commit SHA, and `elementzero.atlas_pin.assert_pin_consistent`
keeps failing the build if they diverge.

## Why the upstream PR is blocked

The reviewed Atlas baseline at the pinned SHA has no root `pyproject.toml`, so
`pip install -e .` against the clone cannot resolve a distribution without
packaging metadata. Fixing that requires a commit in `Sovrance/Atlas`.

The agent executing WO-04 has **read-only** GitHub access (`gh` is read-only in
this environment) and therefore cannot push a branch, open a pull request, or
merge one in `Sovrance/Atlas`. The upstream work is blocked on write access, not
on engineering content. The intended upstream change is fully specified in
`docs/work_orders/v0.3/04_WO_ATLAS_UPSTREAM_PACKAGING.md` sections 1-5:

1. add a root `pyproject.toml` publishing only `pir` and `pir.*` as
   `sovrance-atlas-pir`,
2. verify a clean editable install plus the documented public imports,
3. rename the `b4_area_pipeline.pipeline.test_event` production callable to
   `evaluate_event` so pytest stops collecting it,
4. keep `python -m pytest -q` and `python ci/run_all_certified.py` green,
5. optionally tag `pir-v0.1.0`.

## What is approved

`tools/ensure_atlas_pir.py` may, **only while this exception is open**:

- clone the immutable pinned SHA into `.cache/atlas-pir/<sha>/`,
- write the recommended `sovrance-atlas-pir` `pyproject.toml` into that clone
  when the pinned commit does not already track one,
- stamp `.cache/atlas-pir/<sha>/.elementzero_overlay_exception` so the overlay
  is discoverable on disk and in CI logs,
- print a WARNING block naming this document.

Behaviour that stays forbidden:

- using `main`, `master`, `HEAD`, `latest`, or any non-SHA Atlas ref,
- copying or vendoring `pir/` into `src/elementzero/`,
- importing Atlas benchmark modules (`b1_*`, `b4_*`, `generator`, `canon`,
  `atlas_engine`, ...) from ElementZero production code,
- treating Atlas scientific conjectures as nuclear priors,
- silently mutating the Atlas clone with no warning and no stamp.

`tools/ensure_atlas_pir.py --no-overlay` is the WO-04 section 6 option B
verifier: it installs the pin only if upstream is already packaged and exits
non-zero instead of writing metadata. It is the command to use once the upstream
PR lands, and it is how CI can prove the exception is no longer needed.

## Overlay self-retirement

The tool reads the committed tree of the pinned commit
(`git ls-tree -r --name-only <sha>`) rather than the working directory, so a
previously written overlay can never masquerade as upstream packaging. When a
future pin does track `pyproject.toml`, the tool installs it untouched and
removes any stale exception stamp.

## Scope granted to WO-05 and later

WO-05 (`preregister EZ-B001-A`) and all downstream work orders are explicitly
**allowed to proceed** under this exception. The evidence chain is unaffected:

- prediction certificates, freezes, and Atlas facts still record
  `atlas_pir_ref = 31d76d094f1206e64a6920da4775d0a684618357`,
- the contract tests (`tests/unit/test_atlas_contract.py`) still assert
  `pir.__version__ == 0.1.0`, pin consistency, and the required public imports,
- the import firewall (`tests/unit/test_import_firewall.py`) still forbids
  Atlas research modules in ElementZero production code,
- the overlay changes packaging metadata only. It cannot change a scientific
  result, because it adds no Python code to `pir`.

## Exit criteria

This exception closes when all of the following hold:

1. an upstream Atlas commit tracks a root `pyproject.toml` publishing
   `sovrance-atlas-pir`,
2. `atlas.lock.json` and `pyproject.toml` are bumped to that immutable SHA,
3. `python tools/ensure_atlas_pir.py --no-overlay` succeeds,
4. no `.elementzero_overlay_exception` stamp is produced by a clean install,
5. `docs/adr/ADR-0001-atlas-pir-boundary.md` and
   `docs/architecture/atlas-integration.md` drop the exception note.

Until then the exception is reported, not hidden: the tool warns on every run
and the stamp stays on disk.
