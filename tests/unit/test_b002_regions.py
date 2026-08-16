"""Region geometry, deterministic generation, and manifest hashing (WO-09)."""

from __future__ import annotations

import json
import random

import pytest

from elementzero import B002_PROTOCOL_VERSION, BENCHMARK_EZ_B002
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.regions import (
    DEFAULT_MIN_SUPPORTED_SIDES,
    DEFAULT_MIN_TARGETS,
    DEFAULT_N_SPAN,
    DEFAULT_Z_SPAN,
    REGION_TYPES,
    Region,
    assert_region_populated,
    candidate_windows,
    generate_regions,
    isotonic_region,
    isotopic_region,
    load_region_manifest,
    nearest_training_l1,
    normalize_points,
    rectangle_region,
    region_candidates,
    region_depth_profile,
    region_manifest,
    region_manifest_hash,
    select_regions,
    split_points,
    supported_sides,
)
from elementzero.errors import ProtocolError, SchemaError

SCHEMAS = REPO_ROOT / "schemas"


def lattice(z_range: range, n_range: range) -> list[tuple[int, int]]:
    return [(z, n) for z in z_range for n in n_range]


# --------------------------------------------------------------------------- #
# Membership                                                                  #
# --------------------------------------------------------------------------- #


def test_rectangle_membership():
    region = rectangle_region(20, 23, 25, 29)
    # Inclusive on every bound: the corners belong to the region.
    for corner in ((20, 25), (20, 29), (23, 25), (23, 29)):
        assert region.contains(*corner), corner
    assert region.contains(21, 27)
    # One lattice step outside any face is not a member.
    for outside in ((19, 27), (24, 27), (21, 24), (21, 30)):
        assert not region.contains(*outside), outside
    assert region.contains_id("Z21-N27")
    assert not region.contains_id("Z21-N30")
    assert region.region_id == "rect-Z20-23-N25-29"
    assert region.lattice_sites == 4 * 5
    assert region.z_band == "medium"

    points = lattice(range(18, 26), range(23, 32))
    inside = region.members(points)
    assert len(inside) == 20
    assert set(inside) | set(region.outside(points)) == set(normalize_points(points))
    assert not set(inside) & set(region.outside(points))


def test_isotopic_and_isotonic_membership():
    isotopic = isotopic_region(30, 34, 40)
    assert isotopic.contains(30, 34) and isotopic.contains(30, 40)
    assert not isotopic.contains(31, 36)
    assert isotopic.region_id == "isotopic-Z30-N34-40"

    isotonic = isotonic_region(50, 36, 42)
    assert isotonic.contains(36, 50) and isotonic.contains(42, 50)
    assert not isotonic.contains(38, 51)
    assert isotonic.region_id == "isotonic-N50-Z36-42"

    assert set(REGION_TYPES) == {"rectangle", "isotopic", "isotonic"}


def test_region_round_trips_through_its_declared_type_only():
    for region in (
        rectangle_region(8, 11, 9, 13),
        isotopic_region(8, 9, 13),
        isotonic_region(9, 8, 11),
    ):
        payload = region.to_dict()
        assert payload["region_id"] == region.region_id
        assert Region.from_dict(payload) == region
        assert Region.from_dict(json.loads(json.dumps(payload))) == region

    # A rectangle payload may not carry isotopic keys, and vice versa.
    with pytest.raises(SchemaError):
        Region.from_dict({"type": "rectangle", "Z": 8, "n_min": 9, "n_max": 13})
    with pytest.raises(SchemaError):
        Region.from_dict({"type": "isotopic", "Z": 8, "n_min": 9})
    # A region_id that disagrees with the bounds is a forged identity.
    with pytest.raises(SchemaError):
        Region.from_dict(
            {
                "type": "rectangle",
                "z_min": 8,
                "z_max": 11,
                "n_min": 9,
                "n_max": 13,
                "region_id": "rect-Z8-11-N9-99",
            }
        )


