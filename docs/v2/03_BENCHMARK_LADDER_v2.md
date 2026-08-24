# ElementZero v2 — Benchmark Ladder

## 1. Ladder

    EZ-B004  Calibration qualification      GATE for everything below
      |
      +--> EZ-B001-v2  Historical epochs     A: 2003->2012, B: 2012->2016, C: 2016->2020
      +--> EZ-B002-v2  Geographic holdout    rectangular (Z,N) window withheld
      +--> EZ-B003-v2  Hidden shell          closure neighborhood withheld
      |
      +--> EZ-B005     Multi-observable      masses + charge radii jointly
      +--> EZ-B006     Derived observables   S1n, S2n, S2p, Q_alpha with propagation
      +--> EZ-B007     Prospective forecast  sealed now, scored on the next edition
      +--> EZ-B009     Measurement-date holdout  temporal blindness from data in hand
      |
      +--> EZ-B008     Decay/fission readiness   GATE for any frontier claim
             |
             +--> DEFERRED TRACK: superheavy, then hyperheavy

EZ-B004 is new and gates everything. EZ-B008 is new and gates the deferred
track. EZ-B005/B006/B007 are new. EZ-B001/B002/B003 keep their identity and
their v1 metric definitions so that v2 numbers drop into the existing
comparison without redefining anything.

## 2. EZ-B004 — Calibration qualification (new, gating)

Question: does this model's predictive sigma mean what it says?

Protocol: on a development split disjoint from every scored target, compute
z = (truth - prediction)/sigma and evaluate against the frozen thresholds in
`protocol/acceptance_matrix.json`. Report the coverage CURVE, not two points.

    std(z)          in [0.80, 1.25]
    abs(mean(z))    <= 0.30
    cal_error_90    <= 0.05
    cal_error_95    <= 0.03
    KS statistic D  <= 0.10        (effect size; not a p-value, see below)
    n               >= 20          else NOT_EVALUABLE

The gate uses the KS statistic rather than its p-value deliberately. A p-value
threshold tightens as n grows, so a larger and better benchmark would be
punished for being larger. D is sample-size independent. The p-value is
reported as a diagnostic only.

A model that fails is excluded from scoring with its failure class recorded. It
is not silently down-weighted, and its point metrics are not quietly published
without their sigma.

Reference behaviour, from `scripts/diagnose_v1_sigma.py`:

    v1 frozen kernel   median sigma 66830 keV   std(z) 0.0013   OVERDISPERSED
    v2 learned kernel  median sigma    55 keV   std(z) 0.9355   CALIBRATED

## 3. EZ-B001-v2 — Historical epochs

Unchanged in question and metric definitions. Changed in three ways:

- the model registry is the v2 registry, with physics backbones present
- EZ-B004 qualification precedes scoring
- every row carries a blindness tier, and blind and non-blind rows never share
  a ranked table

Reference numbers to beat, from the frozen v1 series (mass excess, keV):

    epoch  n    best v1 MAE   best v1 RMSE   model
    A      225  510.998       827.689        EZ-SEMF-GP-RESIDUAL-v1
    B      63   543.412       796.271        EZ-SEMF-GP-RESIDUAL-v1
    C      74   388.765       575.287        EZ-SEMF-GP-RESIDUAL-v1

Those remain frozen and are never rerun under the v1 id. They are the baseline
v2 must improve on with a physics backbone, or explain why it did not.

## 4. EZ-B002-v2 — Geographic holdout

Unchanged in mechanics. v1 froze no accuracy criterion and was characterization;
v2 keeps that choice for the region-reconstruction question and adds the
calibration gate, so that a model cannot post a good MAE with meaningless
intervals.

## 5. EZ-B003-v2 — Hidden shell rediscovery

Unchanged in question, criterion structure, and metric definitions
(sign_fraction, top_k_fraction, rank_1_fraction, calibration_error_90).
Changed in that a shell-capable model class is required to be present.

v1 result to improve on, from the frozen synthetic chart:

    EZ-SEMF-GP-RESIDUAL-v1   sign 1.000   top-3 0.800   rank-1 0.086

v2 thresholds are inherited from the frozen v1 criterion and are NOT to be
re-tuned. If the shell-capable class also fails them, that is the result.

The v1 oracle controls remain the mechanics check: an exact oracle, a
200 keV noisy oracle, and a 2 MeV noisy oracle all met the criterion while a
weak quadratic did not, which established that the criterion punishes inability
to localize a discontinuity rather than error magnitude. Those controls are
rerun unchanged in v2.

## 6. EZ-B005 — Multi-observable (new)

