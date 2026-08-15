# PIR Specification v0.1 — the evidence substrate

**Status:** Stage 1 (Substrate). Normative for the `pir/` package.
**Companion:** `docs/adr/ADR-PIR-0001.md` (decisions), `docs/verifier-ops-v0.1.md`
(frozen verifier ops), `pir/schema/*.schema.json` (machine-checkable schemas),
`examples/pir/minimal_circuit.json` (worked example).

PIR (Physics Intermediate Representation) is an **evidence substrate, not a
proof engine**. It records what was measured, what was done, what was certified,
and which grammars remain in play — each fact carrying orthogonal representation
(L) and warrant (E) coordinates, full provenance, and assumption taint. The
atlas engine never reads raw datasets directly; it reads certified PIR facts.
The mathematics that *decides* verdicts lives in the B1–B12 benchmarks and the
verifier ops; PIR is where their inputs, outputs, and dependencies are stored
honestly.

## 1. The two orthogonal axes

Every fact carries both, and neither derives the other (ADJUDICATION #4):

| Axis | Field | Values | Meaning |
|---|---|---|---|
| Representation | `pir_level` | L0, L1, L2, L3 | raw records → operational acts → structural facts → candidate grammars |
| Warrant | `evidence_level` | E0–E4 | exact (E0) → interval (E1) → statistical (E2) → simulation (E3) → proxy (E4); SPEC §3 |

A fact also declares a **layer** (`UNIVERSAL` / `DOMAIN` / `MEASUREMENT`; SPEC §2)
and a **namespace** (below).

## 2. Object model (`pir/models.py`)

- **Artifact** (L0) — immutable, content-addressed evidence in namespace `raw`.
  No theoretical labels, no inferred universal claims (loader-enforced).
- **Event** (L1) — one act-op (`PREPARE … MEASURE … COMPOSE`) grounded in an
  artifact, with typed, unit-bearing ports and explicit uncertainty.
- **Fact** (L2) — an append-only derived claim. Carries the full provenance
  quintet (analyzer id+version, dependency fact IDs, assumption taint, source
  spans, evidence level, pir level, layer, namespace, status) plus an optional
  SPEC-locked `verdict`. Reserves `witness` and `impossibility_certificate` for
  the Stage-2 symbolic bridge.
- **Hypothesis** (L3) — a competing explanatory family, retained in parallel
  (never silently pruned), with `candidate_class` *taxonomy* tags and two-hash
  fingerprint slots.
- **Intervention** — a declared experiment; observational equivalence is defined
  *relative to a declared intervention set* (SPEC §5, ADJUDICATION #6).
- **ProvenanceRecord** — PROV-O core (Entity/Activity/Agent), append-only.

## 3. Locked vocabularies (`pir/types.py`)

- **Verdict** (SPEC §4/§6, LAW): `FORCED, PERMITTED, REJECTED, NONIDENTIFIABLE,
  OBSERVATIONALLY_EQUIVALENT, APPARATUS_LIMITED, REPRESENTATION_DEPENDENT,
  AMBIGUOUS`. These are the ONLY strings a `verdict` accepts.
- **CandidateClass** (taxonomy, never a verdict): `GLOBAL_CANDIDATE,
  TOPOLOGICAL_CANDIDATE, HIDDEN_COMMON_CAUSE_CANDIDATE, REPRESENTATION_ARTIFACT,
  NOT_DETECTED`. Lives only on `hypothesis.candidate_class`.
- **Namespaces**: `raw, apparatus, operational, domain, latent, gauge,
  invariant, global, effective, analyst`.
- **Op families**: 16 act-ops and 6 verifier-ops (see verifier-ops doc).

## 4. Invariants the substrate enforces

1. **Append-only** — no pass mutates or deletes another pass's fact; conflicts
   are stored (`AppendOnlyViolation`).
2. **Dual coordinates** — `pir_level` ⟂ `evidence_level`, both mandatory.
3. **Verdict lock** — a candidate-class label in `verdict` raises.
4. **SOUND/HEURISTIC honesty** — SOUND ⇒ E0–E2; HEURISTIC ⇏ E0; HEURISTIC at
   E3/E4 ⇒ non-empty located `warnings[]`.
5. **Provenance quintet** — every derived fact carries analyzer id+version,
   dependency IDs, assumption taint, source spans, and the four coordinate
   fields.
6. **Namespace transforms** — cross-namespace dependencies require a typed
   transform; implicit promotion raises (`IllegalNamespacePromotion`).
7. **L0 purity** — raw artifacts carry no inferred universal claims.
8. **Invalidation traversal** — invalidating an assumption downgrades every
   transitively dependent fact via appended records, deleting nothing.
9. **Hash-stable canonical JSON** — sorted keys, `Fraction` as `"p/q"` strings,
   non-finite floats rejected.
10. **B1–B12 untouched** — no atlas edits, no verdict changes.
11. **CI fails on degradation** — see the CI section and ADR D8.
12. **Measurement interface** — DOMAIN/MEASUREMENT facts must name their 𝖬.
13. **Similarity ⟂ confidence** — reported as separate numbers with a named
    correlator (BinDiff discipline).

## 5. Provenance and invalidation (`pir/provenance.py`)

The `FactStore` is append-only and content-addressed. It refuses cyclic
dependencies (`ProvenanceCycle`), guards cross-namespace promotions, and
implements `invalidate_assumption(assumption_id, reason)`:

> find every fact that names the assumption OR transitively depends on one that
> does; append a `DowngradeRecord` (preserving prior status) and swap each to a
> `DOWNGRADED` copy. Nothing is deleted.

## 6. Pass registry (`pir/passes.py`)

A pass declares `(id, version, SOUND|HEURISTIC, fn)`. `PassRegistry.run` executes
the pass and validates every emitted fact against the honesty contract before it
reaches a caller or the store. Stage 2's dependency-resolved analyzer runtime
(P3) builds on this contract.

## 7. Schemas and validation

Six Draft-2020-12 schemas under `pir/schema/` encode the constraints. Because
the substrate and CI must run on a clean checkout, validation uses a vendored,
auditable subset validator (`pir/jsonschema_mini.py`); the real `jsonschema`
package, when installed, is used as a cross-check. All six schemas validate
`examples/pir/minimal_circuit.json`.

## 8. CI (`ci/run_all_certified.py`)

Reruns `tests/test_b*.py`, captures regenerated certificates to `build/ci/`,
restores the committed certificates, and diffs with the degradation predicate
(ADR D8). Emits a self-hash–signed manifest (pinned seed, library versions,
per-file content hashes) and exits nonzero on any failure or degradation.
`tests/test_ci_guard.py` proves it goes green on the current repo and red on a
synthetically corrupted certificate.

## 9. Scope and progress

Stage 1 (substrate): schemas, models, provenance, pass registry, verifier-op
reference, CI — complete.

Stage 2 / Stage 3 (analysis + forward loop) — implemented, all additive over the
substrate, no benchmark/verdict/certificate/atlas change:

| Item | Module(s) | Test |
|---|---|---|
| **P2** B9 lowering + Circuit Domain Semantics (4 contracts) + structural graph | `pir/domains/b9.py`, `pir/domains/circuit_semantics.py` | `tests/test_pir_b9_lowering.py` |
| **P3** analyzer runtime + 3 priority analyzers | `pir/runtime.py`, `pir/analyzers.py` | `tests/test_pir_runtime.py` |
| **P4** symbolic constraint bridge (exact SAT/UNSAT, witness + Farkas) | `pir/symbolic/` | `tests/test_pir_symbolic.py` |
| **P5a** candidate lattice + GVAR rules | `pir/candidates.py` | `tests/test_pir_candidates.py` |
| **P5b** two-hash fingerprints + known-grammar DB | `pir/fingerprints.py` | `tests/test_pir_candidates.py` |
| **P6** forward recompilation (held-out comparison) | `pir/forward.py` | `tests/test_pir_s3.py` |
| **P7** intervention search (OED objectives) | `pir/intervention_search.py` | `tests/test_pir_s3.py` |
| **P8** BEC domain + cross-domain PIR-Diff | `pir/domains/bec.py`, `pir/diff.py` | `tests/test_pir_s3.py` |

Deliberately deferred: **P9 workbench UI** (research-first repo; CLI/CI/JSON
artifacts suffice) — scoped for a future session in
`docs/pir-p9-workbench-scope.md`.

**Full benchmark-suite coverage.** Every committed benchmark certificate is now
lowered into PIR facts (23 benchmarks):
- bespoke, verdict-*re-derived* lowerings — B9 (E3, `pir/domains/b9.py`) and
  B1/B2/B3 (E0, `pir/domains/exact_benchmarks.py`);
- a generic, conservative lowering for the rest (B4–B12, M1/M2, S-layer, atlas,
  truncation; `pir/domains/generic.py`) that maps a raw status to a SPEC verdict
  only when unambiguous and otherwise preserves the domain state verbatim with a
  null verdict. Evidence level is read from the certificate class; assumptions
  come from `m_layer_stipulations`. Tests: `tests/test_pir_exact_benchmarks.py`,
  `tests/test_pir_generic_lowering.py`. All read-only over the certificates. Conditional results throughout use assumption-taint per
ADR-0002 rather than a new verdict. Depth note: the constraint bridge, B9/BEC
lowerings, and cross-domain diff are exact where the arithmetic allows and
honest toys where the setting is nonlinear — each carries its evidence level and
warnings, and none promotes an atlas cell.
