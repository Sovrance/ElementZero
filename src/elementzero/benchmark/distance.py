"""Extrapolation distance from a scored target to the training corpus.

Lattice distances between a target (Z_t, N_t) and a training nucleus (Z_r, N_r):

    d_L1 = abs(Z_t - Z_r) + abs(N_t - N_r)
    d_L2 = sqrt((Z_t - Z_r)^2 + (N_t - N_r)^2)

    nearest_training_L1 = min over training nuclei of d_L1

Preregistered distance buckets:

    d = 1
    d = 2
    d = 3-4
    d >= 5

Preregistered Z bands:

    light      : Z < 20
    medium     : 20 <= Z < 50
    heavy      : 50 <= Z < 82
    very_heavy : Z >= 82

Isospin asymmetry:

    I = (N - Z) / A

An empty bucket or region is reported with n = 0; it is never dropped.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

from elementzero.benchmark.metrics import group_metrics
from elementzero.data.identity import parse_nuclide_id

DISTANCE_BUCKET_IDS = ("d=1", "d=2", "d=3-4", "d>=5")
DISTANCE_POLICY_ID = "ez-b001-l1-distance-buckets-v1"

REGION_IDS = ("light", "medium", "heavy", "very_heavy")
REGION_POLICY_ID = "ez-b001-z-bands-v1"
REGION_BOUNDS = {
    "light": (0, 20),
    "medium": (20, 50),
    "heavy": (50, 82),
    "very_heavy": (82, None),
}


def l1_distance(z_a: int, n_a: int, z_b: int, n_b: int) -> int:
    return abs(int(z_a) - int(z_b)) + abs(int(n_a) - int(n_b))


def l2_distance(z_a: int, n_a: int, z_b: int, n_b: int) -> float:
    return math.sqrt((int(z_a) - int(z_b)) ** 2 + (int(n_a) - int(n_b)) ** 2)


def training_lattice(nuclide_ids: Iterable[str]) -> tuple[tuple[int, int], ...]:
    """Training (Z, N) lattice points, sorted for deterministic tie-breaking."""
    return tuple(sorted(parse_nuclide_id(nid) for nid in nuclide_ids))


def nearest_training(
    *,
    z: int,
    n: int,
    lattice: Sequence[tuple[int, int]],
) -> dict[str, Any]:
    """Nearest training nucleus by L1, with L2 reported for the same winner."""
    if not lattice:
        raise ValueError("training lattice is empty")
    best_point = min(lattice, key=lambda point: (l1_distance(z, n, point[0], point[1]), point))
    z_r, n_r = best_point
    return {
        "nearest_training_L1": l1_distance(z, n, z_r, n_r),
        "nearest_training_L2": l2_distance(z, n, z_r, n_r),
        "nearest_training_nuclide_id": f"Z{z_r}-N{n_r}",
    }


def distance_bucket(d_l1: int) -> str:
    d = int(d_l1)
    if d < 1:
        raise ValueError(
            f"L1 distance {d} means the target sits on a training nucleus; "
            "that is a leakage condition, not a bucket"
        )
    if d == 1:
        return "d=1"
    if d == 2:
        return "d=2"
    if d <= 4:
        return "d=3-4"
    return "d>=5"


def region_for_z(z: int) -> str:
    z = int(z)
    if z < 20:
        return "light"
    if z < 50:
        return "medium"
    if z < 82:
        return "heavy"
    return "very_heavy"


def isospin_asymmetry(z: int, n: int) -> float:
    a = int(z) + int(n)
    if a <= 0:
        raise ValueError("A must be positive")
    return (int(n) - int(z)) / a


def bucket_summaries(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Metrics per distance bucket; every declared bucket is present."""
    out: dict[str, Any] = {}
    for bucket in DISTANCE_BUCKET_IDS:
        out[bucket] = group_metrics([r for r in rows if r.get("distance_bucket") == bucket])
    return out


def region_summaries(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Metrics per preregistered Z band; every declared band is present."""
    out: dict[str, Any] = {}
    for region in REGION_IDS:
        selected = [r for r in rows if r.get("region") == region]
        summary = group_metrics(selected)
        summary["Z_range"] = list(REGION_BOUNDS[region])
        if selected:
            summary["mean_isospin_asymmetry"] = sum(
                float(r["isospin_asymmetry"]) for r in selected
            ) / len(selected)
        else:
            summary["mean_isospin_asymmetry"] = None
        out[region] = summary
    return out


def error_vs_distance(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-target absolute error against nearest-training L1 distance."""
    return [
        {
            "nuclide_id": r["nuclide_id"],
            "nearest_training_L1": r["nearest_training_L1"],
            "abs_error_keV": abs(float(r["prediction_keV"]) - float(r["truth_keV"])),
        }
        for r in sorted(rows, key=lambda row: (row["nearest_training_L1"], row["nuclide_id"]))
    ]
