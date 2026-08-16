"""Seal one EZ-B003 shell run before any hidden closure truth is read.

Finalization is the same operation as EZ-B001 and EZ-B002 (an immutable
``LEDGER_FINALIZED`` marker plus an Atlas FinalizationFact), so the sealing logic
is reused rather than re-implemented. What this stage adds is the EZ-B003
identity check: a run that does not declare a shell mask and a benchmark profile
is not a hidden-shell run and must not be sealed as one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_EZ_B003
from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b003_prepare import PROFILES
from elementzero.errors import ProtocolError
from elementzero.evidence.ledger import read_json

REQUIRED_RUN_MANIFEST_FIELDS = (
    "challenge_id",
    "mask_id",
    "mask_hash",
    "challenge_manifest_hash",
    "profile",
    "split_digest",
    "prediction_set_fact_id",
    "shell_hypothesis_fact_id",
)


def finalize_shell_run(run_dir: str | Path, *, created_at: str | None = None) -> dict[str, Any]:
    """Verify the run is an EZ-B003 hidden-shell run, then seal it."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise ProtocolError(f"run {run_dir} has no run manifest; predict before finalizing")
    manifest = read_json(manifest_path)
    if manifest.get("benchmark_id") != BENCHMARK_EZ_B003:
        raise ProtocolError(
            f"run {run_dir} declares benchmark {manifest.get('benchmark_id')!r}, "
            f"not {BENCHMARK_EZ_B003}"
        )
    missing = [field for field in REQUIRED_RUN_MANIFEST_FIELDS if not manifest.get(field)]
    if missing:
        raise ProtocolError(f"EZ-B003 run manifest is missing fields: {missing}")
    if manifest["profile"] not in PROFILES:
        raise ProtocolError(
            f"run {run_dir} declares profile {manifest['profile']!r}; "
            f"supported profiles are {list(PROFILES)}"
        )
    marker = finalize(run_dir, created_at=created_at)
    return {
        **marker,
        "benchmark_id": BENCHMARK_EZ_B003,
        "challenge_id": manifest["challenge_id"],
        "mask_id": manifest["mask_id"],
        "mask_hash": manifest["mask_hash"],
        "challenge_manifest_hash": manifest["challenge_manifest_hash"],
        "profile": manifest["profile"],
        "split_digest": manifest["split_digest"],
        "model_id": manifest.get("model_id"),
    }
