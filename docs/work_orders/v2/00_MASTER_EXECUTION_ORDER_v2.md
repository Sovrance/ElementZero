# ElementZero v2 — Master Execution Order

    protocol_version = 2.0.0
    governing rule   = no new speculative architecture, and no new governance
                       feature, until Gates G0 and G1 pass.

## Sequence

    repair uncertainty
      -> replace the backbone
      -> add a model class that can represent a kink
      -> enforce blindness in code
      -> seal the prospective forecast before it expires
      -> then, and only then, re-run the ladder

## Dependency graph

    WO-201 Calibration gate (EZ-B004)        [G0]
        |
        +-----------+-----------+
        |           |           |
        v           v           v
    WO-202      WO-203      WO-204
    Backbone    Kink class  Blindness ledger
      [G1]        [G3]        [enforced]
        |           |           |
        +-----+-----+-----------+
              |
              v
    WO-206 Prospective seal (EZ-B007)   <-- START EARLY, value decays
              |
        +-----+-----+
        |           |
        v           v
    WO-207      WO-208
    EZ-B002-v2  EZ-B003-v2
        |           |
        +-----+-----+
              |
              v
    WO-209 EZ-B009 measurement-date holdout
              |
              v
    WO-210 EZ-B005 multi-observable + EZ-B006 derived observables
              |
              v
    WO-205 Historical physics refits  [G2]   <-- long pole, background track
              |
              v
    WO-211 v2 report and claim adjudication

WO-202/203/204 may run in parallel after WO-201. WO-205 may start at any time
and blocks only Tier-2 physics claims. WO-206 should be filed in week one.

## Work orders

### WO-201 — Calibration gate (BLOCKING, G0)
Implement `elementzero.uq.calibration` and EZ-B004. Replace the fixed kernel
with learned amplitude, ARD length scales and learned noise, bounded, seeded,
`n_restarts_optimizer >= 3`. Persist the LEARNED hyperparameters into the
KnowledgeFreeze and the model manifest. Pin the environment in
`protocol/protocol.json` and fail CI on an unpinned run.
Accept: every registry model passes the thresholds in
`protocol/acceptance_matrix.json` on development data or is excluded with a
recorded failure class; byte replay holds under the pin.
Status: IMPLEMENTED and LANDED (37 tests green in `tests/unit/test_v2_core.py`;
defect reproduced in `reports/v2/sigma_defect.json`; pin enforced by
`tools/check_environment_pin.py` and the `v2-protocol-pin` CI job).

Amendment on landing — the acceptance clause "byte replay holds under the pin"
was not satisfiable as written. The four-component version pin does not
determine the bytes: see `reports/v2/replay_environment.json`, which records
three distinct byte streams from one declared pin, and
`docs/v2/02_ARCHITECTURE_v2.md` section 7.1 for the mechanism. The pin now also
carries the BLAS thread count, and acceptance is split into findings replay
(portable, enforced) and byte replay (per host). Remaining WO-201 work:
persisting learned hyperparameters into the KnowledgeFreeze and the model
manifest against real freezes — `GPResidualV2.manifest()` emits them, but
nothing writes them into an evidence-graph freeze yet.

### WO-202 — Backbone replacement (G1)
Make the backbone an injected dependency. Integrate FRDM-2012 and WS4 as
macroscopic-microscopic bases and BSkG3 as an EDF base. Record each table's
provenance, license, fit cutoff, and whether its fit set can be enumerated.
Demote SEMF and GP-direct to permanent controls.
Accept: a table-backed residual model is scored under the identical protocol
against the frozen v1 reference MAE (511.0 / 543.4 / 388.8 keV for epochs
A / B / C) and either beats it or the report explains why not.
Note: a table-backed backbone against AME2020 is tier C by default. G1 is an
accuracy gate; it is not a blind claim.

### WO-203 — Kink-capable model class (G3)
Add the free-knot hinge residual model with BIC knot selection under the
discovery feature profile. No magic-number features.
Accept: rank-1 localization reported on the frozen synthetic B003 mechanics with
the v1 thresholds unchanged. A number below threshold is a result, not a
failure to be tuned away.
Status: IMPLEMENTED (`elementzero.models.shell_aware`).

