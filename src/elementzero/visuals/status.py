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
    # WO-13: reconstruction runs earn a badge, never a stage.
    "REAL_RECONSTRUCTION_SCORED": "R",
    # WO-14: control-blind and historical-blind-edge evidence earn badges;
    # stage promotion still requires the claim-checked blind path below.
    "REAL_CONTROL_BLIND_SCORED": "CB",
    "REAL_HISTORICAL_BLIND_EDGE_SCORED": "HB",
    # WO-15: provenance-complete refittable physics family (qualification
    # only) and a scored multi-family blind challenge result.
    "PHYSICS_FAMILY_QUALIFIED": "PF",
    "PHYSICS_BLIND_CHALLENGE_SCORED": "PB",
}

# WO-13 claim firewall: a blind real-data validation event may promote a
# tile only when its payload attests blind_gate_passed with an allowed
# blind claim type; the aggregator maps it onto the corresponding
# validated-stage event type through this table. Reconstruction has no
# entry on purpose.
BLIND_VALIDATION_STAGE_EVENTS = {
    "EZ-B002": "REGION_VALIDATION_SCORED",
    "EZ-B003": "SHELL_VALIDATION_SCORED",
}
ALLOWED_BLIND_STAGE_CLAIMS = ("STRICT_BLIND", "HISTORICAL_BLIND")


def claim_checked_stage_types(
    event_type: str, payload: dict | None, benchmark_id: str | None
) -> list[str]:
    """The stage-granting event types one event contributes (claim-aware)."""
    if event_type == "REAL_RECONSTRUCTION_SCORED":
        return []
    # WO-14: control-only and edge-only blind evidence never promotes a
    # primary validation stage — badge only. Shell promotion additionally
    # requires the full-shell blind criterion to have been met.
    if event_type in ("REAL_CONTROL_BLIND_SCORED", "REAL_HISTORICAL_BLIND_EDGE_SCORED"):
        return []
    # WO-15: backend qualification is an engineering fact about provenance
    # and reproducibility — it says nothing about predictive accuracy, so
    # it never touches a tile's stage. A scored blind challenge is badge-
    # only here too: its claim record, not the visual layer, decides what
    # the science supports.
    if event_type in ("PHYSICS_FAMILY_QUALIFIED", "PHYSICS_BLIND_CHALLENGE_SCORED"):
        return []
    if event_type == "REAL_BLIND_VALIDATION_SCORED":
        data = payload or {}
        if data.get("blind_gate_passed") is not True:
            return []
        if data.get("claim_type") not in ALLOWED_BLIND_STAGE_CLAIMS:
            return []
        family = str(benchmark_id or "").split("-v")[0]
        if family == "EZ-B003" and (
            data.get("blind_gate_status") != "FULL_SHELL_BLIND_CRITERION_MET"
        ):
            return []
        stage_event = BLIND_VALIDATION_STAGE_EVENTS.get(family)
        return [stage_event] if stage_event else []
    return [event_type]

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
