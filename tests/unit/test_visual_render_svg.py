from elementzero.visuals.aggregate import aggregate_events
from elementzero.visuals.event_types import ProgressEvent, make_event_id
from elementzero.visuals.render_html import render_html
from elementzero.visuals.render_svg import render_svg


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


def test_svg_render_deterministic():
    state = aggregate_events(
        [_event("DATA_INGESTED", 8), _event("HISTORICAL_VALIDATION_SCORED", 8)],
        test_health={"overall": "pass", "unit": "pass", "integration": "pass", "leakage": "pass"},
    )
    first = render_svg(state)
    second = render_svg(state)
    assert first == second
    assert 'class="tile stage-historically_validated' in first
    assert 'fill="#3d8b5a"' in first
    assert "not official IUPAC placement" in first


def test_html_render_contains_legend():
    state = aggregate_events([_event("DATA_INGESTED", 1)])
    html = render_html(state)
    assert "legend" in html
    assert "Historically validated" in html
    assert "Data ingested" in html
    assert "ElementZero visual states summarize project artifacts" in html
    assert "Elements 119-200 are project placeholders" in html
    assert 'id="element-table-state"' in html
    assert "Hydrogen" in html
