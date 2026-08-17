"""Choose B005 targets from chronology and identity alone.

The rule may consult when a nuclide's mass first appeared and where it
sits on the chart. It may not consult any model's error, any residual,
any score, or any measured mass — including the AME2020 values that are
the answers. This is checked by AST inspection in the tests, not by
reading the docstring.

Every prior blind set is excluded by identity: WO-14's B002 and B003
holdouts, B004's targets, and every identity that trained or calibrated
any family. A target that a model has already seen is not blind, and a
target that trained the discrepancy model is worse than not blind.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.b005 import (
    B005_ID,
    MIN_TARGETS_EVALUABLE,
    MIN_TARGETS_PREFERRED,
    MIN_Z_REGIONS,
)
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_hex

CHRONOLOGY_RELPATH = "reports/eligibility/wo13/historical_source_chronology.json"

TARGET_RULE_ID = "ez-wo15b-b005-target-rule-v1"

# Two blindness classes, because they are not the same claim and the
# difference has to survive into the report.
STRICT_CHRONOLOGICAL_BLIND = "STRICT_CHRONOLOGICAL_BLIND"
MEASUREMENT_ERA_BLIND = "MEASUREMENT_ERA_BLIND"

BLINDNESS_CLASSES = (STRICT_CHRONOLOGICAL_BLIND, MEASUREMENT_ERA_BLIND)

BLINDNESS_TAXONOMY = (
    f"{STRICT_CHRONOLOGICAL_BLIND}: the AME1995 snapshot carries no parsed "
    "record of the nuclide at all — B004's rule. "
    f"{MEASUREMENT_ERA_BLIND}: AME1995 carries a record but no "
    "ground-truth-eligible mass, only an extrapolation, so no measured "
    "value existed for any frozen fit to consume. The second is a weaker "
    "claim than the first and is never reported as the first"
)

STRICT_EXHAUSTION_FINDING = (
    "ez-wo15b-strict-blind-exhausted-v1: strict chronological blindness is a "
    "depletable resource. Fifteen even-even Z>=8 nuclides were "
    "ground-truth-eligible in AME2020 with no AME1995 record of any kind; "
    "EZ-B004-v1 took fourteen and a WO-14 experiment the last. Zero remain, "
    "so no further strictly-blind mass challenge can be built against the "
    "1995 freeze. This is a structural fact about the programme, not a "
    "shortfall of this work order"
)

TARGET_RULE = (
    f"{TARGET_RULE_ID}: a B005 target is an even-even nuclide with Z >= 8, "
    "ground-truth-eligible in AME2020, for which the AME1995 freeze holds no "
    "ground-truth-eligible mass — so no measured value existed for any "
    "frozen family to fit. It must not appear in any WO-14 blind set, in "
    "B004, or in any training or calibration identity set. Selection reads "
    "first-appearance chronology and identity only: no error, no residual, "
    "no score, and no measured mass. Targets are classified into "
    f"{STRICT_CHRONOLOGICAL_BLIND} and {MEASUREMENT_ERA_BLIND} strata and "
    "the resulting claim is labelled with the weakest stratum it rests on"
)

ODD_POLICY = (
    "EVEN_EVEN_ONLY: odd systems need blocking configurations the frozen "
    "backends do not search, so they are excluded by policy rather than "
    "attempted and silently mishandled"
)

Z_REGIONS = ((8, 40), (40, 70), (70, 100), (100, 140))


def _z_region(z: int) -> str:
    for low, high in Z_REGIONS:
        if low <= z < high:
            return f"Z{low}-{high}"
    return f"Z{Z_REGIONS[-1][1]}+"


def select_targets(
    *,
    repo_root: str | Path | None = None,
    excluded: dict[str, list[str]] | None = None,
    fit_identities: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """The preregistered B005 target manifest."""
    root = Path(repo_root or REPO_ROOT)
    chronology = json.loads(
        (root / CHRONOLOGY_RELPATH).read_text(encoding="utf-8")
    )
    known_1995 = set(chronology["sources"]["AME1995"]["known_nuclide_ids"])
    eligible_2020 = set(
        chronology["sources"]["AME2020"]["eligible_nuclide_ids"]
    )

    from elementzero.model_discrepancy.dataset import excluded_identities

    excluded = (
        excluded
        if excluded is not None
        else excluded_identities(repo_root=root)
    )
    fit_identities = fit_identities or {}
    forbidden = {i for ids in excluded.values() for i in ids}
    forbidden |= {i for ids in fit_identities.values() for i in ids}

    targets = []
    for nuclide_id in sorted(eligible_2020):
        if nuclide_id in known_1995 or nuclide_id in forbidden:
            continue
        z, n = parse_nuclide_id(nuclide_id)
        if z < 8 or z % 2 or n % 2:
            continue
        targets.append(
            {
                "nuclide_id": nuclide_id,
                "Z": z,
                "N": n,
                "z_region": _z_region(z),
                "frontier_direction": "neutron_rich" if n > z else "proton_rich",
            }
        )

    target_ids = [t["nuclide_id"] for t in targets]
    regions = sorted({t["z_region"] for t in targets})
    directions = sorted({t["frontier_direction"] for t in targets})
    evaluable = (
        len(targets) >= MIN_TARGETS_EVALUABLE and len(regions) >= MIN_Z_REGIONS
    )
    manifest = {
        "experiment_id": B005_ID,
        "target_rule_id": TARGET_RULE_ID,
        "target_rule": TARGET_RULE,
        "odd_policy": ODD_POLICY,
        "n_targets": len(targets),
        "targets": targets,
        "target_nuclide_ids": target_ids,
        "target_identity_digest": identity_digest(target_ids),
        "z_regions": regions,
        "frontier_directions": directions,
        "excluded_sets": {k: len(v) for k, v in sorted(excluded.items())},
        "fit_identity_sets": {
            k: len(v) for k, v in sorted(fit_identities.items())
        },
        "exclusion_digest": identity_digest(sorted(forbidden)),
        "n_excluded_identities": len(forbidden),
        "meets_preferred_size": len(targets) >= MIN_TARGETS_PREFERRED,
        "evaluable": evaluable,
        "status": "TARGETS_FROZEN" if evaluable else "B005_NOT_EVALUABLE",
    }
    manifest["target_rule_hash"] = sha256_hex(
        canonical_json(
            {"rule": TARGET_RULE, "odd_policy": ODD_POLICY, "regions": Z_REGIONS}
        )
    )
    return manifest


def assert_targets_disjoint(
    *, manifest: dict[str, Any], forbidden: dict[str, list[str]]
) -> None:
    """No B005 target may come from any prior blind or fitted set."""
    targets = set(manifest["target_nuclide_ids"])
    for name, ids in sorted(forbidden.items()):
        overlap = sorted(targets & set(ids))
        if overlap:
            raise ProtocolError(
                f"B005_TARGET_CONTAMINATED: {overlap} also appears in "
                f"{name}. {TARGET_RULE}"
            )


__all__ = [
    "ODD_POLICY",
    "TARGET_RULE",
    "TARGET_RULE_ID",
    "Z_REGIONS",
    "assert_targets_disjoint",
    "select_targets",
]
