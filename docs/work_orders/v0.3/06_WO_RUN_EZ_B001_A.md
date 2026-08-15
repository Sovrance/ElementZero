# WO-06 - Execute and Seal EZ-B001-A: AME2003 -> AME2012

Priority: CRITICAL
Repository: ElementZero
Depends on: WO-05
Blocks: WO-07 and WO-08

## Objective

Produce ElementZero's first real historical prediction result under the preregistered protocol.

Engineering success is protocol integrity, not low error.

## Required input files

Raw authoritative files:

    AME2003 mass table
    AME2012 mass table

Recommended local paths:

    data/raw/amdc/AME2003/mass.mas03
    data/raw/amdc/AME2012/mass.mas12

Raw source files should normally remain gitignored.

Commit:

    URLs
    SHA-256 hashes
    parser reports

Do not normalize by editing the raw files.

## Phase 0 - Verify environment

Record:

    python version
    numpy version
    scipy version
    scikit-learn version
    ElementZero commit SHA
    Atlas commit SHA
    preregistration SHA

Run:

    ruff check src tests
    python -m pytest -q

Abort on failure.

## Phase 1 - Parser certification

Run each official source through the certified parser.

Persist:

    experiments/EZ-B001-A/data_audit/
        ame2003_parse_report.json
        ame2012_parse_report.json

Verify:

    parsed_records > 0
    eligible_records > 0
    malformed rate within accepted bound
    all A == Z + N
    raw SHA matches preregistration

## Phase 2 - Prepare identity-only targets

The preparation process may read both editions.

Output:

    experiments/EZ-B001-A/targets.json

After creation validate:

    every target has exactly:
        nuclide_id
        Z
        N
        A

    no:
        mass
        uncertainty
        truth
        binding energy

Persist:

    target_identity_digest

## Phase 3 - Build KnowledgeFreeze

Use only AME2003 as allowed training source.

Required freeze contents:

    allowed_source_hashes = [AME2003 hash]
    forbidden_source_hashes contains AME2012 hash
    training_identity_digest
    normalized_table_hash
    feature_policy_hash
    Atlas SHA
    ElementZero SHA

Output:

    experiments/EZ-B001-A/freeze.json

## Phase 4 - Transfer to blind prediction workspace

The prediction workspace contains:

    ElementZero code at preregistered commit
    Atlas at preregistered commit
    AME2003 raw source
    targets.json
    freeze.json
    preregistration files

It must not contain AME2012 raw truth.

Run an automated filesystem preflight that fails if known truth filenames or truth source hash are present in the prediction input directory.

## Phase 5 - Predict all three models

Run directories:

    runs/EZ-B001-A/EZ-SEMF-LS-v1/
    runs/EZ-B001-A/EZ-GP-DIRECT-v1/
    runs/EZ-B001-A/EZ-SEMF-GP-RESIDUAL-v1/

For every model:

    fit using freeze-approved AME2003 observations only
    generate predictions
    generate prediction certificates
    persist Atlas facts/provenance
    write model manifest
    write run manifest

No scoring yet.

## Phase 6 - Finalize each ledger

For each model:

    elementzero benchmark finalize --run <run_dir>

The marker must seal at least:

    freeze.json
    model_manifest.json
    predictions.json
    certificates.json
    Atlas fact bundle
    run_manifest.json

If finalization currently seals fewer artifacts, extend it.

## Phase 7 - Create experiment-level sealed manifest

Before truth unlock create:

    experiments/EZ-B001-A/SEALED_PREDICTIONS.json

Contents:

    experiment_id
    protocol_version
    preregistration_hash
    target_identity_digest
    model run IDs
    each finalization marker hash
    each predictions file hash
    each certificate file hash
    timestamp
    ElementZero SHA
    Atlas SHA

Hash this file and write:

    SEALED_PREDICTIONS_SHA256

## Phase 8 - Commit seal BEFORE scoring

Commit the preregistration, targets, freeze, and sealed prediction manifests.

Recommended tag:

    ez-b001-a-predictions-sealed-v1

The git commit must exist before scoring.

Do not amend that commit after truth unlock.

## Phase 9 - Truth unlock and score

Now provide AME2012 to the separate scoring process.

For each model:

    verify finalization intact
    verify AME2012 hash equals preregistered forbidden hash
    load eligible AME2012 target truth
    calculate all preregistered metrics
    write Atlas TruthDatasetFact
    write Atlas ValidationFact

Outputs:

    results/EZ-B001-A/<model_id>/
        metrics.json
        score_report.json
        scored_predictions.json
        atlas/
            scoring_facts.json
            scoring_provenance.json

## Phase 10 - Model comparison

Generate:

    results/EZ-B001-A/model_comparison.json
    results/EZ-B001-A/model_comparison.md

No cherry-picking.

All three models appear even if one performs badly.

## Required negative tests

During a dry run, verify that each of these fails:

1. put truth field in targets.json
2. use AME2012 as training source
3. put a target identity into training set
4. alter predictions after finalization
5. score before finalization
6. alter preregistration hash
7. use different target set for one model

## Acceptance gates

Engineering PASS if:

- source hashes match preregistration,
- prediction workspace had no truth contents,
- all three models used the exact same freeze/targets,
- all runs finalized before score,
- sealed prediction commit exists before score,
- score reports reproduce,
- Atlas validation lineage is complete,
- all preregistered metrics are reported.

Scientific performance has no minimum pass threshold.

## Stop conditions

STOP scoring if:

- prediction artifacts changed after seal,
- the target manifest differs across models,
- source hash differs from preregistration,
- any run was fit after truth was unlocked,
- code commit differs from preregistration without a protocol bump.
