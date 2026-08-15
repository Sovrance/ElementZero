# Global Variables Extraction Map

This map is based on the supplied `Global-variables-main (2).zip` and references exact files included under `reference/global_variables_reusable_source/`.

## Tier 1: direct core extraction

| Global Variables file | PEC target | Action |
|---|---|---|
| `pir/canonical.py` | `physics_evidence_core/canonical.py` | Copy behavior; preserve deterministic Fraction serialization and content IDs. |
| `pir/types.py` | `physics_evidence_core/types.py` | Copy locked vocabularies. Add domain-distance enum separately. |
| `pir/models.py` | `physics_evidence_core/models.py` | Preserve immutable dataclasses and validation. Keep domain-independent classes only. |
| `pir/namespaces.py` | `physics_evidence_core/namespaces.py` | Preserve explicit cross-namespace transform rule. |
| `pir/provenance.py` | `physics_evidence_core/provenance.py` | Preserve append-only storage, cycle detection, assumption invalidation. |
| `pir/passes.py` | `physics_evidence_core/passes.py` | Preserve SOUND/HEURISTIC honesty enforcement. |
| `pir/runtime.py` | `physics_evidence_core/runtime.py` | Preserve deterministic pass scheduling and quarantine behavior. |

## Tier 2: extract concept, refactor implementation

| Source | Reason | PEC design |
|---|---|---|
| `pir/forward.py` | Hard-coded to transmon B9 realization. | Extract the held-out/no-reuse concept into generic `KnowledgeFreeze`, `PredictionRecord`, and `compare_held_out`. Keep B9 predictor in Global Variables. |
| `pir/intervention_search.py` | Algorithm is generic but vocabulary is research-specific. | Keep deterministic discrete scorer, expose as PEC experiment-design API. |
| `ci/run_all_certified.py` | Contains highly reusable hashing/degradation logic mixed with Global Variables suite discovery. | Extract canonical certificate hashing/degradation functions. Leave suite discovery in Global Variables. |
| `tests/test_ci_guard.py` | Strong regression ideas. | Port benign-churn/corruption/signature tests to PEC. |

## Tier 3: remain Global Variables owned

Do not move these into PEC v0.1:

```text
pir/domains/
pir/symbolic/
atlas_engine/
generator/
measurement_interface/ domain policies
b1_* through b13_*
s2_*, s3_*, s4_*
conjectures-v0.1.md
```

PEC can later provide interfaces they implement.

## Compatibility migration

Do not perform a flag-day rewrite of Global Variables imports.

Recommended migration:

```text
Phase 1:
  create physics_evidence_core package
  run PEC tests

Phase 2:
  make Global Variables depend on PEC
  keep `pir` package as compatibility facade

Phase 3:
  change internal imports module-by-module
  from pir import FactStore
  -> from physics_evidence_core import FactStore

Phase 4:
  after two green releases, deprecate duplicate implementations
```

During Phase 2, `pir/__init__.py` may re-export PEC classes, but domain modules remain under `pir.domains`.

## Identity compatibility gate

For representative objects, old and new canonical IDs MUST be identical when payloads are identical.

Test vectors must cover:

```text
Fraction
float
Enum
nested dict/list/tuple
Artifact
Fact content/provenance skeleton
```

If IDs differ, extraction fails until an intentional certificate-version migration is designed.
