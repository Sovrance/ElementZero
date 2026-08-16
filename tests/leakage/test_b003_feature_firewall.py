"""EZ-B003 leakage controls: the closure label must never reach a feature (WO-10 7).

Two boundaries are attacked here, from as many directions as possible:

* the *feature* boundary — a discovery-profile run may see Z, N, and A, and
  nothing that encodes where the known closures are. The primary protection is
  the explicit feature-policy manifest whose hash enters the split digest, the
  freeze, and every certificate; the denylist is defense in depth.
* the *geometric* boundary — the closure neighborhood lives in the same snapshot
  as the training corpus, so blindness cannot be enforced at the filesystem
  boundary and has to be re-derived on every fit.
"""

from __future__ import annotations

import json

import pytest

from elementzero.benchmark.b003_freeze import (
    ShellFreeze,
    assert_split_geometry,
    freeze_shell_split,
    load_shell_freeze,
)
from elementzero.benchmark.b003_predict import (
    _assert_manifest_free_of_targets,
    assert_fitted_model_features,
    load_shell_targets,
    predict_shell_run,
)
from elementzero.benchmark.b003_prepare import (
    DISCOVERY_ALLOWED_FEATURES,
    DISCOVERY_FEATURE_DENYLIST,
    FEATURE_POLICY_EZ_B003_ACCURACY,
    FEATURE_POLICY_EZ_B003_DISCOVERY,
    FIREWALL_POLICY_ID,
    PROFILE_ACCURACY,
    PROFILE_DISCOVERY,
    SPLIT_MANIFEST_FILE,
    TARGETS_FILE,
    assert_discovery_features,
    assert_profile_not_mixed,
    denied_reason,
    eligible_observations,
    feature_policy_hash,
    feature_policy_payload,
    load_split_manifest,
    normalize_feature_name,
    prepare_shell_split,
    split_digest,
)
from elementzero.benchmark.b003_score import score_shell_run
from elementzero.benchmark.shell_masks import neutron_mask
from elementzero.data.observations import TRUTH_BEARING_FIELDS
from elementzero.errors import LeakageError, ProtocolError, SchemaError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json

EDITION = "AME2020"
CREATED_AT = "2026-01-01T00:00:00Z"
# The neutron closure the small synthetic shell chart can support.
MASK = neutron_mask(50, z_min=26, z_max=32)
MANIFEST_HASH = "0" * 64


def _split(tmp_path, source, mask=MASK, **kwargs):
    return prepare_shell_split(
        source=source,
        edition_id=EDITION,
        mask=mask,
        challenge_manifest_hash=MANIFEST_HASH,
        out_dir=tmp_path / "challenge",
        **kwargs,
    )


def _sealed(tmp_path, source, mask=MASK):
    split = _split(tmp_path, source, mask)
    freeze = freeze_shell_split(
        source=source,
        edition_id=EDITION,
        split_manifest=tmp_path / "challenge" / SPLIT_MANIFEST_FILE,
        output=tmp_path / "challenge" / "freeze.json",
    )
    return split, freeze


# --------------------------------------------------------------------------- #
# WO-10 section 7: the denylist                                               #
# --------------------------------------------------------------------------- #


def test_discovery_feature_firewall():
    """Every name WO-10 forbids is rejected, and so are its obvious disguises."""
    # The allowed set passes, on its own and in any order.
    assert assert_discovery_features(["Z", "N", "A"]) == ["Z", "N", "A"]
    assert assert_discovery_features(["A", "N", "Z"]) == ["A", "N", "Z"]

    # The literal WO-10 denylist.
    for denied in DISCOVERY_FEATURE_DENYLIST:
        assert denied_reason(denied) is not None
        with pytest.raises(LeakageError) as excinfo:
            assert_discovery_features(["Z", "N", denied])
        assert denied in str(excinfo.value)

    # Semantic equivalents: renaming is not a bypass.
    disguised = [
        "is_magic",
        "isMagic",
        "IS-MAGIC",
        "n_magic_distance",
        "shell_distance",
        "shellDistance",
        "distance_to_126",
        "dist_to_82",
        "distance-to-50",
        "distance_to_magic",
        "known_closure_flag",
        "closure_index",
        "shell_label",
        "shell_gap_MeV",
        "gap",
        "delta2n",
        "S2p",
        "binding_energy_MeV",
        "mass_excess_keV",
        "truth",
        "target",
        "label",
    ]
    for name in disguised:
        assert denied_reason(name) is not None, name
        with pytest.raises(LeakageError):
            assert_discovery_features(["Z", "N", "A", name])

    # Anything outside the declared set is refused even when it is innocuous:
    # the allowed list, not the denylist, is the primary control.
    assert "not in the declared discovery feature set" in denied_reason("radius_fm")
    with pytest.raises(LeakageError):
        assert_discovery_features(["Z", "N", "A", "radius_fm"])
    # An empty feature set is not "no leakage", it is an undeclared model.
    with pytest.raises(LeakageError):
        assert_discovery_features([])

    assert normalize_feature_name("Distance-To-82") == "distance_to_82"
    assert normalize_feature_name("distanceTo82") == "distance_to82"
    assert normalize_feature_name("  IS__MAGIC ") == "is_magic"
    # The reason is the specific one, not the generic "not in the allowed set":
    # a renamed magic-number distance is still recognized as one.
    assert "distance to a specific nucleon number" in denied_reason("distanceTo82")
    assert "distance_to_82" in denied_reason("Distance-To-82")


