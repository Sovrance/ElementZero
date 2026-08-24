# ElementZero v2

    protocol_version = 2.0.0
    status           = SPECIFICATION + REPAIR IMPLEMENTATION
    contains         = no run results, no scientific evidence about real nuclei

v2 re-specifies ElementZero after an external adjudication of the v1 evidence
against the published literature. It changes four things and preserves the rest.

## The four changes

1. **Calibration becomes a gate.** The v1 predictive sigma was vacuous —
   `ConstantKernel(1.0e6)` is a variance, so the prior amplitude was 1000, and
   with `normalize_y=True` that multiplies unit-variance targets: sigma came out
   ~1000x the residual scatter, and `optimizer=None` meant data could never
   correct it. That is the whole explanation for coverage 1.000 in every GP row
   of every epoch. Reproduced in `reports/v2/sigma_defect.json`.
2. **SEMF is demoted from backbone to control.** Five parameters, ~2.5 MeV
   class, no shell term. Published backbones sit at 0.3-0.7 MeV.
3. **A model class that can represent a kink is added.** The v1 B003 result
   (sign 1.000, top-3 0.800, rank-1 0.086) is what a smooth interpolator does to
   a discontinuity. No hyperparameter search closes a representational gap.
4. **The hyperheavy endgame leaves the ladder.** In that region the boundary of
   nuclear existence is set by spontaneous fission, not particle emission, so no
   mass model can adjudicate it. It becomes a deferred track behind Gate G4.

## What is preserved

Preregistration hashes, sealed predictions, the content-addressed evidence
graph, leakage firewalls, replay verification, the discovery/accuracy feature
firewall, and the refusal to publish a best-model label. On governance the
project already exceeds normal practice in this literature. Every frozen v1
artifact stays frozen.

## Install and verify

v2 code runs under the environment pin in `protocol/protocol.json`, which is
python 3.12 rather than the 3.11 the v1 jobs use. An unpinned run is refused.

```bash
python3.12 -m venv .venv-v2 && . .venv-v2/bin/activate
python -m pip install "numpy==2.4.4" "scipy==1.18.0" "scikit-learn==1.8.0" "pytest>=8"

export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python tools/check_environment_pin.py            # ENVIRONMENT_PIN: OK
python -m pytest -q tests/unit/test_v2_core.py   # 37 tests
python scripts/diagnose_v1_sigma.py --out /tmp/sigma_defect.json
python scripts/diagnose_replay_determinism.py    # findings replay: HOLDS
```

`--out` is required, and `reports/v2/sigma_defect.json` is refused unless you
pass `--allow-overwrite-recorded`: that file is the recording of record, not
this script's output. `diagnose_replay_determinism.py` is the supported way to
compare a rerun against it.

Expected diagnostic output:

```text
v1 median sigma :      66830.0 keV   std(z) = 0.0013   UNCERTAINTY_OVERDISPERSED
v2 median sigma :         54.5 keV   std(z) = 0.9355   CALIBRATED
```

Those four figures reproduce anywhere the pin holds. The raw floats behind them
do not: see `02_ARCHITECTURE_v2.md` section 7.1, and re-read
`reports/v2/sigma_defect.json` rather than regenerating it in place.

## Layout

```text
docs/v2/00_V2_CHARTER.md            what changed and why
docs/v2/01_DOCTRINES_v2.md          5 retained + 3 added
docs/v2/02_ARCHITECTURE_v2.md       backbone / residual / combination / calibration tiers
docs/v2/03_BENCHMARK_LADDER_v2.md   EZ-B004 gate, B001-B009, deferred track
docs/v2/04_BLINDNESS_LEDGER_v2.md   WO-13 promoted from prose to enforced code
docs/v2/05_CLAIM_POLICY_v2.md       claim ceilings per gate
docs/v2/06_MIGRATION_FROM_V1.md     what freezes, what moves, what is deleted (nothing)
docs/work_orders/v2/                WO-201..WO-211
protocol/                           protocol.json, acceptance_matrix.json
reports/v2/sigma_defect.json        the v1 sigma defect, reproduced
reports/v2/replay_environment.json  what the pin does and does not determine

src/elementzero/uq/calibration.py        PIT, coverage curve, CRPS, KS, conformal repair
src/elementzero/models/gp_calibrated.py  learned-kernel GP residual, injected backbone
src/elementzero/models/shell_aware.py    free-knot hinge residual, discovery firewall
src/elementzero/models/blindness.py      tiers, inheritance, independence groups
tests/unit/test_v2_core.py               37 tests across all four modules
tools/check_environment_pin.py           the pin, enforced

src/elementzero/experiments/b007_prospective.py  WO-206 target set, gate, seal
scripts/seal_b007_forecast.py            build the seal (refuses to overwrite)
scripts/score_b007_forecast.py           score it later; refits nothing
experiments/EZ-B007-v2/                  the sealed prospective forecast
```

## WO-206 is filed

The prospective forecast is sealed: `experiments/EZ-B007-v2/`, 1008 targets,
tier `A_STRICT_BLIND`, seal sha256 `9dc6db809279646e...`. It predicts every
nuclide AME2020 flags as an extrapolation, and it was committed while AME2020 is
still the current evaluation, which is the only time it could honestly be made.

It is a record, not a claim. The sealed model **fails EZ-B004** on the governing
frontier split — intervals about three times too narrow where the forecast
actually operates — and the declared conformal repair was attempted before
sealing and not adopted, because it trades a dispersion error for a worse
distribution shape. Read `experiments/EZ-B007-v2/PREREGISTRATION.md` before
citing anything from it.

That failure is the sharpest argument yet for **WO-202**, the next work order: a
control-class SEMF backbone cannot produce honest intervals at the chart's edge,
and no residual wrapper repairs it. WO-202 now has a concrete target to beat,
under an identical protocol, against a target set that is already frozen.