Question: does jointly modelling masses and charge radii improve either?

Rationale: published multi-task Gaussian process work reports simultaneous
improvement of masses and charge radii by modelling their correlation, with
mass RMS in the 0.09-0.14 MeV range and radius RMS near 0.004-0.007 fm. If
that transfers, it collapses two ladder steps into one and improves the mass
surface as a side effect.

Truth source: charge radii compilation, with its own eligibility and
estimated-value policy mirroring `ez-gt-policy-v1`.

## 7. EZ-B006 — Derived observables (new)

Question: do the uncertainties survive differencing?

Masses are differenced into S1n, S2n, S2p and Q_alpha. Differencing cancels
smooth systematic error and amplifies correlated error structure, so a model
can look calibrated on masses and be badly calibrated on separation energies —
which are the quantities every downstream physics question actually uses.
Uncertainty must be propagated with the predictive covariance, not by treating
neighbouring predictions as independent.

Every derived value is marked `derived` and never counted as independent
evidence, as in v1.

## 8. EZ-B007 — Prospective sealed forecast (new, highest evidential value)

Question: what does the model say about measurements that do not yet exist?

Protocol: preregister and seal predictions for nuclides expected in the next
AME edition, with predictive intervals, before that edition is published.
Commit the hash. Score on release.

This is the only benchmark in the ladder that is immune to every leakage
concern in WO-13 by construction, because no component of the prediction path
can have been fitted to data that does not exist yet. It also costs almost
nothing to execute today and cannot be manufactured retroactively.

It matters now specifically because the historical runway is short: AME2020
remains the current evaluation, the three historical epochs are already spent,
and two of them have n < 80.

### 8a. EZ-B007-v2 — filed (WO-206)

Sealed against AME2020: 1008 targets, every record the edition flags estimated,
trained on the 2550 measured records only. Tier A_STRICT_BLIND by construction.
Seal sha256 9dc6db809279646e..., artifacts under `experiments/EZ-B007-v2/`.

The sealed model does NOT pass the gate, and that is recorded rather than
smoothed over:

    split              regime          std(z)   MAE keV   verdict
    random_holdout     interpolation    0.914     403.0   FAIL (KS D 0.178)
    frontier_holdout   extrapolation    2.824     884.4   FAIL (underdispersed)

Calibration is qualified on two preregistered splits because a random holdout
certifies sigma in a regime this forecast never operates in — every target lies
off the edge of the measured chart. The frontier split governs eligibility. The
forecast is sealed as a dated record and is not claim-eligible; no accuracy or
interval statement may be made from it until it is scored against a real
edition, and not then unless the gate is passed.

## 8b. EZ-B009 — Retrospective measurement-date holdout (new)

Question: can the system predict masses that were unmeasured as of date T, using
only nuclides measured before T, without waiting for a new AME edition?

Rationale: the edition chronology is spent. AME2003 -> 2012 -> 2016 -> 2020 gave
three epochs and all three are consumed; two have n < 80. But an edition is a
coarse clock. NUBASE2020 and ENSDF carry per-nuclide measurement provenance, so
a finer temporal split can be cut inside a single edition: train on first-
measured-before-T, test on first-measured-after-T.

Weaker than an edition split, and labelled as such. The AME adjustment network
correlates masses through reaction and decay links, so a nuclide measured after
T may still have influenced pre-T adjusted values. Default tier is
B_PARTIAL_BLIND unless fit membership can be argued cleanly for the specific
target set. It is reported honestly as a second-best temporal channel, not as a
replacement for EZ-B007.

## 9. EZ-B008 — Decay and fission readiness (new, gating)

Question: can the system reproduce, blind, the decay properties of nuclei that
are already known in the heavy and superheavy region?

Scope: Z = 104-118, blind reproduction of dominant decay mode, Q_alpha, and
alpha half-life order of magnitude, with calibrated uncertainty.

Why it gates the deferred track: in the superheavy and hyperheavy regions the
boundary of nuclear existence is set by spontaneous fission rather than particle
emission, and the model spread on the relevant lifetimes is enormous —
spontaneous-fission half-life predictions differ by up to five orders of
magnitude across models, and a 1 MeV error in Q_alpha moves an alpha half-life
by three to five orders. A mass model that has not demonstrated control of
these quantities on KNOWN superheavy nuclei has no standing to speak about
unknown ones.

## 10. Deferred track

Superheavy, then hyperheavy including Z ~ 154-156 and N ~ 308-310.

Entry conditions: Gates G0-G4 all passed. Until then this track has no work
orders, no schedule, and no presence in any results document. It is the reason
the program exists; it is not a thing the program is currently doing.
