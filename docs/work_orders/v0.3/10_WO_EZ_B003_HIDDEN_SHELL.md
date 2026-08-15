# WO-10 - Implement EZ-B003 Hidden Shell Rediscovery Challenge

Priority: FRONTIER VALIDATION
Repository: ElementZero
Depends on: WO-09

## Objective

Test whether ElementZero can reconstruct known shell-related structure after the relevant region is deliberately withheld.

This benchmark is the closest early analogue to the eventual question:

    can the system discover a stability structure
    without being told where it is?

EZ-B003 is NOT a claim that successful mass reconstruction proves a new magic number.

It is a controlled rediscovery benchmark.

## New benchmark

    benchmark_id = EZ-B003
    title = Hidden Shell Rediscovery Challenge

## Required separation: accuracy vs discovery

Maintain two benchmark profiles.

Discovery profile:

    allowed features:
        Z
        N
        A
        primitive parity terms if preregistered

    forbidden:
        distance to known magic numbers
        "is_magic" flags
        named shell closures
        shell-gap lookup tables
        target truth

Accuracy profile:

    may later include physics-informed shell features

Do not mix their conclusions.

## Candidate known closures

Initial availability set:

Neutron:

    N = 20
    N = 28
    N = 50
    N = 82
    N = 126

Proton:

    Z = 20
    Z = 28
    Z = 50
    Z = 82

Primary production set should be chosen by a preregistered availability rule, not by model performance.

Recommended focus if data support is sufficient:

    neutron N = 50, 82, 126
    proton  Z = 28, 50, 82

## New modules

    src/elementzero/benchmark/b003_prepare.py
    src/elementzero/benchmark/b003_freeze.py
    src/elementzero/benchmark/b003_predict.py
    src/elementzero/benchmark/b003_score.py
    src/elementzero/benchmark/shell_masks.py
    src/elementzero/physics/separation.py
    src/elementzero/benchmark/shell_metrics.py

Schemas:

    schemas/shell_challenge.schema.json
    schemas/shell_mask.schema.json

Tests:

    tests/unit/test_separation.py
    tests/unit/test_shell_masks.py
    tests/unit/test_shell_metrics.py
    tests/leakage/test_b003_feature_firewall.py
    tests/integration/test_synthetic_b003.py

## 1. Hide a neighborhood, not one point

For neutron closure N0, v1 mask:

    N in {N0-1, N0, N0+1}

for all eligible Z values that satisfy the preregistered support rule.

For proton closure Z0:

    Z in {Z0-1, Z0, Z0+1}

for all eligible N values that satisfy the support rule.

The exact masks are written before scoring.

## 2. Support rule

A shell challenge is eligible only if enough neighboring known nuclei exist outside the mask to calculate the requested derived observables.

Define MIN_CHAIN_LENGTH and MIN_TARGETS before scoring.

If a closure fails the support rule, mark:

    NOT_EVALUABLE

Do not silently omit it.

## 3. Derived binding energy

ElementZero already has:

    binding_energy_MeV(...)

Use predicted mass excess to derive B(Z,N).

Do not train on derived target binding energy.

## 4. Two-nucleon separation energies

Define:

    S2n(Z,N) =
        B(Z,N) - B(Z,N-2)

    S2p(Z,N) =
        B(Z,N) - B(Z-2,N)

These are derived observables.

They are not independent evidence from the masses used to compute them.

Atlas provenance must mark this derivation.

## 5. Shell-gap indicators

Define:

    delta2n(Z,N) =
        S2n(Z,N) - S2n(Z,N+2)

    delta2p(Z,N) =
        S2p(Z,N) - S2p(Z+2,N)

Large positive local changes can indicate shell structure.

Do not call every local maximum a magic number.

## 6. Discovery metrics

Mass metrics remain required.

Add shell-structure diagnostics:

For each hidden neutron closure:

    true_delta2n
    predicted_delta2n
    absolute_delta2n_error
    sign_recovered
    local_peak_rank

For proton closure:

    true_delta2p
    predicted_delta2p
    absolute_delta2p_error
    sign_recovered
    local_peak_rank

Peak localization:

Within a preregistered search window, rank the predicted shell-gap magnitude.

Record whether the withheld known closure is:

    rank 1
    top 3
    outside top 3

Do not convert this into a p-value unless a null model is preregistered.

## 7. Feature firewall

Add a code-level denylist for the discovery profile.

Reject feature names containing or semantically equivalent to:

    magic
    shell_distance
    distance_to_20
    distance_to_28
    distance_to_50
    distance_to_82
    distance_to_126
    known_closure
    shell_label

The denylist is defense in depth.

The primary protection is the explicit feature-policy manifest.

## 8. Synthetic shell benchmark first

Before scoring known closures, create a synthetic mass surface with an injected shell-like discontinuity.

The agent implementing the discovery model must not receive the synthetic hidden truth in the fit stage.

Verify the benchmark can:

    hide the shell neighborhood
    reconstruct masses
    derive S2n/S2p
    compute delta2n/delta2p
    rank the hidden feature

This validates benchmark mechanics.

## 9. Pre-register scientific success criteria

Unlike B002 characterization, B003 should eventually have a preregistered rediscovery criterion.

Do NOT invent it after seeing real shell results.

Recommended process:

1. define candidate metrics,
2. calibrate benchmark mechanics on synthetic data only,
3. freeze thresholds,
4. preregister,
5. score known real shell closures once.

Possible criterion structure:

    minimum fraction with correct shell-gap sign
    plus
    minimum fraction ranked top-k
    plus
    calibrated mass coverage requirement

The exact numerical thresholds must be frozen before real shell truth is scored.

## 10. Atlas hypotheses

Represent each competing structure hypothesis explicitly.

Example:

    H0 = no local shell discontinuity
    H1 = local shell discontinuity near masked N0

Use Atlas Hypothesis and Intervention abstractions only as evidence/hypothesis bookkeeping.

Do not import unrelated Atlas conjectures.

## 11. Connection to future unknown nuclei

If B003 eventually succeeds, it gives ElementZero evidence for one narrow capability:

    rediscovery of known shell-related mass structure
    under controlled masking.

It does NOT prove that a predicted Z=154 shell gap exists.

That later claim requires:

    independent physics-model ensembles
    deformation calculations
    fission calculations
    decay competition
    much larger extrapolation UQ

Keep this boundary explicit in the report.

## Required tests

    test_S2n_from_binding
    test_S2p_from_binding
    test_delta2n_definition
    test_delta2p_definition
    test_shell_mask_excludes_truth
    test_discovery_feature_firewall
    test_unsupported_shell_marked_not_evaluable
    test_synthetic_shell_peak_recovery
    test_shell_metrics_reproducible
    test_atlas_marks_derived_observables_as_derived

## Acceptance gates

Engineering PASS if:

- shell masks are deterministic and preregistered,
- discovery profile contains no magic-number features,
- mass predictions are sealed before truth scoring,
- separation/shell observables are derived reproducibly,
- synthetic challenge works,
- all evaluable closures are reported,
- non-evaluable closures are explicit,
- real scientific success thresholds were frozen before scoring.

## Stop conditions

STOP if:

- known closure labels reach discovery-model features,
- target truth is used to tune hyperparameters,
- a threshold is selected after real scoring,
- successful mass interpolation is described as proof of a new island of stability.
