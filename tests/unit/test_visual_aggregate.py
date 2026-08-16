import shutil

from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import VisualError
from elementzero.visuals.aggregate import aggregate_events, validate_state
from elementzero.visuals.build import aggregate_from_events_file
from elementzero.visuals.event_types import ProgressEvent, make_event_id
from elementzero.visuals.ingest import extract_events, write_events_jsonl
from elementzero.visuals.status import select_primary_stage

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "visuals"


def _event(event_type: str, z: int, nuclide_id: str | None = None, payload: dict | None = None) -> ProgressEvent:
    return ProgressEvent(
        event_id=make_event_id(
            event_type=event_type,
            source_hash="abc",
            element_Z=z,
            nuclide_id=nuclide_id,
            extra=str((payload or {}).get("suite") or ""),
        ),
        event_type=event_type,
        event_time="1970-01-01T00:00:00Z",
        project_version="0.2.0",
        source_kind="test",
        source_path="fixture",
        source_hash="abc",
        element_Z=z,
        status="ok",
        nuclide_id=nuclide_id,
        payload=payload or {},
    )


def test_aggregate_counts_per_element(tmp_path):
    shutil.copytree(FIXTURES / "EZ-B001-demo", tmp_path / "EZ-B001-demo")
    shutil.copytree(FIXTURES / "EZ-B002-demo", tmp_path / "EZ-B002-demo")
    shutil.copytree(FIXTURES / "EZ-B003-demo", tmp_path / "EZ-B003-demo")
    events, health, hashes = extract_events(tmp_path)
    state = aggregate_events(events, test_health=health, input_hashes=hashes)
    by_z = {item["Z"]: item for item in state["elements"]}
    assert by_z[8]["counts"]["historical_target_count"] == 1
    assert by_z[8]["counts"]["historical_scored_count"] == 1
    assert by_z[26]["counts"]["geographic_target_count"] == 1
    assert by_z[26]["counts"]["geographic_scored_count"] == 1
    assert by_z[50]["counts"]["shell_target_count"] == 1
    assert by_z[50]["counts"]["shell_scored_count"] == 1
    assert len(state["elements"]) == 200


def test_primary_stage_priority():
    assert select_primary_stage(["DATA_INGESTED"], z=8) == "data_ingested"
    assert select_primary_stage(["DATA_INGESTED", "HISTORICAL_TARGET_CREATED"], z=8) == "benchmark_targeted"
    assert (
        select_primary_stage(["HISTORICAL_TARGET_CREATED", "HISTORICAL_VALIDATION_SCORED"], z=8)
        == "historically_validated"
    )
    assert (
        select_primary_stage(["FRONTIER_PREDICTION_CREATED", "HISTORICAL_VALIDATION_SCORED"], z=8)
        == "historically_validated"
    )
    assert select_primary_stage(["FRONTIER_PREDICTION_CREATED"], z=120) == "frontier_predicted"
    assert select_primary_stage(["CANDIDATE_ISLAND_MARKED", "FRONTIER_PREDICTION_CREATED"], z=120) == (
        "candidate_island_focus"
    )


def test_frontier_prediction_does_not_equal_validation():
    state = aggregate_events([_event("FRONTIER_PREDICTION_CREATED", 120, "Z120-N184")])
    row = next(item for item in state["elements"] if item["Z"] == 120)
    assert row["project_primary_stage"] == "frontier_predicted"
    assert row["project_primary_stage"] != "historically_validated"
    assert "F" in row["badges"]
    assert "I" not in row["badges"]


def test_candidate_island_requires_explicit_event():
    frontier_only = aggregate_events([_event("FRONTIER_PREDICTION_CREATED", 120, "Z120-N184")])
    assert next(item for item in frontier_only["elements"] if item["Z"] == 120)["project_primary_stage"] != (
        "candidate_island_focus"
    )
    marked = aggregate_events(
        [
            _event("FRONTIER_PREDICTION_CREATED", 120, "Z120-N184"),
            _event("CANDIDATE_ISLAND_MARKED", 120),
        ]
    )
    row = next(item for item in marked["elements"] if item["Z"] == 120)
    assert row["project_primary_stage"] == "candidate_island_focus"
    assert "I" in row["badges"]


def test_aggregate_reconstructs_suite_health(tmp_path):
    events = [
        _event("TEST_SUITE_PASS", 1, payload={"suite": "unit"}),
        _event("TEST_SUITE_PASS", 1, payload={"suite": "integration"}),
        _event("TEST_SUITE_FAIL", 1, payload={"suite": "leakage"}),
        _event("DATA_INGESTED", 8, "Z8-N8"),
    ]
    events_path = write_events_jsonl(events, tmp_path / "events.jsonl")
    dest = aggregate_from_events_file(events_path, output=tmp_path / "state.json")
    state = aggregate_events(events)
    assert state["test_health"]["unit"] == "pass"
    assert state["test_health"]["integration"] == "pass"
    assert state["test_health"]["leakage"] == "fail"
    assert state["test_health"]["overall"] == "fail"
    assert dest.is_file()
    assert "fixture" in state["input_hashes"]


def test_visual_bundle_schema_validates():
    state = aggregate_events([])
    validate_state(state)
    assert state["test_health"]["overall"] == "unknown"
    broken = dict(state)
    broken["elements"] = state["elements"][:10]
    try:
        validate_state(broken)
    except VisualError:
        return
    raise AssertionError("expected VisualError for short element list")
