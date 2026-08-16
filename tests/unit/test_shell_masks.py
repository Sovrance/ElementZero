"""Hidden-shell masks, the support rule, and the challenge manifest (WO-10 1, 2).

The three things these tests pin down are the three things a reader of an EZ-B003
result has to be able to trust:

* the mask geometry is exactly ``closure -/+ half_width`` on one axis and a
  contiguous chain span on the other, and it carries no truth,
* a closure the snapshot cannot support is reported ``NOT_EVALUABLE`` with
  reasons instead of disappearing,
* the manifest digest changes when a bound, a closure, or a verdict changes, and
  does not change when the file is merely reordered.
"""

from __future__ import annotations

import json

import pytest
from tests.helpers import (
    INJECTED_NEUTRON_CLOSURE,
    INJECTED_PROTON_CLOSURE,
    write_small_synthetic_shell_chart,
)

from elementzero import B003_PROTOCOL_VERSION, BENCHMARK_EZ_B003
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.b003_prepare import eligible_points
from elementzero.benchmark.shell_masks import (
    AXIS_NEUTRON,
    AXIS_PROTON,
    CHALLENGE_POLICY_ID,
    KNOWN_NEUTRON_CLOSURES,
    KNOWN_PROTON_CLOSURES,
    MASK_POLICY_ID,
    MIN_CHAIN_LENGTH,
    MIN_EVALUABLE_CHAINS,
    MIN_TARGETS,
    STATUS_EVALUABLE,
    STATUS_NOT_EVALUABLE,
    SUPPORT_POLICY_ID,
    ShellMask,
    assert_mask_populated,
    chain_support,
    challenge_manifest,
    challenge_manifest_hash,
    evaluate_challenge,
    generate_challenges,
    load_challenge_manifest,
    mask_by_id,
    mask_hash,
    neutron_mask,
    proton_mask,
    split_points,
    support_settings,
)
from elementzero.data.observations import TRUTH_BEARING_FIELDS
from elementzero.errors import ProtocolError, SchemaError

EDITION = "AME2020"
SCHEMAS = REPO_ROOT / "schemas"


def _rectangle(z_lo=24, z_hi=34, n_lo=40, n_hi=60):
    return [(z, n) for z in range(z_lo, z_hi + 1) for n in range(n_lo, n_hi + 1)]


# --------------------------------------------------------------------------- #
# WO-10 section 1: hide a neighborhood, not one point                          #
# --------------------------------------------------------------------------- #


def test_neutron_mask_hides_the_three_closure_columns():
    mask = neutron_mask(50, z_min=24, z_max=30)
    assert mask.axis == AXIS_NEUTRON
    assert mask.hidden_values == (49, 50, 51)
    assert mask.indicator == "delta2n"
    assert mask.mask_id == "shell-N50-w1-Z24-30"
    assert mask.challenge_id == "neutron-N50"
    assert mask.closure_axis_label == "N"
    assert mask.span_axis_label == "Z"
    assert mask.lattice_sites == 3 * 7
    for z in range(24, 31):
        for n in (49, 50, 51):
            assert mask.contains(z, n)
            assert mask.contains_id(f"Z{z}-N{n}")
        # The two-step neighbors stay outside: delta2n(Z,50) expands to
        # 2B(Z,50) - B(Z,48) - B(Z,52), so those two must remain trainable.
        assert not mask.contains(z, 48)
        assert not mask.contains(z, 52)
    assert not mask.contains(23, 50)
    assert not mask.contains(31, 50)
    assert mask.chain_key(27, 50) == 27
    assert mask.closure_coordinate(27, 50) == 50
    assert mask.point(chain=27, coordinate=50) == (27, 50)


def test_proton_mask_hides_the_three_closure_rows():
    mask = proton_mask(28, n_min=30, n_max=36)
    assert mask.axis == AXIS_PROTON
    assert mask.hidden_values == (27, 28, 29)
    assert mask.indicator == "delta2p"
    assert mask.mask_id == "shell-Z28-w1-N30-36"
    assert mask.challenge_id == "proton-Z28"
    for n in range(30, 37):
        for z in (27, 28, 29):
            assert mask.contains(z, n)
        assert not mask.contains(26, n)
        assert not mask.contains(30, n)
    assert not mask.contains(28, 29)
    assert mask.chain_key(28, 33) == 33
    assert mask.point(chain=33, coordinate=28) == (28, 33)


