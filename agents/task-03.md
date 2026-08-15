# T03 - Extract Physics Evidence Core

## Objective

Create `physics-evidence-core` v0.1 as an independent package containing only domain-neutral evidence machinery.

## Source-to-target map

Follow `docs/03_GLOBAL_VARIABLES_EXTRACTION_MAP.md` exactly.

First-pass source modules:

```text
pir/canonical.py
pir/types.py
pir/models.py
pir/namespaces.py
pir/provenance.py
pir/passes.py
pir/runtime.py
```

Do not copy `pir.domains`, symbolic physics implementations, atlas logic, or Global Variables conjectures.

## Package layout

Use the scaffold as the minimum target:

```text
physics-evidence-core/
  pyproject.toml
  src/physics_evidence_core/
    __init__.py
    canonical.py
    types.py
    models.py
    namespaces.py
    provenance.py
    passes.py
    runtime.py
  tests/
```

## Compatibility tests

Create a test harness that imports both old PIR and new PEC in isolation and compares canonical serialization and IDs for fixed vectors.

Minimum vectors:

```text
integer
float
Fraction(7, 1250)
Enum
nested dict
nested tuple/list
Artifact.to_dict()
Fact.compute_id()
```

Normative requirement:

```text
old_canonical_json(payload) == new_canonical_json(payload)
old_content_id(prefix, payload) == new_content_id(prefix, payload)
```

If not equal, do not paper over the difference. Either restore compatibility or create an explicit certificate-format migration design.

## DomainStatus extension

Add `DomainStatus` as a separate enum. It must not change EvidenceLevel semantics.

```text
INTERPOLATIVE
LOCAL_EXTRAPOLATION
REGIONAL_EXTRAPOLATION
HISTORICALLY_VALIDATED_EXTRAPOLATION
OUT_OF_DISTRIBUTION
EXTREME_EXTRAPOLATION
```

## Provenance negative tests

Require tests for:

```text
mutating existing fact ID -> AppendOnlyViolation
unknown parent -> error
cycle -> ProvenanceCycle
cross-namespace edge without transform -> IllegalNamespacePromotion
invalidated assumption -> dependent facts downgraded transitively
```

## Pass honesty tests

Verify:

```text
HEURISTIC + E0 -> rejected
SOUND + E3/E4 -> rejected
HEURISTIC + E3/E4 without warning -> rejected
```

## Acceptance

```bash
python -m pytest -q
python -m build
```

Both pass in a clean environment. Record wheel SHA-256.
