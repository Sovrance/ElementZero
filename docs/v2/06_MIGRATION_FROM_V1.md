# ElementZero v2 — Migration from v1

## 1. Frozen, never touched

    experiments/EZ-B001-A, -B, -C
    experiments/EZ-B002-v1, EZ-B003-v1
    reports/historical/v1/, reports/adjudication/wo11/,
    reports/model_federation/wo12/, reports/eligibility/wo13/

These keep their protocol id, their hashes, and their numbers. They are cited as
v1 results. They are not rerun, retro-scored, relabelled, or deleted. This is the
v0.3 scientific-result policy applied to itself.

## 2. Carried forward unchanged in kind

Preregistration hashing, sealed predictions, content-addressed evidence graph,
Atlas PIR boundary (ADR-0001) and commit pin, leakage tests that fail closed,
replay verification, the discovery/accuracy feature firewall, oracle controls,
NOT_EVALUABLE as an acceptable outcome, ASCII-first math, one work order per PR.

None of this needed fixing. It is the part of the project that is ahead of the
field.

## 3. Demoted

| v1 element | v2 status | Reason |
| --- | --- | --- |
| `EZ-SEMF-LS-v1` | permanent null control | ~2.5 MeV class; no shell term |
| `EZ-GP-DIRECT-v1` | permanent null control | physics-free mean reverts to training mean inside holdouts |
| `EZ-SEMF-GP-RESIDUAL-v1` | control + v1 reference line | superseded as a production path by table-backed backbones |
| fixed-kernel `optimizer=None` | removed | root cause of the sigma defect |
| `Z~154-156` as ladder terminus | deferred track behind G4 | out of reach of a mass model |

## 4. Renamed / renumbered

    WO-01..WO-13   ->  historical, closed
    WO-201..WO-211 ->  v2 work orders (docs/work_orders/)
    protocol 1.0.0 ->  2.0.0

## 5. Repository actions

1. DONE. `src/elementzero/uq/`, `src/elementzero/models/{gp_calibrated,shell_aware,blindness}.py`,
   `scripts/diagnose_v1_sigma.py` and `protocol/` are in the repository. The test
   module landed at `tests/unit/test_v2_core.py` so the existing `unit` CI job
   collects it; the docs landed under `docs/v2/` and `docs/work_orders/v2/` to
   match the existing `docs/work_orders/v0.3/` convention and to avoid colliding
   with the `docs/0X_*.md` series already in the tree. All of it is additive:
   nothing under `experiments/` or `reports/{historical,adjudication,model_federation,eligibility}/`
   is modified. `src/elementzero/models/__init__.py` gained the v2 exports and
   kept every v1 export.
2. DONE. `reports/v2/sigma_defect.json` is committed as recorded upstream.
3. DONE, and it found something. `tools/check_environment_pin.py` enforces the
   pin and the `v2-protocol-pin` CI job fails an unpinned run. Building it showed
   the four-component version pin does not determine the bytes of a fitted model;
   the pin now carries the BLAS thread count, replay is stated at two levels, and
   the evidence is `reports/v2/replay_environment.json`. See
   `02_ARCHITECTURE_v2.md` section 7.1.
4. NEXT. Open WO-206 (prospective seal) FIRST among the scored work orders,
   because its value decays: it can only be filed before the next AME edition
   exists.
5. Do not add another evidence-graph or reporting feature until G0 and G1 pass.

### 5.1 Not yet done, and deliberately not started here

The v2 modules are landed and tested against controlled synthetic surfaces. They
are not yet wired into the benchmark runners, the evidence graph, or the model
registry that `experiments/` drives — no v2 model has been run against any AME
edition, and `protocol.json` names `elementzero.models` as the registry module
without anything reading it as one yet. Doing that is WO-202 and onward, and it
is one work order per PR by house rule. This branch is WO-201.
