#!/usr/bin/env python3
"""WO-206 — build and seal the EZ-B007 prospective forecast.

    python scripts/seal_b007_forecast.py --out experiments/EZ-B007-v2

Predicts every nuclide AME2020 records as an extrapolation, with calibrated
intervals, and writes a hashed seal. Run it BEFORE the next AME edition exists;
that is the whole point, and it cannot be re-run honestly afterwards.

The AME2020 snapshot is verified byte-for-byte against the sha256 pinned in
`elementzero.eligibility.historical_sources` before anything is fitted. A seal
built from an unverified table would be worthless, so a mismatch is fatal.

Writes, under the output directory:

    PREREGISTRATION.md              prose statement of the frozen protocol
    forecast_protocol.json          identities, policies, code and data identity
    targets.json                    identity-only target manifest
    reference_extrapolations.json   the AMDC's own extrapolations (baseline)
    calibration_qualification.json  EZ-B004 on both preregistered splits
    SEALED_PREDICTIONS.json         the predictions, with the seal hash
    SEAL_SHA256                      the digest, alone, for quick diffing

Re-sealing over an existing seal is refused unless --allow-reseal is passed: the
value of this artifact is that it was committed before the answers existed, and
silently regenerating it destroys exactly that.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import platform
import subprocess
import sys

import numpy as np
import scipy
import sklearn

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from elementzero import __version__  # noqa: E402
from elementzero.atlas_pin import atlas_pir_ref  # noqa: E402
from elementzero.data.amdc.ame2020 import EDITION as AME2020  # noqa: E402
from elementzero.data.amdc.common import parse_ame_mass_table_detailed  # noqa: E402
from elementzero.data.observations import GROUND_TRUTH_POLICY  # noqa: E402
from elementzero.eligibility.historical_sources import (  # noqa: E402
    HISTORICAL_SOURCES,
    snapshot_path,
)
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex  # noqa: E402
from elementzero.experiments import b007_prospective as b007  # noqa: E402
from elementzero.identity_meta import elementzero_commit  # noqa: E402

PIN_CHECKER = REPO_ROOT / "tools" / "check_environment_pin.py"


def assert_pinned_environment(allow_unpinned: bool) -> None:
    """A seal produced off-pin is not a protocol-v2 result.

    `forecast_protocol.json` records the environment the forecast was actually
    fitted in, so the seal IS the run of record — not a portability probe. Under
    a different scikit-learn the optimizer converges to a different kernel and
    the sealed sigmas differ, which is the whole reason protocol.json pins the
    stack and calls an unpinned environment a violation rather than a footnote.

    Enforced here rather than left to discipline, because the first version of
    this script was run off-pin by exactly the person who wrote the pin.
    """
    if allow_unpinned:
        print("WARNING: --allow-unpinned set; this seal is NOT a protocol-v2 result")
        return
    result = subprocess.run(
        [sys.executable, str(PIN_CHECKER)], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise SystemExit(
            f"{result.stdout}{result.stderr}\n"
            "Refusing to seal off-pin. The seal records the environment it was "
            "fitted in and is the protocol-v2 run of record, so an unpinned run "
            "would be evidence of nothing.\n"
            "Install the pinned stack (see docs/v2/README.md), export "
            "OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1, and retry."
        )
    print("environment pin: OK")


def load_verified_ame2020() -> tuple[list, str, pathlib.Path]:
    """Parse AME2020, refusing any byte drift from the pinned snapshot."""
    record = HISTORICAL_SOURCES["AME2020"]
    path = snapshot_path("AME2020", repo_root=REPO_ROOT)
    if not path.is_file():
        raise SystemExit(
            f"AME2020 snapshot missing at {path}.\n"
            "Fetch it first:  python tools/fetch_ame_sources.py AME2020"
        )
    digest = sha256_file(path)
    if digest != record["raw_sha256"]:
        raise SystemExit(
            f"AME2020 snapshot at {path} has sha256 {digest}, but the pinned value is "
            f"{record['raw_sha256']}. Refusing to seal a forecast from an unverified table."
        )
    observations, report = parse_ame_mass_table_detailed(path, AME2020)
    print(f"AME2020: {len(observations)} records parsed ({report.parser_version}), sha256 verified")
    return observations, digest, path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiments/EZ-B007-v2")
    parser.add_argument("--allow-reseal", action="store_true")
    parser.add_argument(
        "--allow-unpinned",
        action="store_true",
        help="produce a seal outside the protocol pin; the result is NOT a "
        "protocol-v2 run of record and must not be committed as one",
    )
    parser.add_argument(
        "--next-edition-year",
        type=int,
        default=2025,
        help="lower bound on the next edition's year, used only to resolve the "
        "blindness tier; the seal makes no claim about the release date",
    )
    args = parser.parse_args()

    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = REPO_ROOT / out
    sealed = out / "SEALED_PREDICTIONS.json"
    # Checked before the pin, because "a seal already exists here" is the more
    # specific problem and you should not need a pinned stack to be told it.
    if sealed.is_file() and not args.allow_reseal:
        raise SystemExit(
            f"refusing to overwrite an existing seal at {sealed}.\n"
            "A prospective forecast is evidence because it was committed before the "
            "answers existed; regenerating it silently destroys that.\n"
            "Pass --allow-reseal only if the existing seal was never committed."
        )

    assert_pinned_environment(args.allow_unpinned)

    observations, raw_sha, raw_path = load_verified_ame2020()
    measured, extrapolated = b007.split_by_measurement_status(observations)
    print(f"  measured (trainable) : {len(measured)}")
    print(f"  extrapolated (targets): {len(extrapolated)}")

    # ---- EZ-B004 qualification on both preregistered splits -----------------
    random_ids = b007.random_holdout_ids(measured)
    frontier_ids = b007.frontier_holdout_ids(measured)
    splits = {}
    for name, ids in (("random_holdout", random_ids), ("frontier_holdout", frontier_ids)):
        report, detail = b007.qualify_calibration(measured, ids)
        splits[name] = {"holdout_nuclide_ids": list(ids), **detail}
        print(
            f"EZ-B004 {name:17s}: {report.verdict:18s} std(z)={report.std_z:6.3f} "
            f"MAE={detail['mae_keV']:8.1f} keV  median sigma={detail['median_sigma_keV']:8.1f} keV"
        )

    governing = splits[b007.GOVERNING_SPLIT]["calibration"]
    print(f"governing split ({b007.GOVERNING_SPLIT}) verdict: {governing['verdict']}")

    # ---- declared, pre-seal conformal repair attempt ------------------------
    repair = b007.attempt_conformal_repair(measured, frontier_ids)
    if repair["scaler"]["fitted"]:
        print(
            f"conformal repair: scale={repair['scaler']['scale']:.3f} "
            f"std_z {repair['before']['std_z']:.3f} -> {repair['after']['std_z']:.3f} "
            f"KS {repair['before']['pit_ks_d']:.3f} -> {repair['after']['pit_ks_d']:.3f} "
            f"| adopted={repair['adopted']}"
        )
    else:
        print(f"conformal repair refused: {repair['reason']}")

    claim_eligible = governing["verdict"] == "CALIBRATION_PASS" or repair["adopted"]

    # ---- the sealed model, fitted on all measured data ----------------------
    model = b007.fit_forecast_model(measured)
    targets = b007.build_target_manifest(extrapolated, measured)
    predictions = b007.predict_targets(model, targets)

    # If — and only if — the declared repair actually qualified, it has to be
    # APPLIED, not merely credited. Granting eligibility from an adopted scaler
    # while sealing raw sigmas would label the intervals conformal-repaired and
    # store un-repaired ones, which is precisely the gate bypass EZ-B004 exists
    # to prevent. Architecture section 5 also folds an adopted repair into model
    # identity, so the model id changes with it.
    model_id = model.model_id
    if repair["adopted"]:
        scale = float(repair["scaler"]["scale"])
        for row in predictions:
            row["predictive_sigma_keV"] *= scale
            row["sigma_conformal_scale_applied"] = scale
        model_id = f"{model_id}+CONF-v2"
        print(f"conformal repair APPLIED to sealed sigmas: scale={scale:.3f}, id={model_id}")
    references = b007.build_reference_extrapolations(extrapolated)
    tier, tier_detail = b007.resolve_forecast_tier(next_edition_year=args.next_edition_year)
    print(f"blindness tier: {tier}")

    out.mkdir(parents=True, exist_ok=True)

    protocol = {
        "experiment_id": b007.EXPERIMENT_ID,
        "benchmark_id": b007.BENCHMARK_ID,
        "protocol_version": "2.0.0",
        "forecast_policy_id": b007.FORECAST_POLICY_ID,
        "module_version": b007.MODULE_VERSION,
        "question": (
            "what does the model say about masses that have not been measured yet?"
        ),
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "source": {
            "edition_id": AME2020.edition_id,
            "release_date": AME2020.release_date,
            "raw_file": raw_path.name,
            "raw_sha256": raw_sha,
            "source_url": HISTORICAL_SOURCES["AME2020"]["source_url"],
        },
        "target_rule": (
            "every AME2020 record flagged estimated (#) — the AMDC's own "
            "extrapolations, i.e. the pool the next edition's measurements come from. "
            "All of them, with no 'most likely' selection: excluding a target is "
            "indistinguishable afterwards from having predicted it badly."
        ),
        "training_rule": (
            "AME2020 measured (non-estimated) values only, per ez-gt-policy-v1. An "
            "AMDC extrapolation is never trained on and never scored as truth."
        ),
        "n_training": len(measured),
        "n_targets": len(targets),
        "calibration_splits": {
            "random_holdout": {
                "fraction": b007.RANDOM_HOLDOUT_FRACTION,
                "seed": b007.RANDOM_HOLDOUT_SEED,
                "regime": "interpolation",
            },
            "frontier_holdout": {
                "fraction": b007.FRONTIER_HOLDOUT_FRACTION,
                "neighbourhood_l1": b007.FRONTIER_NEIGHBOURHOOD_L1,
                "regime": "extrapolation",
                "selection": "sparsest measured neighbourhood, ties by nuclide_id",
            },
            "governing_split": b007.GOVERNING_SPLIT,
            "why": (
                "every target sits off the edge of the measured chart, so the frontier "
                "split is the one that resembles the task; qualifying only on a random "
                "holdout would certify sigma in a regime this forecast never operates in"
            ),
        },
        "blindness": tier_detail,
        "conformal_repair": repair,
        "claim_eligibility": {
            "claim_eligible": claim_eligible,
            "governing_verdict": governing["verdict"],
            "governing_split": b007.GOVERNING_SPLIT,
            "policy": (
                "docs/v2/05_CLAIM_POLICY_v2.md: a model that fails EZ-B004 may say "
                "nothing quantitative, and no point metric may be presented without "
                "its sigma. This seal is a dated RECORD, not a claim: it is committed "
                "because the prospective window closes permanently once the next "
                "edition is published, and a failing forecast scored later is still "
                "evidence about the model."
            ),
            "permitted": (
                "cite the existence, date and hash of this seal; report its verdict"
                if not claim_eligible
                else "report scored accuracy with calibrated intervals on this target set"
            ),
            "forbidden": (
                "any accuracy or interval claim from these predictions, and any "
                "statement about real nuclei derived from them"
                if not claim_eligible
                else "any extrapolation beyond the scored target set"
            ),
        },
        "model": {**model.manifest(), "sealed_model_id": model_id},
        "code_identity": {
            "elementzero_version": __version__,
            "elementzero_commit": elementzero_commit(),
            "atlas_pir_ref": atlas_pir_ref(),
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "blas_threads": os.environ.get("OMP_NUM_THREADS"),
            "produced_under_protocol_pin": not args.allow_unpinned,
        },
        "scoring": {
            "script": "scripts/score_b007_forecast.py",
            "refit_permitted": False,
            "instruction": (
                "when the next AME edition is published, run the scoring script "
                "against it. It joins on nuclide id, scores only targets that became "
                "measured, and refits nothing."
            ),
        },
    }

    (out / "forecast_protocol.json").write_text(canonical_json(protocol) + "\n")
    # Shape matches the existing experiments/*/targets.json contract that
    # elementzero.visuals.ingest consumes: an object with a "targets" list, not
    # a bare array. The visual pipeline scans the repository for this filename.
    target_manifest = {
        "benchmark_id": b007.BENCHMARK_ID,
        "experiment_id": b007.EXPERIMENT_ID,
        "target_policy_id": b007.FORECAST_POLICY_ID,
        "targets": targets,
    }
    (out / "targets.json").write_text(canonical_json(target_manifest) + "\n")
    (out / "reference_extrapolations.json").write_text(canonical_json(references) + "\n")
    (out / "calibration_qualification.json").write_text(canonical_json(splits) + "\n")

    seal = {
        "experiment_id": b007.EXPERIMENT_ID,
        "forecast_policy_id": b007.FORECAST_POLICY_ID,
        "hash_rule": b007.SEAL_HASH_RULE,
        "sealed_before_edition": "AME2020 is the current evaluation; the truth edition does not exist yet",
        "blindness_tier": tier,
        "calibration_governing_verdict": governing["verdict"],
        "calibration_governing_split": b007.GOVERNING_SPLIT,
        "claim_eligible": claim_eligible,
        "conformal_repair_adopted": repair["adopted"],
        "sealed_model_id": model_id,
        "sigma_provenance": (
            "raw model predictive sigma; the declared conformal repair was attempted "
            "and NOT adopted"
            if not repair["adopted"]
            else (
                "conformal-repaired sigma: the adopted scale is applied to every "
                "sealed predictive_sigma_keV and folded into the model id"
            )
        ),
        "protocol_sha256": sha256_hex(canonical_json(protocol)),
        "targets_sha256": sha256_hex(canonical_json(target_manifest)),
        "calibration_sha256": sha256_hex(canonical_json(splits)),
        "reference_extrapolations_sha256": sha256_hex(canonical_json(references)),
        "n_predictions": len(predictions),
        "predictions": predictions,
    }
    seal["seal_sha256"] = b007.seal_digest(seal)
    (out / "SEALED_PREDICTIONS.json").write_text(canonical_json(seal) + "\n")
    (out / "SEAL_SHA256").write_text(seal["seal_sha256"] + "\n")

    print(f"\nsealed {len(predictions)} predictions  (claim_eligible={claim_eligible})")
    print(f"seal sha256: {seal['seal_sha256']}")
    print(f"written to : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
