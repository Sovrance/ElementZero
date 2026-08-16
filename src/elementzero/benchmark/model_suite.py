"""Frozen three-model suite for EZ-B001 and the model comparison report.

The suite is an ordered, preregistered set:

    1. EZ-SEMF-LS-v1
    2. EZ-GP-DIRECT-v1
    3. EZ-SEMF-GP-RESIDUAL-v1

Every model in a suite run uses the same KnowledgeFreeze, the same targets, the
same source hashes, and the same feature policy. Each model gets its own sealed
run directory:

    <suite_dir>/EZ-SEMF-LS-v1/
    <suite_dir>/EZ-GP-DIRECT-v1/
    <suite_dir>/EZ-SEMF-GP-RESIDUAL-v1/

The comparison report prints every metric for every model. No model is labelled
"best", and no single-metric ranking is emitted.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_PROTOCOL_VERSION
from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_predict import predict_run
from elementzero.benchmark.b001_score import score_run
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import KnowledgeFreeze
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.evidence.ledger import read_json
from elementzero.identity_meta import provenance_identity
from elementzero.models.gp_residual import (
    MODEL_ID_GP_DIRECT,
    MODEL_ID_SEMF_GP,
    MODEL_ID_SEMF_LS,
)

MODEL_SUITE_ID = "EZ-B001-SUITE-v1"
SUITE_MODEL_IDS: tuple[str, ...] = (
    MODEL_ID_SEMF_LS,
    MODEL_ID_GP_DIRECT,
    MODEL_ID_SEMF_GP,
)
SUITE_MANIFEST_NAME = "model_suite.json"
COMPARISON_JSON_NAME = "model_comparison.json"
COMPARISON_MARKDOWN_NAME = "model_comparison.md"

# Explicit non-ranking rule (WO-03 section 8).
RANKING_RULE = (
    "none: every metric is reported for every model; no single-metric ranking "
    "and no 'best model' label is emitted by this report"
)

COMPARISON_COLUMNS: tuple[str, ...] = (
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
)


def model_suite_manifest(*, model_ids: Sequence[str] = SUITE_MODEL_IDS) -> dict[str, Any]:
    """Frozen, ordered suite manifest."""
    ordered = list(model_ids)
    if len(set(ordered)) != len(ordered):
        raise ValueError(f"model suite contains duplicates: {ordered}")
    payload = {
        "model_suite_id": MODEL_SUITE_ID,
        "benchmark_id": "EZ-B001",
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "model_ids": ordered,
        "ranking_rule": RANKING_RULE,
    }
    return payload


def suite_manifest_hash(manifest: dict[str, Any]) -> str:
    return sha256_hex(manifest)


def run_suite(
    *,
    freeze: KnowledgeFreeze,
    targets: list[dict[str, Any]],
    training_source: str | Path,
    training_edition_id: str,
    suite_dir: str | Path,
    model_ids: Sequence[str] = SUITE_MODEL_IDS,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Predict and seal one run directory per model under a single freeze."""
    suite_dir = Path(suite_dir)
    manifest = model_suite_manifest(model_ids=model_ids)
    runs = []
    for model_id in manifest["model_ids"]:
        run_dir = suite_dir / model_id
        result = predict_run(
            freeze=freeze,
            targets=targets,
            training_source=training_source,
            training_edition_id=training_edition_id,
            run_dir=run_dir,
            model_id=model_id,
            created_at=created_at,
        )
        marker = finalize(run_dir, created_at=created_at)
        runs.append(
            {
                "model_id": model_id,
                "run_dir": str(run_dir),
                "freeze_id": result["run_manifest"]["freeze_id"],
                "target_identity_digest": result["run_manifest"]["target_identity_digest"],
                "model_manifest_hash": result["run_manifest"]["model_manifest_hash"],
                "prediction_set_fact_id": result["run_manifest"]["prediction_set_fact_id"],
                "finalization_marker_hash": marker["finalization_marker_hash"],
            }
        )
    _assert_shared_freeze(runs)
    payload = {
        **manifest,
        "model_suite_manifest_hash": suite_manifest_hash(manifest),
        "suite_dir": str(suite_dir),
        "freeze_id": freeze.freeze_id,
        "target_identity_digest": runs[0]["target_identity_digest"] if runs else None,
        "source_hashes": list(freeze.allowed_source_hashes),
        "feature_policy_id": freeze.feature_policy_id,
        "runs": runs,
        **provenance_identity(),
    }
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / SUITE_MANIFEST_NAME).write_text(
        canonical_json(payload) + "\n", encoding="utf-8"
    )
    return payload