def test_the_discovery_feature_policy_cannot_declare_a_forbidden_feature():
    policy = feature_policy_payload(profile=PROFILE_DISCOVERY)
    assert policy["feature_policy_id"] == FEATURE_POLICY_EZ_B003_DISCOVERY
    assert policy["features"] == list(DISCOVERY_ALLOWED_FEATURES)
    assert policy["magic_number_distance_features"] is False
    assert policy["shell_label_features"] is False
    assert policy["firewall"]["firewall_policy_id"] == FIREWALL_POLICY_ID
    assert set(DISCOVERY_FEATURE_DENYLIST) <= set(policy["firewall"]["denylist"])
    # v1 preregisters no parity feature, so declaring one is still a policy edit.
    assert policy["preregistrable_parity_features"]
    with pytest.raises(LeakageError):
        feature_policy_payload(profile=PROFILE_DISCOVERY, features=["Z", "N", "A", "is_magic"])
    with pytest.raises(SchemaError):
        feature_policy_payload(profile="whatever")
    # The hash is what enters the freeze, so it must move with the policy.
    assert feature_policy_hash(profile=PROFILE_DISCOVERY) != feature_policy_hash(
        profile=PROFILE_ACCURACY
    )
    assert (
        feature_policy_payload(profile=PROFILE_ACCURACY)["feature_policy_id"]
        == FEATURE_POLICY_EZ_B003_ACCURACY
    )


def test_discovery_and_accuracy_profiles_may_not_be_pooled():
    assert assert_profile_not_mixed([PROFILE_DISCOVERY, PROFILE_DISCOVERY]) == PROFILE_DISCOVERY
    with pytest.raises(ProtocolError):
        assert_profile_not_mixed([PROFILE_DISCOVERY, PROFILE_ACCURACY])
    with pytest.raises(SchemaError):
        assert_profile_not_mixed(["discovery-ish"])


def test_the_firewall_runs_against_the_fitted_model_manifest():
    """A model that quietly added a shell feature cannot seal a run.

    The policy file is the primary control, but it is a file. This check reads
    what the fitted model itself declares.
    """
    honest = {"model_id": "EZ-TEST-v1", "features": ["Z", "N", "A"]}
    assert assert_fitted_model_features(
        honest, profile=PROFILE_DISCOVERY, allowed=list(DISCOVERY_ALLOWED_FEATURES)
    ) == ["Z", "N", "A"]

    sneaky = {"model_id": "EZ-TEST-v1", "features": ["Z", "N", "A", "distance_to_50"]}
    with pytest.raises(LeakageError):
        assert_fitted_model_features(
            sneaky, profile=PROFILE_DISCOVERY, allowed=list(DISCOVERY_ALLOWED_FEATURES)
        )
    # Even a feature the firewall does not recognize is refused when it is
    # outside the frozen policy.
    extra = {"model_id": "EZ-TEST-v1", "features": ["Z", "N", "A", "z_parity"]}
    with pytest.raises(LeakageError):
        assert_fitted_model_features(
            extra, profile=PROFILE_DISCOVERY, allowed=list(DISCOVERY_ALLOWED_FEATURES)
        )
    # A model that declares nothing cannot be checked, so it cannot run.
    with pytest.raises(ProtocolError):
        assert_fitted_model_features(
            {"model_id": "EZ-TEST-v1"},
            profile=PROFILE_DISCOVERY,
            allowed=list(DISCOVERY_ALLOWED_FEATURES),
        )
    # The accuracy profile is allowed shell features; that is the point of the
    # profile split, and its results are never rediscovery evidence.
    assert assert_fitted_model_features(
        sneaky, profile=PROFILE_ACCURACY, allowed=list(DISCOVERY_ALLOWED_FEATURES)
    ) == ["Z", "N", "A", "distance_to_50"]


