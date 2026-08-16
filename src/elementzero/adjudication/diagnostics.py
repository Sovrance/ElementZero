"""WO-11.4 / WO-11.5 / WO-11.6 — diagnostics from the sealed v1 predictions.

Everything here is computed from the *committed* score reports of
EZ-B002-v1 and EZ-B003-v1. No model is fit, no prediction is regenerated, and
no threshold is applied: these are descriptive statistics whose only job is to
locate the failure, not to relabel it.

Per scored target (WO-11.4):

    residual              = prediction_keV - truth_keV
    absolute_error_keV    = abs(residual)
    standardized_residual = residual / std_keV
    nearest_training_L1, Z, N, A, isospin_asymmetry = (N - Z) / A

Calibration (WO-11.5), per model and benchmark, over standardized residuals
z_i = (truth_i - prediction_i) / std_i:

    mean(z), std(z),
    fraction(abs(z) <= 1), fraction(abs(z) <= 1.645),
    fraction(abs(z) <= 1.96), fraction(abs(z) > 3)

Extrapolation depth (WO-11.6): buckets d = 1, d = 2, d = 3-4, d >= 5 over
nearest_training_L1, each with n / MAE / RMSE / NLPD / coverage_90 /
coverage_95, plus a *descriptive* least-squares slope of absolute error
against depth. The slope is not a significance claim: no statistical protocol
is preregistered for it, and the depth range of the v1 evidence is shallow.
"""

from __future__ import annotations

import math
import statistics
from pathlib import Path
from typing import Any

from elementzero.evidence.hashing import canonical_json
from elementzero.evidence.ledger import read_json

UNCERTAINTY_DIAGNOSTICS_FILE = "uncertainty_diagnostics.json"

DEPTH_BUCKETS = ("d=1", "d=2", "d=3-4", "d>=5")

DESCRIPTIVE_SLOPE_RULE = (
    "ez-wo11-depth-slope-v1: ordinary least squares of absolute_error_keV "
    "against nearest_training_L1, reported as a descriptive summary only. No "
    "confidence interval and no significance claim: no statistical protocol "
    "for the slope is preregistered, and v1 depths only reach L1 = 3."
)

CALIBRATION_INTERPRETATION_RULE = (
    "ez-wo11-calibration-readout-v1: mean(z) far from 0 indicates systematic "
    "bias; std(z) >> 1 indicates uncertainty too narrow (undercoverage); "
    "std(z) << 1 indicates uncertainty too wide (overcoverage). These readouts "
    "are diagnostics, not automatic causal proof."
)


def depth_bucket(distance: int) -> str:
    if distance <= 1:
        return "d=1"
    if distance == 2:
        return "d=2"
    if distance <= 4:
        return "d=3-4"
    return "d>=5"


# --------------------------------------------------------------------------- #
# Row loading from the committed experiments                                  #
# --------------------------------------------------------------------------- #


def _diagnostic_row(row: dict[str, Any], *, model_id: str, group: dict[str, Any]) -> dict[str, Any]:
    prediction = float(row["prediction_keV"])
    truth = float(row["truth_keV"])
    std = float(row["std_keV"])
    z_val, n_val = int(row["Z"]), int(row["N"])
    a_val = int(row.get("A", z_val + n_val))
    residual = prediction - truth
    return {
        "model_id": model_id,
        "nuclide_id": row["nuclide_id"],
        "Z": z_val,
        "N": n_val,
        "A": a_val,
        "isospin_asymmetry": (n_val - z_val) / a_val,
        "nearest_training_L1": int(row["nearest_training_L1"]),
        "prediction_keV": prediction,
        "truth_keV": truth,
        "std_keV": std,
        "residual_keV": residual,
        "absolute_error_keV": abs(residual),
        "standardized_residual": residual / std,
        "interval_p90": [float(row["interval_p90"][0]), float(row["interval_p90"][1])],
        "interval_p95": [float(row["interval_p95"][0]), float(row["interval_p95"][1])],
        **group,
    }


def load_b002_rows(experiment_dir: str | Path) -> list[dict[str, Any]]:
    """Every scored target of every sealed EZ-B002-v1 region run."""
    root = Path(experiment_dir)
    sealed = read_json(root / "SEALED_PREDICTIONS.json")
    rows: list[dict[str, Any]] = []
    for region in sealed["regions"]:
        for run in region["runs"]:
            report = read_json(
                root / run["run_relpath"] / "scoring" / "score_report.json"
            )
            for row in report["rows"]:
                rows.append(
                    _diagnostic_row(
                        row,
                        model_id=report["model_id"],
                        group={
                            "benchmark_id": "EZ-B002",
                            "region_id": report["region_id"],
                            "z_band": report["z_band"],
                        },
                    )
                )
    return rows


