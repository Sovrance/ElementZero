# T02 - Global Variables Packaging Baseline

## Objective

Make the supplied research repository compatible with ordinary Python packaging/test tooling without changing scientific benchmark semantics.

## Implementation

Apply `patches/global_variables_packaging_pytest.patch` as its own commit.

The patch intentionally does NOT convert the entire script-style benchmark suite into pytest fixtures. It:

```text
production test_event() -> evaluate_event()
backward alias test_event = evaluate_event
alias marked __test__ = False
add root pyproject.toml
add one pytest bridge test that invokes ci.run_all_certified.run()
```

This is a migration bridge. Preserve it until benchmarks can be refactored independently with certificate-equivalence proof.

## Commands

```bash
git checkout -b chore/gv-packaging-baseline
git apply /path/to/global_variables_packaging_pytest.patch
python -m pytest -q
python ci/run_all_certified.py --build-dir build/post-packaging-baseline
```

## Review requirements

Compare pre/post certified manifests. Ignore documented volatile fields only. No scientific status, verdict, result surface, hard-constraint flag, or benchmark certificate content may degrade.

Verify backwards API compatibility:

```python
from b4_area_pipeline.pipeline import evaluate_event, test_event
assert evaluate_event is test_event
assert getattr(test_event, "__test__", True) is False
```

## Dependency declaration

Review the included pyproject dependencies against actual imports. Do not add unneeded packages. Do not invent a license. If a license exists in the real upstream repository but was absent from the supplied archive, use the authoritative upstream file only after owner review.

## Acceptance

```text
python -m pytest -q = PASS
python ci/run_all_certified.py = PASS
no certificate degradation
B4 demo/falsifier behavior unchanged
working tree contains only packaging/test-discovery changes
```
