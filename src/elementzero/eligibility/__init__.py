"""WO-13 — real-data blindness, eligibility, and claim integrity.

Core rule:

    a target hidden from ElementZero is NOT automatically blind to an
    imported physics table.

A published global model may already have been calibrated on the target
mass. This package decides, target by target and model by model, what claim
each prediction lineage is scientifically allowed to make against real
evaluated data — before any real scoring happens (WO-14).
"""

from __future__ import annotations

WO13_ID = "WO-13"
REPORTS_RELPATH = "reports/eligibility/wo13"
