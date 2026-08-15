"""Separate scoring process: later truth unlocked only after finalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.benchmark.metrics import score_rows
from elementzero.data.amdc import load_edition
from elementzero.errors import LeakageError
from elementzero.evidence.atlas_adapter import AtlasEvidenceAdapter
from elementzero.evidence.freezes import KnowledgeFreeze, assert_holdout_disjoint
from elementzero.evidence.hashing import canonical_json, sha256_file
from elementzero.evidence.ledger import (
    assert_finalized_intact,
    is_finalized,
    read_json,
)
from elementzero.identity_meta import provenance_identity


def score_run(
    *,
    run_dir: str | Path,
    truth_source: str | Path,
    truth_edition_id: str,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    truth_source = Path(truth_source)
    if not is_finalized(run_dir):
        raise LeakageError("prediction ledger was not finalized")
    marker = assert_finalized_intact(run_dir)

    freeze = KnowledgeFreeze.from_dict(read_json(run_dir / "freeze.json"))
    predictions = read_json(run_dir / "predictions.json")
    truth_hash = sha256_file(truth_source)
    if truth_hash in freeze.allowed_source_hashes:
        raise LeakageError("truth source hash was allowed by freeze")
    if truth_hash == freeze.raw_source_hash:
        raise LeakageError("truth source hash equals a training source hash")
    for training_hash in freeze.allowed_source_hashes:
        if truth_hash == training_hash:
            raise LeakageError("truth source hash equals a training source hash")

    truth_obs = {o.nuclide_id: o for o in load_edition(truth_edition_id, str(truth_source))}
    rows = []
    for pred in predictions:
        nid = pred["nuclide_id"]
        if nid in freeze.training_nuclide_ids:
            raise LeakageError(f"held-out nuclide {nid} is present in training IDs")
        if nid not in truth_obs:
            raise LeakageError(f"truth source has no record for {nid}")
        obs = truth_obs[nid]
        if not obs.ground_truth_eligible:
            raise LeakageError(f"truth record {nid} is not ground-truth eligible")
        rows.append(
            {
                "nuclide_id": nid,
                "prediction_keV": pred["mass_excess_keV"],
                "truth_keV": obs.mass_excess_keV,
                "interval_p90": pred["intervals"]["p90"],
                "interval_p95": pred["intervals"]["p95"],
            }
        )
    assert_holdout_disjoint(freeze, [r["nuclide_id"] for r in rows])
    metrics = score_rows(rows)
    adapter = AtlasEvidenceAdapter()
    val = adapter.validation_fact(
        benchmark_id="EZ-B001",
        metrics=metrics,
        depends_on_facts=(),
        run_id=run_dir.name,
    )
    report = {
        "benchmark_id": "EZ-B001",
        "legacy_id": "ZME-B001",
        "stage": "score",
        "run_id": run_dir.name,
        "freeze_id": freeze.freeze_id,
        "truth_source_hash": truth_hash,
        "truth_edition_id": truth_edition_id,
        "metrics": metrics,
        "rows": rows,
        "finalization": marker,
        "validation_fact_id": val.fact_id,
        **provenance_identity(),
    }
    dest = Path(out_dir) if out_dir is not None else run_dir / "scoring"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "metrics.json").write_text(canonical_json(metrics) + "\n", encoding="utf-8")
    (dest / "score_report.json").write_text(canonical_json(report) + "\n", encoding="utf-8")
    return report