def test_shell_mask_excludes_truth():
    """A mask is geometry over identities. It never carries a mass.

    Both the in-memory payload and the committed JSON Schema refuse a
    truth-bearing field, and the split it produces partitions the lattice with no
    target left in training.
    """
    mask = neutron_mask(50, z_min=24, z_max=30)
    payload = mask.to_dict()
    assert not TRUTH_BEARING_FIELDS.intersection(payload)
    assert set(payload) == {
        "axis",
        "closure_N",
        "half_width",
        "hidden_N",
        "z_min",
        "z_max",
        "mask_id",
    }
    for value in payload.values():
        assert isinstance(value, (str, int, list))

    schema = json.loads((SCHEMAS / "shell_mask.schema.json").read_text(encoding="utf-8"))
    forbidden = {
        entry["required"][0] for entry in schema["not"]["anyOf"]
    }
    assert {"mass_excess_keV", "uncertainty_keV", "binding_energy", "truth"} <= forbidden
    assert {"S2n", "S2p", "delta2n", "delta2p"} <= forbidden
    # Anything the schema forbids is also refused by the loader.
    for field in sorted(forbidden):
        with pytest.raises(SchemaError):
            ShellMask.from_dict({**payload, field: 1.0})

    points = _rectangle()
    split = split_points(points, mask)
    assert set(split["targets"]) | set(split["training"]) == set(points)
    assert not set(split["targets"]) & set(split["training"])
    assert all(mask.contains(*p) for p in split["targets"])
    assert not any(mask.contains(*p) for p in split["training"])
    assert len(split["targets"]) == 3 * 7


def test_mask_round_trips_and_refuses_a_hand_edited_identity():
    mask = neutron_mask(82, z_min=50, z_max=60)
    assert ShellMask.from_dict(mask.to_dict()) == mask
    assert mask_hash(mask) == mask_hash(ShellMask.from_dict(mask.to_dict()))
    assert mask_hash(mask) != mask_hash(neutron_mask(82, z_min=50, z_max=61))
    payload = mask.to_dict()
    with pytest.raises(SchemaError):
        ShellMask.from_dict({**payload, "mask_id": "shell-N82-w1-Z1-2"})
    with pytest.raises(SchemaError):
        ShellMask.from_dict({**payload, "hidden_N": [82]})
    with pytest.raises(SchemaError):
        ShellMask.from_dict({k: v for k, v in payload.items() if k != "z_max"})
    with pytest.raises(SchemaError):
        ShellMask.from_dict({**payload, "axis": "isotonic"})


def test_mask_geometry_is_validated():
    with pytest.raises(SchemaError):
        neutron_mask(50, z_min=30, z_max=24)
    with pytest.raises(SchemaError):
        neutron_mask(50, z_min=24, z_max=30, half_width=0)
    with pytest.raises(SchemaError):
        neutron_mask(0, z_min=24, z_max=30)
    with pytest.raises(SchemaError):
        proton_mask(28, n_min=-1, n_max=30)
    with pytest.raises(SchemaError):
        neutron_mask(50.0, z_min=24, z_max=30)
    with pytest.raises(ProtocolError):
        assert_mask_populated(neutron_mask(126, z_min=80, z_max=90), _rectangle())


def test_peak_candidates_share_the_closure_parity():
    mask = neutron_mask(50, z_min=24, z_max=30)
    assert mask.peak_candidates(window=6) == (44, 46, 48, 50, 52, 54, 56)
    assert mask.peak_candidates(window=0) == (50,)
    # Near the axis origin the window is clipped instead of going negative.
    assert min(neutron_mask(4, z_min=2, z_max=4).peak_candidates(window=6)) == 0
    with pytest.raises(ValueError):
        mask.peak_candidates(window=-1)
    assert mask.indicator_inputs(chain=26, coordinate=50) == ((26, 48), (26, 50), (26, 52))


# --------------------------------------------------------------------------- #
# WO-10 section 2: the support rule                                            #
# --------------------------------------------------------------------------- #


