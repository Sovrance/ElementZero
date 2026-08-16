"""Extract visual events from tests, AME tables, and benchmark artifacts."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from elementzero import __version__
from elementzero.data.amdc import EDITIONS, load_edition
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import VisualError
from elementzero.evidence.hashing import sha256_file
from elementzero.visuals.event_types import (
    MAX_Z,
    MIN_Z,
    ProgressEvent,
    make_event_id,
    validate_event,
)

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "scaffold",
    "reference",
}
# Never treat committed software-smoke trees as published visual inputs.
SKIP_ROOT_PREFIXES = ("tests", "docs", "scaffold", "reference")
UNSPECIFIED_TIME = "1970-01-01T00:00:00Z"
PROJECT_SUITE_Z = 1


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VisualError(f"malformed JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise VisualError(f"failed to read {path}: {exc}") from exc


def _iter_files(root: Path) -> Iterable[Path]:
    root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            relative = path.resolve().relative_to(root)
        except ValueError:
            continue
        if relative.parts and relative.parts[0] in SKIP_ROOT_PREFIXES:
            continue
        if any(part in SKIP_DIR_NAMES for part in relative.parts):
            continue
        yield path


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _event(
    *,
    event_type: str,
    source_kind: str,
    source_path: str,
    source_hash: str,
    element_Z: int,
    status: str,
    event_time: str = UNSPECIFIED_TIME,
    benchmark_id: str | None = None,
    benchmark_stage: str | None = None,
    model_id: str | None = None,
    nuclide_id: str | None = None,
    payload: dict[str, Any] | None = None,
    extra: str = "",
) -> ProgressEvent:
    if element_Z < MIN_Z or element_Z > MAX_Z:
        raise VisualError(f"event references Z outside 1..200: {element_Z}")
    event = ProgressEvent(
        event_id=make_event_id(
            event_type=event_type,
            source_hash=source_hash,
            element_Z=element_Z,
            nuclide_id=nuclide_id,
            benchmark_id=benchmark_id,
            extra=extra,
        ),
        event_type=event_type,
        event_time=event_time,
        project_version=__version__,
        source_kind=source_kind,
        source_path=source_path,
        source_hash=source_hash,
        element_Z=element_Z,
        status=status,
        benchmark_id=benchmark_id,
        benchmark_stage=benchmark_stage,
        model_id=model_id,
        nuclide_id=nuclide_id,
        payload=payload or {},
    )
    validate_event(event)
    return event


def _z_from_record(record: dict[str, Any]) -> int:
    if "Z" in record:
        return int(record["Z"])
    if "element_Z" in record:
        return int(record["element_Z"])
    nuclide_id = record.get("nuclide_id")
    if isinstance(nuclide_id, str):
        z, _n = parse_nuclide_id(nuclide_id)
        return z
    raise VisualError(f"record has no Z or nuclide_id: {record!r}")


def _edition_from_name(path: Path) -> str | None:
    name = path.name.lower()
    mapping = (
        ("ame2003", "AME2003"),
        ("ame2012", "AME2012"),
        ("ame2016", "AME2016"),
        ("ame2020", "AME2020"),
        (".mas03", "AME2003"),
        (".mas12", "AME2012"),
        (".mas16", "AME2016"),
        (".mas20", "AME2020"),
    )
    for needle, edition in mapping:
        if needle in name:
            return edition
    return None


def extract_ame_events(path: Path, *, root: Path) -> list[ProgressEvent]:
    edition = _edition_from_name(path)
    if edition is None or edition not in EDITIONS:
        return []
    digest = sha256_file(path)
    rel = _rel(root, path)
    events: list[ProgressEvent] = []
    for obs in load_edition(edition, str(path)):
        if not obs.ground_truth_eligible:
            continue
        # Neutrons (Z=0) and other non-element rows are outside the visual table.
        if obs.Z < MIN_Z or obs.Z > MAX_Z:
            continue
        events.append(
            _event(
                event_type="DATA_INGESTED",
                source_kind="ame_table",
                source_path=rel,
                source_hash=digest,
                element_Z=obs.Z,
                status="ingested",
                benchmark_stage="data",
                nuclide_id=obs.nuclide_id,
                payload={"edition_id": edition, "source_record_status": obs.source_record_status},
            )
        )
    return events


def _classify_nodeid(nodeid: str) -> str:
    lowered = nodeid.replace("\\", "/")
    if "/leakage/" in lowered or lowered.startswith("tests/leakage/"):
        return "leakage"
    if "/integration/" in lowered or lowered.startswith("tests/integration/"):
        return "integration"
    if "/unit/" in lowered or lowered.startswith("tests/unit/"):
        return "unit"
    return "other"


def extract_pytest_report(path: Path, *, root: Path) -> tuple[list[ProgressEvent], dict[str, str]]:
    payload = _read_json(path)
    digest = sha256_file(path)
    rel = _rel(root, path)
    created = payload.get("created")
    event_time = str(created) if created else UNSPECIFIED_TIME
    tests = payload.get("tests") or []
    buckets = {"unit": [], "integration": [], "leakage": [], "other": []}
    for test in tests:
        nodeid = str(test.get("nodeid") or test.get("name") or "")
        outcome = str(test.get("outcome") or test.get("status") or "unknown")
        buckets[_classify_nodeid(nodeid)].append(outcome)
    exitcode = int(payload.get("exitcode", 1 if payload.get("summary", {}).get("failed") else 0))
    health = _health_from_buckets(buckets, overall_fail=exitcode != 0)
    events = _suite_events(
        health,
        source_kind="pytest_report",
        source_path=rel,
        source_hash=digest,
        event_time=event_time,
    )
    return events, health


def extract_junit(path: Path, *, root: Path) -> tuple[list[ProgressEvent], dict[str, str]]:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise VisualError(f"malformed JUnit XML in {path}: {exc}") from exc
    digest = sha256_file(path)
    rel = _rel(root, path)
    buckets = {"unit": [], "integration": [], "leakage": [], "other": []}
    overall_fail = False
    for case in tree.iter("testcase"):
        classname = case.get("classname") or ""
        name = case.get("name") or ""
        nodeid = f"{classname}/{name}"
        failed = case.find("failure") is not None or case.find("error") is not None
        if failed:
            overall_fail = True
        buckets[_classify_nodeid(nodeid.replace(".", "/"))].append("failed" if failed else "passed")
    health = _health_from_buckets(buckets, overall_fail=overall_fail)
    events = _suite_events(
        health,
        source_kind="junit",
        source_path=rel,
        source_hash=digest,
        event_time=UNSPECIFIED_TIME,
    )
    return events, health


def _health_from_buckets(buckets: dict[str, list[str]], *, overall_fail: bool) -> dict[str, str]:
    def bucket_status(name: str) -> str:
        outcomes = buckets.get(name) or []
        if not outcomes:
            return "unknown"
        fail_words = {"failed", "fail", "error", "failed"}
        if any(str(item).lower() in fail_words for item in outcomes):
            return "fail"
        return "pass"

    unit = bucket_status("unit")
    integration = bucket_status("integration")
    leakage = bucket_status("leakage")
    overall = "fail" if overall_fail or "fail" in {unit, integration, leakage} else (
        "pass" if any(value == "pass" for value in (unit, integration, leakage)) else "unknown"
    )
    return {
        "overall": overall,
        "unit": unit,
        "integration": integration,
        "leakage": leakage,
        "benchmark": "unknown",
    }


def _suite_events(
    health: dict[str, str],
    *,
    source_kind: str,
    source_path: str,
    source_hash: str,
    event_time: str,
) -> list[ProgressEvent]:
    events: list[ProgressEvent] = []
    for suite in ("unit", "integration", "leakage", "overall"):
        status = health[suite]
        if status == "unknown":
            continue
        event_type = "TEST_SUITE_PASS" if status == "pass" else "TEST_SUITE_FAIL"
        events.append(
            _event(
                event_type=event_type,
                source_kind=source_kind,
                source_path=source_path,
                source_hash=source_hash,
                element_Z=PROJECT_SUITE_Z,
                status=status,
                event_time=event_time,
                extra=suite,
                payload={"suite": suite},
            )
        )
    return events


def extract_targets(
    path: Path,
    *,
    root: Path,
    event_type: str,
    benchmark_id: str,
    benchmark_stage: str,
) -> list[ProgressEvent]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise VisualError(f"malformed target manifest {path}: expected object")
    records = payload.get("targets")
    if records is None:
        records = payload.get("nuclides") or payload.get("elements")
    if not isinstance(records, list):
        raise VisualError(f"malformed target manifest {path}: missing targets list")
    digest = sha256_file(path)
    rel = _rel(root, path)
    events: list[ProgressEvent] = []
    for record in records:
        if not isinstance(record, dict):
            raise VisualError(f"malformed target record in {path}: {record!r}")
        z = _z_from_record(record)
        events.append(
            _event(
                event_type=event_type,
                source_kind="targets",
                source_path=rel,
                source_hash=digest,
                element_Z=z,
                status="targeted",
                benchmark_id=str(payload.get("benchmark_id") or benchmark_id),
                benchmark_stage=benchmark_stage,
                nuclide_id=record.get("nuclide_id"),
            )
        )
    return events


def extract_score_rows(
    path: Path,
    *,
    root: Path,
    event_type: str,
    benchmark_id: str,
    benchmark_stage: str,
) -> list[ProgressEvent]:
    payload = _read_json(path)
    if isinstance(payload, list):
        rows = payload
        meta: dict[str, Any] = {}
    elif isinstance(payload, dict):
        rows = payload.get("rows") or payload.get("predictions") or payload.get("scored")
        if rows is None and "nuclide_id" in payload:
            rows = [payload]
        meta = payload
    else:
        raise VisualError(f"malformed score artifact {path}")
    if not isinstance(rows, list):
        raise VisualError(f"malformed score artifact {path}: missing rows")
    digest = sha256_file(path)
    rel = _rel(root, path)
    model_id = meta.get("model_id")
    bench = str(meta.get("benchmark_id") or benchmark_id)
    events: list[ProgressEvent] = []
    for row in rows:
        if not isinstance(row, dict):
            raise VisualError(f"malformed score row in {path}: {row!r}")
        z = _z_from_record(row)
        pred = row.get("prediction_keV")
        truth = row.get("truth_keV")
        abs_error = row.get("abs_error_keV")
        if abs_error is None and pred is not None and truth is not None:
            abs_error = abs(float(pred) - float(truth))
        events.append(
            _event(
                event_type=event_type,
                source_kind="score_report",
                source_path=rel,
                source_hash=digest,
                element_Z=z,
                status="scored",
                benchmark_id=bench,
                benchmark_stage=benchmark_stage,
                model_id=model_id,
                nuclide_id=row.get("nuclide_id"),
                payload={
                    "abs_error_keV": abs_error,
                    "interval_hit_90": row.get("interval_hit_90"),
                    "interval_hit_95": row.get("interval_hit_95"),
                    "nearest_training_L1": row.get("nearest_training_L1"),
                },
            )
        )
    return events


def extract_certificates(path: Path, *, root: Path, sealed: bool) -> list[ProgressEvent]:
    payload = _read_json(path)
    records = payload if isinstance(payload, list) else payload.get("certificates")
    if not isinstance(records, list):
        raise VisualError(f"malformed certificates artifact {path}")
    digest = sha256_file(path)
    rel = _rel(root, path)
    events: list[ProgressEvent] = []
    for cert in records:
        if not isinstance(cert, dict):
            raise VisualError(f"malformed certificate in {path}")
        z = _z_from_record(cert)
        ledger = str(cert.get("ledger_state") or "")
        is_sealed = sealed or ledger.lower() in {"finalized", "ledger_finalized", "sealed"}
        frontier = z > 118 or bool(cert.get("frontier_mode"))
        if frontier:
            event_type = "FRONTIER_PREDICTION_CREATED"
            status = "predicted"
            stage = "frontier"
        elif is_sealed:
            event_type = "HISTORICAL_PREDICTION_SEALED"
            status = "sealed"
            stage = "finalize"
        else:
            continue
        events.append(
            _event(
                event_type=event_type,
                source_kind="certificates",
                source_path=rel,
                source_hash=digest,
                element_Z=z,
                status=status,
                benchmark_id=cert.get("benchmark_id"),
                benchmark_stage=stage,
                model_id=cert.get("model_id"),
                nuclide_id=cert.get("nuclide_id"),
                event_time=str(cert.get("created_at") or UNSPECIFIED_TIME),
            )
        )
    return events


def extract_predictions(path: Path, *, root: Path, sealed: bool) -> list[ProgressEvent]:
    payload = _read_json(path)
    records = payload if isinstance(payload, list) else payload.get("predictions")
    if not isinstance(records, list):
        raise VisualError(f"malformed predictions artifact {path}")
    digest = sha256_file(path)
    rel = _rel(root, path)
    events: list[ProgressEvent] = []
    for pred in records:
        if not isinstance(pred, dict):
            raise VisualError(f"malformed prediction in {path}")
        z = _z_from_record(pred)
        frontier = z > 118 or bool(pred.get("frontier_mode"))
        if frontier:
            event_type = "FRONTIER_PREDICTION_CREATED"
            status = "predicted"
            stage = "frontier"
        elif sealed:
            event_type = "HISTORICAL_PREDICTION_SEALED"
            status = "sealed"
            stage = "finalize"
        else:
            continue
        events.append(
            _event(
                event_type=event_type,
                source_kind="predictions",
                source_path=rel,
                source_hash=digest,
                element_Z=z,
                status=status,
                benchmark_id=pred.get("benchmark_id"),
                benchmark_stage=stage,
                model_id=pred.get("model_id"),
                nuclide_id=pred.get("nuclide_id"),
            )
        )
    return events


def extract_island(path: Path, *, root: Path) -> list[ProgressEvent]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise VisualError(f"malformed island governance file {path}")
    explicit = payload.get("event_type") == "CANDIDATE_ISLAND_MARKED" or payload.get("explicit_island_focus") is True
    if not explicit:
        return []
    digest = sha256_file(path)
    rel = _rel(root, path)
    zs = payload.get("elements") or payload.get("element_Z_list") or []
    if "element_Z" in payload and not zs:
        zs = [payload["element_Z"]]
    if not zs and "nuclide_id" in payload:
        zs = [_z_from_record(payload)]
    events: list[ProgressEvent] = []
    for z in zs:
        z_int = int(z)
        events.append(
            _event(
                event_type="CANDIDATE_ISLAND_MARKED",
                source_kind="island_governance",
                source_path=rel,
                source_hash=digest,
                element_Z=z_int,
                status="marked",
                benchmark_id=payload.get("region_id"),
                benchmark_stage="governance",
                payload={
                    "region_id": payload.get("region_id"),
                    "rationale": payload.get("rationale"),
                    "supporting_models": payload.get("supporting_models") or [],
                    "supporting_run_ids": payload.get("supporting_run_ids") or [],
                    "review_status": payload.get("review_status"),
                },
            )
        )
    return events


def _benchmark_kind(path: Path, payload_hint: str | None = None) -> str:
    text = f"{path.as_posix()}|{payload_hint or ''}".upper()
    if "EZ-B003" in text or "B003" in text or "SHELL" in text:
        return "shell"
    if "EZ-B002" in text or "B002" in text or "REGION" in text:
        return "region"
    if "EZ-B001" in text or "B001" in text:
        return "historical"
    return "historical"


def extract_events(input_root: str | Path) -> tuple[list[ProgressEvent], dict[str, str], dict[str, str]]:
    root = Path(input_root)
    if not root.exists():
        raise VisualError(f"input root does not exist: {root}")
    events: list[ProgressEvent] = []
    input_hashes: dict[str, str] = {}
    health = {
        "overall": "unknown",
        "unit": "unknown",
        "integration": "unknown",
        "leakage": "unknown",
        "benchmark": "unknown",
    }

    preferred_pytest = [
        root / ".artifacts" / "tests" / "pytest-report.json",
    ]
    preferred_junit = [
        root / ".artifacts" / "tests" / "junit.xml",
    ]

    report_consumed = False
    for path in preferred_pytest:
        if path.is_file():
            suite_events, health = extract_pytest_report(path, root=root)
            events.extend(suite_events)
            input_hashes[_rel(root, path)] = sha256_file(path)
            report_consumed = True
            break
    if not report_consumed:
        for path in preferred_junit:
            if path.is_file():
                suite_events, health = extract_junit(path, root=root)
                events.extend(suite_events)
                input_hashes[_rel(root, path)] = sha256_file(path)
                report_consumed = True
                break

    for path in _iter_files(root):
        name = path.name
        rel = _rel(root, path)
        if name.endswith((".txt", ".mas03", ".mas12", ".mas16", ".mas20")) and _edition_from_name(path):
            ame_events = extract_ame_events(path, root=root)
            if ame_events:
                events.extend(ame_events)
                input_hashes[rel] = sha256_file(path)
            continue
        if name in {"pytest-report.json", "junit.xml"} and report_consumed:
            continue
        if name == "pytest-report.json":
            suite_events, health = extract_pytest_report(path, root=root)
            events.extend(suite_events)
            input_hashes[rel] = sha256_file(path)
            report_consumed = True
            continue
        if name == "junit.xml" and not report_consumed:
            suite_events, health = extract_junit(path, root=root)
            events.extend(suite_events)
            input_hashes[rel] = sha256_file(path)
            report_consumed = True
            continue
        if name in {"candidate_island.json", "island_focus.json"} or name.startswith("candidate_island"):
            island_events = extract_island(path, root=root)
            events.extend(island_events)
            if island_events:
                input_hashes[rel] = sha256_file(path)
            continue
        if name == "targets.json":
            kind = _benchmark_kind(path)
            event_type = {
                "historical": "HISTORICAL_TARGET_CREATED",
                "region": "REGION_TARGET_CREATED",
                "shell": "SHELL_TARGET_CREATED",
            }[kind]
            bench = {"historical": "EZ-B001", "region": "EZ-B002", "shell": "EZ-B003"}[kind]
            events.extend(
                extract_targets(
                    path,
                    root=root,
                    event_type=event_type,
                    benchmark_id=bench,
                    benchmark_stage="prepare",
                )
            )
            input_hashes[rel] = sha256_file(path)
            continue
        if name == "regions.json":
            # Demo fixtures carry an explicit targets list. Preregistered EZ-B002
            # region registries list geometry only; per-region targets.json files
            # under regions/<id>/ are the published nuclide inputs.
            payload = _read_json(path)
            if isinstance(payload, dict) and isinstance(payload.get("targets"), list):
                events.extend(
                    extract_targets(
                        path,
                        root=root,
                        event_type="REGION_TARGET_CREATED",
                        benchmark_id="EZ-B002",
                        benchmark_stage="prepare",
                    )
                )
                input_hashes[rel] = sha256_file(path)
            elif isinstance(payload, dict) and isinstance(payload.get("regions"), list):
                input_hashes[rel] = sha256_file(path)
            else:
                raise VisualError(
                    f"malformed region registry {path}: expected targets or regions list"
                )
            continue
        if name in {"scored_predictions.json", "score_report.json"}:
            kind = _benchmark_kind(path)
            event_type = {
                "historical": "HISTORICAL_VALIDATION_SCORED",
                "region": "REGION_VALIDATION_SCORED",
                "shell": "SHELL_VALIDATION_SCORED",
            }[kind]
            bench = {"historical": "EZ-B001", "region": "EZ-B002", "shell": "EZ-B003"}[kind]
            events.extend(
                extract_score_rows(path, root=root, event_type=event_type, benchmark_id=bench, benchmark_stage="score")
            )
            input_hashes[rel] = sha256_file(path)
            health["benchmark"] = "pass"
            continue
        if name == "certificates.json":
            sealed = (path.parent / "LEDGER_FINALIZED").exists() or (path.parent / "LEDGER_FINALIZED.json").exists()
            events.extend(extract_certificates(path, root=root, sealed=sealed))
            input_hashes[rel] = sha256_file(path)
            continue
        if name == "predictions.json":
            if (path.parent / "certificates.json").is_file():
                # predict_run writes both files for the same nuclides; certificates are canonical.
                continue
            sealed = (path.parent / "LEDGER_FINALIZED").exists() or (path.parent / "LEDGER_FINALIZED.json").exists()
            pred_events = extract_predictions(path, root=root, sealed=sealed)
            if pred_events:
                events.extend(pred_events)
                input_hashes[rel] = sha256_file(path)
            continue

    events.sort(key=lambda ev: (ev.event_type, ev.element_Z, ev.nuclide_id or "", ev.event_id))
    return events, health, input_hashes


def write_events_jsonl(events: Iterable[ProgressEvent], path: str | Path) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(validate_event(event), sort_keys=True, separators=(",", ":")) for event in events]
    dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return dest


def read_events_jsonl(path: str | Path) -> list[ProgressEvent]:
    events: list[ProgressEvent] = []
    text = Path(path).read_text(encoding="utf-8")
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise VisualError(f"malformed event JSONL {path}:{index}: {exc}") from exc
        validate_event(payload)
        events.append(ProgressEvent(**payload))
    return events
