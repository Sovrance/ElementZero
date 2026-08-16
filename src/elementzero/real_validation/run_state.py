"""The WO-14 run state machine (spec section 3).

    PREREGISTERED -> INPUTS_VERIFIED -> PREDICTIONS_GENERATED ->
    PREDICTIONS_FINALIZED -> SEALED_COMMIT_RECORDED -> TRUTH_UNLOCKED ->
    SCORED -> CLAIM_ADJUDICATED -> REPORTED

Truth cannot be scored before PREDICTIONS_FINALIZED, and a prediction
change after finalization creates a new run id, never an edit.
"""

from __future__ import annotations

from typing import Any

from elementzero.errors import ProtocolError

RUN_STATES = (
    "PREREGISTERED",
    "INPUTS_VERIFIED",
    "PREDICTIONS_GENERATED",
    "PREDICTIONS_FINALIZED",
    "SEALED_COMMIT_RECORDED",
    "TRUTH_UNLOCKED",
    "SCORED",
    "CLAIM_ADJUDICATED",
    "REPORTED",
)

_STATE_INDEX = {state: index for index, state in enumerate(RUN_STATES)}


class RealValidationRun:
    """One sealed run's state record; transitions are forward-only."""

    def __init__(
        self,
        *,
        experiment_id: str,
        run_id: str,
        claim_track: str,
        protocol_hash: str,
        eligibility_manifest_hash: str,
    ) -> None:
        self.experiment_id = experiment_id
        self.run_id = run_id
        self.claim_track = claim_track
        self.protocol_hash = protocol_hash
        self.eligibility_manifest_hash = eligibility_manifest_hash
        self.state = "PREREGISTERED"
        self.prediction_seal_hash: str | None = None
        self.history: list[str] = ["PREREGISTERED"]

    def advance(self, state: str) -> None:
        if state not in _STATE_INDEX:
            raise ProtocolError(f"unknown run state {state!r}")
        if _STATE_INDEX[state] != _STATE_INDEX[self.state] + 1:
            raise ProtocolError(
                f"illegal transition {self.state} -> {state}; the run state "
                "machine is forward-only and skips nothing"
            )
        if state == "TRUTH_UNLOCKED" and self.prediction_seal_hash is None:
            raise ProtocolError(
                "truth cannot be unlocked before the prediction seal exists"
            )
        self.state = state
        self.history.append(state)

    def record_seal(self, seal_hash: str) -> None:
        if _STATE_INDEX[self.state] < _STATE_INDEX["PREDICTIONS_FINALIZED"]:
            raise ProtocolError(
                "a prediction seal requires PREDICTIONS_FINALIZED first"
            )
        if self.prediction_seal_hash is not None and (
            self.prediction_seal_hash != seal_hash
        ):
            raise ProtocolError(
                "a prediction change after finalization requires a NEW run id, "
                "never a reseal"
            )
        self.prediction_seal_hash = seal_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "claim_track": self.claim_track,
            "state": self.state,
            "protocol_hash": self.protocol_hash,
            "eligibility_manifest_hash": self.eligibility_manifest_hash,
            "prediction_seal_hash": self.prediction_seal_hash or "",
            "truth_unlocked": _STATE_INDEX[self.state]
            >= _STATE_INDEX["TRUTH_UNLOCKED"],
            "claim_adjudicated": _STATE_INDEX[self.state]
            >= _STATE_INDEX["CLAIM_ADJUDICATED"],
        }
