"""Truth unlock (spec section 13) — the verifying gate lives with the seal.

Re-exported so the package layout matches the work order; the verification
logic is in ``prediction_seal.unlock_truth`` because the seal hash is the
first thing the unlock checks.
"""

from __future__ import annotations

from elementzero.real_validation.prediction_seal import (
    CLAIM_INTEGRITY_FAILURE,
    read_seal_hash,
    unlock_truth,
)

__all__ = ["CLAIM_INTEGRITY_FAILURE", "read_seal_hash", "unlock_truth"]
