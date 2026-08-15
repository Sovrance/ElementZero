# WO-08 - Publish ElementZero Historical Benchmark Report v1

Priority: HIGH
Repository: ElementZero
Depends on: WO-07
Blocks: WO-09

## Objective

Turn EZ-B001-A/B/C into a complete scientific benchmark record that another researcher or coding agent can reproduce without relying on chat history.

Deliverable:

    ElementZero Historical Benchmark Report v1

This is a repository report, not a marketing summary.

## New modules

Recommended:

    src/elementzero/reporting/__init__.py
    src/elementzero/reporting/historical.py

New output tree:

    reports/historical/v1/
        README.md
        ElementZero_Historical_Benchmark_Report_v1.md
        aggregate_metrics.json
        model_table.csv
        distance_table.csv
        artifact_manifest.json
        figures/
        SHA256SUMS.txt

## 1. Required report sections

1. Research question
2. Protocol and preregistration
3. Data editions
4. Ground-truth eligibility policy
5. Leakage controls
6. Model definitions
7. Uncertainty definitions
8. Metrics
9. EZ-B001-A results
10. EZ-B001-B results
11. EZ-B001-C results
12. Longitudinal comparison
13. Error vs extrapolation distance
14. Calibration
15. Model failures
16. Limitations
17. Deviations from preregistration
18. Reproducibility instructions
19. Artifact hashes
20. Next benchmark decision

## 2. No selective reporting

All preregistered models and metrics must appear.

Forbidden:

    omit a poor model
    omit an epoch with bad calibration
    report only RMSE if NLPD is poor
    call post-hoc metric preregistered
    silently rerun with new hyperparameters

## 3. Tables

Primary table:

    Experiment | Model | N | MAE | MedAE | RMSE | NLPD | Cov90 | Cov95

Calibration table:

    Experiment | Model | CalErr90 | CalErr95

Distance table:

    Experiment | Model | DistanceBucket | N | MAE | RMSE | NLPD

## 4. Figures

Recommended:

    predicted vs truth
    absolute error vs nearest-training L1 distance
    coverage by epoch/model
    RMSE by epoch/model

Figures are secondary to machine-readable tables.

Every figure must be generated from committed JSON/CSV artifacts.

Do not manually edit plotted data.

## 5. Statistical honesty

Do not attach significance claims that were not preregistered.

Do not infer "AI learned nuclear physics" from low error.

Allowed conclusions are limited to what the benchmark measures:

    interpolation/extrapolation behavior
    historical predictive accuracy
    calibration
    distance degradation
    relative behavior of model families

## 6. Atlas evidence summary

Include a diagram:

    source
      ->
    normalized dataset
      ->
    freeze
      ->
    model fit
      ->
    prediction set
      ->
    finalization
      ->
    truth
      ->
    validation

List Atlas and ElementZero commit SHAs.

## 7. Reproducibility command

Provide one top-level command or script:

    python scripts/reproduce_historical_report.py

It should:

    validate hashes
    replay scoring
    rebuild aggregate tables
    rebuild report figures
    verify expected artifact hashes

It must NOT refit models unless an explicit:

    --refit

flag is supplied.

## 8. Machine-readable status

Create:

    reports/historical/v1/benchmark_status.json

Required:

    protocol_version
    experiments_completed
    models
    engineering_status
    scientific_summary
    known_failures
    next_gate

Do not encode a single "PASS" based only on model accuracy.

## 9. Release tag

Recommended after report audit:

    elementzero-historical-benchmark-v1

The tag should point to a commit containing:

    preregistrations
    sealed hashes
    score outputs
    report
    reproduction script

## Required tests

    test_report_contains_all_models_and_epochs
    test_report_metrics_match_json
    test_figures_build_from_committed_artifacts
    test_reproduce_report_does_not_refit_by_default
    test_sha_manifest_complete
    test_posthoc_fields_labeled
    test_no_missing_primary_metric

## Acceptance gates

PASS only if:

- a clean checkout can rebuild the report,
- all 3 epochs x 3 models are represented,
- report matches machine-readable metrics,
- deviations are disclosed,
- poor results are retained,
- artifact hashes verify.

## Stop conditions

Do not start EZ-B002 until:

- the historical report exists,
- reproducibility replay passes,
- unresolved data/parser issues are documented,
- any benchmark protocol changes are versioned.
