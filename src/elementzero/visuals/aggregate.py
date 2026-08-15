"""Aggregate visual events into a 200-element table state bundle."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from elementzero.errors import VisualError
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.visuals import (
    DEFAULT_LAYOUT,
    DISCLAIMER_119_200,
    GENERATOR_VERSION,
    HONESTY_NOTE,
)
from elementzero.visuals.event_types import SUITE_EVENT_TYPES, ProgressEvent, validate_event
from elementzero.visuals.labels import BADGE_LABELS, STAGE_LABELS
from elementzero.visuals.metadata import load_element_metadata, metadata_for, position_for
from elementzero.visuals.status import badges_from_event_types, select_primary_stage

EMPTY_COUNTS = {
    "eligible_observation_count": 0,
    "historical_target_count": 0,
    "historical_scored_count": 0,
    "geographic_target_count": 0,
    "geographic_scored_count": 0,
    "shell_target_count": 0,
    "shell_scored_count": 0,
    "frontier_prediction_count": 0,
}

COUNT_EVENTS = {
    "DATA_INGESTED": "eligible_observation_count",
    "HISTORICAL_TARGET_CREATED": "historical_target_count",
    "HISTORICAL_VALIDATION_SCORED": "historical_scored_count",
    "REGION_TARGET_CREATED": "geographic_target_count",
    "REGION_VALIDATION_SCORED": "geographic_scored_count",
    "SHELL_TARGET_CREATED": "shell_target_count",
    "SHELL_VALIDATION_SCORED": "shell_scored_count",
    "FRONTIER_PREDICTION_CREATED": "frontier_prediction_count",
}


def _dedupe_key(event: ProgressEvent) -> tuple[Any, ...]:
    return (
        event.event_type,
        event.source_hash,
        event.element_Z,
        event.nuclide_id or "",
        event.benchmark_id or "",
        event.model_id or "",
    )


def aggregate_events(
    events: list[ProgressEvent],
    *,
    layout_profile: str = DEFAULT_LAYOUT,
    test_health: dict[str, str] | None = None,
    input_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    load_element_metadata()
    health = {
        "overall": "unknown",
        "unit": "unknown",
        "integration": "unknown",
        "leakage": "unknown",
        "benchmark": "unknown",
    }
    if test_health:
        health.update({key: test_health[key] for key in health if key in test_health})

    by_z: dict[int, list[ProgressEvent]] = defaultdict(list)
    seen: set[tuple[Any, ...]] = set()
    for event in events:
        validate_event(event)
        if event.event_type in SUITE_EVENT_TYPES:
            continue
        key = _dedupe_key(event)
        if key in seen:
            continue
        seen.add(key)
        by_z[event.element_Z].append(event)

    pipeline_red = health.get("overall") == "fail"
    elements: list[dict[str, Any]] = []
    for z in range(1, 201):
        meta = metadata_for(z)
        pos = position_for(z, layout_profile)
        z_events = by_z.get(z, [])
        types = [event.event_type for event in z_events]
        counts = dict(EMPTY_COUNTS)
        for event in z_events:
            field = COUNT_EVENTS.get(event.event_type)
            if field:
                counts[field] += 1
        sources = sorted({event.source_hash for event in z_events})
        last_time = None
        if z_events:
            last_time = max(event.event_time for event in z_events)
        element_health = {
            "unit_tests_green": health["unit"] == "pass",
            "integration_tests_green": health["integration"] == "pass",
            "leakage_tests_green": health["leakage"] == "pass",
            "benchmark_suite_green": health.get("benchmark") == "pass",
            "pipeline_warning": pipeline_red and bool(z_events),
        }
        elements.append(
            {
                "Z": z,
                "symbol": meta["symbol"],
                "name": meta["name"],
                "known_status": meta["known_status"],
                "layout_profile": layout_profile,
                "row": pos["row"],
                "column": pos["column"],
                "project_primary_stage": select_primary_stage(types, z=z),
                "badges": badges_from_event_types(types),
                "counts": counts,
                "last_event_time": last_time,
                "contributing_sources": sources,
                "health": element_health,
            }
        )

    state = {
        "project": "ElementZero",
        "generated_at": "derived-from-artifacts",
        "layout_profile": layout_profile,
        "input_hashes": dict(sorted((input_hashes or {}).items())),
        "test_health": health,
        "legend": {
            "stages": dict(STAGE_LABELS),
            "badges": dict(BADGE_LABELS),
            "disclaimer": DISCLAIMER_119_200,
            "honesty_note": HONESTY_NOTE,
            "generator_version": GENERATOR_VERSION,
        },
        "elements": elements,
    }
    validate_state(state)
    return state


def validate_state(state: dict[str, Any]) -> dict[str, Any]:
    required = ("project", "generated_at", "layout_profile", "input_hashes", "test_health", "legend", "elements")
    missing = [key for key in required if key not in state]
    if missing:
        raise VisualError(f"table state missing {missing}")
    health = state["test_health"]
    for key in ("overall", "unit", "integration", "leakage"):
        if key not in health:
            raise VisualError(f"test_health missing {key}")
    elements = state["elements"]
    if not isinstance(elements, list) or len(elements) != 200:
        raise VisualError("table state must contain exactly 200 elements")
    seen: set[int] = set()
    for item in elements:
        for key in (
            "Z",
            "symbol",
            "name",
            "known_status",
            "layout_profile",
            "row",
            "column",
            "project_primary_stage",
            "badges",
            "counts",
            "last_event_time",
            "contributing_sources",
            "health",
        ):
            if key not in item:
                raise VisualError(f"element row missing {key}: {item!r}")
        z = item["Z"]
        if z in seen or z < 1 or z > 200:
            raise VisualError(f"invalid or duplicate element Z {z!r}")
        seen.add(z)
        metadata_for(z)
    if seen != set(range(1, 201)):
        raise VisualError("table state does not cover Z=1..200")
    return state


def write_state(state: dict[str, Any], path: str | Path) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(canonical_json(validate_state(state)) + "\n", encoding="utf-8")
    return dest


def state_hash(state: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(validate_state(state)))
