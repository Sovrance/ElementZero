"""Append-only prediction ledger with an immutable finalization marker."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_hex

LEDGER_MARKER = "LEDGER_FINALIZED"
LEDGER_FILENAME = "LEDGER_FINALIZED"
PREDICTIONS_NAME = "predictions.json"
CERTIFICATES_NAME = "certificates.json"
MANIFEST_NAME = "run_manifest.json"
MODEL_MANIFEST_NAME = "model_manifest.json"
FREEZE_NAME = "freeze.json"


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = canonical_json(payload)
    if path.exists() and is_finalized(path.parent if path.name != LEDGER_FILENAME else path.parent):
        # Prediction artifacts live in the run directory.
        run_dir = path.parent
        if is_finalized(run_dir) and path.name != LEDGER_FILENAME:
            raise ProtocolError(f"prediction ledger is finalized; cannot rewrite {path}")
    path.write_text(text + "\n", encoding="utf-8")
    return sha256_hex(text.encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_finalized(run_dir: Path) -> bool:
    return (Path(run_dir) / LEDGER_FILENAME).is_file()


def artifact_paths(run_dir: Path) -> dict[str, Path]:
    run_dir = Path(run_dir)
    return {
        "predictions": run_dir / PREDICTIONS_NAME,
        "certificates": run_dir / CERTIFICATES_NAME,
        "run_manifest": run_dir / MANIFEST_NAME,
        "model_manifest": run_dir / MODEL_MANIFEST_NAME,
        "freeze": run_dir / FREEZE_NAME,
    }


def hash_existing_artifacts(run_dir: Path) -> dict[str, str]:
    hashes = {}
    for name, path in artifact_paths(run_dir).items():
        if path.is_file():
            hashes[name] = sha256_hex(path.read_bytes().rstrip(b"\n"))
    return hashes


def finalize_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    if is_finalized(run_dir):
        raise ProtocolError(f"run {run_dir} is already finalized")
    missing = [name for name, path in artifact_paths(run_dir).items() if not path.is_file()]
    if missing:
        raise ProtocolError(f"cannot finalize; missing artifacts: {missing}")
    hashes = hash_existing_artifacts(run_dir)
    marker = {
        "marker": LEDGER_MARKER,
        "artifact_hashes": hashes,
    }
    marker_path = run_dir / LEDGER_FILENAME
    marker_path.write_text(canonical_json(marker) + "\n", encoding="utf-8")
    return marker


def finalization_marker_hash(run_dir: Path) -> str:
    """Hash of the immutable LEDGER_FINALIZED marker itself."""
    path = Path(run_dir) / LEDGER_FILENAME
    if not path.is_file():
        raise ProtocolError("prediction ledger was not finalized")
    return sha256_hex(path.read_bytes().rstrip(b"\n"))


def load_finalization(run_dir: Path) -> dict[str, Any]:
    path = Path(run_dir) / LEDGER_FILENAME
    if not path.is_file():
        raise ProtocolError("prediction ledger was not finalized")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_finalized_intact(run_dir: Path) -> dict[str, Any]:
    marker = load_finalization(run_dir)
    current = hash_existing_artifacts(run_dir)
    expected = marker.get("artifact_hashes", {})
    if current != expected:
        raise LeakageError("prediction artifacts still do not match finalization hashes")
    return marker


def refuse_rewrite(run_dir: Path, path: Path) -> None:
    if is_finalized(run_dir):
        raise ProtocolError(f"prediction modified after finalization is forbidden: {path}")


def write_run_artifact(run_dir: Path, name: str, payload: Any) -> str:
    run_dir = Path(run_dir)
    if is_finalized(run_dir):
        raise ProtocolError("prediction ledger is finalized; any rerun must use a new run ID")
    paths = artifact_paths(run_dir)
    if name not in paths:
        raise ProtocolError(f"unknown run artifact {name!r}")
    return write_json(paths[name], payload)


def scientific_artifact_digest(payloads: Iterable[Mapping[str, Any]]) -> str:
    return sha256_hex([dict(p) for p in payloads])
