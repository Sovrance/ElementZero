"""WO-11.3 — failure records enforce the frozen schema and class list."""

from __future__ import annotations

import json

import pytest

from elementzero.adjudication.failure_taxonomy import (
    ALLOWED_PRIMARY_CLASSES,
    REQUIRED_FIELDS,
    validate_failure_record,
)
from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import SchemaError

SCHEMA = REPO_ROOT / "schemas" / "wo11_failure_record.schema.json"
COMMITTED = REPO_ROOT / "reports" / "adjudication" / "wo11" / "failure_records.json"


def _valid_record() -> dict:
    return {
        "failure_id": "WO11-F-TEST-1",
        "benchmark_id": "EZ-B003",
        "protocol_version": "1.0.0",
        "model_id": "EZ-SEMF-LS-v1",
        "criterion_id": "ez-b003-rediscovery-criterion-v1:sign_fraction",
        "observed_value": 0.4,
        "frozen_threshold": 0.75,
        "primary_class": "MODEL_BIAS",
        "secondary_classes": ["UNCERTAINTY_UNDERCOVERAGE"],
        "evidence": [{"source": "test", "observation": "unit fixture"}],
        "confidence": "HIGH",
        "requires_protocol_change": False,
        "notes": "unit fixture",
    }


def test_failure_record_schema():
    """The code validator and the committed JSON schema agree exactly."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert tuple(schema["required"]) == REQUIRED_FIELDS
    assert schema["additionalProperties"] is False
    assert tuple(schema["properties"]["primary_class"]["enum"]) == ALLOWED_PRIMARY_CLASSES
    validate_failure_record(_valid_record())
    for field in REQUIRED_FIELDS:
        broken = _valid_record()
        del broken[field]
        with pytest.raises(SchemaError):
            validate_failure_record(broken)
    extra = _valid_record()
    extra["surprise"] = True
    with pytest.raises(SchemaError):
        validate_failure_record(extra)


def test_unknown_failure_class_rejected():
    record = _valid_record()
    record["primary_class"] = "COSMIC_RAYS"
    with pytest.raises(SchemaError):
        validate_failure_record(record)
    record = _valid_record()
    record["secondary_classes"] = ["NOT_A_CLASS"]
    with pytest.raises(SchemaError):
        validate_failure_record(record)
    record = _valid_record()
    record["confidence"] = "ABSOLUTE"
    with pytest.raises(SchemaError):
        validate_failure_record(record)


def test_committed_records_validate_and_stay_honest():
    payload = json.loads(COMMITTED.read_text(encoding="utf-8"))
    records = payload["records"]
    assert records, "WO-11 must record the frozen failures"
    for record in records:
        validate_failure_record(record)
    # Every failed frozen EZ-B003 check appears exactly once.
    b003_ids = sorted(r["failure_id"] for r in records if r["benchmark_id"] == "EZ-B003")
    assert b003_ids == sorted(
        [
            "WO11-F-B003-EZ-SEMF-LS-v1-sign_fraction",
            "WO11-F-B003-EZ-SEMF-LS-v1-top_k_fraction",
            "WO11-F-B003-EZ-SEMF-LS-v1-rank_1_fraction",
            "WO11-F-B003-EZ-SEMF-LS-v1-calibration_error_90",
            "WO11-F-B003-EZ-GP-DIRECT-v1-top_k_fraction",
            "WO11-F-B003-EZ-GP-DIRECT-v1-rank_1_fraction",
            "WO11-F-B003-EZ-SEMF-GP-RESIDUAL-v1-rank_1_fraction",
        ]
    )
    # EZ-B002-v1 froze no threshold, so its records must say so instead of
    # inventing one.
    for record in records:
        if record["benchmark_id"] == "EZ-B002":
            assert record["frozen_threshold"] is None
        else:
            assert record["frozen_threshold"] is not None
        assert record["requires_protocol_change"] is False
