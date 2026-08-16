"""Historical KnowledgeFreeze objects owned by ElementZero."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from elementzero.atlas_pin import atlas_pir_ref
from elementzero.data.identity import nuclide_id, parse_nuclide_id
from elementzero.data.observations import TRUTH_BEARING_FIELDS, MassObservation
from elementzero.errors import LeakageError, SchemaError
from elementzero.evidence.hashing import content_id, sha256_hex
from elementzero.identity_meta import elementzero_commit
from elementzero.physics.constants import NORMALIZER_VERSION

FEATURE_POLICY_EZ_B001 = "ez-b001-identity-zn-v1"
ALLOWED_TARGET_FIELDS = frozenset({"nuclide_id", "Z", "N", "A"})


@dataclass(frozen=True)
class KnowledgeFreeze:
    freeze_id: str
    cutoff_date: str
    allowed_source_hashes: tuple[str, ...]
    allowed_edition_ids: tuple[str, ...]
    training_nuclide_ids: tuple[str, ...]
    training_identity_digest: str
    forbidden_source_hashes: tuple[str, ...]
    feature_policy_id: str
    atlas_pir_ref: str
    elementzero_commit: str
    raw_source_hash: str
    normalized_table_hash: str
    feature_policy_hash: str
    normalizer_version: str = NORMALIZER_VERSION
    benchmark_id: str = "EZ-B001"
    legacy_id: str = "ZME-B001"

    def to_dict(self) -> dict[str, Any]:
        return {
            "freeze_id": self.freeze_id,
            "benchmark_id": self.benchmark_id,
            "legacy_id": self.legacy_id,
            "cutoff_date": self.cutoff_date,
            "allowed_source_hashes": list(self.allowed_source_hashes),
            "allowed_edition_ids": list(self.allowed_edition_ids),
            "training_nuclide_ids": list(self.training_nuclide_ids),
            "training_identity_digest": self.training_identity_digest,
            "forbidden_source_hashes": list(self.forbidden_source_hashes),
            "feature_policy_id": self.feature_policy_id,
            "feature_policy_hash": self.feature_policy_hash,
            "atlas_pir_ref": self.atlas_pir_ref,
            "elementzero_commit": self.elementzero_commit,
            "raw_source_hash": self.raw_source_hash,
            "normalized_table_hash": self.normalized_table_hash,
            "normalizer_version": self.normalizer_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeFreeze:
        return cls(
            freeze_id=data["freeze_id"],
            cutoff_date=data["cutoff_date"],
            allowed_source_hashes=tuple(data["allowed_source_hashes"]),
            allowed_edition_ids=tuple(data["allowed_edition_ids"]),
            training_nuclide_ids=tuple(data["training_nuclide_ids"]),
            training_identity_digest=data["training_identity_digest"],
            forbidden_source_hashes=tuple(data.get("forbidden_source_hashes", ())),
            feature_policy_id=data["feature_policy_id"],
            atlas_pir_ref=data["atlas_pir_ref"],
            elementzero_commit=data["elementzero_commit"],
            raw_source_hash=data["raw_source_hash"],
            normalized_table_hash=data["normalized_table_hash"],
            feature_policy_hash=data["feature_policy_hash"],
            normalizer_version=data.get("normalizer_version", NORMALIZER_VERSION),
            benchmark_id=data.get("benchmark_id", "EZ-B001"),
            legacy_id=data.get("legacy_id", "ZME-B001"),
        )


def identity_digest(nuclide_ids: Iterable[str]) -> str:
    ordered = sorted(set(nuclide_ids))
    return sha256_hex({"training_nuclide_ids": ordered})


def feature_policy_payload(policy_id: str) -> dict[str, Any]:
    if policy_id != FEATURE_POLICY_EZ_B001:
        raise SchemaError(f"unsupported feature policy {policy_id!r}")
    return {
        "feature_policy_id": policy_id,
        "features": ["Z", "N", "A"],
        "magic_number_distance_features": False,
        "notes": "EZ-B001 default: identity features only; no shell-gap distances.",
    }


def reject_truth_fields(payload: Any, *, where: str) -> None:
    if isinstance(payload, dict):
        extras = TRUTH_BEARING_FIELDS.intersection(payload)
        if extras:
            raise LeakageError(f"{where} contains truth-bearing fields: {sorted(extras)}")
        unknown = set(payload) - ALLOWED_TARGET_FIELDS
        if unknown:
            raise LeakageError(f"{where} contains non-identity fields: {sorted(unknown)}")
        for value in payload.values():
            reject_truth_fields(value, where=where)
    elif isinstance(payload, list):
        for item in payload:
            reject_truth_fields(item, where=where)


def validate_target_record(record: dict[str, Any]) -> dict[str, int | str]:
    reject_truth_fields(record, where="target manifest")
    z = int(record["Z"])
    n = int(record["N"])
    a = int(record["A"])
    nid = str(record["nuclide_id"])
    if nid != nuclide_id(z, n):
        raise SchemaError(f"nuclide_id {nid!r} does not match Z={z} N={n}")
    if a != z + n:
        raise SchemaError(f"A={a} does not equal Z+N={z + n}")
    parse_nuclide_id(nid)
    return {"nuclide_id": nid, "Z": z, "N": n, "A": a}


def build_freeze(
    *,
    training: Sequence[MassObservation],
    targets: Sequence[dict[str, Any]],
    cutoff_date: str,
    edition_id: str,
    raw_source_hash: str,
    forbidden_source_hashes: Sequence[str] = (),
    feature_policy_id: str = FEATURE_POLICY_EZ_B001,
    atlas_ref: str | None = None,
    ez_commit: str | None = None,
) -> KnowledgeFreeze:
    target_ids = {validate_target_record(t)["nuclide_id"] for t in targets}
    held_out = [obs for obs in training if obs.nuclide_id not in target_ids]
    training = held_out
    training_ids = tuple(sorted({obs.nuclide_id for obs in training}))
    digest = identity_digest(training_ids)
    table_hash = sha256_hex([obs.to_dict() for obs in sorted(training, key=lambda o: o.nuclide_id)])
    policy = feature_policy_payload(feature_policy_id)
    policy_hash = sha256_hex(policy)
    payload = {
        "cutoff_date": cutoff_date,
        "allowed_source_hashes": [raw_source_hash],
        "training_identity_digest": digest,
        "normalized_table_hash": table_hash,
        "feature_policy_hash": policy_hash,
        "atlas_pir_ref": atlas_ref or atlas_pir_ref(),
        "elementzero_commit": ez_commit or elementzero_commit(),
    }
    freeze_id = content_id("frz", payload)
    return KnowledgeFreeze(
        freeze_id=freeze_id,
        cutoff_date=cutoff_date,
        allowed_source_hashes=(raw_source_hash,),
        allowed_edition_ids=(edition_id,),
        training_nuclide_ids=training_ids,
        training_identity_digest=digest,
        forbidden_source_hashes=tuple(forbidden_source_hashes),
        feature_policy_id=feature_policy_id,
        atlas_pir_ref=payload["atlas_pir_ref"],
        elementzero_commit=payload["elementzero_commit"],
        raw_source_hash=raw_source_hash,
        normalized_table_hash=table_hash,
        feature_policy_hash=policy_hash,
    )


def assert_training_digest(freeze: KnowledgeFreeze, nuclide_ids: Iterable[str]) -> None:
    digest = identity_digest(nuclide_ids)
    if digest != freeze.training_identity_digest:
        raise LeakageError("training digest changed after fit")


def assert_holdout_disjoint(freeze: KnowledgeFreeze, target_ids: Iterable[str]) -> None:
    overlap = sorted(set(freeze.training_nuclide_ids) & set(target_ids))
    if overlap:
        raise LeakageError(f"held-out nuclide in training IDs: {overlap}")