def load_b003_rows(experiment_dir: str | Path) -> list[dict[str, Any]]:
    """Every scored masked target of every sealed EZ-B003-v1 challenge run."""
    root = Path(experiment_dir)
    sealed = read_json(root / "SEALED_PREDICTIONS.json")
    rows: list[dict[str, Any]] = []
    for challenge in sealed["challenges"]:
        for run in challenge["runs"]:
            report = read_json(
                root / run["run_relpath"] / "scoring" / "score_report.json"
            )
            closure = int(report["closure"])
            axis = report["axis"]
            for row in report["rows"]:
                coordinate = int(row["N"]) if axis == "neutron" else int(row["Z"])
                rows.append(
                    _diagnostic_row(
                        row,
                        model_id=report["model_id"],
                        group={
                            "benchmark_id": "EZ-B003",
                            "challenge_id": report["challenge_id"],
                            "axis": axis,
                            "closure": closure,
                            "distance_from_closure": abs(coordinate - closure),
                            "chain": int(row["chain"]),
                        },
                    )
                )
    return rows


def load_b003_discovery_rows(experiment_dir: str | Path) -> list[dict[str, Any]]:
    """Indicator-level chain rows (sign / rank) from the sealed shell runs."""
    root = Path(experiment_dir)
    sealed = read_json(root / "SEALED_PREDICTIONS.json")
    rows: list[dict[str, Any]] = []
    for challenge in sealed["challenges"]:
        for run in challenge["runs"]:
            report = read_json(
                root / run["run_relpath"] / "scoring" / "score_report.json"
            )
            for row in report["discovery_rows"]:
                if row.get("status") != "EVALUABLE":
                    continue
                indicator = report["indicator"]
                rows.append(
                    {
                        "model_id": report["model_id"],
                        "challenge_id": report["challenge_id"],
                        "indicator": indicator,
                        "chain": int(row["chain"]),
                        "true_indicator_MeV": float(row[f"true_{indicator}"]),
                        "predicted_indicator_MeV": float(row[f"predicted_{indicator}"]),
                        "absolute_indicator_error_MeV": float(
                            row[f"absolute_{indicator}_error"]
                        ),
                        "sign_recovered": bool(row["sign_recovered"]),
                        "local_peak_rank": int(row["local_peak_rank"]),
                        "rank_bucket": row["rank_bucket"],
                    }
                )
    return rows


# --------------------------------------------------------------------------- #
# Group summaries                                                             #
# --------------------------------------------------------------------------- #


def _nlpd(rows: list[dict[str, Any]]) -> float:
    terms = []
    for r in rows:
        std = r["std_keV"]
        z = (r["truth_keV"] - r["prediction_keV"]) / std
        terms.append(0.5 * math.log(2.0 * math.pi * std * std) + 0.5 * z * z)
    return sum(terms) / len(terms)


def _coverage(rows: list[dict[str, Any]], key: str) -> float:
    hits = sum(1 for r in rows if r[key][0] <= r["truth_keV"] <= r[key][1])
    return hits / len(rows)


def residual_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """WO-11.4 summary block for one group of diagnostic rows."""
    if not rows:
        return {"n": 0}
    residuals = [r["residual_keV"] for r in rows]
    absolute = [r["absolute_error_keV"] for r in rows]
    return {
        "n": len(rows),
        "residual_mean_keV": statistics.fmean(residuals),
        "residual_median_keV": statistics.median(residuals),
        "residual_std_keV": statistics.pstdev(residuals) if len(residuals) > 1 else 0.0,
        "MAE_keV": statistics.fmean(absolute),
        "RMSE_keV": math.sqrt(statistics.fmean([e * e for e in absolute])),
        "NLPD": _nlpd(rows),
        "coverage_90": _coverage(rows, "interval_p90"),
        "coverage_95": _coverage(rows, "interval_p95"),
    }


def calibration_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """WO-11.5 standardized-residual summary for one group."""
    if not rows:
        return {"n": 0}
    z_values = [
        (r["truth_keV"] - r["prediction_keV"]) / r["std_keV"] for r in rows
    ]
    n = len(z_values)
    return {
        "n": n,
        "mean_z": statistics.fmean(z_values),
        "std_z": statistics.pstdev(z_values) if n > 1 else 0.0,
        "fraction_abs_z_le_1": sum(1 for z in z_values if abs(z) <= 1.0) / n,
        "fraction_abs_z_le_1p645": sum(1 for z in z_values if abs(z) <= 1.645) / n,
        "fraction_abs_z_le_1p96": sum(1 for z in z_values if abs(z) <= 1.96) / n,
        "fraction_abs_z_gt_3": sum(1 for z in z_values if abs(z) > 3.0) / n,
        "interpretation_rule": CALIBRATION_INTERPRETATION_RULE,
    }