def test_the_suite_models_declare_only_identity_features(tmp_path, small_synthetic_shell_chart):
    from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
    from elementzero.models.gp_residual import build_model

    observations = eligible_observations(small_synthetic_shell_chart, EDITION)[:60]
    for model_id in SUITE_MODEL_IDS:
        model = build_model(model_id)
        model.fit(observations)
        payload = model.manifest()
        assert assert_fitted_model_features(
            payload, profile=PROFILE_DISCOVERY, allowed=list(DISCOVERY_ALLOWED_FEATURES)
        ) == ["Z", "N", "A"]


# --------------------------------------------------------------------------- #
# The policy has to survive the whole pipeline                                 #
# --------------------------------------------------------------------------- #


def test_a_tampered_split_manifest_policy_is_refused(tmp_path, small_synthetic_shell_chart):
    split = _split(tmp_path, small_synthetic_shell_chart)
    path = tmp_path / "challenge" / SPLIT_MANIFEST_FILE
    assert load_split_manifest(path)["feature_policy_id"] == FEATURE_POLICY_EZ_B003_DISCOVERY

    manifest = split["split_manifest"]
    # Adding a forbidden feature without touching the hash: caught by the firewall.
    tampered = {**manifest, "features": [*manifest["features"], "distance_to_50"]}
    path.write_text(canonical_json(tampered) + "\n", encoding="utf-8")
    with pytest.raises(LeakageError):
        load_split_manifest(path)

    # Adding it *and* rehashing the policy: caught because the split digest
    # binds the policy hash.
    policy = feature_policy_payload(
        profile=PROFILE_ACCURACY, features=[*manifest["features"], "distance_to_50"]
    )
    from elementzero.evidence.hashing import sha256_hex

    relabelled = {
        **manifest,
        "profile": PROFILE_ACCURACY,
        "features": list(policy["features"]),
        "feature_policy_id": policy["feature_policy_id"],
        "feature_policy_hash": sha256_hex(policy),
    }
    path.write_text(canonical_json(relabelled) + "\n", encoding="utf-8")
    with pytest.raises(ProtocolError):
        load_split_manifest(path)


def test_a_discovery_freeze_refuses_a_relabelled_policy(tmp_path, small_synthetic_shell_chart):
    _split, freeze = _sealed(tmp_path, small_synthetic_shell_chart)
    payload = json.loads((tmp_path / "challenge" / "freeze.json").read_text(encoding="utf-8"))
    assert ShellFreeze.from_dict(payload).profile == PROFILE_DISCOVERY
    assert freeze.freeze.feature_policy_id == FEATURE_POLICY_EZ_B003_DISCOVERY
    # Swapping the profile label leaves the policy hash pointing at the other
    # profile, which the freeze loader checks.
    with pytest.raises(ProtocolError):
        ShellFreeze.from_dict({**payload, "profile": PROFILE_ACCURACY})
    with pytest.raises(LeakageError):
        ShellFreeze.from_dict({**payload, "features": ["Z", "N", "A", "is_magic"]})


def test_split_manifest_and_freeze_carry_no_truth(tmp_path, small_synthetic_shell_chart):
    split, freeze = _sealed(tmp_path, small_synthetic_shell_chart)

    def walk(node, where):
        if isinstance(node, dict):
            assert not TRUTH_BEARING_FIELDS.intersection(node), (where, sorted(node))
            for key, value in node.items():
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for item in node:
                walk(item, where)

    walk(split["split_manifest"], "split_manifest")
    walk(freeze.to_dict(), "freeze")
    for target in split["targets"]:
        assert set(target) == {"nuclide_id", "Z", "N", "A"}
    targets = load_shell_targets(tmp_path / "challenge" / TARGETS_FILE)
    for target in targets:
        assert set(target) == {"nuclide_id", "Z", "N", "A"}
        assert MASK.contains(target["Z"], target["N"])


