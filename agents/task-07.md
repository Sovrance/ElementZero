# T07 - Migrate Global Variables to PEC

## Objective

Make Global Variables consume the shared PEC package while preserving its public `pir` surface and all domain-specific behavior.

## Migration strategy

Do not delete `pir/` immediately.

Phase A:

```text
pir/canonical.py -> thin re-export from physics_evidence_core.canonical
pir/types.py -> re-export core types + Global Variables-only extensions if needed
pir/models.py -> re-export compatible classes
pir/namespaces.py -> re-export
pir/provenance.py -> re-export
pir/passes.py -> re-export
pir/runtime.py -> re-export or local adapter
```

Keep:

```text
pir/domains/
pir/symbolic/
pir/analyzers.py
pir/candidates.py
pir/diff.py
pir/fingerprints.py
```

owned by Global Variables.

## Import migration

Migrate internal imports in small batches. After each batch run:

```bash
python -m pytest -q
python ci/run_all_certified.py
```

## Forward compatibility

`pir.forward` must continue exposing the B9 functions expected by Global Variables tests. It may internally use PEC primitives, but do not replace its domain API with ZME concepts.

## Certificate compatibility

Compare regenerated certificates against T01 baseline. A hash difference in a committed certificate must be explained. Do not accept mass rewrite merely because code was reorganized.

## Circular dependency prohibition

Dependency direction must be:

```text
Global Variables -> PEC
Zero-Mass Element -> PEC
PEC -X-> Global Variables
PEC -X-> Zero-Mass Element
```

## Acceptance

- all Global Variables certified benchmarks pass;
- standard pytest bridge passes;
- PEC imports no Global Variables modules;
- representative old `pir` imports continue to work;
- no physical conjecture appears in PEC package metadata/docs.
