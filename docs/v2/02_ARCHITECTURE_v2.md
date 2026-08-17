# ElementZero v2 — Architecture

## 1. The change in one diagram

v1:

    SEMF (hard-coded, 5 params)
      -> GP residual (fixed kernel, optimizer=None)
        -> prediction + vacuous sigma

v2:

    Backbone tier      (injected, provenance-carrying, blindness-tagged)
      -> Residual tier (learned kernel, or kink basis, or both)
        -> Combination tier (BMA / ensemble, inherits worst blindness)
          -> Calibration tier (gate; optional declared conformal repair)
            -> prediction + honest sigma + blindness tier

Every tier is separately swappable, separately manifested, and separately
attributable in a failure decomposition. The v1 stack could not answer "was
that the physics or the residual learner?" because there was only one physics.

## 2. Backbone tier

A backbone supplies the mean function and carries its own provenance:
what it was fitted to, in what year, whether the fit set can be enumerated, and
which physics-independence group it belongs to.

    Class T0  controls           EZ-SEMF-LS-v1 (retained, frozen), zero backbone
    Class T1  published tables   FRDM-2012, WS4, BSkG3/4/5, Duflo-Zuker, DRHBc
    Class T2  historical refits  EZ-REFIT-*-AME2003, EZ-REFIT-*-AME2012
    Class T3  emulators          surrogate for an expensive T2 build

Class T2 is the only route to Tier A blindness for a physics backbone, and is
therefore the gating class for Gate G2. See WO-205.

Independence groups matter more than accuracy. Two Brussels-Skyrme functionals
are one group and count once. The registry records the group; the gate counts
distinct groups, not distinct model ids.

## 3. Residual tier

    R1  GP-ARD-v2         learned amplitude, anisotropic length scales over
                          (Z, N, A), learned noise, bounded, seeded
    R2  KINK-RESIDUAL-v2  free-knot two-sided hinge basis, BIC selection;
                          representationally able to localize a closure
    R3  accuracy-profile   shell-feature models, firewalled from discovery

R1 replaces the v1 GP. The kernel family is unchanged in form; what changed is
that the hyperparameters are learned instead of frozen at values that were
inconsistent with `normalize_y=True`.

R2 exists because R1 provably cannot do what EZ-B003 asks. A squared-
exponential kernel is infinitely differentiable; a shell closure is a kink.
Piecewise-linear bases can represent a kink; smooth kernels and smooth
activations cannot. R2 is the instrument of record for localization; R1 remains
the instrument of record for the smooth mass surface.

## 4. Combination tier

Bayesian model averaging or explicit ensembling across backbones, with two
non-negotiable rules:

    combined_blindness = worst(contributor blindness tiers)
    residual wrappers do not count as independent physics families

Model-form uncertainty only becomes measurable once two independent physics
families are present, so this tier is largely inert until Gate G2 passes. It is
specified now so that the interface does not have to change later.

## 5. Calibration tier

    - EZ-B004 qualification runs before any scoring
    - diagnostics: mean(z), std(z), coverage curve, PIT + KS statistic,
      NLPD, CRPS
    - failure classes are named and distinguished:
        UNCERTAINTY_OVERDISPERSED   sigma too wide
        UNCERTAINTY_UNDERDISPERSED  sigma too narrow
        MEAN_FUNCTION_BIASED        the mean is shifted; sigma is not at fault
    - optional conformal sigma repair, which must be declared pre-seal, fitted
      only on blind-eligible non-target data, and folded into model identity as
      EZ-<MODEL>+CONF-v2

The scaler refuses to fit when calibration residuals are visibly shifted,
because a single multiplier cannot repair a biased mean and pretending
otherwise would hide a MODEL_BIAS failure behind a UQ fix. That refusal is the
point of the class.

