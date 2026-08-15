# AGENTS.md

## Cursor Cloud specific instructions

This repository is a **local Python research stack** (no web app, Docker, or databases). Core packages live under `scaffold/`:

| Package | Path | Role |
| --- | --- | --- |
| physics-evidence-core (PEC) | `scaffold/physics-evidence-core` | Evidence/provenance/certificates |
| zero-mass-element (ZME) | `scaffold/zero-mass-element` | Nuclear mass prediction + `zme` CLI |

### Startup / install caveats

- Editable installs put `zme` and `pytest` in `~/.local/bin`. Ensure that directory is on `PATH` before invoking CLI tools.
- Install **PEC before ZME** (ZME depends on `physics-evidence-core>=0.1.0`).
- There is **no lockfile**; pip resolves numpy/scikit-learn/scipy at install time. Synthetic B001 metrics can differ slightly across sklearn versions; treat `validation/synthetic_b001_metrics.json` as approximate reference for software smoke only.
- Bundled fixtures are **synthetic software smoke data**, not scientific evidence. Official AME historical runs (task T10) need external AMDC/NNDC downloads.

### Commands (canonical sources)

- Bundle smoke: `python3 scripts/validate_bundle.py` (expects `BUNDLE_VALIDATION: PASS`) — also covered in root `README.md`.
- Tests: `python3 -m pytest -q` inside each scaffold package.
- CLI E2E (synthetic): `zme b001-prepare-targets` then `zme b001` against `scaffold/zero-mass-element/tests/fixtures/*.csv`.
- Agent task graph / acceptance: `docs/06_AGENT_EXECUTION_RUNBOOK.md`, `docs/07_ACCEPTANCE_GATES.md`, `agents/task_manifest.json`.
- **Lint:** no ruff/flake8/mypy config in PEC/ZME scaffolds; use `python3 -m compileall` as a minimal syntax check. Global Variables patch optionally adds ruff under `reference/`.

### Research baseline vs current scaffolds

- Canonical research baseline: `docs/research/ElementZero_Initial_Research_Baseline_v0.1.md` (preserve; version successors separately).
- That baseline prefers **commit-pinned Atlas PIR as upstream** (`Sovrance/Atlas`) over forking a long-lived `physics_evidence_core`. The current `scaffold/physics-evidence-core` is the v0.2 handoff extraction; treat Atlas-adapter work as the longer-term direction (Decision R-008), not as a reason to delete the scaffold during routine setup.
- EZ-B001 is the preferred name for the historical mass benchmark; ZME-B001 remains the legacy CLI/scaffold name.

### Optional / out of default E2E scope

- `reference/global_variables_reusable_source` + `scripts/apply_global_variables_patch.sh` — migration/compat only.
- Real AME data ingestion — not required for local scaffold validation.
