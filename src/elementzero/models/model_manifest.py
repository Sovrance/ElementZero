"""Model-manifest hashing for certificates and run artifacts."""

from __future__ import annotations

from typing import Any

from elementzero.evidence.hashing import sha256_hex
from elementzero.identity_meta import runtime_library_versions


def model_manifest(
    *,
    model_id: str,
    model_payload: dict[str, Any],
    freeze_id: str,
    feature_policy_id: str,
    random_seed: int = 0,
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "model": model_payload,
        "freeze_id": freeze_id,
        "feature_policy_id": feature_policy_id,
        "random_seed": random_seed,
        "library_versions": runtime_library_versions(),
    }


def manifest_hash(manifest: dict[str, Any]) -> str:
    return sha256_hex(manifest)