## 6. Feature policy

    discovery profile   Z, N, A and derived local coordinates only.
                        Forbidden: magic-number distance, nearest-magic-Z/N,
                        shell gap, closure flags, valence-to-magic counts.
                        Violations raise FeatureProfileError. They are never
                        silently dropped, because a silent drop turns a
                        firewall into decoration.

    accuracy profile    may use all of the above; results are reported in their
                        own section and never pooled with discovery results.

## 7. Determinism and environment

WO-11 recorded that strict byte replay held under CPython 3.12 but that
content-addressed ids over raw IEEE floats shifted by one ULP under 3.11, and
that refit reproducibility was verified only in the recording environment.
v2 pins interpreter version, library versions and BLAS thread count in
`protocol/protocol.json` and treats an unpinned environment as a protocol
violation rather than a footnote. `tools/check_environment_pin.py` enforces it
and fails CI on an unpinned run.

Training input is sorted before fitting so that permutation of the input order
cannot change a learned kernel. This is tested.

### 7.1 What the version pin does not buy (measured, not assumed)

Landing this package found the original four-component pin insufficient.
`scripts/diagnose_v1_sigma.py` was re-run under python 3.12.3 / numpy 2.4.4 /
scipy 1.18.0 / scikit-learn 1.8.0 — every version the pin named — and did not
reproduce the bytes of `reports/v2/sigma_defect.json`. Re-running it at a
different BLAS thread count moved the numbers again. Three distinct byte streams
came out of one declared pin.

The cause is below the pinned layer. numpy and scipy ship OpenBLAS, whose
threaded reductions sum partial results in a thread-count-dependent order and
whose kernels are runtime-dispatched on the host CPU's SIMD level. Floating-
point addition is not associative, so summation order is part of the result.

The two prediction paths do not degrade equally, and that asymmetry is the
finding:

    v1 path (optimizer=None)   reproduces to ~1e-14 relative   ULP noise only
    v2 path (L-BFGS-B fit)     reproduces to ~1e-5  relative   noise amplified

The amplification is structural. L-BFGS-B handed a gradient perturbed in the
last place converges to a slightly different point in kernel space, so the
learned amplitude, length scales and noise all shift, and sigma shifts with
them. This is the direct cost of the repair in section 3 of the charter, and it
is a good trade: `protocol.json` already says that v1 "achieved determinism by
refusing to fit, which caused the sigma defect", and a sigma reproducible to one
part in 1e6 and honest is worth more than one reproducible to one part in 1e16
and vacuous.

Two replay levels are therefore stated separately, and every artifact says which
one it claims:

    byte replay      PER HOST. One host, one BLAS build, one thread count.
                     Not portable, and not claimed to be.
    findings replay  PORTABLE. Verdicts, dispersion classes and failure lists
                     identical; floats within the tolerances in
                     `protocol/acceptance_matrix.json`.

`scripts/diagnose_replay_determinism.py` measures both and writes
`reports/v2/replay_environment.json`. The committed `sigma_defect.json` predates
the extended pin: it is findings-replayable, not byte-replayable, and it is left
exactly as recorded rather than re-recorded to flatter the new pin.

The tolerances use a combined `atol + rtol * |x|` rule rather than a pure
relative one, because `mean_z`, `cal_error_90/95` and `pit_ks_d` either sit near
zero or are suprema over an order statistic. A `pit_ks_d` of 0.045 that moves by
1e-6 in absolute terms reads as a 2e-5 relative excursion while remaining four
orders of magnitude away from mattering to a gate whose threshold is 0.10. What
has to replay is which side of the threshold a statistic falls on.

## 8. Known limitation carried forward

The ARD length scale for the A dimension runs to its upper bound during
fitting. This is expected and informative: A = Z + N is redundant given Z and
N, so the optimizer correctly declares that dimension uninformative. It is
recorded rather than suppressed, and it is a reason to prefer a physically
motivated coordinate set (for example N - Z, or isospin I = (N-Z)/A) in a later
feature-policy revision.
