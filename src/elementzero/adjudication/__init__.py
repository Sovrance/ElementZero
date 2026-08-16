"""WO-11 — Evidence Adjudication and Frontier Model Readiness.

This package diagnoses the frozen EZ-B002-v1 / EZ-B003-v1 results. It never
edits them: the v1 experiments are immutable historical evidence, and every
function here either reads them, replays them into a *separate* workspace, or
runs development-only diagnostics on new fixtures.

Governing rules (WO-11 section 0):

    - EZ-B002-v1 and EZ-B003-v1 stay byte-for-byte unchanged.
    - No threshold of a frozen criterion moves.
    - No frontier nuclear model is added here; WO-12 is the first work order
      allowed to do that, and only under new benchmark protocol versions.
"""

from __future__ import annotations

WO11_ID = "WO-11"
WO11_PROGRAM = "ElementZero v0.4 - Validation Recovery & Model Federation"

# The frozen evidence baseline WO-11 adjudicates. The tag names the WO-10 head:
# the last commit of the v0.3 validation ladder, which sealed and scored both
# failed benchmarks.
INPUT_RELEASE = "elementzero-validation-ladder-v0.3"

# Default output location for the committed WO-11 report artifacts.
REPORTS_RELPATH = "reports/adjudication/wo11"

# Machine-readable readiness verdicts (WO-11 section 16). Order matters for
# decision precedence: infrastructure defects outrank benchmark defects, which
# outrank any statement about models.
VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED = "INFRASTRUCTURE_REPAIR_REQUIRED"
VERDICT_BENCHMARK_REPAIR_REQUIRED = "BENCHMARK_REPAIR_REQUIRED"
VERDICT_NOT_YET_JUSTIFIED = "FRONTIER_MODEL_RERUN_NOT_YET_JUSTIFIED"
VERDICT_JUSTIFIED = "FRONTIER_MODEL_RERUN_JUSTIFIED"

ALLOWED_READINESS_VERDICTS = (
    VERDICT_JUSTIFIED,
    VERDICT_NOT_YET_JUSTIFIED,
    VERDICT_BENCHMARK_REPAIR_REQUIRED,
    VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED,
)

__all__ = [
    "ALLOWED_READINESS_VERDICTS",
    "INPUT_RELEASE",
    "REPORTS_RELPATH",
    "VERDICT_BENCHMARK_REPAIR_REQUIRED",
    "VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED",
    "VERDICT_JUSTIFIED",
    "VERDICT_NOT_YET_JUSTIFIED",
    "WO11_ID",
    "WO11_PROGRAM",
]
