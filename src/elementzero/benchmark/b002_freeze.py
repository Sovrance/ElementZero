"""EZ-B002 freeze: one KnowledgeFreeze per region x model-suite data split.

The EZ-B001 freeze forbids a *file*: the later edition is a different table with
a different hash, so blindness can be enforced at the filesystem boundary. A
geographic holdout has no second file. Training and truth live in the same
frozen snapshot, and the boundary is geometric.

So the B002 freeze pins the geometry instead of a file list:

    allowed_source_hashes   the one frozen snapshot (it is also the truth source)
    training_nuclide_ids    exactly the eligible nuclei outside the region
    training_identity_digest / normalized_table_hash
                            computed over that training corpus only
    region + region_manifest_hash
                            the withheld block, hashed with the preregistered set
    target_identity_digest  the withheld identities
    split_digest            source + region + training + target + feature policy

``freeze_id`` is content-addressed from the split digest, so a region swap, a
source swap, or a single extra training identity produces a different freeze and
invalidates every certificate that quotes the old one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_EZ_B002
from elementzero.atlas_pin import atlas_pir_ref
from elementzero.benchmark.b002_prepare import (
    FEATURE_POLICY_EZ_B002,
    eligible_observations,
    feature_policy_hash,
    feature_policy_payload,
    load_split_manifest,
    split_digest,
)
from elementzero.benchmark.regions import Region
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.freezes import KnowledgeFreeze, identity_digest
from elementzero.evidence.hashing import canonical_json, content_id, sha256_file, sha256_hex
from elementzero.identity_meta import elementzero_commit

FREEZE_FILE = "freeze.json"

# EZ-B002 has no legacy ZME benchmark; the field stays explicit rather than
# inheriting the EZ-B001 default.
B002_LEGACY_ID = "none"

GEOGRAPHIC_FREEZE_KEYS = (
    "region",
    "region_id",
    "region_manifest_hash",
    "split_digest",
    "split_id",
    "target_identity_digest",
    "target_nuclide_ids",
)


class GeographicFreeze:
    """A KnowledgeFreeze plus the geometry that produced it."""

    def __init__(
        self,
        *,
        freeze: KnowledgeFreeze,
        region: Region,
        region_manifest_hash: str,
        split_id: str,
        split_digest: str,
        target_nuclide_ids: tuple[str, ...],
        target_identity_digest: str,
    ) -> None:
        self.freeze = freeze
        self.region = region
        self.region_manifest_hash = region_manifest_hash
        self.split_id = split_id
        self.split_digest = split_digest
        self.target_nuclide_ids = tuple(target_nuclide_ids)
        self.target_identity_digest = target_identity_digest

    @property
    def freeze_id(self) -> str:
        return self.freeze.freeze_id

    @property
    def region_id(self) -> str:
        return self.region.region_id

    def to_dict(self) -> dict[str, Any]:
        """One payload that is both a KnowledgeFreeze and a geographic split."""
        return {
            **self.freeze.to_dict(),
            "region": self.region.to_dict(),
            "region_id": self.region_id,
            "region_manifest_hash": self.region_manifest_hash,
            "split_id": self.split_id,
            "split_digest": self.split_digest,
            "target_nuclide_ids": list(self.target_nuclide_ids),
            "target_identity_digest": self.target_identity_digest,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GeographicFreeze:
        missing = [key for key in GEOGRAPHIC_FREEZE_KEYS if key not in payload]
        if missing:
            raise ProtocolError(f"geographic freeze payload is missing fields: {missing}")
        freeze = KnowledgeFreeze.from_dict(payload)
        if freeze.benchmark_id != BENCHMARK_EZ_B002:
            raise ProtocolError(
                f"freeze declares benchmark {freeze.benchmark_id!r}, not {BENCHMARK_EZ_B002}"
            )
        region = Region.from_dict(payload["region"])
        if payload["region_id"] != region.region_id:
            raise ProtocolError("freeze region_id does not match its region geometry")
        target_ids = tuple(payload["target_nuclide_ids"])
        if identity_digest(target_ids) != payload["target_identity_digest"]:
            raise ProtocolError("freeze target identity digest does not match its target ids")
        expected = split_digest(
            raw_source_hash=freeze.raw_source_hash,
            region_manifest_hash=payload["region_manifest_hash"],
            training_identity_digest=freeze.training_identity_digest,
            target_identity_digest=payload["target_identity_digest"],
            feature_policy_hash=freeze.feature_policy_hash,
        )
        if expected != payload["split_digest"]:
            raise ProtocolError("freeze split_digest does not match its own components")
        assert_split_geometry(
            region=region,
            training_nuclide_ids=freeze.training_nuclide_ids,
            target_nuclide_ids=target_ids,
        )
        return cls(
            freeze=freeze,
            region=region,
            region_manifest_hash=payload["region_manifest_hash"],
            split_id=payload["split_id"],
            split_digest=payload["split_digest"],
            target_nuclide_ids=target_ids,
            target_identity_digest=payload["target_identity_digest"],
        )


def assert_split_geometry(
    *,
    region: Region,
    training_nuclide_ids: tuple[str, ...] | list[str],
    target_nuclide_ids: tuple[str, ...] | list[str],
) -> None:
    """Every target inside, every training nucleus outside, no overlap."""
    outside = sorted(nid for nid in target_nuclide_ids if not region.contains_id(nid))
    if outside:
        raise LeakageError(f"targets outside region {region.region_id}: {outside[:5]}")
    inside = sorted(nid for nid in training_nuclide_ids if region.contains_id(nid))
    if inside:
        raise LeakageError(
            f"training identities inside the held-out region {region.region_id}: {inside[:5]}"
        )
    overlap = sorted(set(training_nuclide_ids) & set(target_nuclide_ids))
    if overlap:
        raise LeakageError(f"region {region.region_id} keeps targets in training: {overlap[:5]}")


def freeze_geographic_split(
    *,
    source: str | Path,
    edition_id: str,
    split_manifest: str | Path | dict[str, Any],
    output: str | Path | None = None,
    ez_commit: str | None = None,
    atlas_ref: str | None = None,
) -> GeographicFreeze:
    """Build the freeze for one geographic split and verify it against the source."""
    source = Path(source)
    manifest = (
        split_manifest
        if isinstance(split_manifest, dict)
        else load_split_manifest(split_manifest)
    )
    if manifest["benchmark_id"] != BENCHMARK_EZ_B002:
        raise ProtocolError(
            f"split manifest declares benchmark {manifest['benchmark_id']!r}, not {BENCHMARK_EZ_B002}"
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
    if manifest["feature_policy_id"] != FEATURE_POLICY_EZ_B002:
        raise ProtocolError(
            f"split manifest feature policy {manifest['feature_policy_id']!r} is not "
            f"{FEATURE_POLICY_EZ_B002!r}"
        )
    policy_hash = feature_policy_hash()
    if manifest["feature_policy_hash"] != policy_hash:
        raise ProtocolError("split manifest feature policy hash differs from this build")

    region = Region.from_dict(manifest["region"])
    target_ids = tuple(manifest["target_nuclide_ids"])
    observations = eligible_observations(source, edition_id)
    training = [obs for obs in observations if not region.contains(obs.Z, obs.N)]
    training_ids = tuple(sorted(obs.nuclide_id for obs in training))
    if training_ids != tuple(sorted(manifest["training_nuclide_ids"])):
        raise ProtocolError(
            "training identities recomputed from the source differ from the split manifest"
        )
    assert_split_geometry(
        region=region, training_nuclide_ids=training_ids, target_nuclide_ids=target_ids
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
        region_manifest_hash=manifest["region_manifest_hash"],
        training_identity_digest=training_digest,
        target_identity_digest=target_digest,
        feature_policy_hash=policy_hash,
    )
    if digest != manifest["split_digest"]:
        raise ProtocolError("recomputed split digest differs from the split manifest")

    cutoff = training[0].source_release_date if training else "1970-01-01"
    payload = {
        "benchmark_id": BENCHMARK_EZ_B002,
        "cutoff_date": cutoff,
        "allowed_source_hashes": [raw_source_hash],
        "region_manifest_hash": manifest["region_manifest_hash"],
        "region_id": region.region_id,
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
        # source. The geometry and the training identity digest are the control.
        forbidden_source_hashes=(),
        feature_policy_id=FEATURE_POLICY_EZ_B002,
        atlas_pir_ref=payload["atlas_pir_ref"],
        elementzero_commit=payload["elementzero_commit"],
        raw_source_hash=raw_source_hash,
        normalized_table_hash=table_hash,
        feature_policy_hash=policy_hash,
        benchmark_id=BENCHMARK_EZ_B002,
        legacy_id=B002_LEGACY_ID,
    )
    geographic = GeographicFreeze(
        freeze=freeze,
        region=region,
        region_manifest_hash=manifest["region_manifest_hash"],
        split_id=manifest["split_id"],
        split_digest=digest,
        target_nuclide_ids=target_ids,
        target_identity_digest=target_digest,
    )
    if output is not None:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(canonical_json(geographic.to_dict()) + "\n", encoding="utf-8")
    return geographic


def load_geographic_freeze(path: str | Path) -> GeographicFreeze:
    return GeographicFreeze.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def feature_policy() -> dict[str, Any]:
    """Public accessor so a report can print the exact frozen feature policy."""
    return feature_policy_payload()