def score_suite(
    *,
    suite_dir: str | Path,
    truth_source: str | Path,
    truth_edition_id: str,
    out_dir: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Score every sealed model run and write the comparison report."""
    suite_dir = Path(suite_dir)
    suite = read_json(suite_dir / SUITE_MANIFEST_NAME)
    _assert_shared_freeze(suite["runs"])
    dest = Path(out_dir) if out_dir is not None else suite_dir
    dest.mkdir(parents=True, exist_ok=True)
    reports = []
    for run in suite["runs"]:
        run_dir = Path(run["run_dir"])
        if not run_dir.is_absolute():
            run_dir = suite_dir / run_dir.name
        report = score_run(
            run_dir=run_dir,
            truth_source=truth_source,
            truth_edition_id=truth_edition_id,
            out_dir=run_dir / "scoring",
            created_at=created_at,
        )
        reports.append(report)
    comparison = build_comparison(reports, suite=suite)
    (dest / COMPARISON_JSON_NAME).write_text(
        canonical_json(comparison) + "\n", encoding="utf-8"
    )
    (dest / COMPARISON_MARKDOWN_NAME).write_text(
        comparison_markdown(comparison), encoding="utf-8"
    )
    return comparison


def build_comparison(
    reports: Sequence[dict[str, Any]],
    *,
    suite: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Comparison table; a poor result is reported, never dropped."""
    expected = list(suite["model_ids"]) if suite else [r["model_id"] for r in reports]
    by_model = {r["model_id"]: r for r in reports}
    missing = [m for m in expected if m not in by_model]
    if missing:
        raise ProtocolError(f"model comparison is missing scored models: {missing}")
    rows = []
    for model_id in expected:
        report = by_model[model_id]
        metrics = report["metrics"]
        rows.append(
            {
                "model_id": model_id,
                "n": metrics["n"],
                "MAE_keV": metrics["MAE_keV"],
                "MedAE_keV": metrics["MedAE_keV"],
                "RMSE_keV": metrics["RMSE_keV"],
                "NLPD": metrics["NLPD"],
                "coverage_90": metrics["coverage_90"],
                "coverage_95": metrics["coverage_95"],
                "calibration_error_90": metrics["cal_error_90"],
                "calibration_error_95": metrics["cal_error_95"],
                "run_id": report["run_id"],
                "truth_source_hash": report["truth_source_hash"],
                "validation_fact_id": report["validation_fact_id"],
                "distance_buckets": metrics["distance_buckets"],
                "regions": metrics["regions"],
            }
        )
    freeze_ids = sorted({r["freeze_id"] for r in reports})
    truth_hashes = sorted({r["truth_source_hash"] for r in reports})
    if len(freeze_ids) != 1:
        raise ProtocolError(f"compared models do not share one freeze: {freeze_ids}")
    if len(truth_hashes) != 1:
        raise ProtocolError(f"compared models do not share one truth source: {truth_hashes}")
    return {
        "benchmark_id": "EZ-B001",
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "model_suite_id": (suite or {}).get("model_suite_id", MODEL_SUITE_ID),
        "columns": list(COMPARISON_COLUMNS),
        "ranking_rule": RANKING_RULE,
        "freeze_id": freeze_ids[0],
        "truth_source_hash": truth_hashes[0],
        "rows": rows,
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


def comparison_markdown(comparison: dict[str, Any]) -> str:
    columns = list(comparison["columns"])
    lines = [
        "# EZ-B001 model comparison",
        "",
        f"benchmark_id: {comparison['benchmark_id']}",
        f"protocol_version: {comparison['protocol_version']}",
        f"model_suite_id: {comparison['model_suite_id']}",
        f"freeze_id: {comparison['freeze_id']}",
        f"truth_source_hash: {comparison['truth_source_hash']}",
        "",
        f"ranking rule: {comparison['ranking_rule']}",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in comparison["rows"]:
        lines.append("| " + " | ".join(_format_cell(row.get(c)) for c in columns) + " |")
    lines.extend(
        [
            "",
            "Metric definitions (ASCII):",
            "",
            "    error_i = prediction_i - truth_i",
            "    MAE     = mean(abs(error_i))",
            "    MedAE   = median(abs(error_i))",
            "    RMSE    = sqrt(mean(error_i^2))",
            "    NLPD_i  = 0.5*log(2*pi*sigma_i^2) + 0.5*((truth_i - prediction_i)/sigma_i)^2",
            "    cal_error_90 = abs(coverage_90 - 0.90)",
            "    cal_error_95 = abs(coverage_95 - 0.95)",
            "",
        ]
    )
    return "\n".join(lines)


def _assert_shared_freeze(runs: Sequence[dict[str, Any]]) -> None:
    freeze_ids = sorted({r["freeze_id"] for r in runs})
    digests = sorted({r["target_identity_digest"] for r in runs})
    if len(freeze_ids) != 1:
        raise ProtocolError(f"suite runs do not share one freeze: {freeze_ids}")
    if len(digests) != 1:
        raise ProtocolError(f"suite runs do not share one target set: {digests}")
