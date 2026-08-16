"""EZ-B003 preparation: one snapshot plus one shell mask -> a hidden-shell split.

WO-10 sections 1, 2, and 7. Preparation does three things:

1. splits one frozen snapshot around one preregistered closure neighborhood::

       targets  = eligible nuclei inside the mask
       training = eligible nuclei outside the mask

2. records which chains the support rule found evaluable, so a closure that
   cannot supply the derived observables is reported ``NOT_EVALUABLE`` instead of
   being dropped,
3. declares the benchmark *profile* and enforces its feature firewall.

Two profiles, never mixed (WO-10 "Required separation: accuracy vs discovery"):

    discovery   Z, N, A, plus primitive parity terms only if preregistered.
                Forbidden: any feature that encodes where the shell closures are.
    accuracy    may later include physics-informed shell features.

The firewall is defense in depth. The primary protection is the explicit feature
policy manifest, which names the exact allowed features and is hashed into the
split digest and the freeze. The denylist exists because a manifest is only as
good as the code that refuses to contradict it.

The split digest binds the six things that define a hidden-shell split::

    source hash
    challenge manifest hash
    mask hash
    training identity digest
    target identity digest
    feature policy hash

Any change to any of them changes the digest, and therefore the freeze ID and
every certificate that quotes it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from elementzero import B003_PROTOCOL_VERSION, BENCHMARK_EZ_B003
from elementzero.benchmark.shell_masks import (
    CHALLENGE_POLICY_ID,
    MASK_POLICY_ID,
    STATUS_EVALUABLE,
    SUPPORT_POLICY_ID,
    ShellMask,
    assert_mask_populated,
    chain_support,
    mask_hash,
    split_points,
    support_settings,
)
from elementzero.data.amdc import load_edition
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.observations import GROUND_TRUTH_POLICY, MassObservation
from elementzero.errors import LeakageError, ProtocolError, SchemaError
from elementzero.evidence.freezes import identity_digest, validate_target_record
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.physics.constants import NORMALIZER_VERSION
from elementzero.physics.separation import separation_policy

SHELL_SPLIT_POLICY_ID = "ez-b003-shell-split-v1"

PROFILE_DISCOVERY = "discovery"
PROFILE_ACCURACY = "accuracy"
PROFILES: tuple[str, ...] = (PROFILE_DISCOVERY, PROFILE_ACCURACY)

FEATURE_POLICY_EZ_B003_DISCOVERY = "ez-b003-discovery-identity-zn-v1"
FEATURE_POLICY_EZ_B003_ACCURACY = "ez-b003-accuracy-shell-informed-v1"
FEATURE_POLICY_IDS = {
    PROFILE_DISCOVERY: FEATURE_POLICY_EZ_B003_DISCOVERY,
    PROFILE_ACCURACY: FEATURE_POLICY_EZ_B003_ACCURACY,
}

# The discovery profile's allowed feature set. v1 declares identity features
# only; the parity terms are listed so a later protocol version can preregister
# them explicitly instead of smuggling them in as "primitive".
DISCOVERY_ALLOWED_FEATURES: tuple[str, ...] = ("Z", "N", "A")
DISCOVERY_PREREGISTRABLE_PARITY_FEATURES: tuple[str, ...] = (
    "z_parity",
    "n_parity",
    "a_parity",
)

FIREWALL_POLICY_ID = "ez-b003-discovery-feature-firewall-v1"

# WO-10 section 7 denylist, plus the derived observables themselves: a model that
# takes delta2n as a feature is being told the answer.
DISCOVERY_FEATURE_DENYLIST: tuple[str, ...] = (
    "magic",
    "shell_distance",
    "distance_to_20",
    "distance_to_28",
    "distance_to_50",
    "distance_to_82",
    "distance_to_126",
    "known_closure",
    "shell_label",
)

# Semantic equivalents of the denied names. A denylist over literal strings is
# trivially bypassed by renaming, so the firewall also matches the shapes those
# names take: any distance to any integer, any shell/closure wording, any
# separation observable, and any truth-bearing quantity.
DISCOVERY_FEATURE_DENY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"magic", "names a magic number"),
    (r"shell", "names shell structure"),
    (r"closure", "names a shell closure"),
    # ``_?`` after ``to`` so that camelCase names normalize into the same shape:
    # ``distanceTo82`` becomes ``distance_to82``, which is the same feature as
    # ``distance_to_82`` and must be refused with the same reason.
    (r"(^|_)(dist|distance)_to_?[0-9]+($|_)", "is a distance to a specific nucleon number"),
    (r"(^|_)(dist|distance)_to_(magic|closure|shell)", "is a distance to a closure"),
    (r"(^|_)gap($|_)", "names a shell gap"),
    (r"(^|_)(s2n|s2p|delta2n|delta2p)($|_)", "is a derived separation observable"),
    (r"binding", "is a derived binding energy"),
    (r"mass_excess", "is target truth"),
    (r"(^|_)truth($|_)", "is target truth"),
    (r"(^|_)label($|_)", "is a supervised label"),
    (r"(^|_)target($|_)", "is target truth"),
)

FIREWALL_RULE = (
    f"{FIREWALL_POLICY_ID}: in the discovery profile a feature name is rejected "
    "when it is not in the declared allowed set, or when its normalized form "
    "contains a denied token or matches a denied pattern. The denylist is defense "
    "in depth; the primary protection is the explicit feature-policy manifest, "
    "whose hash enters the split digest, the freeze, and every certificate."
)

PROFILE_SEPARATION_RULE = (
    "Discovery-profile and accuracy-profile results answer different questions and "
    "may not be pooled, averaged, or reported as one number. A run declares exactly "
    "one profile, and a comparison across profiles is a protocol error."
)

TARGETS_FILE = "targets.json"
SPLIT_MANIFEST_FILE = "split_manifest.json"
SUPPORT_FILE = "support.json"

SPLIT_DIGEST_RULE = (
    "ez-b003-split-digest-v1: sha256 of canonical JSON of {challenge_manifest_hash, "
    "feature_policy_hash, mask_hash, raw_source_hash, target_identity_digest, "
    "training_identity_digest}"
)

_COMPILED_DENY_PATTERNS = tuple(
    (re.compile(pattern), reason) for pattern, reason in DISCOVERY_FEATURE_DENY_PATTERNS
)


# --------------------------------------------------------------------------- #
# Feature firewall                                                            #
# --------------------------------------------------------------------------- #


def normalize_feature_name(name: str) -> str:
    """Lowercase, with every run of non-alphanumerics collapsed to one underscore.

    Normalizing first is what makes ``Distance-To-82``, ``distanceTo82``, and
    ``distance_to_82`` the same feature to the firewall.
    """
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name))
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    return re.sub(r"_+", "_", text)


def denied_reason(name: str, *, allowed: Sequence[str] = DISCOVERY_ALLOWED_FEATURES) -> str | None:
    """Why the discovery profile refuses this feature name, or None."""
    normalized = normalize_feature_name(name)
    allowed_normalized = {normalize_feature_name(a) for a in allowed}
    if normalized in allowed_normalized:
        return None
    for token in DISCOVERY_FEATURE_DENYLIST:
        if normalize_feature_name(token) in normalized:
            return f"contains the denied token {token!r}"
    for pattern, reason in _COMPILED_DENY_PATTERNS:
        if pattern.search(normalized):
            return reason
    return f"is not in the declared discovery feature set {sorted(allowed_normalized)}"


def assert_discovery_features(
    features: Iterable[str],
    *,
    allowed: Sequence[str] = DISCOVERY_ALLOWED_FEATURES,
    where: str = "discovery feature set",
) -> list[str]:
    """Refuse any feature the discovery profile does not allow."""
    names = [str(f) for f in features]
    if not names:
        raise LeakageError(f"{where} is empty; the discovery profile must declare its features")
    rejected = {name: denied_reason(name, allowed=allowed) for name in names}
    bad = {name: reason for name, reason in rejected.items() if reason is not None}
    if bad:
        detail = "; ".join(f"{name!r} {reason}" for name, reason in sorted(bad.items()))
        raise LeakageError(f"{where} violates the discovery feature firewall: {detail}")
    return names


def assert_profile_not_mixed(profiles: Iterable[str], *, where: str = "comparison") -> str:
    """One profile per reported result (see PROFILE_SEPARATION_RULE)."""
    ordered = sorted({str(p) for p in profiles})
    unknown = [p for p in ordered if p not in PROFILES]
    if unknown:
        raise SchemaError(f"unsupported benchmark profiles {unknown}; supported are {list(PROFILES)}")
    if len(ordered) != 1:
        raise ProtocolError(
            f"{where} mixes benchmark profiles {ordered}. {PROFILE_SEPARATION_RULE}"
        )
    return ordered[0]


def firewall_payload() -> dict[str, Any]:
    return {
        "firewall_policy_id": FIREWALL_POLICY_ID,
        "denylist": list(DISCOVERY_FEATURE_DENYLIST),
        "deny_patterns": [
            {"pattern": pattern, "reason": reason}
            for pattern, reason in DISCOVERY_FEATURE_DENY_PATTERNS
        ],
        "normalization": (
            "lowercase; camelCase split; every run of non-alphanumerics collapsed to "
            "one underscore"
        ),
        "rule": FIREWALL_RULE,
    }


def feature_policy_payload(
    *,
    profile: str = PROFILE_DISCOVERY,
    features: Sequence[str] | None = None,
) -> dict[str, Any]:
    """The frozen feature policy of one profile.

    The discovery policy is validated against its own firewall on construction,
    so a policy that declares a forbidden feature cannot be hashed into a freeze.
    """
    if profile not in PROFILES:
        raise SchemaError(f"unsupported profile {profile!r}; supported are {list(PROFILES)}")
    if profile == PROFILE_DISCOVERY:
        declared = list(features or DISCOVERY_ALLOWED_FEATURES)
        assert_discovery_features(declared, where="discovery feature policy")
        return {
            "feature_policy_id": FEATURE_POLICY_EZ_B003_DISCOVERY,
            "profile": PROFILE_DISCOVERY,
            "features": declared,
            "magic_number_distance_features": False,
            "shell_label_features": False,
            "preregistrable_parity_features": list(DISCOVERY_PREREGISTRABLE_PARITY_FEATURES),
            "firewall": firewall_payload(),
            "profile_separation_rule": PROFILE_SEPARATION_RULE,
            "notes": (
                "EZ-B003 discovery profile: identity features only. No distance to a "
                "known closure, no is_magic flag, no named shell closure, no shell-gap "
                "lookup, no derived separation observable, and no target truth. "
                "Primitive parity terms are allowed only when preregistered, and v1 "
                "does not preregister any."
            ),
        }
    declared = list(features or DISCOVERY_ALLOWED_FEATURES)
    return {
        "feature_policy_id": FEATURE_POLICY_EZ_B003_ACCURACY,
        "profile": PROFILE_ACCURACY,
        "features": declared,
        "magic_number_distance_features": True,
        "shell_label_features": True,
        "firewall": {
            "firewall_policy_id": FIREWALL_POLICY_ID,
            "applies": False,
            "rule": (
                "The accuracy profile may use physics-informed shell features. Its "
                "results are never evidence of rediscovery and are never pooled with "
                "discovery-profile results."
            ),
        },
        "profile_separation_rule": PROFILE_SEPARATION_RULE,
        "notes": (
            "EZ-B003 accuracy profile: reserved for a later protocol version. A run "
            "under this policy answers 'how accurate', never 'was it rediscovered'."
        ),
    }


def feature_policy_hash(
    *, profile: str = PROFILE_DISCOVERY, features: Sequence[str] | None = None
) -> str:
    return sha256_hex(feature_policy_payload(profile=profile, features=features))


# --------------------------------------------------------------------------- #
# Snapshot access                                                             #
# --------------------------------------------------------------------------- #


def eligible_observations(source: str | Path, edition_id: str) -> list[MassObservation]:
    """Ground-truth eligible rows of one frozen snapshot, sorted by identity."""
    observations = [
        obs for obs in load_edition(edition_id, str(source)) if obs.ground_truth_eligible
    ]
    if not observations:
        raise ProtocolError(f"{edition_id} snapshot has no ground-truth eligible rows")
    return sorted(observations, key=lambda o: o.nuclide_id)


def eligible_points(source: str | Path, edition_id: str) -> list[tuple[int, int]]:
    """Eligible (Z, N) lattice points; the input of challenge generation."""
    return sorted({(obs.Z, obs.N) for obs in eligible_observations(source, edition_id)})


def split_digest(
    *,
    raw_source_hash: str,
    challenge_manifest_hash: str,
    mask_hash: str,
    training_identity_digest: str,
    target_identity_digest: str,
    feature_policy_hash: str,
) -> str:
    return sha256_hex(
        {
            "challenge_manifest_hash": challenge_manifest_hash,
            "feature_policy_hash": feature_policy_hash,
            "mask_hash": mask_hash,
            "raw_source_hash": raw_source_hash,
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


def support_report(
    *,
    mask: ShellMask,
    points: Sequence[tuple[int, int]],
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-chain support of one mask, recomputed from identities alone."""
    frozen = dict(settings or support_settings(half_width=mask.half_width))
    supports = [
        chain_support(
            mask,
            points,
            chain=chain,
            min_chain_length=frozen["MIN_CHAIN_LENGTH"],
            min_peak_candidates=frozen["MIN_PEAK_CANDIDATES"],
            peak_window=frozen["PEAK_WINDOW"],
        )
        for chain in range(mask.span_min, mask.span_max + 1)
    ]
    supported = [s for s in supports if s.supported]
    return {
        "mask_id": mask.mask_id,
        "challenge_id": mask.challenge_id,
        "support_policy_id": SUPPORT_POLICY_ID,
        "support_settings": frozen,
        "indicator": mask.indicator,
        "n_chains": len(supports),
        "n_supported_chains": len(supported),
        "supported_chains": [s.chain for s in supported],
        "unsupported_chains": [s.chain for s in supports if not s.supported],
        "chain_support": [s.to_dict() for s in supports],
        "peak_candidates": list(mask.peak_candidates(window=frozen["PEAK_WINDOW"])),
    }


