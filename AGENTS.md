# AGENTS.md

## Cursor Cloud specific instructions

Primary product is the installable **`elementzero`** package (`src/elementzero/`) with commit-pinned Atlas PIR. Legacy ZME/PEC scaffolds under `scaffold/` remain for handoff validation only.

| Layer | Path / entry | Role |
| --- | --- | --- |
| ElementZero (preferred) | `src/elementzero/`, CLI `elementzero` | EZ-B001 + Atlas adapter |
| Atlas PIR pin | `atlas.lock.json`, `tools/ensure_atlas_pir.py` | Immutable evidence kernel |
| PEC scaffold (legacy) | `scaffold/physics-evidence-core` | Handoff extraction |
| ZME scaffold (legacy) | `scaffold/zero-mass-element`, CLI `zme` | Synthetic ZME-B001 smoke |

### Startup / install caveats

- Preferred install matches CI: `python tools/ensure_atlas_pir.py`, install runtime/dev deps, then `python -m pip install -e . --no-deps`. Do not depend on Atlas `main`; use the SHA in `atlas.lock.json`. Plain `pip install -e '.[dev]'` fails because the pinned Atlas SHA is not yet a publishable package without the ensure overlay.
- Editable installs put `elementzero` / `zme` / `pytest` in `~/.local/bin`. Ensure that directory is on `PATH`.
- Root `schemas/nuclear_observation.schema.json` and `schemas/prediction_certificate.schema.json` describe the **ElementZero** contracts. Scaffold/PEC certificate shapes differ and are not loaded from these files.
- Synthetic fixtures are software smoke only, not scientific evidence. Official AME runs need external AMDC/NNDC downloads.

### Commands (canonical sources)

- ElementZero tests/lint: `python -m pytest -q`, `ruff check src tests` (see root `README.md` / `.github/workflows/ci.yml`).
- Bundle/scaffold smoke: `python3 scripts/validate_bundle.py` (expects `BUNDLE_VALIDATION: PASS`).
- Research baseline: `docs/research/ElementZero_Initial_Research_Baseline_v0.1.md` (Decision R-008: Atlas upstream, not a long-lived PEC fork).
- Agent task graph: `docs/06_AGENT_EXECUTION_RUNBOOK.md`, `docs/07_ACCEPTANCE_GATES.md`, `agents/task_manifest.json`.

### Optional / out of default E2E scope

- `reference/global_variables_reusable_source` + `scripts/apply_global_variables_patch.sh` — migration/compat only.
- Real AME data ingestion — not required for local synthetic EZ-B001 / scaffold validation.
