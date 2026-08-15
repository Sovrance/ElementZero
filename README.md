# Zero-Mass Element v0.2 + Physics Evidence Core v0.1

This is the agent-ready implementation handoff for the validation-first Zero-Mass Element program.

## What this bundle contains

1. A complete engineering handoff for Zero-Mass Element v0.2.
2. Physics Evidence Core (PEC) v0.1 extraction and migration specification.
3. A tested patch for the supplied Global Variables repository packaging/test-discovery issue.
4. A runnable PEC scaffold extracted from the reusable PIR/provenance ideas in Global Variables.
5. A runnable Zero-Mass Element scaffold implementing the ZME-B001 historical prediction protocol against normalized snapshots.
6. A synthetic smoke dataset that tests software behavior only. It is NOT scientific evidence.
7. Machine-readable JSON schemas, task manifest, acceptance gates, and provenance records.
8. An agent-readability validator that checks Markdown code fences, internal paths, JSON, ASCII math blocks, and package smoke tests.

## Start here

Coding agents should read these files in order:

- `agents/MASTER_CODING_AGENT_PROMPT.md`
- `docs/00_EXECUTIVE_HANDOFF.md`
- `docs/03_GLOBAL_VARIABLES_EXTRACTION_MAP.md`
- `docs/04_GLOBAL_VARIABLES_MIGRATION_AND_PATCH.md`
- `docs/05_ZME_B001_HISTORICAL_MASS_PREDICTION.md`
- `docs/06_AGENT_EXECUTION_RUNBOOK.md`
- `docs/07_ACCEPTANCE_GATES.md`

Then execute `agents/task_manifest.json` in dependency order.

## Math readability rule

All normative equations are written first as plain ASCII inside fenced `text` blocks. LaTeX may be added as a secondary rendering only; agents MUST implement the ASCII equation, not infer behavior from typography.

Example:

```text
A = Z + N
I = (N - Z) / A
prediction = physics_baseline + learned_residual
```

## Validation

From the bundle root:

```bash
python scripts/validate_bundle.py
```

Expected result:

```text
BUNDLE_VALIDATION: PASS
```

The Global Variables patch was also tested separately against the supplied repository. After applying the patch, ordinary `python -m pytest -q` passes through a bridge to the existing certified benchmark runner without changing the scientific benchmark sequencing.
