# Acceptance Gates

## PEC gates

### PEC-G0 Packaging

```text
PASS if: package builds/imports from clean environment
```

### PEC-G1 Canonical identity

```text
PASS if: extracted canonical IDs match Global Variables test vectors exactly
```

### PEC-G2 Append-only provenance

```text
PASS if: mutation, missing parent, dependency cycle, and illegal namespace promotion all fail closed
```

### PEC-G3 Pass honesty

```text
PASS if: HEURISTIC cannot emit E0 and SOUND cannot claim E3/E4 under current contract
```

### PEC-G4 Certificate integrity

```text
PASS if: benign volatile-field changes do not trigger degradation and certification-surface changes do
```

### PEC-G5 Held-out firewall

```text
PASS if: prediction comparison proves target was not in training IDs and later truth cannot enter fit context
```

## Global Variables migration gates

### GV-G0 Existing certified suite

```text
python ci/run_all_certified.py -> PASS
```

### GV-G1 Standard test entry point

```text
python -m pytest -q -> PASS
```

### GV-G2 Certificate regression

No unexplained degradation or replacement of committed baseline certificates.

## ZME-B001 gates

### ZME-G0 Data provenance

Every raw and normalized source has SHA-256, edition, source location, parser version and ground-truth policy.

### ZME-G1 Chronological isolation

No later truth values are accessible during fit or prediction serialization.

### ZME-G2 Baseline reproducibility

Same snapshot + seed + code produces same model coefficients and prediction artifact hashes, excluding explicitly volatile metadata.

### ZME-G3 Sanity advantage

Residual model must be compared against SEMF. If it does not improve, report failure; do not tune on the test set.

### ZME-G4 Calibration

Coverage is reported at fixed predeclared levels. Failure to achieve calibration is a result, not a reason to edit test labels.

### ZME-G5 Extrapolation analysis

Error must be stratified by distance from training support.

### ZME-G6 Certificate completeness

Every prediction is linked to a freeze, model manifest, source hashes, feature policy and runtime manifest.

### ZME-G7 Unknown-territory lock

No release claim about Z>118 until later program gates authorize it.