def test_empty_or_unsupported_region_rejected():
    points = lattice(range(10, 20), range(10, 20))

    # A region with no eligible nucleus is a protocol error, not a zero-target run.
    empty = rectangle_region(200, 204, 300, 304)
    assert empty.members(points) == []
    with pytest.raises(ProtocolError):
        assert_region_populated(empty, points)
    # A populated region below the declared minimum is also refused.
    with pytest.raises(ProtocolError):
        assert_region_populated(rectangle_region(10, 10, 10, 10), points, min_targets=2)
    assert assert_region_populated(rectangle_region(10, 11, 10, 11), points) == 4

    for payload in (
        {"type": "triangle", "z_min": 1, "z_max": 2, "n_min": 1, "n_max": 2},
        {"type": "blob"},
        {"type": None},
    ):
        with pytest.raises(SchemaError):
            Region.from_dict(payload)
    with pytest.raises(SchemaError):
        Region.from_dict("rect-Z1-2-N1-2")

    # Inverted, negative, and non-integer bounds are all rejected at construction.
    with pytest.raises(SchemaError):
        rectangle_region(12, 10, 10, 12)
    with pytest.raises(SchemaError):
        rectangle_region(10, 12, 12, 10)
    with pytest.raises(SchemaError):
        rectangle_region(-1, 3, 0, 3)
    with pytest.raises(SchemaError):
        rectangle_region(1.5, 3, 0, 3)
    with pytest.raises(SchemaError):
        rectangle_region(True, 3, 0, 3)
    # An "isotopic" segment spanning several Z is not an isotopic segment.
    with pytest.raises(SchemaError):
        Region(region_type="isotopic", z_min=8, z_max=9, n_min=9, n_max=13)
    with pytest.raises(SchemaError):
        Region(region_type="isotonic", z_min=8, z_max=9, n_min=9, n_max=13)

    # An empty manifest has nothing to hash.
    with pytest.raises(ProtocolError):
        region_manifest_hash([])


# --------------------------------------------------------------------------- #
# Distance to training                                                        #
# --------------------------------------------------------------------------- #


def test_distance_to_training():
    # A dense 9x9 block with a 3x3 hole punched in the middle.
    points = lattice(range(20, 29), range(20, 29))
    region = rectangle_region(23, 25, 23, 25)
    split = split_points(points, region)
    training = split["training"]
    assert len(split["targets"]) == 9
    assert len(training) == 81 - 9

    # Hand-computed L1 depths: rim = 1, edge-centres = 2, centre = 2.
    assert nearest_training_l1(z=23, n=23, training=training) == 1
    assert nearest_training_l1(z=24, n=23, training=training) == 1
    assert nearest_training_l1(z=24, n=24, training=training) == 2

    profile = region_depth_profile(region, points)
    assert [row["nuclide_id"] for row in profile[:1]] == ["Z23-N23"]
    depths = {row["nuclide_id"]: row["nearest_training_L1"] for row in profile}
    assert depths["Z24-N24"] == 2
    assert depths["Z23-N24"] == 1
    # Deeper points are strictly deeper: the centre beats every rim nucleus.
    assert depths["Z24-N24"] > max(v for k, v in depths.items() if k != "Z24-N24")
    for row in profile:
        assert row["A"] == row["Z"] + row["N"]
        # The profile is a depth coordinate, never a truth channel.
        assert set(row) == {"nuclide_id", "Z", "N", "A", "nearest_training_L1"}
    # Sorted by depth, so a report cannot silently reorder by error.
    assert [row["nearest_training_L1"] for row in profile] == sorted(
        row["nearest_training_L1"] for row in profile
    )

    # A wider hole puts its centre further from any training nucleus.
    wide = rectangle_region(22, 26, 22, 26)
    wide_training = split_points(points, wide)["training"]
    assert nearest_training_l1(z=24, n=24, training=wide_training) == 3

    with pytest.raises(ValueError):
        nearest_training_l1(z=1, n=1, training=[])