### WO-204 — Blindness ledger in code
Every prediction carries a tier derived from a declared `BackboneProvenance`.
Combination inherits the worst contributor. A mixed-tier ranked table raises.
Accept: `assert_claim_eligible` guards every claim-bearing report path.
Status: IMPLEMENTED (`elementzero.models.blindness`).

### WO-205 — Historical physics refits (G2, LONG POLE)
Refit at least one global mass model to a historical cutoff so a genuinely blind
physics backbone exists in a second independence group.
Ladder, cheapest first:
1. Refit a macroscopic-microscopic model (FRDM-like, or Duflo-Zuker's 10- and
   31-parameter forms) to AME2003-eligible masses only. Days of CPU, tractable
   for one person, and it produces a real tier-A physics backbone.
2. Refit a Skyrme-EDF with an axially-deformed solver (HFBTHO class) to the same
   cutoff. Order 10^3-10^4 CPU-hours for a calibration; cluster work.
3. 3D-mesh BSkG-class refits: out of scope for v2.
Accept: the refit's training set is enumerable and hashed, the refit is scored
alongside the published table, and `independence_groups` returns >= 2 at tier A.
If it returns 1, that is the reported blocking finding and no frontier claim is
made.

### WO-206 — Prospective seal (EZ-B007) — FILE EARLY
Preregister and seal calibrated predictions for the nuclides most likely to
appear in the next AME edition (start from the NUBASE2020 extrapolated-only
set). Hash and commit before the edition exists.
Accept: sealed, hashed, and a scoring script that runs unattended against a
future edition with no refit.
Status: DONE. `experiments/EZ-B007-v2/`, seal sha256 4fd9940d4f9ba691...,
1008 targets (every AME2020 extrapolated record), tier A_STRICT_BLIND, scored by
`scripts/score_b007_forecast.py`.

Result: the sealed model FAILS EZ-B004 on the governing (frontier) split and is
recorded as NOT claim-eligible. std(z) = 2.82 against a [0.80, 1.25] band: the
intervals are about three times too narrow exactly where the forecast operates.
The declared conformal repair was attempted pre-seal and NOT adopted — it fixes
dispersion (std(z) 2.24 -> 0.89) while making the PIT worse (KS 0.165 -> 0.336),
because a multiplier cannot reshape a heavy-tailed error distribution. Sealed
anyway, because the seal is a dated record rather than a claim and the
prospective window closes permanently once the next edition publishes. See
`experiments/EZ-B007-v2/PREREGISTRATION.md` section 5.
Why first: AME/NUBASE is issued every 4-5 years and AME2020 is still current, so
the window is open now and closes without warning. A prospective forecast is
immune by construction to every leakage concern in WO-13 and cannot be
manufactured retroactively.

### WO-207 / WO-208 — EZ-B002-v2 and EZ-B003-v2
Re-run with the v2 registry, calibrated sigmas and tiers. Thresholds re-frozen
on synthetic mechanics before any evaluated truth is read. v1 oracle controls
rerun unchanged as the mechanics check.

### WO-209 — EZ-B009 measurement-date holdout (new)
The chronological supply is spent; this recovers temporal blindness from data
already in hand. Train on nuclides whose FIRST mass determination predates
cutoff T; test on those first measured after T, using NUBASE2020 / ENSDF
year-of-measurement provenance.
Accept: per-nuclide date provenance sourced, hashed and auditable; at least
three cutoffs T; the estimated-to-measured promotion rule matches
`ez-gt-policy-v1`.
Caveat to record: the AME adjustment network correlates masses, so a
measurement-date split is weaker than an edition split. Report it as tier B
unless the fit-membership argument can be made cleanly.

### WO-210 — EZ-B005 and EZ-B006
Multi-observable mass + charge radius, and derived-observable propagation with
the predictive covariance rather than independent-neighbour assumptions.

### WO-211 — v2 report
Sectioned by blindness tier. Claim ceilings from `05_CLAIM_POLICY_v2.md`
applied mechanically. No best-model label. Failures reported, never dropped.

## Definition of done

The seven conditions in `docs/00_V2_CHARTER.md` section 6. A poor scientific
result that satisfies all seven is a successful v2.
