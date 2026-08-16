"""Prediction sealing and truth-unlock verification (spec sections 12-13).

Blind prediction inputs contain no target truth; the sealed prediction set
is hashed and its hash must be committed to git before scoring. Truth
unlock re-verifies every governing hash; any mismatch is
CLAIM_INTEGRITY_FAILURE and the run STOPS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file

CLAIM_INTEGRITY_FAILURE = "CLAIM_INTEGRITY_FAILURE"

SEALED_PREDICTIONS_FILE = "SEALED_PREDICTIONS.json"
SEALED_PREDICTIONS_HASH_FILE = "SEALED_PREDICTIONS_SHA256"

SEAL_INPUT_RULE = (
    "ez-wo14-seal-inputs-v1: prediction inputs are approved training-era "
    "data, identity-only targets, the frozen model registry, eligibility "
    "records, the subfederation manifest, the runtime lock, the "
    "preregistration, and source hashes — never target truth"
)


def write_seal(dest: str | Path, payload: dict[str, Any]) -> str:
    """Write SEALED_PREDICTIONS.json + its recorded hash; return the hash."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    seal_path = dest / SEALED_PREDICTIONS_FILE
    seal_path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    digest = sha256_file(seal_path)
    (dest / SEALED_PREDICTIONS_HASH_FILE).write_text(digest + "\n", encoding="utf-8")
    return digest


def read_seal_hash(dest: str | Path) -> str:
    dest = Path(dest)
    recorded = (
        (dest / SEALED_PREDICTIONS_HASH_FILE).read_text(encoding="utf-8").strip()
    )
    actual = sha256_file(dest / SEALED_PREDICTIONS_FILE)
    if actual != recorded:
        raise ProtocolError(
            f"{CLAIM_INTEGRITY_FAILURE}: sealed predictions in {dest} do not "
            "match their recorded hash"
        )
    return recorded


def unlock_truth(
    *,
    seal_dir: str | Path,
    expected_seal_hash: str,
    eligibility_manifest_hash: str,
    expected_eligibility_hash: str,
    threshold_hash: str,
    expected_threshold_hash: str,
    registry_hash: str,
    expected_registry_hash: str,
    protocol_hash: str,
    expected_protocol_hash: str,
    target_identity_digest: str,
    expected_target_identity_digest: str,
) -> dict[str, Any]:
    """Verify every governing hash before any truth value is scored."""
    seal_hash = read_seal_hash(seal_dir)
    checks = {
        "prediction_seal_hash": (seal_hash, expected_seal_hash),
        "eligibility_manifest_hash": (
            eligibility_manifest_hash,
            expected_eligibility_hash,
        ),
        "threshold_hash": (threshold_hash, expected_threshold_hash),
        "model_registry_hash": (registry_hash, expected_registry_hash),
        "protocol_hash": (protocol_hash, expected_protocol_hash),
        "target_identity_digest": (
            target_identity_digest,
            expected_target_identity_digest,
        ),
    }
    for name, (actual, expected) in checks.items():
        if actual != expected:
            raise ProtocolError(
                f"{CLAIM_INTEGRITY_FAILURE}: {name} is {actual}, expected "
                f"{expected}; truth stays locked"
            )
    return {
        "truth_unlocked": True,
        "verified": {name: actual for name, (actual, _) in checks.items()},
    }