def test_chain_support_needs_both_two_step_neighbors_and_a_long_enough_chain():
    mask = neutron_mask(50, z_min=24, z_max=30)
    full = _rectangle()
    support = chain_support(mask, full, chain=26)
    assert support.supported
    assert support.reasons == ()
    assert support.lower_support and support.upper_support
    assert support.n_masked_targets == 3
    assert support.n_window_training >= MIN_CHAIN_LENGTH

    # Drop N = 52 and the upper two-step neighbor is gone.
    without_upper = [p for p in full if p != (26, 52)]
    broken = chain_support(mask, without_upper, chain=26)
    assert not broken.supported
    assert any("upper neighbor 52" in reason for reason in broken.reasons)

    without_lower = [p for p in full if p != (26, 48)]
    broken = chain_support(mask, without_lower, chain=26)
    assert not broken.supported
    assert any("lower neighbor 48" in reason for reason in broken.reasons)

    # A chain that holds only the closure column has no window support at all.
    sparse = [(26, n) for n in (48, 49, 50, 51, 52)]
    thin = chain_support(mask, sparse, chain=26)
    assert not thin.supported
    assert any("MIN_CHAIN_LENGTH" in reason for reason in thin.reasons)

    # A chain with no masked nucleus cannot be a target chain.
    empty = chain_support(mask, [(26, n) for n in range(40, 49)], chain=26)
    assert not empty.supported
    assert "chain holds no eligible masked target" in empty.reasons


def test_unsupported_shell_marked_not_evaluable():
    """A closure the snapshot cannot support is reported, never dropped."""
    points = _rectangle()
    # N = 126 is nowhere near this lattice.
    absent = evaluate_challenge(AXIS_NEUTRON, 126, points)
    assert absent.status == STATUS_NOT_EVALUABLE
    assert absent.mask is None
    assert absent.challenge_id == "neutron-N126"
    assert absent.supported_chains == ()
    assert any("MIN_EVALUABLE_CHAINS" in reason for reason in absent.reasons)
    payload = absent.to_dict()
    assert payload["status"] == STATUS_NOT_EVALUABLE
    assert payload["mask"] is None and payload["mask_id"] is None
    assert payload["indicator"] is None

    # Present, but with too few chains to compare: still NOT_EVALUABLE, and the
    # reason names the rule rather than saying "skipped".
    narrow = [(z, n) for z in (24, 25) for n in range(40, 61)]
    thin = evaluate_challenge(AXIS_NEUTRON, 50, narrow)
    assert thin.status == STATUS_NOT_EVALUABLE
    assert len(thin.supported_chains) < MIN_EVALUABLE_CHAINS
    assert any(str(MIN_EVALUABLE_CHAINS) in reason for reason in thin.reasons)

    # Enough chains, but the mask is too small to be worth scoring.
    supported = evaluate_challenge(AXIS_NEUTRON, 50, points, min_targets=10_000)
    assert supported.status == STATUS_NOT_EVALUABLE
    assert supported.mask is not None
    assert any("MIN_TARGETS" in reason for reason in supported.reasons)

    # And the healthy case, for contrast.
    healthy = evaluate_challenge(AXIS_NEUTRON, 50, points)
    assert healthy.status == STATUS_EVALUABLE
    assert healthy.evaluable
    assert healthy.n_targets >= MIN_TARGETS
    assert len(healthy.supported_chains) >= MIN_EVALUABLE_CHAINS


def test_the_mask_span_covers_every_chain_that_holds_the_neighborhood():
    """An unsupported chain is hidden anyway, including at the edge of the span.

    The closure feature lives on the closure coordinate and is the same along
    every chain, so one chain left holding its own closure neighborhood would
    reveal the answer for all the others. Support decides what is *scored*; the
    neighborhood is hidden wherever an eligible nucleus sits in it.
    """
    # Chain 28 loses its upper two-step neighbor, so it cannot be scored, and
    # chain 34 -- the top of the lattice -- loses the closure input itself.
    points = [p for p in _rectangle() if p not in {(28, 52), (34, 50)}]
    challenge = evaluate_challenge(AXIS_NEUTRON, 50, points)
    assert challenge.status == STATUS_EVALUABLE
    mask = challenge.mask
    for chain in (28, 34):
        assert chain in challenge.unsupported_chains
        assert mask.span_min <= chain <= mask.span_max
        assert mask.contains(chain, 50)
    # The span is the hull of the chains holding the neighborhood, which reaches
    # past the last *supported* chain.
    assert (mask.span_min, mask.span_max) == (24, 34)
    assert challenge.supported_chains[-1] < mask.span_max
    # Every chain in the span is accounted for, supported or not.
    assert sorted(challenge.supported_chains + challenge.unsupported_chains) == list(
        range(mask.span_min, mask.span_max + 1)
    )


