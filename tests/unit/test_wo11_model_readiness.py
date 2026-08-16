"""WO-11.10 — the readiness verdict is deterministic and candidates are traceable."""

from __future__ import annotations

import json

import pytest

from elementzero.adjudication import (
    VERDICT_BENCHMARK_REPAIR_REQUIRED,
    VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED,
    VERDICT_JUSTIFIED,
    VERDICT_NOT_YET_JUSTIFIED,
)
from elementzero.adjudication.model_readiness import (
    build_frontier_registry,
    frontier_candidates,
    readiness_verdict,
    validate_frontier_candidate,
)
from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import SchemaError
from elementzero.evidence.hashing import canonical_json

COMMITTED_REGISTRY = (
    REPO_ROOT / "reports" / "adjudication" / "wo11" / "frontier_model_candidates.json"
)
COMMITTED_READINESS = REPO_ROOT / "reports" / "adjudication" / "wo11" / "model_readiness.json"


def _inputs(**overrides):
    base = {
        "inventory": {"all_unchanged": True},
        "replay": {"replay_status": "PASS"},
        "controls": {"benchmark_control_status": "PASS"},
        "failure_records": {
            "records": [
                {
                    "failure_id": "WO11-F-B003-x",
                    "benchmark_id": "EZ-B003",
                    "primary_class": "MODEL_BIAS",
                },
                {
                    "failure_id": "WO11-F-B002-x",
                    "benchmark_id": "EZ-B002",
                    "primary_class": "UNCERTAINTY_OVERCOVERAGE",
                },
            ]
        },
    }
    base.update(overrides)
    return base


def test_readiness_verdict_deterministic():
    first = readiness_verdict(**_inputs())
    second = readiness_verdict(**_inputs())
    assert canonical_json(first) == canonical_json(second)
    assert first["model_readiness_verdict"] == VERDICT_JUSTIFIED


def test_verdict_precedence():
    tampered = readiness_verdict(**_inputs(inventory={"all_unchanged": False}))
    assert tampered["model_readiness_verdict"] == VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED

    broken_replay = readiness_verdict(**_inputs(replay={"replay_status": "FAIL"}))
    assert broken_replay["model_readiness_verdict"] == VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED

    broken_controls = readiness_verdict(
        **_inputs(controls={"benchmark_control_status": "FAIL"})
    )
    assert broken_controls["model_readiness_verdict"] == VERDICT_BENCHMARK_REPAIR_REQUIRED

    indeterminate = readiness_verdict(
        **_inputs(controls={"benchmark_control_status": "INDETERMINATE"})
    )
    assert indeterminate["model_readiness_verdict"] == VERDICT_NOT_YET_JUSTIFIED

    defect = readiness_verdict(
        **_inputs(
            failure_records={
                "records": [
                    {
                        "failure_id": "WO11-F-B003-defect",
                        "benchmark_id": "EZ-B003",
                        "primary_class": "IMPLEMENTATION_DEFECT",
                    }
                ]
            }
        )
    )
    assert defect["model_readiness_verdict"] == VERDICT_NOT_YET_JUSTIFIED

    indeterminate_cause = readiness_verdict(
        **_inputs(
            failure_records={
                "records": [
                    {
                        "failure_id": "WO11-F-B003-unknown",
                        "benchmark_id": "EZ-B003",
                        "primary_class": "INDETERMINATE",
                    }
                ]
            }
        )
    )
    assert indeterminate_cause["model_readiness_verdict"] == VERDICT_NOT_YET_JUSTIFIED


def test_frontier_candidate_requires_source():
    candidate = dict(frontier_candidates()[0])
    candidate["source_url"] = "  "
    with pytest.raises(SchemaError):
        validate_frontier_candidate(candidate)
    candidate = dict(frontier_candidates()[0])
    candidate["publication"] = ""
    with pytest.raises(SchemaError):
        validate_frontier_candidate(candidate)
    missing = dict(frontier_candidates()[0])
    del missing["source_url"]
    with pytest.raises(SchemaError):
        validate_frontier_candidate(missing)


def test_registry_matches_schema_and_committed_file():
    schema = json.loads(
        (REPO_ROOT / "schemas" / "frontier_model_candidate.schema.json").read_text(
            encoding="utf-8"
        )
    )
    required = set(schema["required"])
    for candidate in frontier_candidates():
        assert set(candidate) == required
        assert candidate["recommended_role"] in schema["properties"]["recommended_role"]["enum"]
        assert candidate["status"] in schema["properties"]["status"]["enum"]
    committed = json.loads(COMMITTED_REGISTRY.read_text(encoding="utf-8"))
    assert committed == json.loads(canonical_json(build_frontier_registry()))


def test_committed_verdict_is_justified_with_prerequisites():
    readiness = json.loads(COMMITTED_READINESS.read_text(encoding="utf-8"))
    assert readiness["model_readiness_verdict"] == VERDICT_JUSTIFIED
    assert readiness["next_work_order"] == "WO-12 - Nuclear Model Federation v1"
    assert len(readiness["wo12_prerequisites"]) >= 5
