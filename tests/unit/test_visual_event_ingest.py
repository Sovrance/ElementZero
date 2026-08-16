import json
import shutil
from pathlib import Path

import pytest

from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import VisualError
from elementzero.visuals.event_types import validate_event
from elementzero.visuals.ingest import extract_ame_events, extract_events, extract_island

FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _copy(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        dest.write_bytes(src.read_bytes())
    return dest


def test_extract_data_ingested_events(tmp_path):
    ame = _copy(FIXTURES / "amdc" / "ame2020_golden.txt", tmp_path / "ame2020_golden.txt")
    events = extract_ame_events(ame, root=tmp_path)
    types = {event.event_type for event in events}
    zs = {event.element_Z for event in events}
    assert types == {"DATA_INGESTED"}
    assert 1 in zs
    assert 2 in zs
    assert 8 in zs
    assert 4 not in zs  # Be-5 is estimated / not eligible
    for event in events:
        validate_event(event)


def test_extract_historical_events(tmp_path):
    _copy(FIXTURES / "visuals" / "EZ-B001-demo", tmp_path / "EZ-B001-demo")
    events, _health, _hashes = extract_events(tmp_path)
    types = {event.event_type for event in events}
    assert "HISTORICAL_TARGET_CREATED" in types
    assert "HISTORICAL_VALIDATION_SCORED" in types
    oxygen = [event for event in events if event.element_Z == 8]
    scored = [event for event in oxygen if event.event_type == "HISTORICAL_VALIDATION_SCORED"]
    assert scored
    assert scored[0].payload.get("abs_error_keV") == 7.0


def test_extract_ci_health(tmp_path):
    _copy(FIXTURES / "visuals" / "pytest-report.json", tmp_path / ".artifacts" / "tests" / "pytest-report.json")
    events, health, _hashes = extract_events(tmp_path)
    assert health["overall"] == "pass"
    assert health["unit"] == "pass"
    assert health["integration"] == "pass"
    assert health["leakage"] == "pass"
    assert {event.event_type for event in events} == {"TEST_SUITE_PASS"}


def test_extract_ci_health_from_junit(tmp_path):
    _copy(FIXTURES / "visuals" / "junit.xml", tmp_path / ".artifacts" / "tests" / "junit.xml")
    _events, health, _hashes = extract_events(tmp_path)
    assert health["unit"] == "pass"
    assert health["leakage"] == "pass"


def test_invalid_Z_rejected(tmp_path):
    dest = tmp_path / "targets.json"
    dest.write_text('{"targets": [{"nuclide_id": "Z201-N300", "Z": 201, "N": 300, "A": 501}]}\n')
    with pytest.raises(VisualError, match="Z outside 1..200"):
        extract_events(tmp_path)


def test_malformed_benchmark_json_fails(tmp_path):
    (tmp_path / "score_report.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(VisualError, match="malformed JSON"):
        extract_events(tmp_path)


def test_repo_root_skips_committed_fixtures():
    events, _health, hashes = extract_events(REPO_ROOT)
    assert all(not path.startswith("tests/") for path in hashes)
    assert all(not event.source_path.startswith("tests/") for event in events)
    assert all(event.event_type != "CANDIDATE_ISLAND_MARKED" for event in events)


def test_paired_prediction_artifacts_are_not_double_counted(tmp_path):
    run = tmp_path / "prediction"
    run.mkdir()
    payload = [
        {
            "nuclide_id": "Z120-N184",
            "Z": 120,
            "N": 184,
            "A": 304,
            "model_id": "semf_gp",
            "frontier_mode": True,
            "benchmark_id": "EZ-B001",
        }
    ]
    (run / "certificates.json").write_text(json.dumps(payload), encoding="utf-8")
    (run / "predictions.json").write_text(json.dumps(payload), encoding="utf-8")
    events, _health, _hashes = extract_events(tmp_path)
    frontier = [event for event in events if event.event_type == "FRONTIER_PREDICTION_CREATED"]
    assert len(frontier) == 1


def test_candidate_island_not_inferred_from_frontier(tmp_path):
    _copy(FIXTURES / "visuals" / "frontier", tmp_path / "frontier")
    events, _health, _hashes = extract_events(tmp_path)
    assert any(event.event_type == "FRONTIER_PREDICTION_CREATED" for event in events)
    assert all(event.event_type != "CANDIDATE_ISLAND_MARKED" for event in events)
    island_path = tmp_path / "not_an_island.json"
    island_path.write_text('{"elements": [120], "note": "prediction only"}\n')
    assert extract_island(island_path, root=tmp_path) == []