def test_a_chain_whose_closure_indicator_is_incomputable_is_not_supported():
    """The closure indicator is the question; a chain that cannot compute it fails.

    An estimated (non-eligible) nucleus at the closure itself leaves the chain
    with plenty of computable window positions and no answer at the closure. Such
    a chain used to pass the support rule and then turn up NOT_EVALUABLE at
    scoring time, which is the support rule failing to do its job.
    """
    mask = neutron_mask(50, z_min=24, z_max=30)
    without_closure = [p for p in _rectangle() if p != (26, 50)]
    support = chain_support(mask, without_closure, chain=26)
    assert not support.supported
    assert not support.closure_computable
    assert support.lower_support and support.upper_support
    assert support.n_peak_candidates >= 3
    assert any("indicator at the closure is not computable" in r for r in support.reasons)
    assert any("(26, 50)" in r for r in support.reasons)
    # The healthy chain, for contrast.
    healthy = chain_support(mask, _rectangle(), chain=26)
    assert healthy.supported and healthy.closure_computable


def test_support_settings_are_frozen_and_self_describing():
    settings = support_settings()
    assert settings["support_policy_id"] == SUPPORT_POLICY_ID
    assert settings["mask_policy_id"] == MASK_POLICY_ID
    assert settings["MIN_CHAIN_LENGTH"] == MIN_CHAIN_LENGTH
    assert settings["MIN_TARGETS"] == MIN_TARGETS
    assert settings["MIN_EVALUABLE_CHAINS"] == MIN_EVALUABLE_CHAINS
    assert settings["half_width"] == 1
    assert "NOT_EVALUABLE" in settings["closure_rule"]
    assert "never omitted" in settings["closure_rule"]
    assert "Same parity only" in settings["peak_parity_rule"]


# --------------------------------------------------------------------------- #
# The challenge manifest                                                       #
# --------------------------------------------------------------------------- #


def test_generate_challenges_reports_every_declared_closure(tmp_path):
    source = write_small_synthetic_shell_chart(tmp_path / "chart.mas20")
    points = eligible_points(source, EDITION)
    generated = generate_challenges(points)
    ids = [c.challenge_id for c in generated["challenges"]]
    expected = [f"neutron-N{c}" for c in KNOWN_NEUTRON_CLOSURES] + [
        f"proton-Z{c}" for c in KNOWN_PROTON_CLOSURES
    ]
    assert sorted(ids) == sorted(expected)
    assert len(generated["evaluable"]) + len(generated["not_evaluable"]) == len(expected)
    # The injected neutron closure is the one this small chart can support.
    assert [c.challenge_id for c in generated["evaluable"]] == [
        f"neutron-N{INJECTED_NEUTRON_CLOSURE}"
    ]
    assert generated["settings"]["availability_set"] == {
        AXIS_NEUTRON: list(KNOWN_NEUTRON_CLOSURES),
        AXIS_PROTON: list(KNOWN_PROTON_CLOSURES),
    }
    assert generated["n_eligible_points"] == len(points)


def test_challenge_manifest_hash_ignores_order_and_tracks_geometry(tmp_path):
    source = write_small_synthetic_shell_chart(tmp_path / "chart.mas20")
    generated = generate_challenges(eligible_points(source, EDITION))
    manifest = challenge_manifest(
        generated["challenges"],
        benchmark_id=BENCHMARK_EZ_B003,
        protocol_version=B003_PROTOCOL_VERSION,
        settings=generated["settings"],
    )
    assert manifest["challenge_policy_id"] == CHALLENGE_POLICY_ID
    assert manifest["n_challenges"] == len(manifest["challenges"])
    assert manifest["n_evaluable"] + manifest["n_not_evaluable"] == manifest["n_challenges"]
    assert manifest["challenge_manifest_hash"] == challenge_manifest_hash(manifest)

    # Reordering the file cannot change the digest...
    shuffled = {**manifest, "challenges": list(reversed(manifest["challenges"]))}
    assert challenge_manifest_hash(shuffled) == manifest["challenge_manifest_hash"]
    # ...but widening a mask bound always does.
    evaluable = next(c for c in manifest["challenges"] if c["status"] == STATUS_EVALUABLE)
    widened = json.loads(json.dumps(manifest))
    target = next(
        c for c in widened["challenges"] if c["challenge_id"] == evaluable["challenge_id"]
    )
    target["mask"]["z_max"] += 1
    target["mask"].pop("mask_id")
    assert challenge_manifest_hash(widened) != manifest["challenge_manifest_hash"]
    # So does flipping a verdict.
    flipped = json.loads(json.dumps(manifest))
    victim = next(
        c for c in flipped["challenges"] if c["status"] == STATUS_NOT_EVALUABLE
    )
    victim["status"] = STATUS_EVALUABLE
    with pytest.raises(SchemaError):
        challenge_manifest_hash(flipped)


