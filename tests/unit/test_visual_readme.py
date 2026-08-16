from elementzero.visuals.aggregate import aggregate_events
from elementzero.visuals.event_types import ProgressEvent, make_event_id
from elementzero.visuals.readme import (
    MARKER_BEGIN,
    MARKER_END,
    render_readme_snapshot,
    replace_readme_snapshot,
    sync_readme,
)
from elementzero.visuals.render_svg import write_svg


def _event(event_type: str, z: int) -> ProgressEvent:
    return ProgressEvent(
        event_id=make_event_id(event_type=event_type, source_hash="abc", element_Z=z),
        event_type=event_type,
        event_time="1970-01-01T00:00:00Z",
        project_version="0.2.0",
        source_kind="test",
        source_path="fixture",
        source_hash="abc",
        element_Z=z,
        status="ok",
    )


def test_readme_snapshot_replaced_when_values_change(tmp_path):
    first = aggregate_events(
        [],
        test_health={"overall": "unknown", "unit": "unknown", "integration": "unknown", "leakage": "unknown"},
    )
    second = aggregate_events(
        [_event("DATA_INGESTED", 8)],
        test_health={"overall": "pass", "unit": "pass", "integration": "pass", "leakage": "pass"},
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Title\n\n## Visual element table\n\n"
        f"{MARKER_BEGIN}\nold snapshot\n{MARKER_END}\n\n## Architecture rule\n\nkeep\n",
        encoding="utf-8",
    )
    svg = write_svg(first, tmp_path / "table.svg")
    sync_readme(
        state=first,
        svg_path=svg,
        bundle={"state_hash": "aaa", "svg_hash": "bbb", "generator_version": "visual-table-v0.1"},
        n_events=0,
        readme_path=readme,
        image_path=tmp_path / "docs" / "visuals" / "element_table.svg",
    )
    text = readme.read_text(encoding="utf-8")
    assert MARKER_BEGIN in text
    assert MARKER_END in text
    assert "UNKNOWN" in text
    assert "Not touched | 200" in text
    assert "## Architecture rule" in text
    assert (tmp_path / "docs" / "visuals" / "element_table.svg").is_file()

    write_svg(second, svg)
    sync_readme(
        state=second,
        svg_path=svg,
        bundle={"state_hash": "ccc", "svg_hash": "ddd", "generator_version": "visual-table-v0.1"},
        n_events=1,
        readme_path=readme,
        image_path=tmp_path / "docs" / "visuals" / "element_table.svg",
    )
    updated = readme.read_text(encoding="utf-8")
    assert updated.count(MARKER_BEGIN) == 1
    assert "| Unit | PASS |" in updated
    assert "| Overall | PASS |" in updated
    assert "| Unit | UNKNOWN |" not in updated
    assert "Data ingested | 1" in updated
    assert "Not touched | 199" in updated
    assert "| Events | 1 |" in updated
    assert "old snapshot" not in updated
    assert replace_readme_snapshot("no heading", render_readme_snapshot(second)).count(MARKER_BEGIN) == 1


def test_readme_snapshot_is_inserted_under_existing_heading(tmp_path):
    first = aggregate_events(
        [],
        test_health={"overall": "unknown", "unit": "unknown", "integration": "unknown", "leakage": "unknown"},
    )
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Title\n\n## Visual element table\n\nKeep this intro.\n\n```bash\ncmd\n```\n\n## Architecture rule\n\nkeep\n",
        encoding="utf-8",
    )
    svg = write_svg(first, tmp_path / "table.svg")
    sync_readme(
        state=first,
        svg_path=svg,
        bundle={"state_hash": "aaa", "svg_hash": "bbb", "generator_version": "visual-table-v0.1"},
        n_events=0,
        readme_path=readme,
        image_path=tmp_path / "docs" / "visuals" / "element_table.svg",
    )
    text = readme.read_text(encoding="utf-8")
    assert text.index("Keep this intro.") < text.index(MARKER_BEGIN)
    assert text.index(MARKER_END) < text.index("## Architecture rule")
    assert "Keep this intro." in text
    assert "```bash\ncmd\n```" in text
    assert "## Architecture rule" in text
    assert text.count(MARKER_BEGIN) == 1
