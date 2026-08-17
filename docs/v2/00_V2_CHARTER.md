# ElementZero v2 — Charter

Status: SPECIFICATION + REPAIR IMPLEMENTATION
Supersedes: v0.3 work orders WO-01..WO-13
Does not supersede: any sealed v1 experiment artifact
Protocol version: 2.0.0

## 1. What v2 is

v2 is a re-specification of ElementZero after an external adjudication of the
v1 evidence against the published literature. It changes four things that
matter and preserves everything that was already working.

v2 contains:

- a corrected model architecture (physics backbone injected, not hard-coded)
- a calibration gate that runs before scoring, with working code and tests
- a shell-capable model class that can localize a closure
- a blindness ledger promoted from report prose to enforced code
- a revised benchmark ladder with quantitative entry gates
- a claim policy that names, per tier, what may and may not be said

v2 does NOT contain run results. Nothing in this package is scientific
evidence about real nuclei, about any real shell closure, or about any island
of stability.

## 2. What is preserved

The v1 governance apparatus was the strongest part of the project and is
carried forward unchanged in kind: preregistration hashes, sealed predictions,
content-addressed evidence graph, leakage firewalls, replay verification,
the discovery/accuracy feature firewall, and the refusal to publish a
best-model label. On these, ElementZero already exceeds normal practice in the
nuclear-mass literature, where in-sample RMS against the current evaluation is
often the whole reported result.

Every frozen v1 artifact stays frozen. EZ-B001-A/B/C, EZ-B002-v1, EZ-B003-v1
and their sealed predictions are never relabelled, rerun under the v1
protocol id, or retro-scored. v2 is a new protocol version, exactly as the v1
scientific-result policy requires. A restart that erased them would destroy
the one thing that cost the most to build: an auditable record of what was
believed before the answer was known.

## 3. The four changes

### 3.1 Calibration becomes a gate, not a column

The v1 predictive sigma was not merely imperfect; it was vacuous. The frozen
kernel was

    ConstantKernel(constant_value=1.0e6, fixed) * RBF(8.0, fixed)
      + WhiteKernel(1.0e4, fixed),  optimizer=None, normalize_y=True

`constant_value` is a VARIANCE, so the prior amplitude is sqrt(1.0e6) = 1000.
With `normalize_y=True` that amplitude multiplies unit-variance targets and
sklearn rescales the returned sigma by `y_train_std`, so

    sigma_prior = 1000 * y_train_std

With residual scatter of a few hundred keV this is a prior sigma of order
10^5 keV — hundreds of MeV — against sub-MeV errors. `optimizer=None` meant no
amount of data could correct it. That is the entire explanation for
coverage_90 = coverage_95 = 1.000 and std(z) near zero across every GP row of
every epoch.

`scripts/diagnose_v1_sigma.py` reproduces it: the v1 configuration returns
std(z) = 0.0013 on a controlled surface, matching the 0.000-0.002 recorded in
the WO-11 calibration table. The v2 configuration returns std(z) = 0.936.

This was a one-line configuration defect, not a deep modeling failure — but it
invalidated Doctrine 4 for the entire v1 series, because the sigma was the one
quantity the doctrine made load-bearing. In v2 no model may enter a scored
benchmark until it passes EZ-B004, the calibration qualification gate.

### 3.2 SEMF is demoted from backbone to control

A five-parameter semi-empirical mass formula sits near 2.5 MeV RMS. Published
global backbones sit at 0.3-0.7 MeV: WS4 near 0.30, Duflo-Zuker near 0.39,
FRDM-2012 near 0.61, BSkG5 near 0.65, HFB-31 near 0.56. The v1 residual model
reached 389-543 keV MAE on blind later-edition nuclides, which is respectable
for its backbone and behind the physics-informed frontier (published
physics-informed networks and BNNs report 0.08-0.19 MeV on comparable
newly-measured sets).

More importantly, a SEMF has no shell term. It cannot express the structure
EZ-B003 exists to find. WO-11 reached this conclusion from the inside; v2 acts
on it. The backbone becomes an injected dependency: SEMF stays as a control,
and published tables and historical refits become first-class backbones.

### 3.3 Shell localization gets a model class that can represent a kink

EZ-B003 v1 produced a clean negative result: sign of the gap recovered in
100% of scored chains, closure in the top 3 in 80%, ranked first in 8.6%. That
is what a smooth interpolator does to a discontinuity. A squared-exponential
kernel is infinitely differentiable; a closure is a near-discontinuity in the
first derivative of the binding energy. No hyperparameter search closes a
representational gap.

