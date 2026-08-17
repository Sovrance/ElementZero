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

- Preferred install: `python tools/ensure_atlas_pir.py` then `python -m pip install -e '.[dev]'`. Do not depend on Atlas `main`; use the SHA in `atlas.lock.json`. The required dependency list does not fetch the raw Atlas git SHA (it is not installable until packaging lands). The optional `atlas` extra is reserved for after that packaging merge.
- Editable installs put `elementzero` / `zme` / `pytest` in `~/.local/bin`. Ensure that directory is on `PATH`.
- Root `schemas/nuclear_observation.schema.json` and `schemas/prediction_certificate.schema.json` describe the **ElementZero** contracts. Scaffold/PEC certificate shapes differ and are not loaded from these files.
- Synthetic fixtures are software smoke only, not scientific evidence. Official AME runs need external AMDC/NNDC downloads.

### Protocol v2.0.0 caveats

- v2 code (`src/elementzero/uq/`, `src/elementzero/models/{gp_calibrated,shell_aware,blindness}.py`) runs under the pin in `protocol/protocol.json`: python 3.12.3, numpy 2.4.4, scipy 1.18.0, scikit-learn 1.8.0, **and** `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1`. `python tools/check_environment_pin.py` refuses an unpinned run; the `v2-protocol-pin` CI job is the only one on 3.12. v1 jobs stay on 3.11 because their artifacts were recorded there.
- The BLAS thread count is part of the pin for a measured reason, not tidiness: `reports/v2/replay_environment.json` records distinct byte streams from the same pinned library versions at different thread counts. Byte replay is a per-host claim; findings replay is the portable one. Do not describe a v2 number as byte-replayable off the host that recorded it.
- Do not regenerate `reports/v2/sigma_defect.json` in place. It is the recorded reproduction of the v1 sigma defect; re-run it to a scratch path and compare with `scripts/diagnose_replay_determinism.py`. This is enforced, not advisory: `diagnose_v1_sigma.py` requires `--out` and refuses the recorded path without `--allow-overwrite-recorded`.
- The v2 suite carries the `v2_protocol` marker. It runs twice by design: `v2-protocol-pin` (3.12.3 pinned) is the run of record, and the 3.11 `unit` job re-runs it as a portability probe. A failure in the probe means the code does not survive those library versions — worth knowing before bumping the pin, and not itself a protocol violation, since the pin governs recorded results rather than test execution.
- No v2 model is wired into the benchmark runners or evidence graph yet (that is WO-202 onward). Nothing in `experiments/` or the frozen v1 reports may be rerun under a v2 id.

### Commands (canonical sources)

- ElementZero tests/lint: `python -m pytest -q`, `ruff check src tests` (see root `README.md` / `.github/workflows/ci.yml`).
- Bundle/scaffold smoke: `python3 scripts/validate_bundle.py` (expects `BUNDLE_VALIDATION: PASS`).
- Research baseline: `docs/research/ElementZero_Initial_Research_Baseline_v0.1.md` (Decision R-008: Atlas upstream, not a long-lived PEC fork).
- Engineering work orders: `docs/work_orders/v0.3/00_MASTER_EXECUTION_ORDER.md` (one WO per PR; WO-01..WO-13 closed).
- Protocol v2.0.0 work orders: `docs/work_orders/v2/00_MASTER_EXECUTION_ORDER_v2.md` (WO-201..WO-211; still one WO per PR). Spec under `docs/v2/`.
- Agent task graph: `docs/06_AGENT_EXECUTION_RUNBOOK.md`, `docs/07_ACCEPTANCE_GATES.md`, `agents/task_manifest.json`.
- Superseded ZME/PEC docs live under `docs/legacy/` (non-normative).

### Optional / out of default E2E scope

- `reference/global_variables_reusable_source` + `scripts/apply_global_variables_patch.sh` — migration/compat only.
- Real AME data ingestion — not required for local synthetic EZ-B001 / scaffold validation.
