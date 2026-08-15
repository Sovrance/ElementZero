"""Self-contained HTML renderer for the visual element table."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from elementzero.evidence.hashing import canonical_json
from elementzero.visuals import DISCLAIMER_119_200, HONESTY_NOTE
from elementzero.visuals.aggregate import validate_state
from elementzero.visuals.labels import BADGE_LABELS, STAGE_LABELS, health_label, stage_label
from elementzero.visuals.metadata import metadata_for
from elementzero.visuals.palette import DEFAULT_STROKE, STAGE_FILL, STAGE_STROKE, WARNING_STROKE

CSS = """
body { font-family: sans-serif; background: #fff; color: #1a1a1a; margin: 16px; }
.health { margin: 8px 0 16px; }
.legend { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.swatch { width: 12px; height: 12px; border: 1px solid #4a4a4a; }
.table { position: relative; }
.tile { position: absolute; width: 36px; height: 36px; border: 1px solid #4a4a4a;
        box-sizing: border-box; padding: 2px; font-size: 10px; overflow: hidden; }
.tile .z { font-size: 8px; }
.tile .sym { font-size: 12px; font-weight: 600; }
.tile .badges { font-size: 8px; }
.notes { margin-top: 16px; font-size: 12px; max-width: 960px; }
"""


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _tooltip(element: dict[str, Any]) -> str:
    counts = element["counts"]
    sources = ", ".join(element["contributing_sources"][:4]) or "none"
    return (
        f"{element['symbol']} {element['name']}\n"
        f"Z={element['Z']} {element['known_status']}\n"
        f"stage={element['project_primary_stage']}\n"
        f"observations={counts['eligible_observation_count']}\n"
        f"historical={counts['historical_target_count']}/{counts['historical_scored_count']}\n"
        f"geographic={counts['geographic_scored_count']}\n"
        f"shell={counts['shell_scored_count']}\n"
        f"frontier={counts['frontier_prediction_count']}\n"
        f"sources={sources}"
    )


def render_html(state: dict[str, Any]) -> str:
    validate_state(state)
    for element in state["elements"]:
        metadata_for(element["Z"])
    health = state["test_health"]
    max_row = max(item["row"] for item in state["elements"])
    max_col = max(item["column"] for item in state["elements"])
    height = max_row * 40 + 8
    width = max_col * 40 + 8
    legend_items = []
    for stage, label in STAGE_LABELS.items():
        legend_items.append(
            f'<div class="legend-item"><span class="swatch" style="background:{STAGE_FILL[stage]}"></span>'
            f"{_escape(label)} ({_escape(stage)})</div>"
        )
    badge_items = " ".join(f"{code}={_escape(label)}" for code, label in BADGE_LABELS.items())
    tiles = []
    for element in sorted(state["elements"], key=lambda item: item["Z"]):
        left = (element["column"] - 1) * 40
        top = (element["row"] - 1) * 40
        stage = element["project_primary_stage"]
        stroke = STAGE_STROKE.get(stage, DEFAULT_STROKE)
        if element["health"].get("pipeline_warning"):
            stroke = WARNING_STROKE
        tiles.append(
            f'<div class="tile stage-{_escape(stage)} known-{_escape(element["known_status"])}" '
            f'style="left:{left}px;top:{top}px;background:{STAGE_FILL[stage]};border-color:{stroke}" '
            f'title="{_escape(_tooltip(element))}">'
            f'<div class="z">{element["Z"]}</div>'
            f'<div class="sym">{_escape(element["symbol"])}</div>'
            f'<div class="badges">{_escape("".join(element["badges"]))} {_escape(stage_label(stage))}</div>'
            f"</div>"
        )
    embedded = html.escape(canonical_json(state), quote=False)
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"/>"
        "<title>ElementZero visual element table</title>"
        f"<style>{CSS}</style></head><body>"
        "<h1>ElementZero visual element table</h1>"
        "<div class=\"health\">"
        f"Unit tests: {health_label(health['unit'])} | "
        f"Integration tests: {health_label(health['integration'])} | "
        f"Leakage tests: {health_label(health['leakage'])} | "
        f"Visual pipeline: {health_label(health['overall'])}"
        "</div>"
        f"<div class=\"legend\">{''.join(legend_items)}</div>"
        f"<p>Badges: {badge_items}</p>"
        f'<div class="table" style="width:{width}px;height:{height}px">{"".join(tiles)}</div>'
        f"<div class=\"notes\"><p>{_escape(DISCLAIMER_119_200)}</p>"
        f"<p>{_escape(HONESTY_NOTE)}</p></div>"
        f"<script type=\"application/json\" id=\"element-table-state\">{embedded}</script>"
        "</body></html>\n"
    )


def write_html(state: dict[str, Any], path: str | Path) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_html(state), encoding="utf-8")
    return dest
