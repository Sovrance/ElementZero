# T06 - Extract Intervention Search

## Objective

Port the reusable experiment-selection logic from Global Variables into PEC without pretending the v0.1 discrete scorer is a full nuclear experimental-design engine.

## Preserve v0.1 behavior

For discrete predicted outcome labels, preserve:

```text
candidate_disagreement
expected_information_gain as entropy of outcome partition
d_identifiable_reduction
cost-aware deterministic ranking
NONIDENTIFIABLE negative control
```

Reproduce existing synthetic discriminator tests before extending the API.

## API cleanup

Rename research-specific terms only where it improves generality, but provide a compatibility adapter for Global Variables.

Recommended core object:

```text
AdmissibleIntervention
  id
  kind
  cost
  feasibility
  assumptions
  predicted_outcomes
```

## Nuclear extension boundary

Do NOT implement accelerator operation or synthesis recipes in PEC. A later Zero-Mass nuclear experiment-design adapter may rank candidate *measurements* or high-fidelity calculations by information value, using public scientific model outputs.

Future interface should allow continuous predictive distributions and measurement noise:

```text
p(y | hypothesis, intervention)
expected_information_gain = E_y[KL(p(h|y) || p(h))]
```

This equation is design guidance only for a later release.

## Tests

- known synthetic discriminator ranked first;
- no separating intervention -> NONIDENTIFIABLE;
- infeasible interventions filtered;
- ties deterministic;
- least-cost discriminator deterministic.

## Acceptance

PEC tests and original Global Variables intervention-search tests both pass through the compatibility layer.
