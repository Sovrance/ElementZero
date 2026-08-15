# Supplied Global Variables Source Review

## Snapshot reviewed

Input artifact:

```text
Global-variables-main (2).zip
```

The bundle manifest records its SHA-256.

## Reusable architecture found

The strongest directly reusable areas are:

```text
pir/models.py
pir/types.py
pir/canonical.py
pir/namespaces.py
pir/provenance.py
pir/passes.py
pir/runtime.py
pir/forward.py (concept; implementation domain-specific)
pir/intervention_search.py
ci/run_all_certified.py (certificate/degradation concepts)
```

## Particularly valuable behaviors

- frozen dataclasses;
- content-addressed identity;
- exact Fraction serialization;
- append-only facts;
- cross-namespace transform requirement;
- assumption-taint invalidation;
- SOUND versus HEURISTIC honesty;
- deterministic analyzer ordering;
- analyzer quarantine;
- held-out provenance field `held_out_reused_in_fit`;
- deterministic intervention ranking;
- certificate degradation guard;
- run manifest with input/test/certificate hashes and environment versions.

## Current forward module limitation

`pir/forward.py` is not generic despite the generic filename. It hard-codes the B9 transmon relationship:

```text
E01 = sqrt(8 * EJ * EC) - EC
anharmonicity = -EC
```

PEC therefore extracts the no-leakage/forward-comparison concept, not that domain predictor.

## Current intervention limitation

`pir/intervention_search.py` computes discrete outcome partition metrics. This is good for PEC v0.1, but future nuclear experimental design requires continuous predictive distributions and expected information gain under measurement noise.

## Verified test behavior

Original snapshot:

```text
python -m pytest -q
-> ERROR: fixture 'samples' not found for imported b4_area_pipeline.pipeline.test_event
```

Original scientific runner:

```text
python ci/run_all_certified.py
-> PASS
```

Patched copy using this bundle's patch:

```text
python -m pytest -q
-> PASS through certified-suite pytest bridge
```

## Packaging finding

No root packaging metadata or obvious top-level license file was found in the supplied root. A pyproject is included in the tested patch. Licensing remains an owner decision.
