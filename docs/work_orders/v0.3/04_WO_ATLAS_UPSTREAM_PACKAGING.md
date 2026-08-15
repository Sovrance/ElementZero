# WO-04 - Make Atlas PIR a Clean Upstream Dependency

Priority: HIGH
Repositories: Sovrance/Atlas and ElementZero
Depends on: WO-01
Blocks: WO-05

## Objective

Remove ElementZero's temporary local packaging overlay and make Atlas PIR installable directly from an immutable upstream commit.

Current ElementZero pin reviewed:

    31d76d094f1206e64a6920da4775d0a684618357

Current ElementZero helper:

    tools/ensure_atlas_pir.py

This helper clones Atlas and writes a pyproject.toml into the local clone if Atlas packaging metadata is absent.

That is a valid bootstrap mechanism, not the desired permanent architecture.

## Part A - Atlas upstream PR

Repository:

    https://github.com/Sovrance/Atlas

## 1. Add root pyproject.toml

Distribution:

    sovrance-atlas-pir

Python import remains:

    import pir

Package only:

    pir
    pir.*

Do NOT package the entire Atlas research repository into the distribution by default.

Recommended metadata:

    [build-system]
    requires = ["setuptools>=75", "wheel"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "sovrance-atlas-pir"
    version = "0.1.0"
    requires-python = ">=3.11"

    [tool.setuptools.packages.find]
    where = ["."]
    include = ["pir", "pir.*"]

    [tool.setuptools.package-data]
    pir = ["schema/*.json", "manifest.json"]

## 2. Clean install test

From a fresh virtual environment:

    pip install -e .

Then:

    python -c "import pir; print(pir.__version__)"

and:

    python -c "from pir import Artifact, Fact, FactStore, Hypothesis, Intervention"

and:

    python -c "from pir import forward, intervention_search"

All must pass without repository-root sys.path manipulation.

## 3. Fix B4 pytest discovery collision if still present

Current reviewed Atlas files contain:

    b4_area_pipeline/pipeline.py:
        def test_event(...)

and:

    tests/test_b4.py:
        from b4_area_pipeline.pipeline import ... test_event

Rename production callable:

    evaluate_event(...)

Temporary compatibility if needed:

    test_event = evaluate_event
    test_event.__test__ = False

Update callers.

This change MUST NOT change scientific output.

## 4. Preserve Atlas certified runner

Run both:

    python -m pytest -q
    python ci/run_all_certified.py

The upstream PR is not complete until both pass.

## 5. Optional release tag

Recommended:

    pir-v0.1.0

The immutable commit SHA remains the downstream source of truth.

## Part B - ElementZero downstream PR

After Atlas upstream merges, capture:

    NEW_ATLAS_SHA=<40-character merged commit>

Modify:

    atlas.lock.json
    pyproject.toml
    [tool.elementzero.atlas]
    docs/adr/ADR-0001-atlas-pir-boundary.md
    docs/architecture/atlas-integration.md

Dependency:

    sovrance-atlas-pir @
      git+https://github.com/Sovrance/Atlas.git@NEW_ATLAS_SHA

Never use:

    main
    HEAD
    master
    latest

## 6. Retire overlay behavior

Change:

    tools/ensure_atlas_pir.py

from:

    clone + synthesize pyproject + install

to either:

A. remove it entirely and let pip install pyproject dependencies,

or:

B. retain only as a verifier that:
   - checks lock SHA,
   - installs the real upstream package,
   - refuses to create packaging metadata.

Preferred: B for CI diagnostics, but no source mutation.

## 7. Contract test

ElementZero must test:

    pir.__version__ in supported_versions
    installed Atlas repository SHA == atlas.lock.json ref
    required public imports exist
    no Atlas benchmark modules imported by ElementZero production package

Existing firewall tests must remain.

## 8. Rollback

If the Atlas packaging PR cannot be made without breaking Atlas:

- keep the current immutable overlay temporarily,
- record the blocked upstream issue,
- DO NOT change ElementZero to a mutable Atlas branch.

WO-05 is blocked until either:
- upstream package is clean, or
- a formally documented exception approves the immutable overlay.

## Acceptance gates

Atlas:

- clean editable install works,
- pytest passes,
- certified runner passes,
- B4 production symbol is not accidentally collected.

ElementZero:

- dependency resolves directly from pinned Atlas SHA,
- no local packaging metadata is injected into Atlas clone,
- contract/firewall tests pass,
- full ElementZero suite passes.

## Stop conditions

STOP if:

- Atlas main is used as a dependency,
- ElementZero copies pir/ into its own src tree,
- Atlas benchmark conclusions are imported as nuclear priors,
- upstream packaging changes alter certified benchmark results.