def test_supported_sides_counts_only_adjacent_training():
    points = lattice(range(20, 29), range(20, 29))
    interior = rectangle_region(23, 25, 23, 25)
    assert supported_sides(interior, points) == ("n_high", "n_low", "z_high", "z_low")

    # A window hanging off the high-Z corner keeps only its low faces.
    corner = rectangle_region(27, 30, 27, 30)
    assert supported_sides(corner, points) == ("n_low", "z_low")

    # Z=0 has no lower neighbour, so z_low cannot be claimed.
    origin_points = lattice(range(0, 5), range(0, 5))
    assert "z_low" not in supported_sides(rectangle_region(0, 1, 1, 2), origin_points)


# --------------------------------------------------------------------------- #
# Deterministic candidate generation                                          #
# --------------------------------------------------------------------------- #


def test_candidate_generation_is_deterministic_and_order_free():
    points = lattice(range(6, 40), range(6, 46))
    shuffled = list(points)
    random.Random(1234).shuffle(shuffled)

    first = region_candidates(points)
    second = region_candidates(shuffled)
    assert [c.region.region_id for c in first] == [c.region.region_id for c in second]
    assert [c.n_targets for c in first] == [c.n_targets for c in second]
    # The declared order is exactly what the generator emits.
    assert first == sorted(first, key=lambda c: c.order_key)

    windows = candidate_windows(points)
    assert len({w.region_id for w in windows}) == len(windows)
    for window in windows:
        assert window.z_max - window.z_min + 1 == DEFAULT_Z_SPAN
        assert window.n_max - window.n_min + 1 == DEFAULT_N_SPAN

    for candidate in first:
        assert candidate.n_targets >= DEFAULT_MIN_TARGETS
        assert len(candidate.supported_sides) >= DEFAULT_MIN_SUPPORTED_SIDES
        payload = candidate.to_dict()
        assert payload["region_id"] == candidate.region.region_id
        assert payload["z_band"] == candidate.z_band


def test_selection_spans_the_declared_z_bands():
    points = lattice(range(6, 60), range(6, 90))
    generated = generate_regions(points)
    selected = generated["selected"]
    assert [r.z_band for r in selected] == ["light", "medium", "heavy"]
    assert len({r.region_id for r in selected}) == 3
    settings = generated["settings"]
    assert settings["z_span"] == DEFAULT_Z_SPAN
    assert settings["min_targets"] == DEFAULT_MIN_TARGETS
    assert "never a metric or an error" in settings["candidate_order"]
    # Selection is the deterministic top of each band, not a hand-picked subset.
    for region in selected:
        band = [c for c in generated["candidates"] if c["z_band"] == region.z_band]
        assert band[0]["region_id"] == region.region_id
    # Repeating the whole generation reproduces the same selection.
    assert [r.region_id for r in generate_regions(points)["selected"]] == [
        r.region_id for r in selected
    ]


def test_selection_refuses_to_report_a_partial_band_set():
    # Light Z only: the medium and heavy bands cannot supply a candidate.
    light_only = lattice(range(6, 18), range(6, 20))
    candidates = region_candidates(light_only)
    with pytest.raises(ProtocolError):
        select_regions(candidates)
    relaxed = select_regions(candidates, allow_missing_bands=True)
    assert [r.z_band for r in relaxed] == ["light"]
    with pytest.raises(ProtocolError):
        generate_regions(light_only)
    with pytest.raises(ValueError):
        select_regions(candidates, per_band=0)


# --------------------------------------------------------------------------- #
# Region manifest hash                                                        #
# --------------------------------------------------------------------------- #