def test_load_challenge_manifest_verifies_its_own_claims(tmp_path):
    source = write_small_synthetic_shell_chart(tmp_path / "chart.mas20")
    generated = generate_challenges(eligible_points(source, EDITION))
    manifest = challenge_manifest(
        generated["challenges"],
        benchmark_id=BENCHMARK_EZ_B003,
        protocol_version=B003_PROTOCOL_VERSION,
        settings=generated["settings"],
    )
    loaded = load_challenge_manifest(manifest)
    assert loaded["benchmark_id"] == BENCHMARK_EZ_B003
    assert loaded["challenge_manifest_hash"] == manifest["challenge_manifest_hash"]
    assert sorted(loaded["masks"]) == sorted(manifest["evaluable_challenge_ids"])
    mask = loaded["masks"][loaded["evaluable_challenge_ids"][0]]
    assert mask_by_id(loaded, mask.mask_id) is mask
    with pytest.raises(ProtocolError):
        mask_by_id(loaded, "shell-N1-w1-Z1-2")
    with pytest.raises(ProtocolError):
        load_challenge_manifest({**manifest, "challenge_manifest_hash": "0" * 64})
    with pytest.raises(ProtocolError):
        load_challenge_manifest({**manifest, "challenge_ids": ["neutron-N50"]})
    with pytest.raises(ProtocolError):
        load_challenge_manifest({**manifest, "evaluable_challenge_ids": []})
    with pytest.raises(ProtocolError):
        challenge_manifest_hash([])


def test_a_challenge_manifest_carries_no_truth(tmp_path):
    source = write_small_synthetic_shell_chart(tmp_path / "chart.mas20")
    generated = generate_challenges(eligible_points(source, EDITION))
    manifest = challenge_manifest(
        generated["challenges"],
        benchmark_id=BENCHMARK_EZ_B003,
        protocol_version=B003_PROTOCOL_VERSION,
        settings=generated["settings"],
    )

    def walk(node):
        if isinstance(node, dict):
            assert not TRUTH_BEARING_FIELDS.intersection(node), sorted(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(manifest)
    assert INJECTED_PROTON_CLOSURE in KNOWN_PROTON_CLOSURES

    # The committed schema declares the same contract: every required field is
    # present, and the truth-bearing fields it forbids are the ones the walk above
    # asserts are absent.
    schema = json.loads((SCHEMAS / "shell_challenge.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["benchmark_id"]["const"] == BENCHMARK_EZ_B003
    for field in schema["required"]:
        assert field in manifest, field
    forbidden = {entry["required"][0] for entry in schema["not"]["anyOf"]}
    assert forbidden <= TRUTH_BEARING_FIELDS
    challenge_schema = schema["properties"]["challenges"]["items"]
    for entry in manifest["challenges"]:
        for field in challenge_schema["required"]:
            assert field in entry, field
        assert entry["status"] in challenge_schema["properties"]["status"]["enum"]
        assert entry["axis"] in challenge_schema["properties"]["axis"]["enum"]
        assert entry["indicator"] in challenge_schema["properties"]["indicator"]["enum"]
        if entry["status"] == STATUS_EVALUABLE:
            # The conditional branch of the schema: an evaluable closure must
            # carry a mask identity and a discriminating observable.
            for field in challenge_schema["allOf"][0]["then"]["required"]:
                assert entry[field] is not None, field
        for support in entry["chain_support"]:
            for field in challenge_schema["properties"]["chain_support"]["items"]["required"]:
                assert field in support, field
