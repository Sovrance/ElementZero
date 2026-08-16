"""Separate scoring process: later truth unlocked only after finalization.

Scoring rehydrates the sealed Atlas graph, adds the truth corpus, and lands a
ValidationFact whose lineage reaches prediction set + finalization + truth.
Predictive sigma is read from the sealed prediction file; it is never
reconstructed from truth or from rounded intervals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_PROTOCOL_VERSION
from elementzero.benchmark.distance import (
    DISTANCE_POLICY_ID,
    REGION_POLICY_ID,
    bucket_summaries,
    distance_bucket,
    error_vs_distance,
    isospin_asymmetry,
    nearest_training,
    region_for_z,
    region_summaries,
    training_lattice,
)
from elementzero.benchmark.metrics import score_rows
from elementzero.data.amdc import load_edition
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.identity import parse_nuclide_id
from elementzero.data.observations import GROUND_TRUTH_POLICY
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.atlas_adapter import (
    AtlasEvidenceAdapter,
    atlas_bundle_exists,
    read_atlas_facts,
    stable_source_uri,
    write_atlas_bundle,
)
from elementzero.evidence.freezes import KnowledgeFreeze, assert_holdout_disjoint, identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import (
    assert_finalized_intact,
    finalization_marker_hash,
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
    created_at: str | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    truth_source = Path(truth_source)
    if not is_finalized(run_dir):
        raise LeakageError("prediction ledger was not finalized")
    marker = assert_finalized_intact(run_dir)
    marker_hash = finalization_marker_hash(run_dir)

    freeze = KnowledgeFreeze.from_dict(read_json(run_dir / "freeze.json"))
    predictions = read_json(run_dir / "predictions.json")
    run_manifest = read_json(run_dir / "run_manifest.json")
    truth_hash = sha256_file(truth_source)
    if truth_hash in freeze.allowed_source_hashes:
        raise LeakageError("truth source hash was allowed by freeze")
    if truth_hash == freeze.raw_source_hash:
        raise LeakageError("truth source hash equals a training source hash")
    for training_hash in freeze.allowed_source_hashes:
        if truth_hash == training_hash:
            raise LeakageError("truth source hash equals a training source hash")

    truth_obs = {o.nuclide_id: o for o in load_edition(truth_edition_id, str(truth_source))}
    lattice = training_lattice(freeze.training_nuclide_ids)
    rows = []
    scored_truth = []
    for pred in predictions:
        nid = pred["nuclide_id"]
        if nid in freeze.training_nuclide_ids:
            raise LeakageError(f"held-out nuclide {nid} is present in training IDs")
        if nid not in truth_obs:
            raise LeakageError(f"truth source has no record for {nid}")
        if "std_keV" not in pred:
            raise ProtocolError(
                f"sealed prediction for {nid} has no std_keV; sigma must come from "
                "the model, never from truth"
            )
        obs = truth_obs[nid]
        if not obs.ground_truth_eligible:
            raise LeakageError(f"truth record {nid} is not ground-truth eligible")
        z, n = parse_nuclide_id(nid)
        near = nearest_training(z=z, n=n, lattice=lattice)
        scored_truth.append(obs)
        rows.append(
            {
                "nuclide_id": nid,
                "Z": z,
                "N": n,
                "A": z + n,
                "prediction_keV": float(pred["mass_excess_keV"]),
                "std_keV": float(pred["std_keV"]),
                "truth_keV": obs.mass_excess_keV,
                "truth_uncertainty_keV": obs.uncertainty_keV,
                "interval_p90": [float(v) for v in pred["intervals"]["p90"]],
                "interval_p95": [float(v) for v in pred["intervals"]["p95"]],
                "nearest_training_L1": near["nearest_training_L1"],
                "nearest_training_L2": near["nearest_training_L2"],
                "nearest_training_nuclide_id": near["nearest_training_nuclide_id"],
                "distance_bucket": distance_bucket(near["nearest_training_L1"]),
                "region": region_for_z(z),
                "isospin_asymmetry": isospin_asymmetry(z, n),
            }
        )
    assert_holdout_disjoint(freeze, [r["nuclide_id"] for r in rows])
    target_ids = [r["nuclide_id"] for r in rows]
    metrics = {
        **score_rows(rows),
        "distance_policy_id": DISTANCE_POLICY_ID,
        "region_policy_id": REGION_POLICY_ID,
        "distance_buckets": bucket_summaries(rows),
        "regions": region_summaries(rows),
    }

    model_id = str(run_manifest.get("model_id", ""))
    for stage in ("predict", "finalize"):
        if not atlas_bundle_exists(run_dir, stage=stage):
            raise ProtocolError(
                f"run {run_dir} has no Atlas {stage} bundle; validation must not exist "
                "without a sealed, lineage-complete prediction set"
            )
    adapter = AtlasEvidenceAdapter(created_at=created_at)
    adapter.rehydrate(read_atlas_facts(run_dir, stage="predict"))
    adapter.rehydrate(read_atlas_facts(run_dir, stage="finalize"))
    prediction_set_fact_id = run_manifest["prediction_set_fact_id"]
    finalization_fact_id = _finalization_fact_id(run_dir, marker_hash)

    truth_artifact = adapter.source_artifact(
        truth_source.read_bytes(),
        source_uri=stable_source_uri(truth_source),
        acquired_at=scored_truth[0].source_release_date if scored_truth else "1970-01-01",
    )
    truth_event = adapter.observation_event(truth_artifact)
    adapter.append_provenance(
        entity=truth_artifact.artifact_id,
        activity_type="LOAD",
        used=(),
        generated=(truth_artifact.artifact_id,),
    )
    truth_fact = adapter.truth_dataset_fact(
        artifact=truth_artifact,
        truth_edition_id=truth_edition_id,
        truth_source_hash=truth_hash,
        normalized_truth_hash=sha256_hex(
            [o.to_dict() for o in sorted(scored_truth, key=lambda o: o.nuclide_id)]
        ),
        target_identity_digest=identity_digest(target_ids),
        truth_count=len(scored_truth),
        parser_version=PARSER_VERSION,
        ground_truth_policy=GROUND_TRUTH_POLICY,
        event=truth_event,
    )
    adapter.append_fact(truth_fact)
    adapter.append_provenance(
        entity=truth_fact.fact_id,
        activity_type="LOWER",
        used=(truth_artifact.artifact_id,),
        generated=(truth_fact.fact_id,),
    )

    val = adapter.validation_fact(
        benchmark_id="EZ-B001",
        metrics=metrics,
        run_id=run_dir.name,
        prediction_set_fact_id=prediction_set_fact_id,
        finalization_fact_id=finalization_fact_id,
        truth_dataset_fact_id=truth_fact.fact_id,
        protocol_version=BENCHMARK_PROTOCOL_VERSION,
        model_id=model_id,
        truth_source_hash=truth_hash,
        finalization_marker_hash=marker_hash,
    )
    adapter.append_fact(val)
    adapter.append_provenance(
        entity=val.fact_id,
        activity_type="CERTIFY",
        used=(prediction_set_fact_id, finalization_fact_id, truth_fact.fact_id),
        generated=(val.fact_id,),
    )

    dest = Path(out_dir) if out_dir is not None else run_dir / "scoring"
    dest.mkdir(parents=True, exist_ok=True)
    atlas_bundle = write_atlas_bundle(
        dest,
        stage="score",
        facts=[truth_fact, val],
        provenance=[
            r
            for r in adapter.store.provenance()
            if r.entity in {truth_artifact.artifact_id, truth_fact.fact_id, val.fact_id}
        ],
    )
    report = {
        "benchmark_id": "EZ-B001",
        "legacy_id": "ZME-B001",
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "stage": "score",
        "run_id": run_dir.name,
        "freeze_id": freeze.freeze_id,
        "model_id": model_id,
        "truth_source_hash": truth_hash,
        "truth_edition_id": truth_edition_id,
        "parser_version": PARSER_VERSION,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "metrics": metrics,
        "rows": rows,
        "error_vs_distance": error_vs_distance(rows),
        "finalization": marker,
        "finalization_marker_hash": marker_hash,
        "prediction_set_fact_id": prediction_set_fact_id,
        "finalization_fact_id": finalization_fact_id,
        "truth_dataset_fact_id": truth_fact.fact_id,
        "validation_fact_id": val.fact_id,
        "atlas_bundle_hashes": atlas_bundle,
        **provenance_identity(),
    }
    (dest / "metrics.json").write_text(canonical_json(metrics) + "\n", encoding="utf-8")
    (dest / "score_report.json").write_text(canonical_json(report) + "\n", encoding="utf-8")
    return report


def _finalization_fact_id(run_dir: Path, marker_hash: str) -> str:
    """The sealed FinalizationFact must match the marker actually on disk."""
    payloads = read_atlas_facts(run_dir, stage="finalize")
    for payload in payloads:
        content = payload.get("content", {})
        if content.get("kind") != "nuclear_prediction_finalization":
            continue
        if content.get("finalization_marker_hash") != marker_hash:
            raise LeakageError("finalization fact does not match the LEDGER_FINALIZED marker")
        return payload["fact_id"]
    raise ProtocolError("run has no persisted finalization fact")
