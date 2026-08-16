import math

import pytest

from elementzero.benchmark.distance import (
    DISTANCE_BUCKET_IDS,
    REGION_IDS,
    bucket_summaries,
    distance_bucket,
    error_vs_distance,
    isospin_asymmetry,
    l1_distance,
    l2_distance,
    nearest_training,
    region_for_z,
    region_summaries,
    training_lattice,
)


def _row(nid, z, n, mu, truth, sigma, d_l1):
    return {
        "nuclide_id": nid,
        "Z": z,
        "N": n,
        "prediction_keV": mu,
        "truth_keV": truth,
        "std_keV": sigma,
        "interval_p90": [mu - 1.6448536269514722 * sigma, mu + 1.6448536269514722 * sigma],
        "interval_p95": [mu - 1.959963984540054 * sigma, mu + 1.959963984540054 * sigma],
        "nearest_training_L1": d_l1,
        "distance_bucket": distance_bucket(d_l1),
        "region": region_for_z(z),
        "isospin_asymmetry": isospin_asymmetry(z, n),
    }


def test_nearest_training_l1():
    lattice = training_lattice(["Z8-N8", "Z10-N10", "Z16-N16"])
    assert lattice == ((8, 8), (10, 10), (16, 16))
    assert l1_distance(18, 19, 16, 16) == 5
    assert l2_distance(18, 19, 16, 16) == pytest.approx(math.sqrt(4 + 9))
    near = nearest_training(z=18, n=19, lattice=lattice)
    assert near["nearest_training_L1"] == 5
    assert near["nearest_training_nuclide_id"] == "Z16-N16"
    assert near["nearest_training_L2"] == pytest.approx(math.sqrt(13))
    # A target one neutron away from a training nucleus has d_L1 = 1.
    assert nearest_training(z=10, n=11, lattice=lattice)["nearest_training_L1"] == 1
    with pytest.raises(ValueError):
        nearest_training(z=1, n=1, lattice=())


def test_distance_bucket_boundaries():
    assert distance_bucket(1) == "d=1"
    assert distance_bucket(2) == "d=2"
    assert distance_bucket(3) == "d=3-4"
    assert distance_bucket(4) == "d=3-4"
    assert distance_bucket(5) == "d>=5"
    assert distance_bucket(97) == "d>=5"
    # d = 0 means the target is a training nucleus, which is leakage.
    with pytest.raises(ValueError):
        distance_bucket(0)


def test_region_boundaries():
    assert region_for_z(1) == "light"
    assert region_for_z(19) == "light"
    assert region_for_z(20) == "medium"
    assert region_for_z(49) == "medium"
    assert region_for_z(50) == "heavy"
    assert region_for_z(81) == "heavy"
    assert region_for_z(82) == "very_heavy"
    assert region_for_z(120) == "very_heavy"


def test_isospin_asymmetry():
    assert isospin_asymmetry(8, 8) == pytest.approx(0.0)
    assert isospin_asymmetry(20, 28) == pytest.approx(8 / 48)
    with pytest.raises(ValueError):
        isospin_asymmetry(0, 0)


def test_bucket_and_region_summaries_keep_empty_groups_explicit():
    rows = [
        _row("Z10-N11", 10, 11, 0.0, 1.0, 10.0, 1),
        _row("Z18-N19", 18, 19, 0.0, -3.0, 10.0, 5),
        _row("Z30-N35", 30, 35, 0.0, 2.0, 10.0, 3),
    ]
    buckets = bucket_summaries(rows)
    assert list(buckets) == list(DISTANCE_BUCKET_IDS)
    assert buckets["d=1"]["n"] == 1
    assert buckets["d=2"]["n"] == 0
    assert buckets["d=2"]["MAE_keV"] is None
    assert buckets["d=3-4"]["n"] == 1
    assert buckets["d>=5"]["n"] == 1
    assert buckets["d=1"]["NLPD"] is not None

    regions = region_summaries(rows)
    assert list(regions) == list(REGION_IDS)
    assert regions["light"]["n"] == 2
    assert regions["medium"]["n"] == 1
    assert regions["heavy"]["n"] == 0
    assert regions["very_heavy"]["n"] == 0
    assert regions["heavy"]["mean_isospin_asymmetry"] is None
    assert regions["light"]["Z_range"] == [0, 20]
    assert regions["very_heavy"]["Z_range"] == [82, None]


def test_error_vs_distance_is_sorted_by_distance():
    rows = [
        _row("Z18-N19", 18, 19, 0.0, -3.0, 10.0, 5),
        _row("Z10-N11", 10, 11, 0.0, 1.0, 10.0, 1),
    ]
    series = error_vs_distance(rows)
    assert [item["nearest_training_L1"] for item in series] == [1, 5]
    assert series[0]["abs_error_keV"] == pytest.approx(1.0)
    assert series[1]["abs_error_keV"] == pytest.approx(3.0)