def test_region_manifest_hash_stable():
    a = rectangle_region(14, 17, 15, 19)
    b = rectangle_region(33, 36, 42, 46)
    c = rectangle_region(50, 53, 70, 74)

    baseline = region_manifest_hash([a, b, c])
    # Re-hashing the same geometry is stable across calls and across orderings.
    assert region_manifest_hash([a, b, c]) == baseline
    assert region_manifest_hash([c, a, b]) == baseline
    assert region_manifest_hash([b.to_dict(), c.to_dict(), a.to_dict()]) == baseline

    # A single changed bound always changes the digest.
    assert region_manifest_hash([a, b, rectangle_region(50, 53, 70, 75)]) != baseline
    assert region_manifest_hash([a, b]) != baseline
    # So does a changed region type over the same lattice sites.
    assert region_manifest_hash([isotopic_region(14, 15, 19)]) != region_manifest_hash(
        [isotonic_region(15, 14, 14)]
    )

    manifest = region_manifest(
        [c, a, b],
        benchmark_id=BENCHMARK_EZ_B002,
        protocol_version=B002_PROTOCOL_VERSION,
        source={"edition_id": "AME2020"},
        generator={"z_span": DEFAULT_Z_SPAN},
        notes="test",
    )
    assert manifest["region_manifest_hash"] == baseline
    assert manifest["region_ids"] == [a.region_id, b.region_id, c.region_id]
    assert manifest["z_bands"] == ["light", "medium", "heavy"]
    assert manifest["n_regions"] == 3

    # Generator provenance and notes are outside the digest.
    without = region_manifest(
        [a, b, c],
        benchmark_id=BENCHMARK_EZ_B002,
        protocol_version=B002_PROTOCOL_VERSION,
    )
    assert without["region_manifest_hash"] == baseline

    parsed = load_region_manifest(manifest)
    assert [r.region_id for r in parsed["regions"]] == manifest["region_ids"]
    assert parsed["region_manifest_hash"] == baseline

    # A manifest whose recorded hash or id list was edited is refused.
    with pytest.raises(ProtocolError):
        load_region_manifest({**manifest, "region_manifest_hash": "0" * 64})
    with pytest.raises(ProtocolError):
        load_region_manifest({**manifest, "region_ids": ["rect-Z1-2-N1-2"]})
    with pytest.raises(SchemaError):
        region_manifest_hash([a, a])


# --------------------------------------------------------------------------- #
# Schemas and the committed preregistration                                   #
# --------------------------------------------------------------------------- #


def test_b002_schemas_are_readable_json():
    for name in ("geographic_region.schema.json", "geographic_split_manifest.schema.json"):
        payload = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
        assert payload["title"]
        assert "$schema" in payload
        assert payload["$id"].endswith(name)
    split = json.loads((SCHEMAS / "geographic_split_manifest.schema.json").read_text("utf-8"))
    # The schema forbids truth-bearing fields outright, not merely by omission.
    forbidden = {clause["required"][0] for clause in split["not"]["anyOf"]}
    assert {"mass_excess_keV", "uncertainty_keV"} <= forbidden
    assert split["properties"]["benchmark_id"]["const"] == BENCHMARK_EZ_B002


def test_committed_region_manifest_validates_and_matches_its_schema():
    path = REPO_ROOT / "experiments" / "EZ-B002-v1" / "regions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    parsed = load_region_manifest(payload)
    assert payload["benchmark_id"] == BENCHMARK_EZ_B002
    assert payload["protocol_version"] == B002_PROTOCOL_VERSION
    assert payload["region_manifest_hash"] == parsed["region_manifest_hash"]
    assert [r.z_band for r in parsed["regions"]] == ["light", "medium", "heavy"]

    schema = json.loads((SCHEMAS / "geographic_region.schema.json").read_text("utf-8"))
    allowed = {
        key
        for branch in schema["oneOf"]
        for key in branch["properties"]
    }
    for region in payload["regions"]:
        assert region["type"] in REGION_TYPES
        assert set(region) <= allowed

    # The committed selection must be the deterministic top of the committed
    # candidate list, which is what makes "regions were not hand-picked" checkable.
    candidates = json.loads(
        (REPO_ROOT / "experiments" / "EZ-B002-v1" / "region_candidates.json").read_text("utf-8")
    )
    assert candidates["selected_region_ids"] == payload["region_ids"]
    for region_id in payload["region_ids"]:
        band = next(c["z_band"] for c in candidates["candidates"] if c["region_id"] == region_id)
        first = next(c for c in candidates["candidates"] if c["z_band"] == band)
        assert first["region_id"] == region_id
