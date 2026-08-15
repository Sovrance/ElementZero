# T11 - Release and Cross-Agent Readability Audit

## Objective

Prove the v0.2/PEC v0.1 handoff is reproducible, reviewable, and readable by another coding agent without relying on hidden context or rendered equation objects.

## Full validation matrix

### Global Variables

```bash
python -m pytest -q
python ci/run_all_certified.py
```

### PEC

```bash
python -m pytest -q
python -m build
```

### Zero-Mass Element

```bash
python -m pytest -q
zme --help
```

### Documentation/bundle

```bash
python scripts/validate_bundle.py
```

## Determinism check

Run ZME-B001 twice with identical source files, target manifest, seed, code and dependencies. Compare scientific artifact hashes excluding documented volatile metadata.

## Cross-agent handoff test

Give a fresh coding agent only:

```text
README.md
agents/MASTER_CODING_AGENT_PROMPT.md
agents/task_manifest.json
relevant task file
docs/
```

Ask it to explain:

1. the package boundaries;
2. how historical leakage is prevented;
3. when later truth is parsed;
4. the SEMF equation;
5. which components remain Global Variables-specific;
6. which command proves the supplied GV suite remains healthy.

If it cannot answer these without guessing, improve docs before release.

## Math audit

Search normative docs for Unicode-only equations, embedded images used as equations, or undefined symbols. Every implementation equation must have an ASCII `text` block.

## Release report

Create `RELEASE_READINESS_v0.2.md` with:

```text
PASS/FAIL per gate
known scientific limitations
known engineering limitations
real B001 checkpoint results if T10 complete
whether unknown-territory mode remains locked (must be YES)
next recommended release scope
```

## Acceptance

No red gate is hidden. Release can be engineering-complete even if a model underperforms scientifically; in that case the scientific result is recorded as a failure to beat baseline.
