#!/usr/bin/env python3
"""Fit a family's discrepancy GP on training-era residuals only.

Hyperparameters come from the preregistered grid by the two-stage rule
frozen before any B005 target existed: marginal likelihood first, then,
among candidates statistically indistinguishable from the best, the one
whose cross-validated 90% coverage sits closest to 0.90.

The cross-validated numbers are the honest preview of what the model
will do on blind targets, and they are recorded in the artifact whether
they flatter it or not.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elementzero.evidence.hashing import canonical_json  # noqa: E402
from elementzero.model_discrepancy.artifacts import (  # noqa: E402
    build_calibration_artifact,
    build_discrepancy_artifact,
)
from elementzero.model_discrepancy.dataset import design_matrix  # noqa: E402
from elementzero.model_discrepancy.gp import (  # noqa: E402
    select_hyperparameters,
    standardize,
)

READINESS = Path("reports/readiness/wo15b")

FAMILIES = {
    "skyrme_hfb_edf": {
        "artifact": READINESS / "parameter_artifact_EZ-PHYS-SKYRME-HFB-v2.json",
        "provenance_class": "REFIT_STRICT",
        "blind_eligible": True,
    },
    "gogny_finite_range_hfb": {
        "artifact": Path(
            "reports/physics_backends/wo15/fits/"
            "parameter_artifact_EZ-PHYS-GOGNY-HFB-v1.json"
        ),
        "provenance_class": "HISTORICAL_FROZEN_PARTIAL",
        "blind_eligible": True,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True, choices=sorted(FAMILIES))
    args = parser.parse_args()

    spec = FAMILIES[args.family]
    training = json.loads(
        (READINESS / f"training_set_{args.family}.json").read_text(
            encoding="utf-8"
        )
    )
    parameter_artifact = json.loads(
        spec["artifact"].read_text(encoding="utf-8")
    )

    x_raw, y, names = design_matrix(training)
    print(f"{len(y)} training residuals, {len(names)} features", flush=True)
    x, means, stds = standardize(x_raw)

    chosen = select_hyperparameters(x, y)
    cv = chosen["cv"]
    print(
        f"length_scale={chosen['length_scale']} "
        f"signal={chosen['signal_std_keV']} noise={chosen['noise_std_keV']} "
        f"(shortlist {chosen['n_shortlisted']}/{chosen['n_grid_points_evaluated']})"
    )
    print(
        f"cv MAE {cv['cv_MAE_keV']:.1f} keV | RMSE {cv['cv_RMSE_keV']:.1f} keV "
        f"| coverage_90 {cv['cv_coverage_90']:.3f} "
        f"| z-std {cv['cv_standardized_std']:.3f}"
    )

    discrepancy = build_discrepancy_artifact(
        family_id=args.family,
        independence_group=args.family,
        training_set=training,
        hyperparameters={
            "length_scale": chosen["length_scale"],
            "signal_std_keV": chosen["signal_std_keV"],
            "noise_std_keV": chosen["noise_std_keV"],
            "selection_rule": chosen["selection_rule"],
        },
        cv_metrics=cv,
        feature_names=names,
        scaling={"means": means, "stds": stds},
    )
    (READINESS / f"discrepancy_artifact_{args.family}.json").write_text(
        canonical_json(discrepancy) + "\n", encoding="utf-8"
    )

    calibration = build_calibration_artifact(
        family_id=args.family,
        independence_group=args.family,
        raw_parameter_artifact=parameter_artifact["artifact_id"],
        discrepancy_artifact=discrepancy,
        training_set=training,
        calibration_set_hash=training["training_set_hash"],
        training_coverage=None,
        cv_coverage=cv,
        provenance_class=spec["provenance_class"],
        blind_eligible=spec["blind_eligible"],
    )
    (READINESS / f"calibration_artifact_{args.family}.json").write_text(
        canonical_json(calibration) + "\n", encoding="utf-8"
    )
    print(f"discrepancy {discrepancy['artifact_id']}")
    print(f"calibration {calibration['calibration_artifact_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
