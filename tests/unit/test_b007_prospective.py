"""WO-206 / EZ-B007 — prospective sealed forecast.

These run on synthetic tables, not the licensed AME snapshot, so CI can exercise
the whole seal-and-score path without a download. The committed seal under
`experiments/EZ-B007-v2/` is the real artifact; this is the machinery check.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from tests.helpers import toy_mass_excess, write_ame_table

from elementzero.data.amdc.common import AME_MAS20_COLUMNS, EditionSpec, parse_ame_mass_table
from elementzero.data.observations import TRUTH_BEARING_FIELDS
from elementzero.evidence.freezes import ALLOWED_TARGET_FIELDS
from elementzero.experiments import b007_prospective as b007
from elementzero.models.blindness import TIER_A

pytestmark = pytest.mark.v2_protocol

SPEC = EditionSpec("AME2020", "2021-03-01", AME_MAS20_COLUMNS, year=2020)


def _chart(tmp_path, n_measured=140, n_extrapolated=30):
    """A small chart whose outer band is flagged estimated, like a real edition."""
    rows = []
    made = 0
    for z in range(8, 40):
        for n in range(z - 2, z + 8):
            if made >= n_measured + n_extrapolated:
                break
            # the neutron-rich edge is where AME runs out of measurements
            estimated = n >= z + 6
            if estimated and sum(1 for r in rows if r[5]) >= n_extrapolated:
                continue
            if not estimated and sum(1 for r in rows if not r[5]) >= n_measured:
                continue
            rows.append((z, n, "Xx", toy_mass_excess(z, n), 5.0, estimated))
            made += 1
    path = write_ame_table(tmp_path / "chart.mas20", rows, SPEC)
    return parse_ame_mass_table(path, SPEC)


# ------------------------------------------------------------------ splitting


def test_split_separates_measured_from_extrapolated(tmp_path):
    obs = _chart(tmp_path)
    measured, extrapolated = b007.split_by_measurement_status(obs)
    assert measured and extrapolated
    assert all(b007.is_measured(o) for o in measured)
    assert all(not b007.is_measured(o) for o in extrapolated)
    assert len(measured) + len(extrapolated) == len(obs)


def test_holdouts_are_deterministic_and_are_measured_nuclides(tmp_path):
    obs = _chart(tmp_path)
    measured, _ = b007.split_by_measurement_status(obs)
    ids = {o.nuclide_id for o in measured}
    for fn in (b007.frontier_holdout_ids, b007.random_holdout_ids):
        first, second = fn(measured), fn(measured)
        assert first == second, f"{fn.__name__} is not deterministic"
        assert set(first) <= ids


def test_frontier_holdout_is_sparser_than_a_random_one(tmp_path):
    """The frontier split must actually select the edge, or it proves nothing."""
    obs = _chart(tmp_path)
    measured, _ = b007.split_by_measurement_status(obs)
    counts = b007._neighbour_counts([(o.Z, o.N) for o in measured])
    by_id = {o.nuclide_id: (o.Z, o.N) for o in measured}
    frontier = b007.frontier_holdout_ids(measured)
    random_ids = b007.random_holdout_ids(measured)
    mean_frontier = np.mean([counts[by_id[i]] for i in frontier])
    mean_random = np.mean([counts[by_id[i]] for i in random_ids])
    assert mean_frontier < mean_random


# ------------------------------------------------------------- leakage guards


def test_target_manifest_is_identity_only(tmp_path):
    """A target row may not carry a mass. The firewall is the whole point."""
    obs = _chart(tmp_path)
    measured, extrapolated = b007.split_by_measurement_status(obs)
    targets = b007.build_target_manifest(extrapolated, measured)
    assert targets
    for row in targets:
        assert not (set(row) & TRUTH_BEARING_FIELDS), row
        identity = set(row) & {"nuclide_id", "Z", "N", "A"}
        assert identity <= ALLOWED_TARGET_FIELDS
        assert set(row) - ALLOWED_TARGET_FIELDS <= {
            "l1_distance_to_measured",
            "distance_bucket",
        }


def test_training_on_an_extrapolated_value_is_refused(tmp_path):
    obs = _chart(tmp_path)
    measured, extrapolated = b007.split_by_measurement_status(obs)
    with pytest.raises(ValueError, match="ez-gt-policy-v1"):
        b007.fit_forecast_model(measured + extrapolated[:1])


def test_reference_extrapolations_are_never_labelled_measurements(tmp_path):
    obs = _chart(tmp_path)
    _, extrapolated = b007.split_by_measurement_status(obs)
    refs = b007.build_reference_extrapolations(extrapolated)
    assert refs
    assert all(r["is_measurement"] is False for r in refs)
    # the AMDC value must not masquerade under a truth-bearing key
    assert all(not (set(r) & TRUTH_BEARING_FIELDS) for r in refs)


# ---------------------------------------------------------------- blindness


def test_prospective_forecast_is_strictly_blind():
    tier, detail = b007.resolve_forecast_tier()
    assert tier == TIER_A
    assert detail["combined_tier"] == TIER_A
    assert all(t == TIER_A for t in detail["contributor_tiers"])


def test_blindness_is_insensitive_to_the_assumed_release_year():
    """Any real release year postdates the fit, so the tier must not hinge on it."""
    for year in (2024, 2025, 2030, 2040):
        tier, _ = b007.resolve_forecast_tier(next_edition_year=year)
        assert tier == TIER_A


# --------------------------------------------------------------- seal digest


def test_seal_digest_detects_tampering():
    seal = {"experiment_id": "EZ-B007-v2", "predictions": [{"nuclide_id": "Z8N8", "v": 1.0}]}
    seal["seal_sha256"] = b007.seal_digest(seal)
    assert b007.seal_digest(seal) == seal["seal_sha256"]

    tampered = json.loads(json.dumps(seal))
    tampered["predictions"][0]["v"] = 1.000001
    assert b007.seal_digest(tampered) != tampered["seal_sha256"]


def test_seal_digest_ignores_only_its_own_field():
    seal = {"a": 1, "predictions": []}
    digest = b007.seal_digest(seal)
    assert b007.seal_digest({**seal, "seal_sha256": "anything"}) == digest
