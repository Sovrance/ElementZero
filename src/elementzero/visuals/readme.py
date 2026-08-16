"""Keep README.md in sync with the latest visual-table snapshot."""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.visuals.labels import STAGE_LABELS, health_label, stage_label

MARKER_BEGIN = "<!-- ELEMENTZERO_VISUAL_TABLE_BEGIN -->"
MARKER_END = "<!-- ELEMENTZERO_VISUAL_TABLE_END -->"
README_IMAGE_REL = "docs/visuals/element_table.svg"


def render_readme_snapshot(
    state: dict[str, Any],
    *,
    bundle: dict[str, Any] | None = None,
    n_events: int = 0,
    image_rel: str = README_IMAGE_REL,
) -> str:
    health = state.get("test_health") or {}
    counts = Counter(item["project_primary_stage"] for item in state.get("elements", []))
    health_rows = "\n".join(
        f"| {label} | {health_label(str(health.get(key, 'unknown')))} |"
        for label, key in (
            ("Unit", "unit"),
            ("Integration", "integration"),
            ("Leakage", "leakage"),
            ("Overall", "overall"),
            ("Benchmark", "benchmark"),
        )
    )
    stage_rows = "\n".join(
        f"| {stage_label(stage)} | {counts.get(stage, 0)} |" for stage in STAGE_LABELS
    )
    bundle = bundle or {}
    state_hash = str(bundle.get("state_hash") or "")
    svg_hash = str(bundle.get("svg_hash") or "")
    generator = str(bundle.get("generator_version") or state.get("legend", {}).get("generator_version") or "")
    lines = [
        f"![{state.get('project', 'ElementZero')} visual element table]({image_rel})",
        "",
        "| Check | Status |",
        "| --- | --- |",
        health_rows,
        "",
        "| Primary stage | Elements |",
        "| --- | --- |",
        stage_rows,
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Layout | `{state.get('layout_profile', '')}` |",
        f"| Events | {n_events} |",
        f"| Generator | `{generator}` |",
        f"| State hash | `{_short_hash(state_hash)}` |",
        f"| SVG hash | `{_short_hash(svg_hash)}` |",
        "",
        "Elements 119-200 are project placeholders, not official IUPAC placement. "
        "Prediction-only runs are never shown as validated. Visual states summarize "
        "project artifacts and do not constitute experimental discovery claims.",
        "",
    ]
    return "\n".join(lines)


def _short_hash(value: str, length: int = 16) -> str:
    if not value:
        return ""
    return value[:length]


def replace_readme_snapshot(readme_text: str, snapshot: str) -> str:
    block = f"{MARKER_BEGIN}\n{snapshot.rstrip()}\n{MARKER_END}"
    if MARKER_BEGIN in readme_text and MARKER_END in readme_text:
        start = readme_text.index(MARKER_BEGIN)
        end = readme_text.index(MARKER_END) + len(MARKER_END)
        return readme_text[:start] + block + readme_text[end:]
    heading = "## Visual element table"
    if heading in readme_text:
        insert_at = readme_text.index(heading)
        next_heading = readme_text.find("\n## ", insert_at + len(heading))
        if next_heading == -1:
            return readme_text.rstrip() + "\n\n" + block + "\n"
        prefix = readme_text[:next_heading].rstrip()
        suffix = readme_text[next_heading:]
        return prefix + "\n\n" + block + "\n\n" + suffix.lstrip()
    return readme_text.rstrip() + "\n\n## Visual element table\n\n" + block + "\n"


def sync_readme(
    *,
    state: dict[str, Any],
    svg_path: str | Path,
    bundle: dict[str, Any] | None = None,
    n_events: int = 0,
    readme_path: str | Path | None = None,
    image_path: str | Path | None = None,
) -> Path:
    readme = Path(readme_path) if readme_path is not None else REPO_ROOT / "README.md"
    image = Path(image_path) if image_path is not None else REPO_ROOT / README_IMAGE_REL
    image.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(svg_path, image)
    snapshot = render_readme_snapshot(state, bundle=bundle, n_events=n_events)
    readme.write_text(replace_readme_snapshot(readme.read_text(encoding="utf-8"), snapshot), encoding="utf-8")
    return readme


def should_update_readme(input_root: str | Path) -> bool:
    try:
        return Path(input_root).resolve() == REPO_ROOT.resolve()
    except OSError:
        return False
