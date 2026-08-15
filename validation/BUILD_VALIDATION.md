# Build and Validation Record

## Status

```text
BUNDLE_VALIDATION: PASS
```

## Global Variables supplied snapshot

Observed before patch:

```text
python -m pytest -q
-> error during collection: imported b4_area_pipeline.pipeline.test_event is collected and requests fixture "samples"
```

Observed native scientific runner:

```text
python ci/run_all_certified.py
-> PASS
```

Patched copy:

```text
python -m pytest -q
-> 1 passed
```

The single native pytest test is a bridge that executes the existing certified benchmark runner and requires no failures or certificate degradations. The patch also adds root package metadata and package discovery rules.

An editable package import check was performed with build isolation disabled because the artifact environment has no Internet access:

```text
pip install -e . --no-deps --no-build-isolation
import pir, b4_area_pipeline, measurement_interface
-> PASS
```

## Physics Evidence Core scaffold

The bundle validator runs the PEC pytest suite using the local source tree.

```text
PEC scaffold tests -> PASS
```

The tests cover held-out comparison, certificate verification and a deliberate target-in-training leakage failure.

## Zero-Mass Element scaffold

The bundle validator runs the ZME pytest suite using the local PEC and ZME source trees.

```text
ZME scaffold tests -> PASS
```

ZME-B001 uses a separate unblinded target-manifest preparation step. The target manifest is checked to contain identity metadata only and is rejected if truth-bearing fields such as `mass_excess_keV` are present.

## Synthetic smoke result

This result tests software behavior only. It is NOT a scientific nuclear-mass result.

```text
n_targets = 18
MAE_keV = 37.41448538208877
RMSE_keV = 63.407676029782
coverage_68 = 0.5
coverage_90 = 0.7777777777777778
coverage_95 = 0.8888888888888888
```

The fixture was deliberately generated from an SEMF-like function, so good error is expected and has no scientific evidentiary meaning.

## Deterministic rerun check

Two fresh runs with identical fixture data, target manifest, code and seed produced matching SHA-256 values for:

```text
model_manifest.json
predictions.json
prediction_certificates.json
LEDGER_FINALIZED
split_manifest.json
scored_predictions.json
metrics.json
run_manifest.json
```

## Documentation readability audit

`python scripts/validate_bundle.py` checks:

```text
all JSON parses
all required task files exist
Markdown code fences are balanced
normative math text blocks are ASCII encodable
PEC tests pass
ZME tests pass
v0.2 CLI contains no hyperheavy/Z=154 production command
```

All checks passed at package construction.
