"""Orchestrate extract -> aggregate -> render for the visual element table."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.atlas_pin import atlas_pir_ref
from elementzero.evidence.hashing import canonical_json, sha256_file
from elementzero.identity_meta import elementzero_commit
from elementzero.visuals import DEFAULT_LAYOUT, GENERATOR_VERSION
from elementzero.visuals.aggregate import aggregate_events, write_state
from elementzero.visuals.ingest import extract_events, read_events_jsonl, write_events_jsonl
from elementzero.visuals.readme import should_update_readme, sync_readme
from elementzero.visuals.render_html import write_html
from elementzero.visuals.render_svg import write_svg


def write_render_bundle(
    *,
    output_root: Path,
    state_path: Path,
    events_path: Path,
    html_path: Path | None,
    svg_path: Path | None,
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    bundle = {
        "state_hash": sha256_file(state_path),
        "events_hash": sha256_file(events_path),
        "html_hash": sha256_file(html_path) if html_path and html_path.is_file() else None,
        "svg_hash": sha256_file(svg_path) if svg_path and svg_path.is_file() else None,
        "generator_version": GENERATOR_VERSION,
        "elementzero_commit": elementzero_commit(),
        "atlas_commit": atlas_pir_ref(),
        "source_hashes": dict(sorted(source_hashes.items())),
    }
    dest = output_root / "visual_render_bundle.json"
    dest.write_text(canonical_json(bundle) + "\n", encoding="utf-8")
    return bundle


def build_visual_table(
    *,
    input_root: str | Path,
    output_root: str | Path,
    layout_profile: str = DEFAULT_LAYOUT,
    update_readme: bool | None = None,
) -> dict[str, Any]:
    input_root = Path(input_root)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    events, health, input_hashes = extract_events(input_root)
    events_path = write_events_jsonl(events, output_root / "element_progress_events.jsonl")
    state = aggregate_events(
        events,
        layout_profile=layout_profile,
        test_health=health,
        input_hashes=input_hashes,
    )
    state_path = write_state(state, output_root / "element_table_state.json")
    html_path = write_html(state, output_root / "element_table.html")
    svg_path = write_svg(state, output_root / "element_table.svg")
    bundle = write_render_bundle(
        output_root=output_root,
        state_path=state_path,
        events_path=events_path,
        html_path=html_path,
        svg_path=svg_path,
        source_hashes=input_hashes,
    )
    readme_path = None
    if update_readme is True or (update_readme is None and should_update_readme(input_root)):
        readme_path = sync_readme(
            state=state,
            svg_path=svg_path,
            bundle=bundle,
            n_events=len(events),
        )
    return {
        "events": events_path,
        "state": state_path,
        "html": html_path,
        "svg": svg_path,
        "bundle": output_root / "visual_render_bundle.json",
        "n_events": len(events),
        "test_health": health,
        "bundle_payload": bundle,
        "readme": readme_path,
    }


def aggregate_from_events_file(
    events_path: str | Path,
    *,
    output: str | Path,
    layout_profile: str = DEFAULT_LAYOUT,
    test_health: dict[str, str] | None = None,
) -> Path:
    events = read_events_jsonl(events_path)
    state = aggregate_events(events, layout_profile=layout_profile, test_health=test_health)
    return write_state(state, output)