def descriptive_depth_slope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """OLS slope of absolute error vs nearest_training_L1 — descriptive only."""
    if len(rows) < 2:
        return {"n": len(rows), "slope_keV_per_L1": None, "intercept_keV": None}
    xs = [float(r["nearest_training_L1"]) for r in rows]
    ys = [r["absolute_error_keV"] for r in rows]
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0.0:
        return {"n": len(rows), "slope_keV_per_L1": None, "intercept_keV": None}
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    return {
        "n": len(rows),
        "slope_keV_per_L1": slope,
        "intercept_keV": mean_y - slope * mean_x,
        "rule": DESCRIPTIVE_SLOPE_RULE,
    }


def depth_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """WO-11.6 depth buckets; empty buckets are reported, never dropped."""
    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in DEPTH_BUCKETS}
    for row in rows:
        buckets[depth_bucket(row["nearest_training_L1"])].append(row)
    return {
        "buckets": {name: residual_summary(group) for name, group in buckets.items()},
        "descriptive_slope": descriptive_depth_slope(rows),
        "max_observed_depth": max((r["nearest_training_L1"] for r in rows), default=None),
    }


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row[key]), []).append(row)
    return dict(sorted(groups.items()))


def _model_ids(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({r["model_id"] for r in rows})


def b002_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_model: dict[str, Any] = {}
    for model_id in _model_ids(rows):
        mine = [r for r in rows if r["model_id"] == model_id]
        per_model[model_id] = {
            "pooled": residual_summary(mine),
            "calibration": calibration_summary(mine),
            "depth": depth_summaries(mine),
            "by_z_band": {
                band: residual_summary(group)
                for band, group in _group_by(mine, "z_band").items()
            },
            "by_region": {
                region: residual_summary(group)
                for region, group in _group_by(mine, "region_id").items()
            },
        }
    return {"benchmark_id": "EZ-B002", "n_rows": len(rows), "by_model": per_model}


def b003_diagnostics(
    rows: list[dict[str, Any]], discovery_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    per_model: dict[str, Any] = {}
    for model_id in _model_ids(rows):
        mine = [r for r in rows if r["model_id"] == model_id]
        my_discovery = [r for r in discovery_rows if r["model_id"] == model_id]
        per_model[model_id] = {
            "pooled": residual_summary(mine),
            "calibration": calibration_summary(mine),
            "depth": depth_summaries(mine),
            "by_hidden_closure": {
                challenge: residual_summary(group)
                for challenge, group in _group_by(mine, "challenge_id").items()
            },
            "by_distance_from_closure": {
                f"offset={distance}": residual_summary(group)
                for distance, group in _group_by(mine, "distance_from_closure").items()
            },
            "indicator": {
                "n_chains": len(my_discovery),
                "sign_recovered_fraction": (
                    sum(1 for r in my_discovery if r["sign_recovered"]) / len(my_discovery)
                    if my_discovery
                    else None
                ),
                "rank_1_fraction": (
                    sum(1 for r in my_discovery if r["local_peak_rank"] == 1)
                    / len(my_discovery)
                    if my_discovery
                    else None
                ),
                "mean_absolute_indicator_error_MeV": (
                    statistics.fmean(
                        r["absolute_indicator_error_MeV"] for r in my_discovery
                    )
                    if my_discovery
                    else None
                ),
            },
        }
    return {
        "benchmark_id": "EZ-B003",
        "n_rows": len(rows),
        "n_chain_rows": len(discovery_rows),
        "by_model": per_model,
    }


def build_uncertainty_diagnostics(
    *,
    b002_dir: str | Path,
    b003_dir: str | Path,
) -> dict[str, Any]:
    b002_rows = load_b002_rows(b002_dir)
    b003_rows = load_b003_rows(b003_dir)
    b003_chains = load_b003_discovery_rows(b003_dir)
    return {
        "work_order": "WO-11",
        "source_rule": (
            "Every number below is derived from the committed, sealed v1 score "
            "reports. No model was refit and no prediction was regenerated."
        ),
        "EZ-B002-v1": b002_diagnostics(b002_rows),
        "EZ-B003-v1": b003_diagnostics(b003_rows, b003_chains),
    }


def write_uncertainty_diagnostics(
    *, out_dir: str | Path, b002_dir: str | Path, b003_dir: str | Path
) -> dict[str, Any]:
    payload = build_uncertainty_diagnostics(b002_dir=b002_dir, b003_dir=b003_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / UNCERTAINTY_DIAGNOSTICS_FILE).write_text(
        canonical_json(payload) + "\n", encoding="utf-8"
    )
    return payload
