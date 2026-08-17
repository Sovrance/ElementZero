# ElementZero v2 — Scientific Doctrines

The five v0.1 doctrines are retained. Three are added, each because a specific
v1 finding showed the original five were not sufficient to prevent a specific
error.

## Retained

**D1. Validation precedes extrapolation.**
Unknown-nucleus mode stays locked until preregistered blind benchmarks pass.

**D2. Time is part of the benchmark.**
Train on what was known at a cutoff; score against what became eligible later.

**D3. Physics remains in the loop.**
AI corrects, emulates, mixes, or interrogates physics models. It does not
replace nuclear theory. v2 strengthens this: the physics backbone is now an
injected dependency with its own provenance, not a hard-coded formula.

**D4. Uncertainty is an output, not an afterthought.**
Every prediction carries calibrated predictive uncertainty, model
disagreement, and an extrapolation-risk measure.

**D5. Discovery models are separated from production models.**
A high-accuracy model may use shell features. A restricted-feature model must
rediscover hidden structure without being handed the answer. Results from the
two profiles are never pooled.

## Added in v2

**D6. Blindness is a property of the whole prediction path, not of the split.**

A target hidden from ElementZero is not automatically blind to an imported
physics table. Blindness is determined by what every component of the
prediction was fitted to, and a combination inherits its worst contributor.
Unknown fit-set membership is never promoted to blind. No reweighting, wrapper,
or residual learner converts a non-blind base into a blind claim.

Origin: WO-13. Enforced by `src/elementzero/models/blindness.py`.

**D7. An uncalibrated model is not scored.**

Calibration is a gate, not a reported column. A model whose predictive sigma
fails EZ-B004 qualification does not enter a scored benchmark; it is excluded
with a recorded reason. Coverage is reported as a curve across nominal levels,
never at two points only, because a vacuous interval reads as perfect coverage
at 90% and 95% and is exposed immediately by the curve.

Origin: the v1 sigma defect, which passed every v1 report because
coverage 1.000 looks like success in a two-column table.

**D8. A claim requires the observables that actually determine it.**

No claim about the existence, stability, or observability of a nucleus may be
made from mass predictions alone. Existence claims in the heavy and superheavy
regions require fission barriers and decay lifetimes, whose model spread is
orders of magnitude larger than mass spread. Each claim class names its
required observable set in `05_CLAIM_POLICY_v2.md`, and a claim missing any
required observable is refused, not hedged.

Origin: external adjudication. In hyperheavy systems the landscape boundary is
set by spontaneous fission rather than particle emission, so a mass-only
program cannot reach the question it was named for.

## Doctrine conflicts

D7 can conflict with D2: the later AME epochs have n = 63 and n = 74, and the
calibration gate is marginal at those sizes. The resolution is explicit and is
not to weaken the gate: a model that is NOT_EVALUABLE for calibration on a
small epoch is reported as NOT_EVALUABLE, its point metrics are still
published, and no uncertainty claim is attached to that epoch.

D6 can conflict with the desire to use the best available physics. The
resolution is also explicit: use the best physics, report it in the non-blind
section, and never let it appear in a blind-claim table. Sections may share
metrics; they may not share claims.
