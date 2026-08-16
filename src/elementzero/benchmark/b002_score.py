"""EZ-B002 scoring: unlock the withheld region only after the run is sealed.

EZ-B001 scoring refuses a truth file whose hash the freeze allowed. EZ-B002
cannot use that test, because the frozen snapshot *is* the truth source: the
region was withheld geometrically, not by withholding a file. So the checks are
inverted and made explicit:

* the truth source must be exactly the frozen snapshot (same sha256),
* the run must be finalized and its sealed artifacts must still hash as sealed,
* every scored identity must be inside the region and absent from training,
* sigma is read from the sealed prediction file, never re-derived from truth.

Reported diagnostics (WO-09 section 8) are the EZ-B001 primaries plus metrics by
extrapolation depth (``nearest_training_L1``), by region, and by model, with the
worst region reported rather than dropped.

EZ-B002 v1 declares no accuracy pass/fail threshold. Engineering PASS means the
masking is correct, leakage is absent, outputs are calibrated and scored, and
results reproduce.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero import B002_PROTOCOL_VERSION, BENCHMARK_EZ_B002, BENCHMARK_PROTOCOL_VERSION
from elementzero.benchmark.b001_score import _finalization_fact_id as finalization_fact_id
from elementzero.benchmark.b002_freeze import GeographicFreeze
from elementzero.benchmark.b002_predict import SUITE_MANIFEST_NAME
from elementzero.benchmark.distance import (
    DISTANCE_POLICY_ID,
    bucket_summaries,
    distance_bucket,
    error_vs_distance,
    isospin_asymmetry,
    nearest_training,
    region_for_z,
    region_summaries,
    training_lattice,
)
from elementzero.benchmark.distance import (
    REGION_POLICY_ID as Z_BAND_POLICY_ID,
)
from elementzero.benchmark.metrics import (
    NOMINAL_90,
    NOMINAL_95,
    calibration_error,
    group_metrics,
    score_rows,
)
from elementzero.benchmark.regions import REGION_POLICY_ID
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
from elementzero.evidence.freezes import assert_holdout_disjoint, identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import (
    assert_finalized_intact,
    finalization_marker_hash,
    is_finalized,
    read_json,
)
from elementzero.identity_meta import provenance_identity

DEPTH_POLICY_ID = "ez-b002-exact-l1-depth-v1"
REGION_COMPARISON_JSON = "region_comparison.json"
REGION_COMPARISON_MARKDOWN = "region_comparison.md"
REGION_AGGREGATE_JSON = "region_aggregate.json"
REGION_AGGREGATE_MARKDOWN = "region_aggregate.md"

COMPARISON_COLUMNS: tuple[str, ...] = (
    "region_id",
    "z_band",
    "model_id",
    "n",
    "MAE_keV",
    "MedAE_keV",
    "RMSE_keV",
    "NLPD",
    "coverage_90",
    "coverage_95",
    "calibration_error_90",
    "calibration_error_95",
    "max_nearest_training_L1",
)

NO_THRESHOLD_RULE = (
    "EZ-B002 v1 is characterization. Engineering PASS means correct masking, "
    "absent leakage, scored and calibrated outputs, and reproducible results. No "
    "accuracy pass/fail threshold is defined here, and none may be added after "
    "seeing these numbers; a scientific threshold requires a later preregistered "
    "protocol version."
)


def depth_summaries(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Metrics per exact extrapolation depth, with calibration at each depth."""
    out: dict[str, Any] = {}
    for depth in sorted({int(r["nearest_training_L1"]) for r in rows}):
        selected = [r for r in rows if int(r["nearest_training_L1"]) == depth]
        summary = group_metrics(selected)
        summary["nearest_training_L1"] = depth
        summary["calibration_error_90"] = calibration_error(summary["coverage_90"], NOMINAL_90)
        summary["calibration_error_95"] = calibration_error(summary["coverage_95"], NOMINAL_95)
        out[f"L1={depth}"] = summary
    return out


