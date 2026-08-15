# Master Coding Agent Prompt

You are implementing Zero-Mass Element v0.2 and Physics Evidence Core v0.1 from this bundle.

## Read order

Read the root README and every file in `docs/` before modifying code. Then read your assigned task file and `agents/task_manifest.json`.

## Mission

Build a falsifiable, validation-first nuclear prediction platform. The system must prove historical predictive credibility on known data before unknown-nucleus extrapolation is enabled.

## Critical constraints

- Global Variables and Zero-Mass Element remain separate domain projects.
- Extract generic evidence/provenance/certification machinery into Physics Evidence Core.
- Do not import Global Variables physical conjectures into PEC or Zero-Mass.
- Preserve Global Variables scientific benchmark behavior and committed certificates.
- No data leakage from later AME snapshots into historical model fit, preprocessing, feature scaling, hyperparameter selection, or target-derived features.
- Every equation affecting implementation must have ASCII form in documentation.
- Every scientific output must be linked to source hashes, code identity, model identity, knowledge cutoff and feature policy.
- Unknown territory Z>118 is release-locked.
- Do not invent missing source-data semantics. Read official AME edition documentation and preserve raw flags.
- Do not invent a software license.

## Required workflow

For each task:

```text
READ -> PLAN -> IMPLEMENT -> TEST -> CERTIFY -> REVIEW DIFF -> COMMIT
```

No task is complete because code "looks right". Satisfy its explicit acceptance commands.

## Stop conditions

Stop and produce a blocking report rather than guessing if:

- official source format semantics are ambiguous;
- canonical IDs change unexpectedly;
- historical cutoff cannot be proven;
- a required data file is missing;
- an existing Global Variables certificate degrades;
- a dependency license is incompatible or unknown for intended distribution.

A failed scientific benchmark is not automatically a coding failure. Preserve and report scientifically meaningful failures.
