"""Human-readable labels and abbreviations for the visual table."""

from __future__ import annotations

STAGE_LABELS = {
    "not_touched": "Not touched",
    "data_ingested": "Data ingested",
    "benchmark_targeted": "Benchmark targeted",
    "historically_validated": "Historically validated",
    "geographic_holdout_validated": "Geographic holdout validated",
    "shell_challenge_participant": "Shell challenge participant",
    "shell_rediscovery_validated": "Shell rediscovery validated",
    "frontier_predicted": "Frontier predicted",
    "candidate_island_focus": "Candidate island focus",
}

BADGE_LABELS = {
    "D": "data ingested",
    "H": "historical validation",
    "G": "geographic holdout",
    "S": "shell rediscovery",
    "F": "frontier prediction",
    "I": "island focus",
    "R": "reconstruction reference (never blind validation)",
    "CB": "control-blind real validation (statistical baselines only)",
    "HB": "historical-blind edge evidence (never full shell rediscovery)",
}

HEALTH_LABELS = {
    "pass": "PASS",
    "fail": "FAIL",
    "unknown": "UNKNOWN",
}


def stage_label(stage: str) -> str:
    return STAGE_LABELS.get(stage, stage)


def health_label(value: str) -> str:
    return HEALTH_LABELS.get(value, value.upper())
