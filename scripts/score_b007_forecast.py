#!/usr/bin/env python3
"""WO-206 — score the sealed EZ-B007 forecast against a future AME edition.

    python scripts/score_b007_forecast.py \
        --seal experiments/EZ-B007-v2 \
        --edition data/amdc/mass.mas25.txt \
        --edition-id AME2025 \
        --out experiments/EZ-B007-v2/scoring

Runs unattended and REFITS NOTHING. It reads the sealed predictions, joins them
to the new edition on nuclide id, keeps only targets that became measured, and
scores those. Everything it needs was fixed at seal time; this script has no
model in it at all, which is the point — there is nothing here that could be
tuned after seeing the answers.

Three comparisons are reported:

    model      the sealed predictions
    AMDC       the evaluators' own AME2020 extrapolation for the same nuclides
    delta      whether the model beat the extrapolation it was competing with

The AMDC baseline is what makes the result meaningful. A mass model that cannot
beat the evaluation's own extrapolation has not demonstrated anything, and
without the baseline in the same table that question is easy to avoid.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from elementzero.data.amdc.common import (  # noqa: E402
    AME_MAS20_COLUMNS,  # noqa: E402
    EditionSpec,
    parse_ame_mass_table_detailed,
)
from elementzero.evidence.hashing import canonical_json, sha256_file  # noqa: E402
from elementzero.experiments import b007_prospective as b007  # noqa: E402
from elementzero.uq.calibration import calibration_report  # noqa: E402


def summarize(truth: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    err = truth - pred
    return {
        "n": int(err.size),
        "mae_keV": float(np.mean(np.abs(err))),
        "rmse_keV": float(np.sqrt(np.mean(err**2))),
        "median_abs_error_keV": float(np.median(np.abs(err))),
        "max_abs_error_keV": float(np.max(np.abs(err))),
        "bias_keV": float(np.mean(err)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", default="experiments/EZ-B007-v2")
    parser.add_argument("--edition", required=True, help="path to the new AME mass table")
    parser.add_argument("--edition-id", required=True, help="e.g. AME2025")
    parser.add_argument("--edition-year", type=int, default=0)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    seal_dir = pathlib.Path(args.seal)
    if not seal_dir.is_absolute():
        seal_dir = REPO_ROOT / seal_dir
    seal = json.loads((seal_dir / "SEALED_PREDICTIONS.json").read_text())
    protocol = json.loads((seal_dir / "forecast_protocol.json").read_text())
    references = json.loads((seal_dir / "reference_extrapolations.json").read_text())

    # The seal must verify before anything is scored against it.
    recomputed = b007.seal_digest(seal)
    if recomputed != seal["seal_sha256"]:
        raise SystemExit(
            f"seal digest mismatch: recomputed {recomputed}, sealed {seal['seal_sha256']}.\n"
            "The sealed predictions have been altered since they were committed; "
            "refusing to score."
        )
    print(f"seal verified: {seal['seal_sha256']}")
    print(f"  sealed predictions : {seal['n_predictions']}")
    print(f"  blindness tier     : {seal['blindness_tier']}")
    print(f"  claim eligible     : {seal.get('claim_eligible')}")

    spec = EditionSpec(
        edition_id=args.edition_id,
        release_date="",
        columns=AME_MAS20_COLUMNS,
        filename_hints=(),
        year=args.edition_year or 9999,
    )
    observations, _ = parse_ame_mass_table_detailed(args.edition, spec)
    newly_measured = {
        o.nuclide_id: o for o in observations if b007.is_measured(o)
    }
    print(f"{args.edition_id}: {len(observations)} records, {len(newly_measured)} measured")

    amdc = {r["nuclide_id"]: r for r in references}
    rows = []
    for p in seal["predictions"]:
        obs = newly_measured.get(p["nuclide_id"])
        if obs is None:
            continue  # still unmeasured: not scoreable, not a miss
        ref = amdc.get(p["nuclide_id"], {})
        rows.append(
            {
                "nuclide_id": p["nuclide_id"],
                "Z": p["Z"],
                "N": p["N"],
                "A": p["A"],
                "distance_bucket": p["distance_bucket"],
                "truth_mass_excess_keV": obs.mass_excess_keV,
                "truth_uncertainty_keV": obs.uncertainty_keV,
                "predicted_mass_excess_keV": p["predicted_mass_excess_keV"],
                "predictive_sigma_keV": p["predictive_sigma_keV"],
                "amdc_extrapolated_mass_excess_keV": ref.get(
                    "amdc_extrapolated_mass_excess_keV"
                ),
            }
        )

    if not rows:
        print("\nNo sealed target has been measured in this edition yet. Nothing to score.")
        print("That is a legitimate outcome, not a failure: re-run on the next edition.")
        return 0

    truth = np.array([r["truth_mass_excess_keV"] for r in rows], dtype=float)
    pred = np.array([r["predicted_mass_excess_keV"] for r in rows], dtype=float)
    sigma = np.array([r["predictive_sigma_keV"] for r in rows], dtype=float)
    model_metrics = summarize(truth, pred)
    calibration = calibration_report(truth, pred, sigma)

    have_ref = [r for r in rows if r["amdc_extrapolated_mass_excess_keV"] is not None]
    baseline_metrics = None
    if have_ref:
        bt = np.array([r["truth_mass_excess_keV"] for r in have_ref], dtype=float)
        bp = np.array([r["amdc_extrapolated_mass_excess_keV"] for r in have_ref], dtype=float)
        baseline_metrics = summarize(bt, bp)

    by_bucket: dict[str, dict] = {}
    for bucket in sorted({r["distance_bucket"] for r in rows}):
        sel = [r for r in rows if r["distance_bucket"] == bucket]
        bt = np.array([r["truth_mass_excess_keV"] for r in sel], dtype=float)
        bp = np.array([r["predicted_mass_excess_keV"] for r in sel], dtype=float)
        by_bucket[bucket] = summarize(bt, bp)

    result = {
        "experiment_id": b007.EXPERIMENT_ID,
        "scored_against": {
            "edition_id": args.edition_id,
            "file": str(args.edition),
            "sha256": sha256_file(args.edition),
        },
        "seal_sha256": seal["seal_sha256"],
        "seal_verified": True,
        "blindness_tier": seal["blindness_tier"],
        "claim_eligible_at_seal_time": seal.get("claim_eligible"),
        "refit_performed": False,
        "n_sealed": seal["n_predictions"],
        "n_scoreable": len(rows),
        "n_still_unmeasured": seal["n_predictions"] - len(rows),
        "model": model_metrics,
        "amdc_extrapolation_baseline": baseline_metrics,
        "model_beats_amdc_baseline": (
            None
            if baseline_metrics is None
            else bool(model_metrics["mae_keV"] < baseline_metrics["mae_keV"])
        ),
        "calibration": calibration.to_dict(),
        "by_distance_bucket": by_bucket,
        "rows": rows,
        "claim_ceiling": protocol.get("claim_eligibility", {}),
    }

    out = pathlib.Path(args.out) if args.out else seal_dir / "scoring"
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    (out / "SCORE_REPORT.json").write_text(canonical_json(result) + "\n")

    print(f"\nscoreable targets: {len(rows)} of {seal['n_predictions']}")
    print(f"  model MAE : {model_metrics['mae_keV']:10.1f} keV   RMSE {model_metrics['rmse_keV']:10.1f} keV")
    if baseline_metrics:
        print(f"  AMDC  MAE : {baseline_metrics['mae_keV']:10.1f} keV   RMSE {baseline_metrics['rmse_keV']:10.1f} keV")
        print(f"  model beats AMDC extrapolation: {result['model_beats_amdc_baseline']}")
    print(f"  calibration: {calibration.verdict} (std_z {calibration.std_z:.3f})")
    print(f"written: {out / 'SCORE_REPORT.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
