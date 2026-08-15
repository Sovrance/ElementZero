"""Longitudinal aggregate across scored EZ-B001 epochs (WO-07 sections 5 and 6).

The aggregate answers one question: does ElementZero behave consistently across
historical transitions under one unchanged protocol? It therefore refuses to mix
protocol versions, model suites, or protocol code digests, and it reports every
epoch and every model, including the ones that behave badly.

Outputs:

    results/EZ-B001/aggregate_v1.json
    results/EZ-B001/aggregate_v1.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_EZ_B001
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.distance import DISTANCE_BUCKET_IDS, REGION_IDS
from elementzero.benchmark.model_suite import COMPARISON_JSON_NAME, SUITE_MODEL_IDS
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json
from elementzero.evidence.ledger import read_json
from elementzero.experiments.epochs import EPOCH_ORDER
from elementzero.experiments.preregister import (
    EXPERIMENT_PROTOCOL_VERSION,
    PROTOCOL_FILE,
    read_preregistration_hash,
)
from elementzero.experiments.runner import SCORE_MANIFEST_FILE

AGGREGATE_DIRNAME = "results/EZ-B001"
AGGREGATE_JSON = "aggregate_v1.json"
AGGREGATE_MARKDOWN = "aggregate_v1.md"

MODEL_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "training_edition",
    "truth_edition",
    "model_id",
    "n",
    "MAE_keV",
    "MedAE_keV",
    "RMSE_keV",
    "NLPD",
    "coverage_90",
    "coverage_95",
    "cal_error_90",
    "cal_error_95",
)

DISTANCE_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "model_id",
    "distance_bucket",
    "n",
    "MAE_keV",
    "RMSE_keV",
    "NLPD",
)


def experiment_dirs(root: str | Path | None = None) -> list[Path]:
    """Scored experiment directories, in declared epoch order."""
    base = Path(root or REPO_ROOT) / "experiments"
    return [
        base / experiment_id
        for experiment_id in EPOCH_ORDER
        if (base / experiment_id / COMPARISON_JSON_NAME).is_file()
    ]


def load_experiment(experiment_dir: str | Path) -> dict[str, Any]:
    """Comparison, score manifest, and protocol of one scored experiment."""
    experiment_dir = Path(experiment_dir)
    comparison = read_json(experiment_dir / COMPARISON_JSON_NAME)
    score_manifest = read_json(experiment_dir / SCORE_MANIFEST_FILE)
    protocol = read_json(experiment_dir / PROTOCOL_FILE)
    return {
        "experiment_dir": experiment_dir,
        "experiment_id": protocol["experiment_id"],
        "comparison": comparison,
        "score_manifest": score_manifest,
        "protocol": protocol,
        "preregistration_hash": read_preregistration_hash(experiment_dir),
    }


def assert_one_protocol(experiments: list[dict[str, Any]]) -> dict[str, Any]:
    """A benchmark series is one protocol; a mixed series is refused."""
    if not experiments:
        raise ProtocolError("no scored experiment was found")
    versions = {e["protocol"]["protocol_version"] for e in experiments}
    digests = {e["protocol"]["protocol_code_digest"] for e in experiments}
    suites = {tuple(e["protocol"]["model_ids"]) for e in experiments}
    atlas = {e["protocol"]["atlas_pir_ref"] for e in experiments}
    features = {tuple(e["protocol"]["features"]) for e in experiments}
    policies = {
        (
            e["protocol"]["ground_truth_policy"],
            e["protocol"]["parser_version"],
            e["protocol"]["normalizer_version"],
            e["protocol"]["feature_policy_id"],
            e["protocol"]["metrics_policy_id"],
            e["protocol"]["target_policy_id"],
        )
        for e in experiments
    }
    if len(versions) != 1:
        raise ProtocolError(f"epochs do not share one protocol version: {sorted(versions)}")
    if versions != {EXPERIMENT_PROTOCOL_VERSION}:
        raise ProtocolError(f"unsupported protocol version in the series: {sorted(versions)}")
    if len(digests) != 1:
        raise ProtocolError(
            "epochs were run against different protocol code; bump the protocol version "
            f"and rerun every epoch instead of aggregating {sorted(digests)}"
        )
    if len(suites) != 1:
        raise ProtocolError(f"epochs do not share one model suite: {sorted(suites)}")
    if suites != {tuple(SUITE_MODEL_IDS)}:
        raise ProtocolError(f"model suite drifted from the frozen suite: {sorted(suites)}")
    if len(atlas) != 1 or len(features) != 1 or len(policies) != 1:
        raise ProtocolError("epochs do not share one Atlas pin, feature policy, or data policy")
    return {
        "protocol_version": versions.pop(),
        "protocol_code_digest": digests.pop(),
        "model_ids": list(suites.pop()),
        "atlas_pir_ref": atlas.pop(),
        "features": list(features.pop()),
    }


def number(value: Any) -> float | int | None:
    """Canonical JSON stores finite floats as 12-digit strings; read them back.

    See ADR-0002: ``canonical_json`` renders floats as ``format(x, '.12e')`` so
    two scientifically identical values hash identically. Anything that recomputes
    from committed artifacts therefore has to parse the string back to a float.
    """
    if value is None or isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return float(value)


def _row(experiment: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    protocol = experiment["protocol"]
    return {
        "experiment_id": experiment["experiment_id"],
        "training_edition": protocol["training"]["edition"],
        "truth_edition": protocol["later_edition"]["edition"],
        "model_id": row["model_id"],
        "n": int(row["n"]),
        "MAE_keV": number(row["MAE_keV"]),
        "MedAE_keV": number(row["MedAE_keV"]),
        "RMSE_keV": number(row["RMSE_keV"]),
        "NLPD": number(row["NLPD"]),
        "coverage_90": number(row["coverage_90"]),
        "coverage_95": number(row["coverage_95"]),
        "cal_error_90": number(row["calibration_error_90"]),
        "cal_error_95": number(row["calibration_error_95"]),
    }


def _distance_rows(experiment: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for bucket in DISTANCE_BUCKET_IDS:
        summary = row["distance_buckets"][bucket]
        out.append(
            {
                "experiment_id": experiment["experiment_id"],
                "model_id": row["model_id"],
                "distance_bucket": bucket,
                "n": int(summary["n"]),
                "MAE_keV": number(summary["MAE_keV"]),
                "RMSE_keV": number(summary["RMSE_keV"]),
                "NLPD": number(summary["NLPD"]),
            }
        )
    return out


def _region_rows(experiment: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for region in REGION_IDS:
        summary = row["regions"][region]
        out.append(
            {
                "experiment_id": experiment["experiment_id"],
                "model_id": row["model_id"],
                "region": region,
                "n": int(summary["n"]),
                "MAE_keV": number(summary["MAE_keV"]),
                "RMSE_keV": number(summary["RMSE_keV"]),
                "NLPD": number(summary["NLPD"]),
                "mean_isospin_asymmetry": number(summary["mean_isospin_asymmetry"]),
            }
        )
    return out


def _drift(values: list[float | None]) -> dict[str, Any]:
    present = [v for v in values if v is not None]
    if not present:
        return {"values": values, "first": None, "last": None, "delta": None, "direction": "unknown"}
    delta = present[-1] - present[0]
    if delta > 0:
        direction = "increasing"
    elif delta < 0:
        direction = "decreasing"
    else:
        direction = "flat"
    return {
        "values": values,
        "first": present[0],
        "last": present[-1],
        "delta": delta,
        "min": min(present),
        "max": max(present),
        "direction": direction,
    }


def stability_diagnostics(
    *, rows: list[dict[str, Any]], distance_rows: list[dict[str, Any]], epoch_ids: list[str]
) -> dict[str, Any]:
    """Metric, calibration, target-count, and distance-trend drift per model.

    A later epoch is not assumed to be better. Worsening behaviour is reported.
    """
    out: dict[str, Any] = {}
    for model_id in SUITE_MODEL_IDS:
        by_epoch = {r["experiment_id"]: r for r in rows if r["model_id"] == model_id}
        ordered = [by_epoch.get(e) for e in epoch_ids]
        metrics = {
            metric: _drift([None if r is None else r[metric] for r in ordered])
            for metric in ("MAE_keV", "MedAE_keV", "RMSE_keV", "NLPD")
        }
        calibration = {
            metric: _drift([None if r is None else r[metric] for r in ordered])
            for metric in ("coverage_90", "coverage_95", "cal_error_90", "cal_error_95")
        }
        target_counts = _drift([None if r is None else float(r["n"]) for r in ordered])
        trends = {}
        for epoch_id in epoch_ids:
            buckets = [
                d
                for d in distance_rows
                if d["model_id"] == model_id and d["experiment_id"] == epoch_id
            ]
            mae = [b["MAE_keV"] for b in buckets]
            populated = [(b["distance_bucket"], b["MAE_keV"]) for b in buckets if b["n"] > 0]
            increasing = all(
                left[1] <= right[1] for left, right in zip(populated, populated[1:])
            )
            trends[epoch_id] = {
                "buckets": list(DISTANCE_BUCKET_IDS),
                "MAE_keV": mae,
                "populated_buckets": [name for name, _ in populated],
                "mae_non_decreasing_with_distance": increasing if len(populated) > 1 else None,
            }
        out[model_id] = {
            "metric_drift": metrics,
            "calibration_drift": calibration,
            "target_count_drift": target_counts,
            "error_vs_distance_trend": trends,
        }
    return out


def build_aggregate(experiment_paths: list[str | Path]) -> dict[str, Any]:
    experiments = [load_experiment(path) for path in experiment_paths]
    shared = assert_one_protocol(experiments)
    epoch_ids = [e["experiment_id"] for e in experiments]
    rows: list[dict[str, Any]] = []
    distance_rows: list[dict[str, Any]] = []
    region_rows: list[dict[str, Any]] = []
    for experiment in experiments:
        comparison_rows = {r["model_id"]: r for r in experiment["comparison"]["rows"]}
        missing = [m for m in SUITE_MODEL_IDS if m not in comparison_rows]
        if missing:
            raise ProtocolError(
                f"{experiment['experiment_id']} is missing scored models {missing}; "
                "every model appears in every epoch or the aggregate is not published"
            )
        for model_id in SUITE_MODEL_IDS:
            row = comparison_rows[model_id]
            rows.append(_row(experiment, row))
            distance_rows.extend(_distance_rows(experiment, row))
            region_rows.extend(_region_rows(experiment, row))
    return {
        "benchmark_id": BENCHMARK_EZ_B001,
        "aggregate_version": "v1",
        "protocol_version": shared["protocol_version"],
        "protocol_code_digest": shared["protocol_code_digest"],
        "atlas_pir_ref": shared["atlas_pir_ref"],
        "features": shared["features"],
        "model_ids": list(SUITE_MODEL_IDS),
        "experiment_ids": epoch_ids,
        "epochs": [
            {
                "experiment_id": e["experiment_id"],
                "training_edition": e["protocol"]["training"]["edition"],
                "truth_edition": e["protocol"]["later_edition"]["edition"],
                "preregistration_hash": e["preregistration_hash"],
                "training_source_hash": e["protocol"]["training"]["raw_sha256"],
                "truth_source_hash": e["protocol"]["later_edition"]["raw_sha256"],
                "sealed_predictions_sha256": e["score_manifest"]["sealed_predictions_sha256"],
                "target_identity_digest": e["score_manifest"]["target_identity_digest"],
                "experiment_dir": f"experiments/{e['experiment_id']}",
            }
            for e in experiments
        ],
        "model_columns": list(MODEL_COLUMNS),
        "rows": rows,
        "distance_columns": list(DISTANCE_COLUMNS),
        "distance_rows": distance_rows,
        "region_rows": region_rows,
        "stability": stability_diagnostics(
            rows=rows, distance_rows=distance_rows, epoch_ids=epoch_ids
        ),
        "ranking_rule": (
            "Every metric is reported for every model in every epoch. No ranking, no "
            "best-model label, and no epoch is dropped for behaving badly."
        ),
    }


def _cell(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def aggregate_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# EZ-B001 longitudinal aggregate v1",
        "",
        f"benchmark_id: {payload['benchmark_id']}",
        f"protocol_version: {payload['protocol_version']}",
        f"protocol_code_digest: {payload['protocol_code_digest']}",
        f"atlas_pir_ref: {payload['atlas_pir_ref']}",
        "",
        payload["ranking_rule"],
        "",
        "## Epochs",
        "",
        "| experiment_id | training | truth | preregistration_hash |",
        "| --- | --- | --- | --- |",
    ]
    for epoch in payload["epochs"]:
        lines.append(
            f"| {epoch['experiment_id']} | {epoch['training_edition']} | "
            f"{epoch['truth_edition']} | `{epoch['preregistration_hash']}` |"
        )
    lines.extend(
        [
            "",
            "## Primary metrics",
            "",
            "| " + " | ".join(MODEL_COLUMNS) + " |",
            "| " + " | ".join(["---"] * len(MODEL_COLUMNS)) + " |",
        ]
    )
    for row in payload["rows"]:
        lines.append("| " + " | ".join(_cell(row[c]) for c in MODEL_COLUMNS) + " |")
    lines.extend(
        [
            "",
            "## Error versus nearest-training L1 distance",
            "",
            "| " + " | ".join(DISTANCE_COLUMNS) + " |",
            "| " + " | ".join(["---"] * len(DISTANCE_COLUMNS)) + " |",
        ]
    )
    for row in payload["distance_rows"]:
        lines.append("| " + " | ".join(_cell(row[c]) for c in DISTANCE_COLUMNS) + " |")
    lines.extend(["", "## Stability diagnostics", ""])
    for model_id, diagnostics in payload["stability"].items():
        lines.append(f"### {model_id}")
        lines.append("")
        lines.append("| quantity | first epoch | last epoch | delta | direction |")
        lines.append("| --- | --- | --- | --- | --- |")
        for group in ("metric_drift", "calibration_drift"):
            for name, drift in diagnostics[group].items():
                lines.append(
                    f"| {name} | {_cell(drift['first'])} | {_cell(drift['last'])} | "
                    f"{_cell(drift['delta'])} | {drift['direction']} |"
                )
        count = diagnostics["target_count_drift"]
        lines.append(
            f"| n_targets | {_cell(count['first'])} | {_cell(count['last'])} | "
            f"{_cell(count['delta'])} | {count['direction']} |"
        )
        lines.append("")
        for epoch_id, trend in diagnostics["error_vs_distance_trend"].items():
            lines.append(
                f"- {epoch_id}: MAE by bucket {trend['buckets']} = "
                f"{[_cell(v) for v in trend['MAE_keV']]}, non-decreasing with distance: "
                f"{trend['mae_non_decreasing_with_distance']}"
            )
        lines.append("")
    return "\n".join(lines)


def write_aggregate(
    *,
    experiment_paths: list[str | Path] | None = None,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    base = Path(root or REPO_ROOT)
    paths = list(experiment_paths) if experiment_paths else experiment_dirs(base)
    payload = build_aggregate(paths)
    dest = Path(out_dir or base / AGGREGATE_DIRNAME)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / AGGREGATE_JSON).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    (dest / AGGREGATE_MARKDOWN).write_text(aggregate_markdown(payload), encoding="utf-8")
    return {"out_dir": str(dest), "aggregate": payload}
