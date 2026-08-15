# Zero-Mass Element v0.2 Engineering Specification

## 1. Scope

v0.2 adds an evidence kernel and implements the first real benchmark protocol. It does not attempt decay, fission, chemistry, reaction synthesis, or unknown hyperheavy prediction.

## 2. Major components

```text
Official source snapshots
        |
        v
Normalizer + source manifest
        |
        v
Historical knowledge freeze
        |
        +-------------------+
        |                   |
        v                   v
Physics baseline        Direct ML control
(SEMF first)            (optional GP)
        |                   |
        +---- residual -----+
                 |
                 v
         Probabilistic prediction
                 |
                 v
        PEC prediction certificate
                 |
          later truth unlocked
                 |
                 v
      scoring + calibration report
```

## 3. Package boundary

`physics_evidence_core` owns generic mechanisms:

- immutable evidence objects;
- evidence/warrant classifications;
- content addressing;
- append-only fact storage;
- provenance dependency graphs;
- explicit namespace transforms;
- scientific pass honesty tags;
- generic knowledge freezes;
- held-out comparison records;
- certificate creation and degradation checks;
- intervention ranking.

`zero_mass_element` owns nuclear-specific mechanisms:

- nuclide identity;
- AME/NUBASE adapters;
- historical source policies;
- SEMF and nuclear model adapters;
- nuclear ML features;
- chronological splits;
- nuclear metrics;
- separation-energy calculations;
- benchmark gates;
- future superheavy policies.

## 4. Stable interfaces

The following PEC API should be considered stable at 0.1:

```text
Artifact
Event
Fact
Hypothesis
Intervention
ProvenanceRecord
FactStore
KnowledgeFreeze
PredictionRecord
HeldOutObservation
compare_held_out()
create_certificate()
verify_certificate()
search_interventions()
```

Zero-Mass model API:

```text
fit(train_records, freeze) -> fitted_model
predict(records) -> list[Prediction]
model_manifest() -> dict
```

## 5. Nuclear identity

Never identify a nuclide by element name alone.

```text
nuclide_id = "Z{Z}-N{N}"
A = Z + N
```

Optional human-readable symbol is metadata, not identity.

## 6. Minimum normalized observation

Each normalized mass observation carries:

```text
nuclide_id
Z
N
A
mass_excess_keV
uncertainty_keV
source_edition
source_release_date
source_record_status
ground_truth_eligible
raw_source_hash
normalizer_version
```

`ground_truth_eligible` must be derived by an explicit edition-specific policy. Do not silently treat extrapolated/evaluated values as direct experimental truth.

## 7. No-leakage enforcement

A KnowledgeFreeze has:

```text
freeze_id
cutoff_date
allowed_source_hashes
allowed_edition_ids
training_nuclide_ids
forbidden_source_hashes
feature_policy_id
```

The model fitting layer receives an object that exposes only allowed training rows. Test records are not passed into `fit()`.

A certificate MUST include the exact sorted training nuclide ID digest.

## 8. Model ladder

v0.2 model IDs:

- `ZME-SEMF-LS-v1`: least-squares SEMF baseline.
- `ZME-GP-DIRECT-v1`: direct GP control, optional in first merge.
- `ZME-SEMF-GP-RESIDUAL-v1`: default probabilistic hybrid.

The GP is a residual learner:

```text
residual = observed_mass - physics_mass
predicted_mass = physics_mass + predicted_residual
```

The scaffold expresses the calculation through binding energy internally, then converts back to mass excess.

## 9. SEMF baseline

Normative ASCII equation:

```text
B(Z,N) = a_v*A
       - a_s*A^(2/3)
       - a_c*Z*(Z-1)/A^(1/3)
       - a_a*(N-Z)^2/A
       + a_p*pairing_sign/sqrt(A)
```

where:

```text
A = Z + N
pairing_sign = +1 for even-even
pairing_sign = -1 for odd-odd
pairing_sign =  0 otherwise
```

Coefficients are refit on each historical training snapshot. Never reuse coefficients fit using future data.

## 10. Atomic mass excess to binding energy

Pin the numerical constants in the normalization manifest.

Normative ASCII equation:

```text
M_atom_u = A + mass_excess_keV / u_to_keV
B_MeV = (Z*m_H_u + N*m_n_u - M_atom_u) * u_to_MeV
```

Inverse:

```text
mass_excess_MeV = (Z*m_H_u + N*m_n_u - A) * u_to_MeV - B_MeV
mass_excess_keV = 1000 * mass_excess_MeV
```

The chosen constants are part of the run manifest. Changing constants creates a new normalization version.

## 11. GP residual features

Initial feature policy `ZME-FEATURES-DISCOVERY-MIN-v1`:

```text
Z
N
A
I = (N - Z) / A
pairing_sign
```

Do not provide magic numbers or distances to known magic numbers to the discovery model.

## 12. Uncertainty labels

The first GP standard deviation is NOT full scientific uncertainty. Label it:

```text
uncertainty_scope = "statistical_surrogate_conditioned_on_model"
```

Full uncertainty later separates:

```text
experimental
parameter
surrogate
model_form
model_ensemble
extrapolation_risk
```

## 13. Metrics

Point metrics:

```text
MAE_keV  = mean(abs(pred - truth))
RMSE_keV = sqrt(mean((pred - truth)^2))
```

Coverage:

```text
coverage_90 = count(truth inside 90_percent_interval) / n
coverage_95 = count(truth inside 95_percent_interval) / n
```

Use proper probabilistic scores when available, including negative log predictive density.

## 14. Evidence output

Each run creates:

```text
run_manifest.json
split_manifest.json
model_manifest.json
predictions.jsonl
prediction_certificates/*.json
metrics.json
calibration.json
report.md
```

These are append-only release artifacts. Rerunning with the same inputs must reproduce the same non-volatile hashes.

## 15. Unknown-territory lock

No CLI command may expose Z>118 prediction as a normal production command in v0.2. If an experimental developer command exists, it must emit:

```text
status = "EXTREME_EXTRAPOLATION"
scientific_release_allowed = false
```

and it must not be used in published v0.2 benchmark claims.
