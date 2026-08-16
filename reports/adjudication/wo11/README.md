# WO-11 — Evidence Adjudication artifacts

Machine-readable adjudication of the frozen EZ-B002-v1 and EZ-B003-v1
results. The v1 experiments under `experiments/` are immutable inputs;
nothing in this directory reruns, relaxes, or relabels them.

Read `WO11_Evidence_Adjudication_Report.md` first; every table in it is
derived from the JSON artifacts committed next to it. Rebuild with:

    elementzero adjudicate wo11

The rebuild is deterministic: it reproduces every file in this
directory byte for byte from the frozen evidence baseline.
