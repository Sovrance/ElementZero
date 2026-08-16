"""Normalized visual progress events."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from elementzero.errors import VisualError
from elementzero.evidence.hashing import content_id

EVENT_TYPES = (
    "TEST_SUITE_PASS",
    "TEST_SUITE_FAIL",
    "DATA_INGESTED",
    "HISTORICAL_TARGET_CREATED",
    "HISTORICAL_PREDICTION_SEALED",
    "HISTORICAL_VALIDATION_SCORED",
    "REGION_TARGET_CREATED",
    "REGION_VALIDATION_SCORED",
    "SHELL_TARGET_CREATED",
    "SHELL_VALIDATION_SCORED",
    "FRONTIER_PREDICTION_CREATED",
    "CANDIDATE_ISLAND_MARKED",
    # WO-12 federation events. Qualification-only: none of these maps to a
    # validated tile stage, and FEDERATION_QUALIFICATION_SCORED is excluded
    # from the benchmark-health shortcut (a qualification run is rehearsal,
    # not a validated benchmark result).
    "FEDERATION_MODEL_AVAILABLE",
    "FEDERATION_QUALIFICATION_TARGETED",
    "FEDERATION_QUALIFICATION_SCORED",
)

QUALIFICATION_EVENT_TYPES = frozenset(
    {
        "FEDERATION_MODEL_AVAILABLE",
        "FEDERATION_QUALIFICATION_TARGETED",
        "FEDERATION_QUALIFICATION_SCORED",
    }
)

SUITE_EVENT_TYPES = frozenset({"TEST_SUITE_PASS", "TEST_SUITE_FAIL"})
MIN_Z = 1
MAX_Z = 200


@dataclass(frozen=True)
class ProgressEvent:
    event_id: str
    event_type: str
    event_time: str
    project_version: str
    source_kind: str
    source_path: str
    source_hash: str
    element_Z: int
    status: str
    benchmark_id: str | None = None
    benchmark_stage: str | None = None
    model_id: str | None = None
    nuclide_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event_id(
    *,
    event_type: str,
    source_hash: str,
    element_Z: int,
    nuclide_id: str | None = None,
    benchmark_id: str | None = None,
    extra: str = "",
) -> str:
    return content_id(
        "evt",
        {
            "event_type": event_type,
            "source_hash": source_hash,
            "element_Z": element_Z,
            "nuclide_id": nuclide_id or "",
            "benchmark_id": benchmark_id or "",
            "extra": extra,
        },
    )


def validate_event(event: ProgressEvent | dict[str, Any]) -> dict[str, Any]:
    data = event.to_dict() if isinstance(event, ProgressEvent) else dict(event)
    required = (
        "event_id",
        "event_type",
        "event_time",
        "project_version",
        "source_kind",
        "source_path",
        "source_hash",
        "element_Z",
        "status",
    )
    missing = [key for key in required if key not in data or data[key] in (None, "")]
    if missing:
        raise VisualError(f"malformed visual event missing {missing}: {data!r}")
    if data["event_type"] not in EVENT_TYPES:
        raise VisualError(f"unknown visual event_type {data['event_type']!r}")
    z = data["element_Z"]
    if not isinstance(z, int) or isinstance(z, bool) or z < MIN_Z or z > MAX_Z:
        raise VisualError(f"event references Z outside 1..200: {z!r}")
    return data
