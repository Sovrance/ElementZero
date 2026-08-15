# Reviewed Repository Snapshot

Input archive:

    ElementZero-main.zip

Observed root files:

    AGENTS.md
    README.md
    VERSION
    atlas.lock.json
    manifest.json
    pyproject.toml
    .github/workflows/ci.yml

Observed package:

    src/elementzero

Observed benchmark stages:

    b001_prepare.py
    b001_freeze.py
    b001_predict.py
    b001_finalize.py
    b001_score.py

Observed models:

    EZ-SEMF-LS-v1
    EZ-GP-DIRECT-v1
    EZ-SEMF-GP-RESIDUAL-v1

Observed controls:

    identity-only targets
    KnowledgeFreeze
    immutable Atlas SHA validation
    leakage tests
    prediction finalization
    separate truth scoring
    reproducibility tests

Observed technical debt relevant to the next work:

    VERSION still uses Zero-Mass Element / PEC names.
    AME2020 currently shares old AME column slices.
    current AME status vocabulary may overstate direct experimental provenance.
    b001_prepare subtracts all old identities, including estimated old rows.
    prediction Atlas lineage uses only obs_facts[:1].
    validation facts are not linked to persisted prediction/truth/finalization parents.
    scoring lacks NLPD, median error, calibration error, and distance analysis.
    tools/ensure_atlas_pir.py synthesizes packaging metadata into a cloned Atlas checkout.

This snapshot is informational. Current repository code at implementation time remains authoritative.
