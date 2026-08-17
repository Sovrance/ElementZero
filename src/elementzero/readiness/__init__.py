"""WO-15B: mass calibration, model discrepancy, and B005 readiness.

WO-15 established that two independent blind-eligible physics families
can produce sealed, converged predictions. It did not establish that
those predictions are any good: blind mass errors ran to several MeV and
the registered uncertainty missed the dominant term entirely.

WO-15B repairs both using training-era evidence only, then tests the
result on a fresh blind challenge, EZ-B005-v1. The firewall widens
accordingly: WO-14 truth was already forbidden, and B004 truth — now
revealed — joins it. Neither may touch a fit, a hyperparameter, a
threshold, a weight, or a stopping rule.
"""

from __future__ import annotations

WO15B_ID = "WO-15B"
B005_ID = "EZ-B005-v1"

REPORTS_RELPATH = "reports/readiness/wo15b"
EXPERIMENT_RELPATH = "experiments/EZ-B005-v1"
RESULTS_RELPATH = "results/EZ-B005-v1"

# Every stage of WO-15B is downstream of these two statements.
TRUTH_FIREWALL_RULE = (
    "ez-wo15b-truth-firewall-v1: B004 truth is revealed and is retrospective "
    "evidence only. It may not enter EDF parameter fitting, discrepancy "
    "fitting, hyperparameter selection, uncertainty scaling, family "
    "selection, ensemble weights, stopping criteria, or acceptance "
    "thresholds. WO-14 truth and B005 truth are forbidden on the same terms"
)

CHILD_FAMILY_RULE = (
    "ez-wo15b-child-family-v1: a discrepancy model is a child of the physics "
    "family it corrects. It carries that family's independence group and "
    "never creates a new one, so correcting a family can improve its numbers "
    "but can never increase the count of independent blind families"
)

__all__ = [
    "B005_ID",
    "CHILD_FAMILY_RULE",
    "EXPERIMENT_RELPATH",
    "REPORTS_RELPATH",
    "RESULTS_RELPATH",
    "TRUTH_FIREWALL_RULE",
    "WO15B_ID",
]