# --------------------------------------------------------------------------- #
# The split                                                                   #
# --------------------------------------------------------------------------- #


def prepare_shell_split(
    *,
    source: str | Path,
    edition_id: str,
    mask: ShellMask,
    challenge_manifest_hash: str,
    out_dir: str | Path | None = None,
    min_targets: int = 1,
    profile: str = PROFILE_DISCOVERY,
    features: Sequence[str] | None = None,
    support_settings_payload: dict[str, Any] | None = None,
    benchmark_id: str = BENCHMARK_EZ_B003,
) -> dict[str, Any]:
    """Split one snapshot around one shell mask and write identity-only artifacts."""
    if benchmark_id != BENCHMARK_EZ_B003:
        raise ValueError(f"unsupported benchmark {benchmark_id}; this stage is {BENCHMARK_EZ_B003}")
    source = Path(source)
    observations = eligible_observations(source, edition_id)
    points = [(obs.Z, obs.N) for obs in observations]
    assert_mask_populated(mask, points, min_targets=min_targets)

    inside = [obs for obs in observations if mask.contains(obs.Z, obs.N)]
    outside = [obs for obs in observations if not mask.contains(obs.Z, obs.N)]
    if not outside:
        raise ProtocolError(
            f"mask {mask.mask_id} leaves no training nuclei; the split would have nothing to fit"
        )
    # Geometry is the whole leakage control here, so it is re-derived rather than
    # trusted: the two sides must partition the eligible set exactly.
    geometric = split_points(points, mask)
    if sorted({(o.Z, o.N) for o in inside}) != geometric["targets"]:
        raise LeakageError(f"mask {mask.mask_id} target set does not match its geometry")
    if sorted({(o.Z, o.N) for o in outside}) != geometric["training"]:
        raise LeakageError(f"mask {mask.mask_id} training set does not match its geometry")

    targets = _identity_records(inside)
    target_ids = [t["nuclide_id"] for t in targets]
    training_ids = [obs.nuclide_id for obs in outside]
    overlap = sorted(set(target_ids) & set(training_ids))
    if overlap:
        raise LeakageError(f"mask {mask.mask_id} keeps targets in training: {overlap}")

    raw_source_hash = sha256_file(source)
    policy = feature_policy_payload(profile=profile, features=features)
    policy_hash = sha256_hex(policy)
    training_digest = identity_digest(training_ids)
    target_digest = identity_digest(target_ids)
    digest = split_digest(
        raw_source_hash=raw_source_hash,
        challenge_manifest_hash=challenge_manifest_hash,
        mask_hash=mask_hash(mask),
        training_identity_digest=training_digest,
        target_identity_digest=target_digest,
        feature_policy_hash=policy_hash,
    )
    support = support_report(mask=mask, points=points, settings=support_settings_payload)
    manifest = {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": B003_PROTOCOL_VERSION,
        "split_policy_id": SHELL_SPLIT_POLICY_ID,
        "split_id": f"{mask.mask_id}@{digest[:16]}",
        "profile": policy["profile"],
        "challenge_policy_id": CHALLENGE_POLICY_ID,
        "mask_policy_id": MASK_POLICY_ID,
        "challenge_id": mask.challenge_id,
        "mask_id": mask.mask_id,
        "mask": mask.to_dict(),
        "mask_hash": mask_hash(mask),
        "challenge_manifest_hash": challenge_manifest_hash,
        "axis": mask.axis,
        "closure": mask.closure,
        "indicator": mask.indicator,
        "support_status": (
            STATUS_EVALUABLE if support["n_supported_chains"] else "NOT_EVALUABLE"
        ),
        "n_supported_chains": support["n_supported_chains"],
        "supported_chains": list(support["supported_chains"]),
        "unsupported_chains": list(support["unsupported_chains"]),
        "edition_id": edition_id,
        "raw_source_hash": raw_source_hash,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "parser_version": PARSER_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "feature_policy_id": policy["feature_policy_id"],
        "feature_policy_hash": policy_hash,
        "features": list(policy["features"]),
        "n_eligible": len(observations),
        "n_targets": len(target_ids),
        "n_training": len(training_ids),
        "target_nuclide_ids": target_ids,
        "training_nuclide_ids": sorted(training_ids),
        "target_identity_digest": target_digest,
        "training_identity_digest": training_digest,
        "split_digest": digest,
        "split_digest_rule": SPLIT_DIGEST_RULE,
        "separation_policy": separation_policy(),
        "leakage_rule": (
            "targets are the eligible nuclei inside the masked closure neighborhood "
            "and training is the eligible nuclei outside it; target masses enter no "
            "fit, no feature, no hyperparameter, and no uncertainty calibration. "
            "Target identities (Z, N, A) are allowed. Derived observables are never "
            "training targets."
        ),
        "profile_separation_rule": PROFILE_SEPARATION_RULE,
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
        (dest / SUPPORT_FILE).write_text(canonical_json(support) + "\n", encoding="utf-8")
        written = {
            "targets_path": str(dest / TARGETS_FILE),
            "split_manifest_path": str(dest / SPLIT_MANIFEST_FILE),
            "support_path": str(dest / SUPPORT_FILE),
            "targets_sha256": sha256_file(dest / TARGETS_FILE),
            "split_manifest_sha256": sha256_file(dest / SPLIT_MANIFEST_FILE),
            "support_sha256": sha256_file(dest / SUPPORT_FILE),
        }
    return {
        "mask": mask,
        "targets": targets,
        "split_manifest": manifest,
        "support": support,
        **written,
    }


def _assert_identity_only(payload: Any) -> None:
    """A split manifest may carry identities, hashes, and policy text, never a mass."""
    from elementzero.data.observations import TRUTH_BEARING_FIELDS

    if isinstance(payload, dict):
        leaked = sorted(TRUTH_BEARING_FIELDS.intersection(payload))
        if leaked:
            raise LeakageError(f"shell split manifest carries truth fields: {leaked}")
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
    mask = ShellMask.from_dict(payload["mask"])
    if payload.get("mask_id") != mask.mask_id:
        raise ProtocolError("split manifest mask_id does not match its mask geometry")
    if payload.get("mask_hash") != mask_hash(mask):
        raise ProtocolError("split manifest mask_hash does not match its mask geometry")
    if payload.get("profile") == PROFILE_DISCOVERY:
        assert_discovery_features(payload["features"], where="split manifest features")
    expected_policy_hash = sha256_hex(
        feature_policy_payload(profile=payload["profile"], features=payload["features"])
    )
    if payload["feature_policy_hash"] != expected_policy_hash:
        raise ProtocolError(
            "split manifest feature policy hash does not match the declared profile and features"
        )
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
        challenge_manifest_hash=payload["challenge_manifest_hash"],
        mask_hash=payload["mask_hash"],
        training_identity_digest=payload["training_identity_digest"],
        target_identity_digest=payload["target_identity_digest"],
        feature_policy_hash=payload["feature_policy_hash"],
    )
    if expected != payload["split_digest"]:
        raise ProtocolError("split manifest split_digest does not match its own components")
    for nid in target_ids:
        if not mask.contains_id(nid):
            raise LeakageError(f"split manifest lists {nid} as a target but it is outside the mask")
    for nid in training_ids:
        if mask.contains_id(nid):
            raise LeakageError(f"split manifest lists {nid} as training but it is inside the mask")
    return payload
