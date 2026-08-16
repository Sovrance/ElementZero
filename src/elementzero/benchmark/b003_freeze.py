"""EZ-B003 freeze: one KnowledgeFreeze per hidden closure x model-suite split.

Like EZ-B002 and unlike EZ-B001, a hidden-shell holdout has no second file: the
training corpus and the withheld truth live in the same frozen snapshot, so
blindness cannot be enforced at the filesystem boundary. The freeze therefore
pins the geometry:

    allowed_source_hashes       the one frozen snapshot (it is also the truth source)
    training_nuclide_ids        exactly the eligible nuclei outside the mask
    training_identity_digest /
    normalized_table_hash       computed over that training corpus only
    mask + mask_hash            the withheld closure neighborhood
    challenge_manifest_hash     the preregistered closure set the mask came from
    target_identity_digest      the withheld identities
    split_digest               source + challenges + mask + training + target + policy

``freeze_id`` is content-addressed from the split digest, so widening the mask,
swapping the snapshot, or adding one training identity produces a different
freeze and invalidates every certificate that quotes the old one.

The freeze also pins the *profile*. A discovery-profile freeze whose feature
policy names a shell feature cannot be built, which is what stops the firewall
from being bypassed by editing a manifest between preparation and prediction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_EZ_B003
from elementzero.atlas_pin import atlas_pir_ref
from elementzero.benchmark.b003_prepare import (
    PROFILE_DISCOVERY,
    assert_discovery_features,
    eligible_observations,
    feature_policy_payload,
    load_split_manifest,
    split_digest,
)
from elementzero.benchmark.shell_masks import ShellMask, mask_hash
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.freezes import KnowledgeFreeze, identity_digest
from elementzero.evidence.hashing import canonical_json, content_id, sha256_file, sha256_hex
from elementzero.identity_meta import elementzero_commit

FREEZE_FILE = "freeze.json"

# EZ-B003 has no legacy ZME benchmark; the field stays explicit rather than
# inheriting the EZ-B001 default.
B003_LEGACY_ID = "none"

SHELL_FREEZE_KEYS = (
    "challenge_id",
    "challenge_manifest_hash",
    "mask",
    "mask_hash",
    "mask_id",
    "profile",
    "split_digest",
    "split_id",
    "supported_chains",
    "target_identity_digest",
    "target_nuclide_ids",
)


class ShellFreeze:
    """A KnowledgeFreeze plus the shell mask and support record that produced it."""

    def __init__(
        self,
        *,
        freeze: KnowledgeFreeze,
        mask: ShellMask,
        challenge_manifest_hash: str,
        split_id: str,
        split_digest: str,
        target_nuclide_ids: tuple[str, ...],
        target_identity_digest: str,
        supported_chains: tuple[int, ...],
        unsupported_chains: tuple[int, ...] = (),
        profile: str = PROFILE_DISCOVERY,
    ) -> None:
        self.freeze = freeze
        self.mask = mask
        self.challenge_manifest_hash = challenge_manifest_hash
        self.split_id = split_id
        self.split_digest = split_digest
        self.target_nuclide_ids = tuple(target_nuclide_ids)
        self.target_identity_digest = target_identity_digest
        self.supported_chains = tuple(int(c) for c in supported_chains)
        self.unsupported_chains = tuple(int(c) for c in unsupported_chains)
        self.profile = profile

    @property
    def freeze_id(self) -> str:
        return self.freeze.freeze_id

    @property
    def mask_id(self) -> str:
        return self.mask.mask_id

    @property
    def challenge_id(self) -> str:
        return self.mask.challenge_id

    @property
    def mask_hash(self) -> str:
        return mask_hash(self.mask)

    def to_dict(self) -> dict[str, Any]:
        """One payload that is both a KnowledgeFreeze and a hidden-shell split."""
        return {
            **self.freeze.to_dict(),
            "mask": self.mask.to_dict(),
            "mask_id": self.mask_id,
            "mask_hash": self.mask_hash,
            "challenge_id": self.challenge_id,
            "challenge_manifest_hash": self.challenge_manifest_hash,
            "axis": self.mask.axis,
            "closure": self.mask.closure,
            "indicator": self.mask.indicator,
            "profile": self.profile,
            "split_id": self.split_id,
            "split_digest": self.split_digest,
            "supported_chains": list(self.supported_chains),
            "unsupported_chains": list(self.unsupported_chains),
            "target_nuclide_ids": list(self.target_nuclide_ids),
            "target_identity_digest": self.target_identity_digest,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ShellFreeze:
        missing = [key for key in SHELL_FREEZE_KEYS if key not in payload]
        if missing:
            raise ProtocolError(f"shell freeze payload is missing fields: {missing}")
        freeze = KnowledgeFreeze.from_dict(payload)
        if freeze.benchmark_id != BENCHMARK_EZ_B003:
            raise ProtocolError(
                f"freeze declares benchmark {freeze.benchmark_id!r}, not {BENCHMARK_EZ_B003}"
            )
        mask = ShellMask.from_dict(payload["mask"])
        if payload["mask_id"] != mask.mask_id:
            raise ProtocolError("freeze mask_id does not match its mask geometry")
        if payload["mask_hash"] != mask_hash(mask):
            raise ProtocolError("freeze mask_hash does not match its mask geometry")
        if payload["challenge_id"] != mask.challenge_id:
            raise ProtocolError("freeze challenge_id does not match its mask")
        profile = payload["profile"]
        policy = feature_policy_payload(profile=profile, features=payload.get("features"))
        if policy["feature_policy_id"] != freeze.feature_policy_id:
            raise ProtocolError(
                f"freeze feature policy {freeze.feature_policy_id!r} is not the "
                f"{profile!r} profile policy {policy['feature_policy_id']!r}"
            )
        if sha256_hex(policy) != freeze.feature_policy_hash:
            raise ProtocolError("freeze feature policy hash does not match its declared profile")
        if profile == PROFILE_DISCOVERY:
            assert_discovery_features(policy["features"], where="sealed freeze feature policy")
        target_ids = tuple(payload["target_nuclide_ids"])
        if identity_digest(target_ids) != payload["target_identity_digest"]:
            raise ProtocolError("freeze target identity digest does not match its target ids")
        expected = split_digest(
            raw_source_hash=freeze.raw_source_hash,
            challenge_manifest_hash=payload["challenge_manifest_hash"],
            mask_hash=payload["mask_hash"],
            training_identity_digest=freeze.training_identity_digest,
            target_identity_digest=payload["target_identity_digest"],
            feature_policy_hash=freeze.feature_policy_hash,
        )
        if expected != payload["split_digest"]:
            raise ProtocolError("freeze split_digest does not match its own components")
        assert_split_geometry(
            mask=mask,
            training_nuclide_ids=freeze.training_nuclide_ids,
            target_nuclide_ids=target_ids,
        )
        return cls(
            freeze=freeze,
            mask=mask,
            challenge_manifest_hash=payload["challenge_manifest_hash"],
            split_id=payload["split_id"],
            split_digest=payload["split_digest"],
            target_nuclide_ids=target_ids,
            target_identity_digest=payload["target_identity_digest"],
            supported_chains=tuple(payload["supported_chains"]),
            unsupported_chains=tuple(payload.get("unsupported_chains", ())),
            profile=profile,
        )


def assert_split_geometry(
    *,
    mask: ShellMask,
    training_nuclide_ids: tuple[str, ...] | list[str],
    target_nuclide_ids: tuple[str, ...] | list[str],
) -> None:
    """Every target inside the mask, every training nucleus outside, no overlap."""
    outside = sorted(nid for nid in target_nuclide_ids if not mask.contains_id(nid))
    if outside:
        raise LeakageError(f"targets outside mask {mask.mask_id}: {outside[:5]}")
    inside = sorted(nid for nid in training_nuclide_ids if mask.contains_id(nid))
    if inside:
        raise LeakageError(
            f"training identities inside the hidden closure neighborhood {mask.mask_id}: {inside[:5]}"
        )
    overlap = sorted(set(training_nuclide_ids) & set(target_nuclide_ids))
    if overlap:
        raise LeakageError(f"mask {mask.mask_id} keeps targets in training: {overlap[:5]}")


def freeze_shell_split(
    *,
    source: str | Path,
    edition_id: str,
    split_manifest: str | Path | dict[str, Any],
    output: str | Path | None = None,
    ez_commit: str | None = None,
    atlas_ref: str | None = None,
) -> ShellFreeze:
    """Build the freeze for one hidden-shell split and verify it against the source."""
    source = Path(source)
    manifest = (
        split_manifest
        if isinstance(split_manifest, dict)
        else load_split_manifest(split_manifest)
    )
    if manifest["benchmark_id"] != BENCHMARK_EZ_B003:
        raise ProtocolError(
            f"split manifest declares benchmark {manifest['benchmark_id']!r}, "
            f"not {BENCHMARK_EZ_B003}"
        )
    raw_source_hash = sha256_file(source)
    if raw_source_hash != manifest["raw_source_hash"]:
        raise ProtocolError(
            "source hash differs from the split manifest; the snapshot is not the frozen one"
        )
    if manifest["edition_id"] != edition_id:
        raise ProtocolError(
            f"split manifest edition {manifest['edition_id']!r} differs from {edition_id!r}"
        )
    profile = manifest["profile"]
    policy = feature_policy_payload(profile=profile, features=manifest["features"])
    if manifest["feature_policy_id"] != policy["feature_policy_id"]:
        raise ProtocolError(
            f"split manifest feature policy {manifest['feature_policy_id']!r} is not "
            f"{policy['feature_policy_id']!r}"
        )
    policy_hash = sha256_hex(policy)
    if manifest["feature_policy_hash"] != policy_hash:
        raise ProtocolError("split manifest feature policy hash differs from this build")
    if profile == PROFILE_DISCOVERY:
        assert_discovery_features(policy["features"], where="frozen feature policy")

    mask = ShellMask.from_dict(manifest["mask"])
    if manifest["mask_hash"] != mask_hash(mask):
        raise ProtocolError("split manifest mask hash differs from its mask geometry")
    target_ids = tuple(manifest["target_nuclide_ids"])
    observations = eligible_observations(source, edition_id)
    training = [obs for obs in observations if not mask.contains(obs.Z, obs.N)]
    training_ids = tuple(sorted(obs.nuclide_id for obs in training))
    if training_ids != tuple(sorted(manifest["training_nuclide_ids"])):
        raise ProtocolError(
            "training identities recomputed from the source differ from the split manifest"
        )
    assert_split_geometry(
        mask=mask, training_nuclide_ids=training_ids, target_nuclide_ids=target_ids
    )

    training_digest = identity_digest(training_ids)
    target_digest = identity_digest(target_ids)
    if training_digest != manifest["training_identity_digest"]:
        raise ProtocolError("recomputed training identity digest differs from the split manifest")
    if target_digest != manifest["target_identity_digest"]:
        raise ProtocolError("recomputed target identity digest differs from the split manifest")

    # The normalized table hash covers the training corpus only: the withheld
    # rows are never serialized into anything the fitting stage can read.
    table_hash = sha256_hex([obs.to_dict() for obs in sorted(training, key=lambda o: o.nuclide_id)])
    digest = split_digest(
        raw_source_hash=raw_source_hash,
        challenge_manifest_hash=manifest["challenge_manifest_hash"],
        mask_hash=manifest["mask_hash"],
        training_identity_digest=training_digest,
        target_identity_digest=target_digest,
        feature_policy_hash=policy_hash,
    )
    if digest != manifest["split_digest"]:
        raise ProtocolError("recomputed split digest differs from the split manifest")

    cutoff = training[0].source_release_date if training else "1970-01-01"
    payload = {
        "benchmark_id": BENCHMARK_EZ_B003,
        "cutoff_date": cutoff,
        "allowed_source_hashes": [raw_source_hash],
        "challenge_manifest_hash": manifest["challenge_manifest_hash"],
        "mask_hash": manifest["mask_hash"],
        "mask_id": mask.mask_id,
        "profile": profile,
        "split_digest": digest,
        "training_identity_digest": training_digest,
        "target_identity_digest": target_digest,
        "normalized_table_hash": table_hash,
        "feature_policy_hash": policy_hash,
        "atlas_pir_ref": atlas_ref or atlas_pir_ref(),
        "elementzero_commit": ez_commit or elementzero_commit(),
    }
    freeze = KnowledgeFreeze(
        freeze_id=content_id("frz", payload),
        cutoff_date=cutoff,
        allowed_source_hashes=(raw_source_hash,),
        allowed_edition_ids=(edition_id,),
        training_nuclide_ids=training_ids,
        training_identity_digest=training_digest,
        # Nothing is file-forbidden here: the frozen snapshot is also the truth
        # source. The mask geometry and the training identity digest are the control.
        forbidden_source_hashes=(),
        feature_policy_id=policy["feature_policy_id"],
        atlas_pir_ref=payload["atlas_pir_ref"],
        elementzero_commit=payload["elementzero_commit"],
        raw_source_hash=raw_source_hash,
        normalized_table_hash=table_hash,
        feature_policy_hash=policy_hash,
        benchmark_id=BENCHMARK_EZ_B003,
        legacy_id=B003_LEGACY_ID,
    )
    shell = ShellFreeze(
        freeze=freeze,
        mask=mask,
        challenge_manifest_hash=manifest["challenge_manifest_hash"],
        split_id=manifest["split_id"],
        split_digest=digest,
        target_nuclide_ids=target_ids,
        target_identity_digest=target_digest,
        supported_chains=tuple(manifest["supported_chains"]),
        unsupported_chains=tuple(manifest.get("unsupported_chains", ())),
        profile=profile,
    )
    if output is not None:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        payload_out = {**shell.to_dict(), "features": list(policy["features"])}
        Path(output).write_text(canonical_json(payload_out) + "\n", encoding="utf-8")
    return shell


def load_shell_freeze(path: str | Path) -> ShellFreeze:
    return ShellFreeze.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def feature_policy(*, profile: str = PROFILE_DISCOVERY) -> dict[str, Any]:
    """Public accessor so a report can print the exact frozen feature policy."""
    return feature_policy_payload(profile=profile)
