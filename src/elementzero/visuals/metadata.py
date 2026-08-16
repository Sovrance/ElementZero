"""Load repository-controlled element metadata and table layouts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from elementzero.errors import VisualError
from elementzero.visuals import (
    DEFAULT_LAYOUT,
    LAYOUT_EXTENDED_200,
    LAYOUT_STANDARD_118,
    METADATA_VERSION,
)

LAYOUTS_DIR = Path(__file__).resolve().parent / "layouts"
METADATA_PATH = LAYOUTS_DIR / "element_metadata_v1.json"
LAYOUT_FILES = {
    LAYOUT_STANDARD_118: LAYOUTS_DIR / "standard_118.json",
    LAYOUT_EXTENDED_200: LAYOUTS_DIR / "extended_200_project_v1.json",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisualError(f"failed to read {path}: {exc}") from exc


@lru_cache(maxsize=1)
def load_element_metadata() -> dict[int, dict[str, Any]]:
    payload = _load_json(METADATA_PATH)
    if payload.get("version") != METADATA_VERSION:
        raise VisualError(f"unexpected metadata version {payload.get('version')!r}")
    records = payload.get("elements")
    if not isinstance(records, list) or len(records) != 200:
        raise VisualError("element metadata must contain exactly 200 records")
    by_z: dict[int, dict[str, Any]] = {}
    for record in records:
        z = record.get("Z")
        if not isinstance(z, int) or z in by_z:
            raise VisualError(f"invalid or duplicate metadata Z {z!r}")
        required = (
            "symbol",
            "name",
            "known_status",
            "display_group",
            "display_period",
            "series",
            "row",
            "column",
            "layout_profile",
        )
        missing = [key for key in required if key not in record]
        if missing:
            raise VisualError(f"metadata for Z={z} missing {missing}")
        by_z[z] = dict(record)
    if set(by_z) != set(range(1, 201)):
        raise VisualError("element metadata must cover Z=1..200 exactly")
    return by_z


@lru_cache(maxsize=4)
def load_layout(layout_profile: str = DEFAULT_LAYOUT) -> dict[str, Any]:
    if layout_profile not in LAYOUT_FILES:
        raise VisualError(f"unknown layout_profile {layout_profile!r}")
    payload = _load_json(LAYOUT_FILES[layout_profile])
    positions = payload.get("positions")
    if not isinstance(positions, dict) or not positions:
        raise VisualError(f"layout {layout_profile} has no positions")
    parsed: dict[int, dict[str, int]] = {}
    for key, value in positions.items():
        z = int(key)
        parsed[z] = {"row": int(value["row"]), "column": int(value["column"])}
    expected = set(range(1, 119 if layout_profile == LAYOUT_STANDARD_118 else 201))
    if set(parsed) != expected:
        raise VisualError(f"layout {layout_profile} positions do not cover {min(expected)}..{max(expected)}")
    payload = dict(payload)
    payload["positions"] = parsed
    return payload


def metadata_for(z: int) -> dict[str, Any]:
    records = load_element_metadata()
    if z not in records:
        raise VisualError(f"required metadata missing for Z={z}")
    return records[z]


def position_for(z: int, layout_profile: str = DEFAULT_LAYOUT) -> dict[str, int]:
    layout = load_layout(layout_profile)
    positions: dict[int, dict[str, int]] = layout["positions"]
    if z in positions:
        return positions[z]
    # standard_118 still needs coordinates for Z=119..200 in the 200-row state bundle
    extended = load_layout(LAYOUT_EXTENDED_200)["positions"]
    if z not in extended:
        raise VisualError(f"required layout position missing for Z={z}")
    return extended[z]
