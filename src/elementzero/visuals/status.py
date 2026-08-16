"""Deterministic primary-stage and badge selection."""

from __future__ import annotations

from collections.abc import Iterable

from elementzero.visuals.event_types import SUITE_EVENT_TYPES

STAGE_PRIORITY = (
    "candidate_island_focus",
    "shell_rediscovery_validated",
    "geographic_holdout_validated",
    "historically_validated",
    "frontier_predicted",
    "shell_challenge_participant",
    "benchmark_targeted",
    "data_ingested",
    "not_touched",
)

EVENT_TO_STAGE = {
    "CANDIDATE_ISLAND_MARKED": "candidate_island_focus",
    "SHELL_VALIDATION_SCORED": "shell_rediscovery_validated",
    "REGION_VALIDATION_SCORED": "geographic_holdout_validated",
    "HISTORICAL_VALIDATION_SCORED": "historically_validated",
    "FRONTIER_PREDICTION_CREATED": "frontier_predicted",
    "SHELL_TARGET_CREATED": "shell_challenge_participant",
    "HISTORICAL_TARGET_CREATED": "benchmark_targeted",
    "HISTORICAL_PREDICTION_SEALED": "benchmark_targeted",
    "REGION_TARGET_CREATED": "benchmark_targeted",
    "DATA_INGESTED": "data_ingested",
}

EVENT_TO_BADGE = {
    "DATA_INGESTED": "D",
    "HISTORICAL_TARGET_CREATED": "H",
    "HISTORICAL_PREDICTION_SEALED": "H",
    "HISTORICAL_VALIDATION_SCORED": "H",
    "REGION_TARGET_CREATED": "G",
    "REGION_VALIDATION_SCORED": "G",
    "SHELL_TARGET_CREATED": "S",
    "SHELL_VALIDATION_SCORED": "S",
    "FRONTIER_PREDICTION_CREATED": "F",
    "CANDIDATE_ISLAND_MARKED": "I",
}

_PRIORITY_INDEX = {stage: index for index, stage in enumerate(STAGE_PRIORITY)}


def stages_from_event_types(event_types: Iterable[str], *, z: int) -> set[str]:
    stages: set[str] = set()
    for event_type in event_types:
        if event_type in SUITE_EVENT_TYPES:
            continue
        stage = EVENT_TO_STAGE.get(event_type)
        if stage is None:
            continue
        if stage == "frontier_predicted" and z <= 118:
            # Known elements stay frontier-predicted only for explicit frontier-mode events.
            # Those still use FRONTIER_PREDICTION_CREATED; keep the stage.
            stages.add(stage)
            continue
        stages.add(stage)
    return stages


def select_primary_stage(event_types: Iterable[str], *, z: int) -> str:
    stages = stages_from_event_types(event_types, z=z)
    if not stages:
        return "not_touched"
    return min(stages, key=lambda stage: _PRIORITY_INDEX[stage])


def badges_from_event_types(event_types: Iterable[str]) -> list[str]:
    badges: list[str] = []
    seen: set[str] = set()
    for event_type in event_types:
        badge = EVENT_TO_BADGE.get(event_type)
        if badge and badge not in seen:
            seen.add(badge)
            badges.append(badge)
    return badges