def score_region_run(
    *,
    run_dir: str | Path,
    truth_source: str | Path,
    truth_edition_id: str,
    out_dir: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Score one sealed EZ-B002 model run against the withheld region truth."""
    run_dir = Path(run_dir)
    truth_source = Path(truth_source)
    if not is_finalized(run_dir):
        raise LeakageError("prediction ledger was not finalized")
    marker = assert_finalized_intact(run_dir)
    marker_hash = finalization_marker_hash(run_dir)

    geographic = GeographicFreeze.from_dict(read_json(run_dir / "freeze.json"))
    freeze = geographic.freeze
    region = geographic.region
    predictions = read_json(run_dir / "predictions.json")
    run_manifest = read_json(run_dir / "run_manifest.json")
    if run_manifest.get("benchmark_id") != BENCHMARK_EZ_B002:
        raise ProtocolError(
            f"run {run_dir} is not an {BENCHMARK_EZ_B002} run: "
            f"{run_manifest.get('benchmark_id')!r}"
        )
    if run_manifest["region_id"] != region.region_id:
        raise ProtocolError("run manifest and sealed freeze disagree on the region")
    if run_manifest["split_digest"] != geographic.split_digest:
        raise ProtocolError("run manifest and sealed freeze disagree on the split digest")

    truth_hash = sha256_file(truth_source)
    # A geographic holdout has one snapshot. Scoring a different table would
    # silently change the benchmark, so the identity is asserted, not assumed.
    if truth_hash != freeze.raw_source_hash:
        raise ProtocolError(
            "EZ-B002 truth source must be the frozen snapshot itself; "
            f"{truth_hash} is not {freeze.raw_source_hash}"
        )
    if truth_edition_id not in freeze.allowed_edition_ids:
        raise ProtocolError(
            f"truth edition {truth_edition_id!r} is not the frozen edition "
            f"{list(freeze.allowed_edition_ids)}"
        )

    truth_obs = {o.nuclide_id: o for o in load_edition(truth_edition_id, str(truth_source))}
    lattice = training_lattice(freeze.training_nuclide_ids)
    rows = []
    scored_truth = []
    for pred in predictions:
        nid = pred["nuclide_id"]
        if nid in freeze.training_nuclide_ids:
            raise LeakageError(f"held-out nuclide {nid} is present in training IDs")
        if not region.contains_id(nid):
            raise LeakageError(f"scored nuclide {nid} lies outside region {region.region_id}")
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
                "region_id": region.region_id,
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
    if not rows:
        raise ProtocolError(f"region {region.region_id} produced no scored rows")
    assert_holdout_disjoint(freeze, [r["nuclide_id"] for r in rows])
    target_ids = [r["nuclide_id"] for r in rows]
    if identity_digest(target_ids) != geographic.target_identity_digest:
        raise ProtocolError("scored identities differ from the target set pinned by the freeze")

    depths = [int(r["nearest_training_L1"]) for r in rows]
    metrics = {
        **score_rows(rows),
        "benchmark_id": BENCHMARK_EZ_B002,
        "region_id": region.region_id,
        "z_band": region.z_band,
        "distance_policy_id": DISTANCE_POLICY_ID,
        "depth_policy_id": DEPTH_POLICY_ID,
        "region_policy_id": REGION_POLICY_ID,
        "z_band_policy_id": Z_BAND_POLICY_ID,
        "max_nearest_training_L1": max(depths),
        "min_nearest_training_L1": min(depths),
        "distance_buckets": bucket_summaries(rows),
        "depths": depth_summaries(rows),
        "z_bands": region_summaries(rows),
        "no_threshold_rule": NO_THRESHOLD_RULE,
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
    final_fact_id = finalization_fact_id(run_dir, marker_hash)

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
        benchmark_id=BENCHMARK_EZ_B002,
        metrics=metrics,
        run_id=run_dir.name,
        prediction_set_fact_id=prediction_set_fact_id,
        finalization_fact_id=final_fact_id,
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
        used=(prediction_set_fact_id, final_fact_id, truth_fact.fact_id),
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
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "b002_protocol_version": B002_PROTOCOL_VERSION,
        "stage": "score",
        "run_id": run_dir.name,
        "freeze_id": freeze.freeze_id,
        "region_id": region.region_id,
        "region": region.to_dict(),
        "region_manifest_hash": geographic.region_manifest_hash,
        "split_digest": geographic.split_digest,
        "z_band": region.z_band,
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
        "finalization_fact_id": final_fact_id,
        "truth_dataset_fact_id": truth_fact.fact_id,
        "validation_fact_id": val.fact_id,
        "atlas_bundle_hashes": atlas_bundle,
        **provenance_identity(),
    }
    (dest / "metrics.json").write_text(canonical_json(metrics) + "\n", encoding="utf-8")
    (dest / "score_report.json").write_text(canonical_json(report) + "\n", encoding="utf-8")
    return report


def score_region_suite(
    *,
    suite_dir: str | Path,
    truth_source: str | Path,
    truth_edition_id: str,
    out_dir: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Score every sealed model run of one region and compare the models."""
    suite_dir = Path(suite_dir)
    suite = read_json(suite_dir / SUITE_MANIFEST_NAME)
    dest = Path(out_dir) if out_dir is not None else suite_dir
    dest.mkdir(parents=True, exist_ok=True)
    reports = []
    for run in suite["runs"]:
        run_dir = Path(run["run_dir"])
        if not run_dir.is_absolute():
            run_dir = suite_dir / run_dir.name
        if not run_dir.is_dir():
            run_dir = suite_dir / run["model_id"]
        if finalization_marker_hash(run_dir) != run["finalization_marker_hash"]:
            raise LeakageError(
                f"finalization marker of {run['model_id']} changed after the seal"
            )
        reports.append(
            score_region_run(
                run_dir=run_dir,
                truth_source=truth_source,
                truth_edition_id=truth_edition_id,
                out_dir=run_dir / "scoring",
                created_at=created_at,
            )
        )
    comparison = build_region_comparison(reports, suite=suite)
    (dest / REGION_COMPARISON_JSON).write_text(canonical_json(comparison) + "\n", encoding="utf-8")
    (dest / REGION_COMPARISON_MARKDOWN).write_text(
        comparison_markdown(comparison, title=f"EZ-B002 region {comparison['region_id']}"),
        encoding="utf-8",
    )
    return comparison


def _comparison_row(report: dict[str, Any]) -> dict[str, Any]:
    metrics = report["metrics"]
    return {
        "region_id": report["region_id"],
        "z_band": report["z_band"],
        "model_id": report["model_id"],
        "n": metrics["n"],
        "MAE_keV": metrics["MAE_keV"],
        "MedAE_keV": metrics["MedAE_keV"],
        "RMSE_keV": metrics["RMSE_keV"],
        "NLPD": metrics["NLPD"],
        "coverage_90": metrics["coverage_90"],
        "coverage_95": metrics["coverage_95"],
        "calibration_error_90": metrics["cal_error_90"],
        "calibration_error_95": metrics["cal_error_95"],
        "max_nearest_training_L1": metrics["max_nearest_training_L1"],
        "run_id": report["run_id"],
        "freeze_id": report["freeze_id"],
        "split_digest": report["split_digest"],
        "validation_fact_id": report["validation_fact_id"],
        "distance_buckets": metrics["distance_buckets"],
        "depths": metrics["depths"],
    }


def build_region_comparison(
    reports: Sequence[dict[str, Any]],
    *,
    suite: dict[str, Any],
) -> dict[str, Any]:
    """Every model of one region, every metric. No ranking, nothing dropped."""
    expected = list(suite["model_ids"])
    by_model = {r["model_id"]: r for r in reports}
    missing = [m for m in expected if m not in by_model]
    if missing:
        raise ProtocolError(f"region comparison is missing scored models: {missing}")
    freeze_ids = sorted({r["freeze_id"] for r in reports})
    splits = sorted({r["split_digest"] for r in reports})
    regions = sorted({r["region_id"] for r in reports})
    if len(freeze_ids) != 1 or len(splits) != 1 or len(regions) != 1:
        raise ProtocolError(
            f"compared models do not share one geographic split: freezes={freeze_ids} "
            f"splits={splits} regions={regions}"
        )
    return {
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "b002_protocol_version": B002_PROTOCOL_VERSION,
        "model_suite_id": suite["model_suite_id"],
        "region_id": regions[0],
        "region": suite.get("region"),
        "region_manifest_hash": suite.get("region_manifest_hash"),
        "z_band": reports[0]["z_band"],
        "freeze_id": freeze_ids[0],
        "split_digest": splits[0],
        "truth_source_hash": sorted({r["truth_source_hash"] for r in reports})[0],
        "columns": list(COMPARISON_COLUMNS),
        "ranking_rule": suite["ranking_rule"],
        "no_threshold_rule": NO_THRESHOLD_RULE,
        "rows": [_comparison_row(by_model[model_id]) for model_id in expected],
        **provenance_identity(),
    }


def aggregate_regions(
    reports: Sequence[dict[str, Any]],
    *,
    region_ids: Sequence[str],
    model_ids: Sequence[str],
    region_manifest_hash: str,
) -> dict[str, Any]:
    """One table over every selected region and every model.

    Every preregistered region must appear for every model. A missing region is
    a protocol error, which is what stops a run from quietly reporting only the
    regions that reconstructed well.
    """
    rows = [_comparison_row(r) for r in reports]
    present = {(row["region_id"], row["model_id"]) for row in rows}
    missing = sorted(
        f"{region_id}/{model_id}"
        for region_id in region_ids
        for model_id in model_ids
        if (region_id, model_id) not in present
    )
    if missing:
        raise ProtocolError(f"aggregate is missing scored region/model pairs: {missing}")
    extra = sorted({row["region_id"] for row in rows} - set(region_ids))
    if extra:
        raise ProtocolError(f"aggregate contains regions outside the frozen manifest: {extra}")
    hashes = sorted({r["region_manifest_hash"] for r in reports})
    if hashes != [region_manifest_hash]:
        raise ProtocolError(
            f"scored runs quote region manifest hashes {hashes}, not {region_manifest_hash!r}"
        )

    ordered_rows = sorted(rows, key=lambda row: (row["region_id"], model_ids.index(row["model_id"])))
    by_model = {}
    all_rows = [row for report in reports for row in report["rows"]]
    for model_id in model_ids:
        model_reports = [r for r in reports if r["model_id"] == model_id]
        model_rows = [row for r in model_reports for row in r["rows"]]
        # Reloaded score reports carry canonically serialized floats as
        # strings (ADR-0002); the worst region is a numeric ranking, so the
        # comparison must go through float(), never string order.
        worst = max(
            model_reports, key=lambda r: (float(r["metrics"]["MAE_keV"]), r["region_id"])
        )
        by_model[model_id] = {
            "n_regions": len(model_reports),
            "pooled": {
                **score_rows(model_rows),
                "distance_buckets": bucket_summaries(model_rows),
                "depths": depth_summaries(model_rows),
            },
            "worst_region": {
                "region_id": worst["region_id"],
                "z_band": worst["z_band"],
                "MAE_keV": worst["metrics"]["MAE_keV"],
                "RMSE_keV": worst["metrics"]["RMSE_keV"],
                "NLPD": worst["metrics"]["NLPD"],
                "coverage_90": worst["metrics"]["coverage_90"],
                "coverage_95": worst["metrics"]["coverage_95"],
            },
            "per_region": [
                {
                    "region_id": r["region_id"],
                    "z_band": r["z_band"],
                    "MAE_keV": r["metrics"]["MAE_keV"],
                    "MedAE_keV": r["metrics"]["MedAE_keV"],
                    "RMSE_keV": r["metrics"]["RMSE_keV"],
                    "NLPD": r["metrics"]["NLPD"],
                    "coverage_90": r["metrics"]["coverage_90"],
                    "coverage_95": r["metrics"]["coverage_95"],
                    "calibration_error_90": r["metrics"]["cal_error_90"],
                    "calibration_error_95": r["metrics"]["cal_error_95"],
                    "max_nearest_training_L1": r["metrics"]["max_nearest_training_L1"],
                }
                for r in sorted(model_reports, key=lambda r: r["region_id"])
            ],
        }
    return {
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "b002_protocol_version": B002_PROTOCOL_VERSION,
        "region_manifest_hash": region_manifest_hash,
        "region_ids": list(region_ids),
        "model_ids": list(model_ids),
        "columns": list(COMPARISON_COLUMNS),
        "n_scored_targets": len(all_rows),
        "rows": ordered_rows,
        "by_model": by_model,
        "depths_all_regions": depth_summaries(all_rows),
        "no_threshold_rule": NO_THRESHOLD_RULE,
        **provenance_identity(),
    }


def _format_cell(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def comparison_markdown(payload: dict[str, Any], *, title: str) -> str:
    columns = list(payload["columns"])
    lines = [
        f"# {title}",
        "",
        f"benchmark_id: {payload['benchmark_id']}",
        f"protocol_version: {payload['protocol_version']}",
        f"b002_protocol_version: {payload['b002_protocol_version']}",
        f"region_manifest_hash: {payload.get('region_manifest_hash')}",
        "",
        f"ranking rule: {payload.get('ranking_rule', 'none')}",
        "",
        f"threshold rule: {payload['no_threshold_rule']}",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in payload["rows"]:
        lines.append("| " + " | ".join(_format_cell(row.get(c)) for c in columns) + " |")
    lines.extend(
        [
            "",
            "Extrapolation depth (ASCII):",
            "",
            "    nearest_training_L1 = min over training nuclei of "
            "abs(Z_t - Z_r) + abs(N_t - N_r)",
            "",
        ]
    )
    by_model = payload.get("by_model")
    if by_model:
        lines.extend(
            [
                "Worst region per model (reported, never dropped):",
                "",
                "| model_id | worst_region_id | MAE_keV | RMSE_keV | coverage_90 | coverage_95 |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for model_id in payload["model_ids"]:
            worst = by_model[model_id]["worst_region"]
            lines.append(
                f"| {model_id} | {worst['region_id']} | {_format_cell(worst['MAE_keV'])} | "
                f"{_format_cell(worst['RMSE_keV'])} | {_format_cell(worst['coverage_90'])} | "
                f"{_format_cell(worst['coverage_95'])} |"
            )
        lines.append("")
        lines.extend(
            [
                "Pooled metrics by extrapolation depth:",
                "",
                "| model_id | depth | n | MAE_keV | RMSE_keV | coverage_90 | coverage_95 | NLPD |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for model_id in payload["model_ids"]:
            for depth, summary in by_model[model_id]["pooled"]["depths"].items():
                lines.append(
                    f"| {model_id} | {depth} | {summary['n']} | "
                    f"{_format_cell(summary['MAE_keV'])} | {_format_cell(summary['RMSE_keV'])} | "
                    f"{_format_cell(summary['coverage_90'])} | "
                    f"{_format_cell(summary['coverage_95'])} | {_format_cell(summary['NLPD'])} |"
                )
        lines.append("")
    return "\n".join(lines)


def write_region_aggregate(
    *,
    out_dir: str | Path,
    reports: Sequence[dict[str, Any]],
    region_ids: Sequence[str],
    model_ids: Sequence[str],
    region_manifest_hash: str,
) -> dict[str, Any]:
    aggregate = aggregate_regions(
        reports,
        region_ids=region_ids,
        model_ids=model_ids,
        region_manifest_hash=region_manifest_hash,
    )
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / REGION_AGGREGATE_JSON).write_text(canonical_json(aggregate) + "\n", encoding="utf-8")
    (dest / REGION_AGGREGATE_MARKDOWN).write_text(
        comparison_markdown(aggregate, title="EZ-B002 geographic holdout aggregate"),
        encoding="utf-8",
    )
    return aggregate
