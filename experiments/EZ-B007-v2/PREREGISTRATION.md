# EZ-B007-v2 — Prospective sealed forecast

    protocol_version = 2.0.0
    work_order       = WO-206
    experiment_id    = EZ-B007-v2
    seal_sha256      = 9dc6db809279646e6c725985bf77014417cdac87c345957456b6b1a3a6df3d4d
    blindness_tier   = A_STRICT_BLIND
    claim_eligible   = NO  (fails EZ-B004 on the governing split)

This document is prose and is deliberately outside the seal hash, following the
same rule as the v1 preregistrations: editing a sentence here must not be able to
invalidate a sealed experiment, and it can never change a number.

## 1. The question

What does the model say about masses that have not been measured yet?

AME2020 marks estimated (non-experimental) values with `#`. Those 1008 records
are the AMDC's own extrapolations — nuclides not measured today, and therefore
the pool from which the next edition's new measurements will be drawn. All 1008
are predicted here, with intervals, and hashed before the answers exist.

## 2. Why this is sealed before anything else in v2

Every other benchmark on the ladder is retrospective, and WO-13 established how
hard retrospective blindness is to defend: a target hidden from ElementZero is
not automatically blind to an imported physics table, and fit-set membership is
frequently unknowable. A prospective forecast sidesteps the entire problem by
construction. No component of a prediction can have been fitted to a measurement
that does not exist.

It also cannot be manufactured afterwards. AME/NUBASE is issued every four to
five years, AME2020 is still current, and the moment the next edition appears the
opportunity to have predicted it is gone permanently. That is why the charter
directs this to be filed first even though the dependency graph places it after
WO-202.

## 3. What is frozen

    training set     2550 AME2020 measured (non-estimated) nuclides
    target set       1008 AME2020 extrapolated (#) nuclides — all of them
    source           mass_1.mas20.txt, sha256 e8599c6d...3307, verified at seal time
    ground truth     ez-gt-policy-v1: evaluated_non_estimated_only
    model            EZ-SEMF-GP-RESIDUAL-v2 (SEMF backbone + learned-kernel GP)
    scoring          scripts/score_b007_forecast.py, no refit permitted
    environment      python 3.12.3, numpy 2.4.4, scipy 1.18.0, scikit-learn 1.8.0,
                     single-threaded BLAS — the protocol/protocol.json pin

The seal is the protocol-v2 run of record, not a portability probe, so it is
produced under the pin and `scripts/seal_b007_forecast.py` refuses to run
otherwise. `forecast_protocol.json` records the environment it was actually
fitted in, with `produced_under_protocol_pin: true`.

An earlier revision of this seal was fitted on python 3.11 / scikit-learn 1.9.0
and was rejected in review for that reason. Refitting under the pin moved the
governing std(z) from 2.823577 to 2.823576 and the frontier MAE by 2.4e-6 keV —
about one part in 1e6, which is exactly the fitted-path replay tolerance
recorded in `protocol/acceptance_matrix.json`. The verdicts are unchanged. That
the numbers barely moved is not a reason the pin was optional: it is a
measurement that could only be made by doing it correctly.

No "most likely" subset was selected. Excluding a target is indistinguishable,
after the fact, from having predicted it badly, so every extrapolated nuclide is
predicted and each carries its preregistered L1 distance bucket instead:

    d=1     388      d=2     241      d=3-4   236      d>=5    143

The target manifest is identity-only, as `ALLOWED_TARGET_FIELDS` requires. The
AMDC's own extrapolated values are recorded separately in
`reference_extrapolations.json`, marked `is_measurement: false`, so that the
future report can answer the question that decides whether this program adds
anything — did the model beat the evaluators' extrapolation? — without that
value ever being reachable as a model feature.

## 4. Calibration was qualified where the model will actually be used

Doctrine 7 gates scoring on EZ-B004. A random holdout of measured nuclides
qualifies sigma in the interpolation regime, which is not the regime this
forecast operates in: every target sits off the edge of the measured chart. Two
splits were therefore preregistered and both verdicts are sealed.

    split              regime          std(z)   MAE keV   class
    random_holdout     interpolation    0.914     403.0   CALIBRATED
    frontier_holdout   extrapolation    2.824     884.4   UNCERTAINTY_UNDERDISPERSED

The frontier split governs eligibility, because it is the one that resembles the
task. Reporting only the flattering split is precisely the error EZ-B004 exists
to prevent.

## 5. The result, stated plainly: this model fails the gate

**The forecast is sealed and it is not claim-eligible.**

On the governing split the predictive intervals are roughly three times too
narrow (std(z) = 2.82 against a threshold band of [0.80, 1.25]), the mean is
shifted (mean(z) = -0.66), and 90% intervals cover 86% of targets. The random
split fails too, though only on the PIT KS statistic (D = 0.178): its sigma
*scale* is about right while the error distribution is not Gaussian — MAE 403
keV against RMSE 744 keV and median absolute error 243 keV is a heavy tail.

The conformal repair permitted by architecture section 5 was declared before
sealing, fitted on half the frontier holdout and qualified on the disjoint other
half. It was **not adopted**, because it does not work:

    scale = 2.527
    std(z)   2.241  ->  0.887      dispersion repaired
    KS D     0.165  ->  0.336      distribution shape made worse

A single multiplier can rescale a sigma; it cannot reshape a heavy-tailed error
distribution. Matching the 90th percentile of |z| when the tail is heavy
over-inflates sigma for the bulk, so coverage overshoots and the PIT moves
further from uniform. The sealed sigmas are therefore the raw model's, and the
attempted repair is recorded in `forecast_protocol.json` rather than applied.

## 6. Why a failing model was sealed anyway

Because the seal is a dated **record**, not a claim, and the window closes
permanently. When the next edition lands, a failing sealed forecast still
answers real questions: how large the errors actually were, whether the frontier
split predicted that in advance, and whether the model beat the AMDC
extrapolation it was competing against. Sealing nothing would have destroyed the
one thing that cannot be recreated later.

What may be said about this artifact, per `docs/v2/05_CLAIM_POLICY_v2.md`:

    MAY say      this seal exists, its date, its hash, and its verdict
    MAY NOT say  any accuracy or interval claim from these predictions, or
                 anything about real nuclei derived from them

## 7. What this tells WO-202

The backbone is SEMF, which protocol v2.0.0 already demotes to a permanent
control: five parameters, roughly the 2.5 MeV class, no shell term. This result
gives that demotion a concrete number. A control-class backbone cannot produce
honest intervals at the frontier, and the failure is not a sigma-scaling problem
that a wrapper can fix — it is the mean function being wrong in a structured,
heavy-tailed way where the chart runs out.

WO-202 (integrate a real physics backbone) is therefore the correct next step,
and it now has a target to beat: the frontier-holdout numbers above, under an
identical protocol. When a table-backed backbone lands it can be sealed as an
additional prospective entrant against this same frozen target set, and the two
compared directly.

## 8. Scoring, when the edition arrives

```bash
python tools/fetch_ame_sources.py <NEW_EDITION>
python scripts/score_b007_forecast.py \
    --seal experiments/EZ-B007-v2 \
    --edition data/amdc/<new mass table> \
    --edition-id AME<YYYY> --edition-year <YYYY>
```

The scorer verifies the seal digest before it scores anything, joins on nuclide
id, keeps only targets that became measured, refits nothing, and reports the
model against the AMDC extrapolation baseline. Targets still unmeasured are
reported as such and are not counted as misses.
