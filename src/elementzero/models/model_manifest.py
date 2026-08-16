"""Model-manifest hashing for certificates and run artifacts."""

from __future__ import annotations

from typing import Any

from elementzero.evidence.hashing import sha256_hex
from elementzero.identity_meta import runtime_library_versions
from elementzero.models.protocol import PREDICTIVE_DISTRIBUTION_GAUSSIAN


def model_manifest(
    *,
    model_id: str,
    model_payload: dict[str, Any],
    freeze_id: str,
    feature_policy_id: str,
    random_seed: int = 0,
) -> dict[str, Any]:
    """Manifest for one fitted model.

    ``uncertainty_method`` is surfaced at the top level so a reader never has to
    guess how sigma was constructed (WO-03 section 1).
    """
    uncertainty_method = model_payload.get("uncertainty_method")
    if not uncertainty_method:
        raise ValueError(f"model {model_id!r} manifest must state uncertainty_method")
    return {
        "model_id": model_id,
        "model": model_payload,
        "freeze_id": freeze_id,
        "feature_policy_id": feature_policy_id,
        "random_seed": random_seed,
        "predictive_distribution": model_payload.get(
            "predictive_distribution", PREDICTIVE_DISTRIBUTION_GAUSSIAN
        ),
        "uncertainty_method": uncertainty_method,
        "library_versions": runtime_library_versions(),
    }


def manifest_hash(manifest: dict[str, Any]) -> str:
    return sha256_hex(manifest)