def test_a_target_moved_outside_the_mask_is_refused(tmp_path, small_synthetic_shell_chart):
    split = _split(tmp_path, small_synthetic_shell_chart)
    manifest = split["split_manifest"]
    outside = next(nid for nid in manifest["training_nuclide_ids"] if not MASK.contains_id(nid))
    tampered = {
        **manifest,
        "target_nuclide_ids": [*manifest["target_nuclide_ids"], outside],
    }
    tampered["target_identity_digest"] = identity_digest(tampered["target_nuclide_ids"])
    tampered["split_digest"] = split_digest(
        raw_source_hash=tampered["raw_source_hash"],
        challenge_manifest_hash=tampered["challenge_manifest_hash"],
        mask_hash=tampered["mask_hash"],
        training_identity_digest=tampered["training_identity_digest"],
        target_identity_digest=tampered["target_identity_digest"],
        feature_policy_hash=tampered["feature_policy_hash"],
    )
    path = tmp_path / "challenge" / SPLIT_MANIFEST_FILE
    path.write_text(canonical_json(tampered) + "\n", encoding="utf-8")
    with pytest.raises(LeakageError):
        load_split_manifest(path)


def test_assert_split_geometry_catches_every_boundary_violation():
    inside = "Z28-N50"
    outside = "Z28-N48"
    assert MASK.contains_id(inside) and not MASK.contains_id(outside)
    assert_split_geometry(
        mask=MASK, training_nuclide_ids=[outside], target_nuclide_ids=[inside]
    )
    with pytest.raises(LeakageError):
        assert_split_geometry(
            mask=MASK, training_nuclide_ids=[outside], target_nuclide_ids=[outside]
        )
    with pytest.raises(LeakageError):
        assert_split_geometry(
            mask=MASK, training_nuclide_ids=[inside], target_nuclide_ids=[inside]
        )


# --------------------------------------------------------------------------- #
# The geometric boundary, enforced on every fit                                #
# --------------------------------------------------------------------------- #


def test_the_fit_never_sees_a_masked_mass(tmp_path, small_synthetic_shell_chart, monkeypatch):
    """Spy on the fit: identities and masses inside the mask must be absent."""
    _split, freeze = _sealed(tmp_path, small_synthetic_shell_chart)
    targets = load_shell_targets(tmp_path / "challenge" / TARGETS_FILE)
    seen: list[list] = []
    real_build = __import__(
        "elementzero.models.gp_residual", fromlist=["build_model"]
    ).build_model

    def spying_build(model_id):
        model = real_build(model_id)
        real_fit = model.fit

        def fit(observations):
            seen.append(list(observations))
            return real_fit(observations)

        model.fit = fit
        return model

    monkeypatch.setattr("elementzero.benchmark.b003_predict.build_model", spying_build)
    predict_shell_run(
        shell_freeze=freeze,
        targets=targets,
        source=small_synthetic_shell_chart,
        edition_id=EDITION,
        run_dir=tmp_path / "run",
        created_at=CREATED_AT,
    )
    assert len(seen) == 1
    fitted = seen[0]
    withheld = set(freeze.target_nuclide_ids)
    assert fitted and withheld
    assert not {o.nuclide_id for o in fitted} & withheld
    assert not [o for o in fitted if MASK.contains(o.Z, o.N)]
    hidden_masses = {
        o.mass_excess_keV
        for o in eligible_observations(small_synthetic_shell_chart, EDITION)
        if o.nuclide_id in withheld
    }
    assert not {o.mass_excess_keV for o in fitted} & hidden_masses
    assert {o.nuclide_id for o in fitted} == set(freeze.freeze.training_nuclide_ids)


def test_prediction_refuses_a_tampered_target_set(tmp_path, small_synthetic_shell_chart):
    _split, freeze = _sealed(tmp_path, small_synthetic_shell_chart)
    targets = load_shell_targets(tmp_path / "challenge" / TARGETS_FILE)
    with pytest.raises(LeakageError):
        predict_shell_run(
            shell_freeze=freeze,
            targets=targets[:-1],
            source=small_synthetic_shell_chart,
            edition_id=EDITION,
            run_dir=tmp_path / "short",
            created_at=CREATED_AT,
        )
    outside = next(
        nid for nid in freeze.freeze.training_nuclide_ids if not MASK.contains_id(nid)
    )
    z, n = outside[1:].split("-N")
    smuggled = [
        *targets,
        {"nuclide_id": outside, "Z": int(z), "N": int(n), "A": int(z) + int(n)},
    ]
    with pytest.raises(LeakageError):
        predict_shell_run(
            shell_freeze=freeze,
            targets=smuggled,
            source=small_synthetic_shell_chart,
            edition_id=EDITION,
            run_dir=tmp_path / "smuggled",
            created_at=CREATED_AT,
        )


