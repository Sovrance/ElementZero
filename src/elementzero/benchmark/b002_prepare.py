"""EZ-B002 preparation: one frozen edition plus one region -> a geographic split.

WO-09 section 4 defines the split for a region::

    targets  = all eligible nuclei inside the region
    training = all eligible nuclei outside the region

Preparation may read the whole snapshot, exactly like EZ-B001 preparation may
read the later edition. What it emits is identities: the target manifest is
identity-only, and the split manifest records identities, counts, and hashes.
No mass value is written by this stage.

The split digest (WO-09 section 7) binds the five things that define the split::

    source hash
    region manifest hash
    training identity digest
    target identity digest
    feature policy hash

Any change to any of them changes the digest, and therefore the freeze ID and
every certificate that quotes it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero import B002_PROTOCOL_VERSION, BENCHMARK_EZ_B002
from elementzero.benchmark.regions import (
    REGION_POLICY_ID,
    Region,
    assert_region_populated,
    split_points,
    supported_sides,
)
from elementzero.data.amdc import load_edition
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.observations import GROUND_TRUTH_POLICY, MassObservation
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.freezes import identity_digest, validate_target_record
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.physics.constants import NORMALIZER_VERSION

GEOGRAPHIC_SPLIT_POLICY_ID = "ez-b002-geographic-split-v1"

# EZ-B002 v1 reuses the EZ-B001 identity feature set (Z, N, A) under its own
# policy id, so a B002 freeze can never be mistaken for a B001 freeze while the
# two remain feature-comparable.
FEATURE_POLICY_EZ_B002 = "ez-b002-identity-zn-v1"

SPLIT_DIGEST_RULE = (
    "ez-b002-split-digest-v1: sha256 of canonical JSON of {feature_policy_hash, "
    "raw_source_hash, region_manifest_hash, target_identity_digest, "
    "training_identity_digest}"
)

TARGETS_FILE = "targets.json"
SPLIT_MANIFEST_FILE = "split_manifest.json"


def feature_policy_payload() -> dict[str, Any]:
    return {
        "feature_policy_id": FEATURE_POLICY_EZ_B002,
        "features": ["Z", "N", "A"],
        "magic_number_distance_features": False,
        "notes": (
            "EZ-B002 v1: identity features only. No shell-gap distances, no "
            "region-derived features, and no statistic computed from inside the "
            "held-out region."
        ),
    }


def feature_policy_hash() -> str:
    return sha256_hex(feature_policy_payload())


def eligible_observations(source: str | Path, edition_id: str) -> list[MassObservation]:
    """Ground-truth eligible rows of one frozen snapshot, sorted by identity."""
    observations = [
        obs for obs in load_edition(edition_id, str(source)) if obs.ground_truth_eligible
    ]
    if not observations:
        raise ProtocolError(f"{edition_id} snapshot has no ground-truth eligible rows")
    return sorted(observations, key=lambda o: o.nuclide_id)


def eligible_points(source: str | Path, edition_id: str) -> list[tuple[int, int]]:
    """Eligible (Z, N) lattice points; the input of region generation."""
    return sorted({(obs.Z, obs.N) for obs in eligible_observations(source, edition_id)})


def split_digest(
    *,
    raw_source_hash: str,
    region_manifest_hash: str,
    training_identity_digest: str,
    target_identity_digest: str,
    feature_policy_hash: str,
) -> str:
    return sha256_hex(
        {
            "feature_policy_hash": feature_policy_hash,
            "raw_source_hash": raw_source_hash,
            "region_manifest_hash": region_manifest_hash,
            "target_identity_digest": target_identity_digest,
            "training_identity_digest": training_identity_digest,
        }
    )


def _identity_records(observations: Sequence[MassObservation]) -> list[dict[str, int | str]]:
    return [
        validate_target_record(
            {"nuclide_id": obs.nuclide_id, "Z": obs.Z, "N": obs.N, "A": obs.A}
        )
        for obs in observations
    ]


def prepare_geographic_split(
    *,
    source: str | Path,
    edition_id: str,
    region: Region,
    region_manifest_hash: str,
    out_dir: str | Path | None = None,
    min_targets: int = 1,
    benchmark_id: str = BENCHMARK_EZ_B002,
) -> dict[str, Any]:
    """Split one snapshot around one region and write identity-only artifacts."""
    if benchmark_id != BENCHMARK_EZ_B002:
        raise ValueError(f"unsupported benchmark {benchmark_id}; this stage is {BENCHMARK_EZ_B002}")
    source = Path(source)
    observations = eligible_observations(source, edition_id)
    points = [(obs.Z, obs.N) for obs in observations]
    assert_region_populated(region, points, min_targets=min_targets)

    inside = [obs for obs in observations if region.contains(obs.Z, obs.N)]
    outside = [obs for obs in observations if not region.contains(obs.Z, obs.N)]
    if not outside:
        raise ProtocolError(
            f"region {region.region_id} leaves no training nuclei; the split would have nothing to fit"
        )
    # Geometry is the whole leakage control here, so it is re-derived rather
    # than trusted: the two sides must partition the eligible set exactly.
    # Observations are ordered by nuclide_id and lattice points numerically, so
    # the comparison is on sorted point sets, not on iteration order.
    geometric = split_points(points, region)
    if sorted({(o.Z, o.N) for o in inside}) != geometric["targets"]:
        raise LeakageError(f"region {region.region_id} target set does not match its geometry")
    if sorted({(o.Z, o.N) for o in outside}) != geometric["training"]:
        raise LeakageError(f"region {region.region_id} training set does not match its geometry")

    targets = _identity_records(inside)
    target_ids = [t["nuclide_id"] for t in targets]
    training_ids = [obs.nuclide_id for obs in outside]
    overlap = sorted(set(target_ids) & set(training_ids))
    if overlap:
        raise LeakageError(f"region {region.region_id} keeps targets in training: {overlap}")

    raw_source_hash = sha256_file(source)
    policy_hash = feature_policy_hash()
    training_digest = identity_digest(training_ids)
    target_digest = identity_digest(target_ids)
    digest = split_digest(
        raw_source_hash=raw_source_hash,
        region_manifest_hash=region_manifest_hash,
        training_identity_digest=training_digest,
        target_identity_digest=target_digest,
        feature_policy_hash=policy_hash,
    )
    manifest = {
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": B002_PROTOCOL_VERSION,
        "split_policy_id": GEOGRAPHIC_SPLIT_POLICY_ID,
        "split_id": f"{region.region_id}@{digest[:16]}",
        "region_policy_id": REGION_POLICY_ID,
        "region_id": region.region_id,
        "region": region.to_dict(),
        "region_manifest_hash": region_manifest_hash,
        "z_band": region.z_band,
        "edition_id": edition_id,
        "raw_source_hash": raw_source_hash,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "parser_version": PARSER_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "feature_policy_id": FEATURE_POLICY_EZ_B002,
        "feature_policy_hash": policy_hash,
        "n_eligible": len(observations),
        "n_targets": len(target_ids),
        "n_training": len(training_ids),
        "target_nuclide_ids": target_ids,
        "training_nuclide_ids": sorted(training_ids),
        "target_identity_digest": target_digest,
        "training_identity_digest": training_digest,
        "supported_sides": list(supported_sides(region, points)),
        "split_digest": digest,
        "split_digest_rule": SPLIT_DIGEST_RULE,
        "leakage_rule": (
            "targets are the eligible nuclei inside the region and training is the "
            "eligible nuclei outside it; target masses enter no fit, no feature, no "
            "hyperparameter, and no uncertainty calibration. Target identities "
            "(Z, N, A) are allowed."
        ),
    }
    _assert_identity_only(manifest)

    written: dict[str, str] = {}
    if out_dir is not None:
        dest = Path(out_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / TARGETS_FILE).write_text(
            canonical_json({"targets": targets}) + "\n", encoding="utf-8"
        )
        (dest / SPLIT_MANIFEST_FILE).write_text(canonical_json(manifest) + "\n", encoding="utf-8")
        written = {
            "targets_path": str(dest / TARGETS_FILE),
            "split_manifest_path": str(dest / SPLIT_MANIFEST_FILE),
            "targets_sha256": sha256_file(dest / TARGETS_FILE),
            "split_manifest_sha256": sha256_file(dest / SPLIT_MANIFEST_FILE),
        }
    return {"region": region, "targets": targets, "split_manifest": manifest, **written}


def prepare_geographic_splits(
    *,
    source: str | Path,
    edition_id: str,
    regions: Sequence[Region],
    out_dir: str | Path,
    min_targets: int = 1,
    region_manifest_hash: str,
) -> list[dict[str, Any]]:
    """One split per region, each in its own ``<out_dir>/<region_id>`` directory."""
    base = Path(out_dir)
    results = []
    for region in regions:
        results.append(
            prepare_geographic_split(
                source=source,
                edition_id=edition_id,
                region=region,
                region_manifest_hash=region_manifest_hash,
                out_dir=base / region.region_id,
                min_targets=min_targets,
            )
        )
    return results


def _assert_identity_only(payload: Any) -> None:
    """A split manifest may carry identities and hashes, never a mass."""
    from elementzero.data.observations import TRUTH_BEARING_FIELDS

    if isinstance(payload, dict):
        leaked = sorted(TRUTH_BEARING_FIELDS.intersection(payload))
        if leaked:
            raise LeakageError(f"geographic split manifest carries truth fields: {leaked}")
        for value in payload.values():
            _assert_identity_only(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_identity_only(item)


def load_split_manifest(path: str | Path) -> dict[str, Any]:
    """Read a split manifest and refuse one that carries truth or contradicts itself."""
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    _assert_identity_only(payload)
    region = Region.from_dict(payload["region"])
    if payload.get("region_id") != region.region_id:
        raise ProtocolError("split manifest region_id does not match its region geometry")
    target_ids = list(payload["target_nuclide_ids"])
    training_ids = list(payload["training_nuclide_ids"])
    if identity_digest(target_ids) != payload["target_identity_digest"]:
        raise ProtocolError("split manifest target identity digest does not match its target ids")
    if identity_digest(training_ids) != payload["training_identity_digest"]:
        raise ProtocolError(
            "split manifest training identity digest does not match its training ids"
        )
    expected = split_digest(
        raw_source_hash=payload["raw_source_hash"],
        region_manifest_hash=payload["region_manifest_hash"],
        training_identity_digest=payload["training_identity_digest"],
        target_identity_digest=payload["target_identity_digest"],
        feature_policy_hash=payload["feature_policy_hash"],
    )
    if expected != payload["split_digest"]:
        raise ProtocolError("split manifest split_digest does not match its own components")
    for nid in target_ids:
        if not region.contains_id(nid):
            raise LeakageError(f"split manifest lists {nid} as a target but it is outside the region")
    for nid in training_ids:
        if region.contains_id(nid):
            raise LeakageError(f"split manifest lists {nid} as training but it is inside the region")
    return payload
