"""B004 target construction — chronology in, identities out.

Every input to this module is an identity, a date, or a frozen snapshot
membership. Nothing here may consult a prediction, a residual, a model
disagreement, a WO-14 performance table, or a truth value (spec section
9). The rule is hashed so a later reader can prove the target set was not
chosen to flatter a family.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import sha256_hex

CHRONOLOGY_RELPATH = "reports/eligibility/wo13/historical_source_chronology.json"
SUBFEDERATION_RELPATH = "reports/eligibility/wo13/subfederation_summary.json"

TARGET_RULE_ID = "ez-b004-target-rule-v1"
TARGET_RULE = (
    f"{TARGET_RULE_ID}: a B004 target is a nuclide that (a) is "
    "ground-truth-eligible in the AME2020 snapshot, (b) has no parsed "
    "record of any kind in the AME1995 snapshot that bounds the fit "
    "freeze, (c) has even proton and even neutron number, matching the "
    "preregistered EVEN_EVEN_ONLY policy of every candidate backend, and "
    "(d) is not a target of any WO-14 scored experiment. Selection reads "
    "evidence chronology, Z, N, and A only: no prediction, no residual, no "
    "model disagreement, no WO-14 performance, and no truth value takes "
    "part. Every qualifying nuclide is included — there is no cap, no "
    "sampling, and no discretionary drop"
)

ODD_POLICY = "EVEN_EVEN_ONLY"

MAGIC_NUMBERS = (2, 8, 20, 28, 50, 82, 126)
SHELL_ADJACENCY_WINDOW = 2

# Preregistered strata (spec section 19). Fixed before scoring.
Z_BANDS = (
    ("light", 1, 28),
    ("medium", 28, 58),
    ("heavy", 58, 84),
    ("very_heavy", 84, 120),
)

MIN_EVALUABLE_TARGETS = 8
SMALL_SAMPLE_NOTE = (
    "B004 is a small-n challenge by construction: strict blindness against a "
    "1995 freeze leaves few even-even nuclides. Point estimates carry wide "
    "uncertainty and are reported with per-target detail rather than as a "
    "headline average alone"
)


def _load(relpath: str, root: Path) -> dict[str, Any]:
    path = root / relpath
    if not path.is_file():
        raise ProtocolError(f"{path} is missing; B004 selection cannot proceed")
    return json.loads(path.read_text(encoding="utf-8"))


def wo14_scored_target_ids(*, repo_root: str | Path | None = None) -> set[str]:
    """Every identity any WO-14 experiment scored, blind or reconstruction."""
    root = Path(repo_root or REPO_ROOT)
    subfed = _load(SUBFEDERATION_RELPATH, root)
    ids: set[str] = set()
    for manifest in subfed["manifests"].values():
        ids.update(t["target_id"] for t in manifest["targets"])
    return ids


def shell_adjacent(z: int, n: int) -> bool:
    return any(
        abs(n - m) <= SHELL_ADJACENCY_WINDOW or abs(z - m) <= SHELL_ADJACENCY_WINDOW
        for m in MAGIC_NUMBERS
    )


def _z_band(z: int) -> str:
    for name, low, high in Z_BANDS:
        if low <= z < high:
            return name
    return "beyond_registry"


def _frontier_direction(
    z: int, n: int, known_by_z: dict[int, tuple[int, int]]
) -> str:
    """Neutron-rich or proton-rich relative to the frozen 1995 chart."""
    span = known_by_z.get(z)
    if span is None:
        return "unknown_isotopic_chain_in_freeze"
    low, high = span
    if n > high:
        return "neutron_rich_frontier"
    if n < low:
        return "proton_rich_frontier"
    return "interior_gap"


def nearest_freeze_distance(z: int, n: int, lattice: frozenset[tuple[int, int]]) -> int:
    """L1 distance to the nearest nuclide the freeze admitted."""
    if not lattice:
        raise ProtocolError("the freeze lattice is empty")
    return min(abs(z - lz) + abs(n - ln) for lz, ln in lattice)


def select_targets(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Apply TARGET_RULE deterministically and describe every stratum."""
    root = Path(repo_root or REPO_ROOT)
    chronology = _load(CHRONOLOGY_RELPATH, root)
    eligible_2020 = set(chronology["sources"]["AME2020"]["eligible_nuclide_ids"])
    known_1995 = set(chronology["sources"]["AME1995"]["known_nuclide_ids"])
    eligible_1995 = set(chronology["sources"]["AME1995"]["eligible_nuclide_ids"])
    excluded_wo14 = wo14_scored_target_ids(repo_root=root)

    lattice = frozenset(parse_nuclide_id(i) for i in eligible_1995)
    known_by_z: dict[int, tuple[int, int]] = {}
    for nuclide_id in known_1995:
        z, n = parse_nuclide_id(nuclide_id)
        low, high = known_by_z.get(z, (n, n))
        known_by_z[z] = (min(low, n), max(high, n))

    targets: list[dict[str, Any]] = []
    for nuclide_id in sorted(eligible_2020 - known_1995):
        z, n = parse_nuclide_id(nuclide_id)
        if z % 2 or n % 2:
            continue
        if nuclide_id in excluded_wo14:
            continue
        targets.append(
            {
                "nuclide_id": nuclide_id,
                "Z": z,
                "N": n,
                "A": z + n,
                "z_band": _z_band(z),
                "shell_adjacent": shell_adjacent(z, n),
                "frontier_direction": _frontier_direction(z, n, known_by_z),
                "nearest_freeze_distance_L1": nearest_freeze_distance(z, n, lattice),
                "odd_policy_class": ODD_POLICY,
            }
        )

    target_ids = [t["nuclide_id"] for t in targets]
    strata = {
        "z_band": _tally(targets, "z_band"),
        "frontier_direction": _tally(targets, "frontier_direction"),
        "shell_adjacent": _tally(targets, "shell_adjacent"),
        "nearest_freeze_distance_L1": _tally(targets, "nearest_freeze_distance_L1"),
    }
    payload = {
        "experiment_id": "EZ-B004-v1",
        "target_rule_id": TARGET_RULE_ID,
        "target_rule": TARGET_RULE,
        "odd_policy": ODD_POLICY,
        "n_targets": len(targets),
        "targets": targets,
        "target_nuclide_ids": target_ids,
        "target_identity_digest": identity_digest(target_ids),
        "strata": strata,
        "n_excluded_wo14_scored": len(excluded_wo14),
        "evaluable": len(targets) >= MIN_EVALUABLE_TARGETS,
        "min_evaluable_targets": MIN_EVALUABLE_TARGETS,
        "small_sample_note": SMALL_SAMPLE_NOTE,
        "identity_only_rule": (
            "this manifest carries identities and chronology-derived strata "
            "only; no mass value appears in it"
        ),
    }
    payload["target_rule_hash"] = sha256_hex(
        {"rule": TARGET_RULE, "odd_policy": ODD_POLICY, "z_bands": list(Z_BANDS)}
    )
    return payload


def _tally(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row[key])] = counts.get(str(row[key]), 0) + 1
    return dict(sorted(counts.items()))
