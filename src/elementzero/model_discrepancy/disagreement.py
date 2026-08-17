"""Cross-family disagreement, kept outside every family's own sigma.

Two families disagreeing by 3 MeV is real information about model
uncertainty, and it is tempting to fold it into each family's error bar
— which would immediately make both families look calibrated. It would
also destroy the meaning of the number: a family's sigma is a claim
about that family, and a claim about the ensemble belongs to the
ensemble. WO-15 kept these separate and WO-15B keeps them separate.
"""

from __future__ import annotations

import math
from typing import Any

DISAGREEMENT_RULE = (
    "ez-wo15b-disagreement-v1: cross-family spread is reported as its own "
    "quantity and never added to any single family's sigma. A family's "
    "uncertainty describes that family; the spread describes the ensemble"
)


def family_disagreement(
    predictions_by_family: dict[str, dict[str, float]],
) -> dict[str, Any]:
    """Per-nuclide spread across families, and its summary."""
    nuclide_ids: set[str] = set()
    for rows in predictions_by_family.values():
        nuclide_ids |= set(rows)

    per_target = []
    for nuclide_id in sorted(nuclide_ids):
        values = [
            rows[nuclide_id]
            for rows in predictions_by_family.values()
            if rows.get(nuclide_id) is not None
        ]
        if len(values) < 2:
            continue
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        per_target.append(
            {
                "nuclide_id": nuclide_id,
                "n_families": len(values),
                "spread_keV": max(values) - min(values),
                "std_keV": math.sqrt(var),
            }
        )
    spreads = [row["spread_keV"] for row in per_target]
    return {
        "rule": DISAGREEMENT_RULE,
        "n_rows": len(per_target),
        "mean_spread_keV": sum(spreads) / len(spreads) if spreads else None,
        "max_spread_keV": max(spreads) if spreads else None,
        "per_target": per_target,
    }


def disagreement_lookup(record: dict[str, Any]) -> dict[str, float]:
    return {row["nuclide_id"]: row["spread_keV"] for row in record["per_target"]}


__all__ = ["DISAGREEMENT_RULE", "disagreement_lookup", "family_disagreement"]
