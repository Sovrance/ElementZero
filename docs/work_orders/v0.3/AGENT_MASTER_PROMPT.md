# Master Coding Agent Prompt

You are implementing ElementZero Engineering Work Orders 01-10.

## Source of truth

Read in this order:

1. 00_MASTER_EXECUTION_ORDER.md
2. the numbered work order you are assigned
3. SOURCES.md
4. current ElementZero repository code
5. current pinned Atlas PIR public API

Do not treat legacy Zero-Mass Element / PEC documents as normative.

## Non-negotiable rules

1. Work cumulatively from current ElementZero code.
2. One work order per PR unless explicitly directed otherwise.
3. Do not weaken leakage controls.
4. Do not expose later truth to prediction code.
5. Do not replace Atlas PIR with copied local classes.
6. Do not change model hyperparameters after historical scoring under the same protocol version.
7. Preserve all poor scientific results.
8. Every scientific artifact must be hashable and reproducible.
9. All normative equations are ASCII-first.
10. Stop at the work order's STOP conditions rather than improvising around them.

## Required completion response

At the end of each work order, report:

    WORK_ORDER
    STATUS
    COMMIT_SHA
    FILES_CHANGED
    TESTS_RUN
    TEST_RESULTS
    SCHEMA_CHANGES
    MIGRATION_NOTES
    SCIENTIFIC_BEHAVIOR_CHANGES
    KNOWN_LIMITATIONS
    NEXT_WORK_ORDER_READY: yes/no

Do not merely say "done."

## Scientific firewall

ElementZero may import Atlas PIR evidence infrastructure.

ElementZero must not silently import Atlas research conjectures as nuclear-physics priors.

## Result honesty

A model can perform badly and the work order can still be engineering-complete.

Never tune after looking at held-out truth without creating a new protocol version and rerunning the comparable benchmark set.
