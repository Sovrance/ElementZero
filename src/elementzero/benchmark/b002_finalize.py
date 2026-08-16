"""Seal one EZ-B002 region run before any truth inside the region is read.

Finalization is the same operation as EZ-B001 (an immutable ``LEDGER_FINALIZED``
marker plus an Atlas FinalizationFact), so the sealing logic is reused rather
than re-implemented. What this stage adds is the EZ-B002 identity check: a run
that does not declare a region is not a geographic holdout run and must not be
sealed as one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_EZ_B002
from elementzero.benchmark.b001_finalize import finalize
from elementzero.errors import ProtocolError
from elementzero.evidence.ledger import read_json

REQUIRED_RUN_MANIFEST_FIELDS = (
    "region_id",
    "region_manifest_hash",
    "split_digest",
    "prediction_set_fact_id",
)


def finalize_region_run(run_dir: str | Path, *, created_at: str | None = None) -> dict[str, Any]:
    """Verify the run is an EZ-B002 region run, then seal it."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise ProtocolError(f"run {run_dir} has no run manifest; predict before finalizing")
    manifest = read_json(manifest_path)
    if manifest.get("benchmark_id") != BENCHMARK_EZ_B002:
        raise ProtocolError(
            f"run {run_dir} declares benchmark {manifest.get('benchmark_id')!r}, "
            f"not {BENCHMARK_EZ_B002}"
        )
    missing = [field for field in REQUIRED_RUN_MANIFEST_FIELDS if not manifest.get(field)]
    if missing:
        raise ProtocolError(f"EZ-B002 run manifest is missing fields: {missing}")
    marker = finalize(run_dir, created_at=created_at)
    return {
        **marker,
        "benchmark_id": BENCHMARK_EZ_B002,
        "region_id": manifest["region_id"],
        "region_manifest_hash": manifest["region_manifest_hash"],
        "split_digest": manifest["split_digest"],
        "model_id": manifest.get("model_id"),
    }
