"""WO-14 — evaluated-data v2 validation with claim integrity.

Executes the four preregistered real tracks (B002/B003 x BLIND/RECON)
against real evaluated nuclear data while preserving every claim boundary
WO-13 established. Engineering success is protocol integrity and honest
claim adjudication; scientific success is never assumed, and
FULL_SHELL_BLIND_NOT_EVALUABLE is a valid result.
"""

from __future__ import annotations

WO14_ID = "WO-14"
REPORTS_RELPATH = "reports/real_validation/wo14"
RESULTS_RELPATH = "results"
