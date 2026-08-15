# Global Variables Packaging, Test Discovery, and Migration Patch

## Verified current behavior

On the supplied source snapshot:

```text
python -m pytest -q
```

fails because `tests/test_b4.py` imports a production function named `test_event`. Pytest sees the imported name and tries to execute it as a test, treating its `samples` argument as a fixture.

The repository's own scientific runner:

```text
python ci/run_all_certified.py
```

passes on the supplied snapshot.

Therefore this is primarily a Python test-discovery/tooling mismatch, not evidence that the certified B4 calculation fails.

## Tested patch

The bundle includes:

```text
patches/global_variables_packaging_pytest.patch
```

It performs four changes:

1. Rename production `test_event()` to `evaluate_event()`.
2. Keep a backward-compatible `test_event` alias marked `__test__ = False`.
3. Update B4 benchmark imports to use `evaluate_event`.
4. Add `pyproject.toml` plus a pytest bridge that invokes the existing certified runner.

Why a bridge instead of immediately renaming all benchmark functions?

The benchmark suite is script-oriented and uses ordered functions such as `t1_*`, `t2_*`, sometimes passing returned values explicitly in `__main__`. Turning every one into native pytest fixtures in the same extraction release would alter semantics and create unnecessary regression risk.

The bridge makes ordinary pytest a supported entry point while preserving the scientific runner exactly.

## Verified patched behavior

The patch was applied to a copy of the supplied repository and tested with:

```text
python -m pytest -q
```

Result at bundle construction:

```text
1 passed
```

The single pytest test delegates to the certified suite and requires its manifest to be PASS with no failure and no degradation.

## Agent application instructions

From a clean Global Variables checkout matching the supplied snapshot:

```bash
git checkout -b chore/pec-extraction-foundation
git apply /path/to/patches/global_variables_packaging_pytest.patch
python -m pytest -q
python ci/run_all_certified.py
```

Commit this patch separately from PEC extraction so any failure can be bisected.

## Packaging follow-up

The supplied root does not contain a root `pyproject.toml`, setup file, requirements lock, or obvious top-level license file. The included patch adds project metadata/dependency declaration, but the repository owner must choose/confirm licensing before public package publication. Coding agents MUST NOT invent a license.

After the first packaging commit, add a lock strategy compatible with your environment, for example `uv.lock` or a pinned constraints file. Do not commit a lock generated on a contaminated environment without reviewing platform markers.
