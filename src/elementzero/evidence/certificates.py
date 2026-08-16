"""ElementZero prediction certificates (benchmark-specific, Atlas-linked)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from elementzero.errors import SchemaError
from elementzero.evidence.hashing import content_id, sha256_hex

PREDICTIVE_DISTRIBUTION_GAUSSIAN = "gaussian"

REQUIRED_FIELDS = (
    "certificate_id",
    "benchmark_id",
    "nuclide_id",
    "observable",
    "prediction",
    "intervals",
    "predictive_distribution",
    "predictive_std_keV",
    "uncertainty_method",
    "uncertainty_scope",
    "model_id",
    "model_manifest_hash",
    "freeze_id",
    "training_identity_digest",
    "feature_policy_id",
    "atlas_pir_ref",
    "elementzero_commit",
    "source_hashes",
    "created_at",
    "ledger_state",
)


@dataclass(frozen=True)
class PredictionCertificate:
    certificate_id: str
    benchmark_id: str
    nuclide_id: str
    observable: str
    prediction: dict[str, Any]
    intervals: dict[str, list[float]]
    predictive_distribution: str
    predictive_std_keV: float
    uncertainty_method: str
    uncertainty_scope: str
    model_id: str
    model_manifest_hash: str
    freeze_id: str
    training_identity_digest: str
    feature_policy_id: str
    atlas_pir_ref: str
    elementzero_commit: str
    source_hashes: tuple[str, ...]
    created_at: str
    ledger_state: str
    atlas_fact_id: str | None = None
    legacy_id: str = "ZME-B001"

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "benchmark_id": self.benchmark_id,
            "legacy_id": self.legacy_id,
            "nuclide_id": self.nuclide_id,
            "observable": self.observable,
            "prediction": self.prediction,
            "intervals": self.intervals,
            "predictive_distribution": self.predictive_distribution,
            "predictive_std_keV": self.predictive_std_keV,
            "uncertainty_method": self.uncertainty_method,
            "uncertainty_scope": self.uncertainty_scope,
            "model_id": self.model_id,
            "model_manifest_hash": self.model_manifest_hash,
            "freeze_id": self.freeze_id,
            "training_identity_digest": self.training_identity_digest,
            "feature_policy_id": self.feature_policy_id,
            "atlas_pir_ref": self.atlas_pir_ref,
            "elementzero_commit": self.elementzero_commit,
            "source_hashes": list(self.source_hashes),
            "created_at": self.created_at,
            "ledger_state": self.ledger_state,
            "atlas_fact_id": self.atlas_fact_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PredictionCertificate:
        validate_certificate(data)
        return cls(
            certificate_id=data["certificate_id"],
            benchmark_id=data["benchmark_id"],
            nuclide_id=data["nuclide_id"],
            observable=data["observable"],
            prediction=dict(data["prediction"]),
            intervals={k: list(v) for k, v in data["intervals"].items()},
            predictive_distribution=data["predictive_distribution"],
            predictive_std_keV=float(data["predictive_std_keV"]),
            uncertainty_method=data["uncertainty_method"],
            uncertainty_scope=data["uncertainty_scope"],
            model_id=data["model_id"],
            model_manifest_hash=data["model_manifest_hash"],
            freeze_id=data["freeze_id"],
            training_identity_digest=data["training_identity_digest"],
            feature_policy_id=data["feature_policy_id"],
            atlas_pir_ref=data["atlas_pir_ref"],
            elementzero_commit=data["elementzero_commit"],
            source_hashes=tuple(data["source_hashes"]),
            created_at=data["created_at"],
            ledger_state=data["ledger_state"],
            atlas_fact_id=data.get("atlas_fact_id"),
            legacy_id=data.get("legacy_id", "ZME-B001"),
        )


def validate_certificate(data: Mapping[str, Any]) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise SchemaError(f"certificate missing fields: {missing}")
    if data["benchmark_id"] != "EZ-B001":
        raise SchemaError(f"new certificates must use EZ-B001, got {data['benchmark_id']!r}")
    if "mass_excess_keV" not in data["prediction"]:
        raise SchemaError("certificate.prediction must include mass_excess_keV")
    if data["predictive_distribution"] != PREDICTIVE_DISTRIBUTION_GAUSSIAN:
        raise SchemaError(
            "EZ-B001 v0.3 certificates declare a gaussian predictive distribution, "
            f"got {data['predictive_distribution']!r}"
        )
    if float(data["predictive_std_keV"]) <= 0.0:
        raise SchemaError("certificate.predictive_std_keV must be positive")
    if not data["uncertainty_method"]:
        raise SchemaError("certificate must state uncertainty_method")


def make_certificate(
    *,
    nuclide_id: str,
    prediction_keV: float,
    intervals: Mapping[str, Sequence[float]],
    predictive_std_keV: float,
    uncertainty_method: str,
    model_id: str,
    model_manifest_hash: str,
    freeze_id: str,
    training_identity_digest: str,
    feature_policy_id: str,
    atlas_pir_ref: str,
    elementzero_commit: str,
    source_hashes: Sequence[str],
    created_at: str,
    ledger_state: str = "OPEN",
    atlas_fact_id: str | None = None,
    observable: str = "mi:nuclear_atomic_mass_excess",
    uncertainty_scope: str = "model_and_training_freeze",
    predictive_distribution: str = PREDICTIVE_DISTRIBUTION_GAUSSIAN,
) -> PredictionCertificate:
    prediction = {"mass_excess_keV": prediction_keV}
    payload = {
        "benchmark_id": "EZ-B001",
        "nuclide_id": nuclide_id,
        "prediction": prediction,
        "intervals": {k: list(v) for k, v in intervals.items()},
        "predictive_std_keV": predictive_std_keV,
        "model_id": model_id,
        "freeze_id": freeze_id,
        "model_manifest_hash": model_manifest_hash,
    }
    return PredictionCertificate(
        certificate_id=content_id("crt", payload),
        benchmark_id="EZ-B001",
        nuclide_id=nuclide_id,
        observable=observable,
        prediction=prediction,
        intervals={k: list(v) for k, v in intervals.items()},
        predictive_distribution=predictive_distribution,
        predictive_std_keV=float(predictive_std_keV),
        uncertainty_method=uncertainty_method,
        uncertainty_scope=uncertainty_scope,
        model_id=model_id,
        model_manifest_hash=model_manifest_hash,
        freeze_id=freeze_id,
        training_identity_digest=training_identity_digest,
        feature_policy_id=feature_policy_id,
        atlas_pir_ref=atlas_pir_ref,
        elementzero_commit=elementzero_commit,
        source_hashes=tuple(source_hashes),
        created_at=created_at,
        ledger_state=ledger_state,
        atlas_fact_id=atlas_fact_id,
    )


def certificate_digest(cert: PredictionCertificate | Mapping[str, Any]) -> str:
    payload = cert.to_dict() if isinstance(cert, PredictionCertificate) else dict(cert)
    return sha256_hex(payload)