v2 adds a free-knot piecewise-linear (hinge) residual model. It selects the
knot by BIC on training data only, uses no magic-number features, and remains
admissible under the discovery profile. `tests/test_v2_core.py` shows it
recovering a hidden knot at rank 1 where the GP cannot.

### 3.4 The endgame moves off the ladder

This is the largest change of direction, and it is a narrowing.

The v0.1 dossier ends at "a principled investigation of predicted hyperheavy
regions such as Z approximately 154-156 and N approximately 308-310". Those
regions are real predictions in the covariant-DFT literature: large neutron
gaps at N = 228, 308, 406 and a proton gap at Z = 154 appear in Afanasjev and
collaborators' hyperheavy surveys. But the same literature is explicit that in
hyperheavy systems the boundary of nuclear existence is set by SPONTANEOUS
FISSION rather than particle emission, and that many predicted hyperheavy
configurations are toroidal and expected to be unstable to multifragmentation.

The consequence is unavoidable: no mass model, at any accuracy, can support an
existence or stability claim in that region. Masses give Q-values; Q-values
give half-lives only through models whose spread is measured in orders of
magnitude — spontaneous-fission half-life predictions differ across models by
up to five orders of magnitude, and an error of 1 MeV in Q_alpha moves an
alpha half-life by three to five orders of magnitude.

So Z ~ 154-156 leaves the benchmark ladder and becomes a DEFERRED TRACK behind
an explicit entry gate (G4, EZ-B008): blind reproduction of known superheavy
decay modes for Z = 104-118 with calibrated uncertainty. Until that gate
passes, hyperheavy is a motivation for the program, not a deliverable of it,
and no document in this repository may describe it as a target.

## 4. Two structural problems v2 must plan around

### 4.1 Historical epochs are nearly exhausted

The AME chronology gives three usable epochs (2003->2012, 2012->2016,
2016->2020) with n = 225, 63, 74. AME2020 remains the current evaluation; no
later edition appears to exist as of August 2026. The time-machine doctrine is
therefore running out of runway, and epochs B and C are already small enough
that a calibration gate is marginal on them.

Two mitigations, both in the ladder:

- EZ-B007, a PROSPECTIVE sealed forecast: preregister and seal predictions for
  the next AME edition now. A prospective forecast is immune to every leakage
  concern in WO-13 by construction, and it is the single strongest evidential
  move available to this project. It costs almost nothing today and cannot be
  manufactured retroactively later.
- historical refits (WO-205), which create new genuinely blind
  physics/epoch combinations from the editions already in hand.

### 4.2 Only one blind physics family exists

WO-13's finding stands and is the correct one: a target hidden from
ElementZero is not automatically blind to an imported physics table. Published
tables were fitted to modern evaluations, so BSkG3 against AME2020 is a
non-blind reference, FRDM95 membership is unknown and therefore ineligible,
and a blind residual wrapper cannot repair a non-blind base. That leaves one
blind independence group where the gate requires two.

This concern is under-recognized in the published literature — most
extrapolation studies use present-day model tables against present-day
holdouts without addressing it — which makes it both a genuine methodological
strength of this project and a genuine blocker. The only honest fix is to
build physics backbones fitted to historical cutoffs. That is WO-205, and it
is the hardest work order in v2.

## 5. Governance budget

From v2 onward, no new evidence-graph, provenance, or reporting feature may be
added until the modeling gates G0 and G1 pass. The infrastructure is ahead of
the science it certifies; further investment there has negative marginal value
until the models it wraps are worth certifying.

## 6. Success definition for v2

v2 is complete when all of the following hold:

1. Every model in the v2 registry passes EZ-B004 calibration qualification, or
   is excluded from scoring with a recorded reason.
2. At least one physics-rich backbone (table or refit) is integrated and
   scored under the same protocol as the controls.
3. EZ-B003-v2 reports rank-1 localization from a shell-capable model class,
   whatever the number turns out to be.
4. At least two independent blind physics families exist, or the gap is
   reported as the blocking finding and no frontier claim is made.
5. EZ-B007 prospective predictions are sealed and committed.
6. The environment (interpreter version, library versions and BLAS thread
   count) is pinned in the protocol, an unpinned run fails CI, and both replay
   levels hold: findings replay portably, and byte replay on the recording host.
   Amended from "strict byte replay is achievable" on measured evidence — see
   `docs/v2/02_ARCHITECTURE_v2.md` section 7.1 and
   `reports/v2/replay_environment.json`. Portable byte replay is not achievable
   for any fitted model on a BLAS-backed stack, so requiring it would have made
   condition 6 unsatisfiable rather than strict.
7. Every published number carries its blindness tier, and no two tiers appear
   in one ranked table.

A poor scientific result satisfying all seven is a successful v2.
