"""Finalize the prediction ledger before any truth unlock.

Finalization also records the Atlas FinalizationFact: it seals the prediction
set and carries no truth value, which is what lets the scoring process prove it
did not score an unsealed run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.errors import ProtocolError
from elementzero.evidence.atlas_adapter import (
    AtlasEvidenceAdapter,
    atlas_bundle_exists,
    read_atlas_facts,
    write_atlas_bundle,
)
from elementzero.evidence.ledger import (
    finalization_marker_hash,
    finalize_run,
    read_json,
)


def finalize(run_dir: str | Path, *, created_at: str | None = None) -> dict[str, Any]:
    run_dir = Path(run_dir)
    if not atlas_bundle_exists(run_dir, stage="predict"):
        raise ProtocolError(
            f"run {run_dir} has no Atlas prediction bundle; re-run predict under "
            "the current protocol before finalizing"
        )
    marker = finalize_run(run_dir)
    marker_hash = finalization_marker_hash(run_dir)
    manifest = read_json(run_dir / "run_manifest.json")
    if "prediction_set_fact_id" not in manifest:
        raise ProtocolError("run manifest has no prediction_set_fact_id")
    prediction_set_fact_id = manifest["prediction_set_fact_id"]

    adapter = AtlasEvidenceAdapter(created_at=created_at)
    adapter.rehydrate(read_atlas_facts(run_dir, stage="predict"))
    fact = adapter.finalization_fact(
        run_id=str(manifest.get("run_id", run_dir.name)),
        finalization_marker_hash=marker_hash,
        sealed_artifact_hashes=marker["artifact_hashes"],
        finalization_timestamp=adapter.created_at,
        prediction_set_fact_id=prediction_set_fact_id,
    )
    adapter.append_fact(fact)
    record = adapter.append_provenance(
        entity=fact.fact_id,
        activity_type="CERTIFY",
        used=(prediction_set_fact_id,),
        generated=(fact.fact_id,),
    )
    bundle = write_atlas_bundle(
        run_dir,
        stage="finalize",
        facts=[fact],
        provenance=[record],
    )
    return {
        **marker,
        "finalization_marker_hash": marker_hash,
        "finalization_timestamp": adapter.created_at,
        "finalization_fact_id": fact.fact_id,
        "prediction_set_fact_id": prediction_set_fact_id,
        "atlas_bundle_hashes": bundle,
    }
