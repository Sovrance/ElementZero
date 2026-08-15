"""Stable visual palette. Color is never the only encoding."""

from __future__ import annotations

STAGE_FILL = {
    "not_touched": "#d9d9d9",
    "data_ingested": "#4c78a8",
    "benchmark_targeted": "#7b61a8",
    "historically_validated": "#3d8b5a",
    "geographic_holdout_validated": "#2a9d8f",
    "shell_challenge_participant": "#c9a227",
    "shell_rediscovery_validated": "#d4a017",
    "frontier_predicted": "#e07a2f",
    "candidate_island_focus": "#e6b422",
}

KNOWN_STATUS_FILL = {
    "known_element": "#c5d0d8",
    "unknown_element": "#ececec",
}

STAGE_STROKE = {
    "candidate_island_focus": "#b30000",
}

DEFAULT_STROKE = "#4a4a4a"
WARNING_STROKE = "#b30000"
TEXT_FILL = "#1a1a1a"
BACKGROUND = "#ffffff"
