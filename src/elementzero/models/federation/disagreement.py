"""Model-disagreement metrics (WO-12 section 15).

For one target t with available model predictions m_j:

    ensemble_mean    = mean(m_j)
    disagreement_std = population standard deviation(m_j)
    disagreement_mad = median(abs(m_j - median(m_j)))

High agreement is not proof of correctness; high disagreement is evidence of
epistemic uncertainty. Disagreement is reported per target and grouped by
extrapolation depth, by independence group pair, and by benchmark.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from typing import Any

from elementzero.benchmark.distance import distance_bucket

DISAGREEMENT_RULE = (
    "ez-wo12-disagreement-v1: over available predictions only; a missing "
    "model shrinks the panel and is listed, it never contributes a zero"
)


def target_disagreement(predictions_keV: Mapping[str, float]) -> dict[str, Any]:
    """Disagreement for one target over {model_id: point_keV}."""
    values = [float(v) for _, v in sorted(predictions_keV.items())]
    if len(values) < 2:
        return {
            "n_models": len(values),
            "ensemble_mean_keV": values[0] if values else None,
            "disagreement_std_keV": None,
            "disagreement_mad_keV": None,
        }
    med = statistics.median(values)
    return {
        "n_models": len(values),
        "ensemble_mean_keV": statistics.fmean(values),
        "disagreement_std_keV": statistics.pstdev(values),
        "disagreement_mad_keV": statistics.median(abs(v - med) for v in values),
    }


def disagreement_rows(
    *,
    per_model_points: Mapping[str, Mapping[str, float]],
    target_meta: Mapping[str, Mapping[str, Any]],
    model_groups: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Per-target disagreement rows.

    ``per_model_points``: {model_id: {nuclide_id: point_keV}} — only available
    predictions appear. ``target_meta``: {nuclide_id: {"nearest_training_L1",
    ...}}. ``model_groups``: {model_id: independence_group}.
    """
    rows = []
    for nuclide_id, meta in sorted(target_meta.items()):
        points = {
            model_id: table[nuclide_id]
            for model_id, table in per_model_points.items()
            if nuclide_id in table
        }
        missing = sorted(set(per_model_points) - set(points))
        summary = target_disagreement(points)
        group_points: dict[str, list[float]] = {}
        for model_id, value in points.items():
            group_points.setdefault(model_groups[model_id], []).append(value)
        group_means = {
            group: statistics.fmean(values) for group, values in sorted(group_points.items())
        }
        across_groups = target_disagreement(group_means)
        rows.append(
            {
                "nuclide_id": nuclide_id,
                "nearest_training_L1": meta.get("nearest_training_L1"),
                **summary,
                "missing_models": missing,
                "n_independence_groups": len(group_means),
                "group_disagreement_std_keV": across_groups["disagreement_std_keV"],
                "rule": DISAGREEMENT_RULE,
            }
        )
    return rows


def disagreement_by_depth(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[float]] = {}
    for row in rows:
        distance = row.get("nearest_training_L1")
        std = row.get("disagreement_std_keV")
        if distance is None or std is None:
            continue
        buckets.setdefault(distance_bucket(int(distance)), []).append(float(std))
    return {
        bucket: {
            "n": len(values),
            "mean_disagreement_std_keV": statistics.fmean(values),
            "max_disagreement_std_keV": max(values),
        }
        for bucket, values in sorted(buckets.items())
    }
