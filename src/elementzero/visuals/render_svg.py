"""Deterministic SVG renderer for the visual element table."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from elementzero.visuals import DISCLAIMER_119_200, HONESTY_NOTE
from elementzero.visuals.aggregate import validate_state
from elementzero.visuals.labels import STAGE_LABELS, health_label, stage_label
from elementzero.visuals.metadata import metadata_for
from elementzero.visuals.palette import (
    BACKGROUND,
    DEFAULT_STROKE,
    STAGE_FILL,
    STAGE_STROKE,
    TEXT_FILL,
    WARNING_STROKE,
)

TILE = 36
GAP = 4
LEFT = 16
TOP = 64
LEGEND_ITEM_WIDTH = 240
LEGEND_ITEM_HEIGHT = 16
LEGEND_COLUMNS = 3


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _tooltip(element: dict[str, Any]) -> str:
    counts = element["counts"]
    sources = ",".join(element["contributing_sources"][:3])
    return (
        f"{element['symbol']} {element['name']} Z={element['Z']} "
        f"{element['known_status']} {element['project_primary_stage']} "
        f"obs={counts['eligible_observation_count']} "
        f"hist={counts['historical_target_count']}/{counts['historical_scored_count']} "
        f"geo={counts['geographic_scored_count']} "
        f"shell={counts['shell_scored_count']} "
        f"frontier={counts['frontier_prediction_count']} "
        f"sources={sources or 'none'}"
    )


def render_svg(state: dict[str, Any]) -> str:
    validate_state(state)
    for element in state["elements"]:
        metadata_for(element["Z"])
    max_row = max(item["row"] for item in state["elements"])
    max_col = max(item["column"] for item in state["elements"])
    table_width = LEFT * 2 + max_col * (TILE + GAP)
    table_height = max_row * (TILE + GAP)
    legend_rows = (len(STAGE_LABELS) + LEGEND_COLUMNS - 1) // LEGEND_COLUMNS
    legend_width = LEFT * 2 + LEGEND_COLUMNS * LEGEND_ITEM_WIDTH
    width = max(table_width, legend_width)
    legend_top = TOP + table_height + 16
    height = legend_top + legend_rows * LEGEND_ITEM_HEIGHT + 56
    health = state["test_health"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">',
        f'<rect width="{width}" height="{height}" fill="{BACKGROUND}"/>',
        f'<text x="{LEFT}" y="28" fill="{TEXT_FILL}" font-family="sans-serif" font-size="16">'
        f"ElementZero visual element table</text>",
        f'<text x="{LEFT}" y="48" fill="{TEXT_FILL}" font-family="sans-serif" font-size="11">'
        f"Unit {health_label(health['unit'])} | Integration {health_label(health['integration'])} | "
        f"Leakage {health_label(health['leakage'])} | Overall {health_label(health['overall'])}</text>",
    ]
    for index, (stage, label) in enumerate(STAGE_LABELS.items()):
        col = index % LEGEND_COLUMNS
        row = index // LEGEND_COLUMNS
        legend_x = LEFT + col * LEGEND_ITEM_WIDTH
        legend_y = legend_top + row * LEGEND_ITEM_HEIGHT
        fill = STAGE_FILL[stage]
        parts.append(
            f'<rect class="legend-swatch stage-{_escape(stage)}" x="{legend_x}" y="{legend_y}" '
            f'width="10" height="10" fill="{fill}" stroke="{DEFAULT_STROKE}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 14}" y="{legend_y + 9}" fill="{TEXT_FILL}" '
            f'font-family="sans-serif" font-size="9">{_escape(label)}</text>'
        )

    for element in sorted(state["elements"], key=lambda item: item["Z"]):
        x = LEFT + (element["column"] - 1) * (TILE + GAP)
        y = TOP + (element["row"] - 1) * (TILE + GAP)
        stage = element["project_primary_stage"]
        fill = STAGE_FILL[stage]
        stroke = STAGE_STROKE.get(stage, DEFAULT_STROKE)
        if element["health"].get("pipeline_warning"):
            stroke = WARNING_STROKE
        badges = "".join(element["badges"])
        title = _escape(_tooltip(element))
        parts.append(
            f'<g class="tile stage-{_escape(stage)} known-{_escape(element["known_status"])}" '
            f'data-z="{element["Z"]}">'
            f"<title>{title}</title>"
            f'<rect x="{x}" y="{y}" width="{TILE}" height="{TILE}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1"/>'
            f'<text x="{x + 3}" y="{y + 12}" fill="{TEXT_FILL}" font-family="sans-serif" '
            f'font-size="8">{element["Z"]}</text>'
            f'<text x="{x + 3}" y="{y + 24}" fill="{TEXT_FILL}" font-family="sans-serif" '
            f'font-size="11">{_escape(element["symbol"])}</text>'
            f'<text x="{x + 3}" y="{y + 33}" fill="{TEXT_FILL}" font-family="sans-serif" '
            f'font-size="8">{_escape(badges)} {_escape(stage_label(stage)[:1])}</text>'
            f"</g>"
        )
    parts.append(
        f'<text x="{LEFT}" y="{height - 36}" fill="{TEXT_FILL}" font-family="sans-serif" font-size="10">'
        f"{_escape(DISCLAIMER_119_200)}</text>"
    )
    parts.append(
        f'<text x="{LEFT}" y="{height - 18}" fill="{TEXT_FILL}" font-family="sans-serif" font-size="10">'
        f"{_escape(HONESTY_NOTE)}</text>"
    )
    parts.append("</svg>\n")
    return "".join(parts)


def write_svg(state: dict[str, Any], path: str | Path) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_svg(state), encoding="utf-8")
    return dest