def test_prediction_refuses_a_snapshot_the_freeze_never_saw(
    tmp_path, small_synthetic_shell_chart, small_synthetic_chart
):
    _split, freeze = _sealed(tmp_path, small_synthetic_shell_chart)
    targets = load_shell_targets(tmp_path / "challenge" / TARGETS_FILE)
    with pytest.raises(LeakageError):
        predict_shell_run(
            shell_freeze=freeze,
            targets=targets,
            source=small_synthetic_chart,
            edition_id=EDITION,
            run_dir=tmp_path / "wrong_source",
            created_at=CREATED_AT,
        )
    with pytest.raises(LeakageError):
        predict_shell_run(
            shell_freeze=freeze,
            targets=targets,
            source=small_synthetic_shell_chart,
            edition_id="AME2016",
            run_dir=tmp_path / "wrong_edition",
            created_at=CREATED_AT,
        )


def test_a_withheld_identity_may_not_appear_in_a_fitted_manifest():
    _assert_manifest_free_of_targets({"fitted_nuclide_ids": ["Z28-N48"]}, ["Z28-N50"])
    with pytest.raises(LeakageError):
        _assert_manifest_free_of_targets(
            {"fitted_nuclide_ids": ["Z28-N48", "Z28-N50"]}, ["Z28-N50"]
        )
    # Anywhere in the manifest counts, not only the fitted identity list.
    with pytest.raises(LeakageError):
        _assert_manifest_free_of_targets({"notes": {"excluded": ["Z28-N50"]}}, ["Z28-N50"])


def test_scoring_refuses_an_unsealed_run(tmp_path, small_synthetic_shell_chart):
    _split, freeze = _sealed(tmp_path, small_synthetic_shell_chart)
    targets = load_shell_targets(tmp_path / "challenge" / TARGETS_FILE)
    run_dir = tmp_path / "run"
    predict_shell_run(
        shell_freeze=freeze,
        targets=targets,
        source=small_synthetic_shell_chart,
        edition_id=EDITION,
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    with pytest.raises(LeakageError):
        score_shell_run(
            run_dir=run_dir,
            truth_source=small_synthetic_shell_chart,
            truth_edition_id=EDITION,
            scope="synthetic",
            out_dir=tmp_path / "score",
            created_at=CREATED_AT,
        )


def test_scoring_refuses_a_truth_table_that_is_not_the_frozen_snapshot(
    tmp_path, small_synthetic_shell_chart, small_synthetic_chart
):
    from elementzero.benchmark.b003_finalize import finalize_shell_run

    _split, freeze = _sealed(tmp_path, small_synthetic_shell_chart)
    targets = load_shell_targets(tmp_path / "challenge" / TARGETS_FILE)
    run_dir = tmp_path / "run"
    predict_shell_run(
        shell_freeze=freeze,
        targets=targets,
        source=small_synthetic_shell_chart,
        edition_id=EDITION,
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    finalize_shell_run(run_dir, created_at=CREATED_AT)
    with pytest.raises(ProtocolError):
        score_shell_run(
            run_dir=run_dir,
            truth_source=small_synthetic_chart,
            truth_edition_id=EDITION,
            scope="synthetic",
            out_dir=tmp_path / "score",
            created_at=CREATED_AT,
        )
    # And a scoring run has to say what it is scoring.
    with pytest.raises(SchemaError):
        score_shell_run(
            run_dir=run_dir,
            truth_source=small_synthetic_shell_chart,
            truth_edition_id=EDITION,
            scope="",
            out_dir=tmp_path / "score",
            created_at=CREATED_AT,
        )


def test_the_sealed_freeze_reloads_with_its_geometry_intact(
    tmp_path, small_synthetic_shell_chart
):
    _split, freeze = _sealed(tmp_path, small_synthetic_shell_chart)
    reloaded = load_shell_freeze(tmp_path / "challenge" / "freeze.json")
    assert reloaded.mask == freeze.mask
    assert reloaded.split_digest == freeze.split_digest
    assert reloaded.freeze_id == freeze.freeze_id
    assert reloaded.profile == PROFILE_DISCOVERY
    assert reloaded.target_nuclide_ids == freeze.target_nuclide_ids
    payload = json.loads((tmp_path / "challenge" / "freeze.json").read_text(encoding="utf-8"))
    with pytest.raises(ProtocolError):
        ShellFreeze.from_dict({**payload, "split_digest": "0" * 64})
    with pytest.raises(ProtocolError):
        ShellFreeze.from_dict({**payload, "mask_hash": "0" * 64})
    with pytest.raises(ProtocolError):
        ShellFreeze.from_dict({**payload, "challenge_id": "neutron-N82"})
    with pytest.raises(ProtocolError):
        ShellFreeze.from_dict({k: v for k, v in payload.items() if k != "mask"})
