"""Reproduce and quantify the v1 predictive-sigma defect.

Run:

    python scripts/diagnose_v1_sigma.py --out /tmp/sigma_defect.json

This script does not touch any sealed v1 artifact. It re-runs the frozen v1
kernel configuration on a controlled synthetic surface, next to the v2 kernel,
and records the calibration verdict for each. It exists so the defect is a
committed, reproducible finding rather than a claim in a report.

`--out` is required and the committed `reports/v2/sigma_defect.json` is refused
by default: that file is the recording of record, not this script's output. To
compare a rerun against it, write to a scratch path and use
`scripts/diagnose_replay_determinism.py`, which does the comparison at both the
byte and the findings level.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import sys

import numpy as np
import sklearn
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from elementzero.models.gp_calibrated import (  # noqa: E402
    CallableBackbone,
    GPResidualV2,
    prior_sigma_scale_keV,
)
from elementzero.uq.calibration import calibration_report  # noqa: E402

V1_KERNEL_DESCRIPTION = (
    "ConstantKernel(1.0e6, fixed) * RBF(8.0, fixed) + WhiteKernel(1.0e4, fixed), "
    "optimizer=None, normalize_y=True"
)


def synthetic_surface(seed: int = 0, n_points: int = 400):
    rng = np.random.default_rng(seed)
    z = rng.integers(8, 100, n_points)
    n = rng.integers(8, 150, n_points)
    y = 300.0 * np.sin(z / 9.0) + 200.0 * np.cos(n / 11.0) + rng.normal(0, 50, n_points)
    return z, n, y


ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORDED_ARTIFACT = pathlib.Path("reports/v2/sigma_defect.json")


def resolve_out(out: str, allow_overwrite_recorded: bool) -> pathlib.Path:
    """Refuse to overwrite the recorded reproduction by accident.

    `reports/v2/sigma_defect.json` is the committed recording of the v1 sigma
    defect. AGENTS.md says not to regenerate it in place, and the charter treats
    it as evidence rather than output. A default that wrote straight over it
    left that rule enforced by prose alone, one bare invocation away from
    silently replacing the artifact with a rerun from a different host — which,
    per `reports/v2/replay_environment.json`, would not even be byte-identical.

    So `--out` is required, and the recorded path is refused unless the caller
    asks for it explicitly. Re-recording it is a legitimate act after a protocol
    version bump; doing it without meaning to is not.
    """
    path = pathlib.Path(out)
    target = path if path.is_absolute() else pathlib.Path.cwd() / path
    # Anchored to the repository, not the working directory: the artifact is at
    # a fixed place in the tree, and a guard that moved with `cd` would not be
    # one.
    recorded = ROOT / RECORDED_ARTIFACT

    if target.resolve() == recorded.resolve() and not allow_overwrite_recorded:
        raise SystemExit(
            f"refusing to overwrite the recorded artifact {RECORDED_ARTIFACT}.\n"
            "It is the committed reproduction of the v1 sigma defect, not scratch output.\n"
            "Write elsewhere and compare:\n"
            "    python scripts/diagnose_v1_sigma.py --out /tmp/sigma_defect.json\n"
            "    python scripts/diagnose_replay_determinism.py\n"
            "If you genuinely intend to re-record it (protocol version bump), pass "
            "--allow-overwrite-recorded."
        )
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        required=True,
        help="where to write the diagnostic; the recorded artifact path is refused "
        "unless --allow-overwrite-recorded is also passed",
    )
    parser.add_argument(
        "--allow-overwrite-recorded",
        action="store_true",
        help=f"permit writing over {RECORDED_ARTIFACT}; only for a deliberate re-record",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--n-points", type=int, default=400)
    args = parser.parse_args()
    out_path = resolve_out(args.out, args.allow_overwrite_recorded)

    z, n, y = synthetic_surface(args.seed, args.n_points)
    split = int(0.7 * len(z))
    y_std = float(np.std(y))

    # --- frozen v1 configuration -------------------------------------------
    x = np.column_stack([z, n, z + n]).astype(float)
    v1 = GaussianProcessRegressor(
        kernel=ConstantKernel(1.0e6, "fixed") * RBF(8.0, length_scale_bounds="fixed")
        + WhiteKernel(1.0e4, noise_level_bounds="fixed"),
        optimizer=None,
        normalize_y=True,
        random_state=0,
    ).fit(x[:split], y[:split])
    v1_mean, v1_sigma = v1.predict(x[split:], return_std=True)
    v1_report = calibration_report(y[split:], v1_mean, v1_sigma)

    # --- v2 configuration ---------------------------------------------------
    backbone = CallableBackbone("ZERO", lambda a, b: np.zeros(np.asarray(a).shape, dtype=float))
    v2_model = GPResidualV2(backbone=backbone).fit(z[:split], n[:split], y[:split])
    v2_mean, v2_sigma = v2_model.predict(z[split:], n[split:])
    v2_report = calibration_report(y[split:], v2_mean, v2_sigma)

    payload = {
        "diagnostic": "ez-v2-sigma-defect-v1",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "surface": {
            "kind": "synthetic",
            "seed": args.seed,
            "n_points": args.n_points,
            "n_train": split,
            "n_test": len(z) - split,
            "y_std_keV": y_std,
        },
        "root_cause": (
            "ConstantKernel.constant_value is a VARIANCE, so the v1 amplitude is "
            "sqrt(1.0e6) = 1000. With normalize_y=True that amplitude multiplies "
            "unit-variance targets and sklearn rescales sigma by y_train_std, giving "
            "a prior predictive sigma of 1000 * y_train_std. optimizer=None meant the "
            "data could never correct it."
        ),
        "v1": {
            "kernel": V1_KERNEL_DESCRIPTION,
            "prior_sigma_bound_keV": prior_sigma_scale_keV(1.0e6, y_std),
            "median_sigma_keV": float(np.median(v1_sigma)),
            "median_abs_error_keV": float(np.median(np.abs(y[split:] - v1_mean))),
            "sigma_over_y_std": float(np.median(v1_sigma) / y_std),
            "calibration": v1_report.to_dict(),
        },
        "v2": {
            "kernel": v2_model.manifest()["kernel_learned"],
            "median_sigma_keV": float(np.median(v2_sigma)),
            "median_abs_error_keV": float(np.median(np.abs(y[split:] - v2_mean))),
            "sigma_over_y_std": float(np.median(v2_sigma) / y_std),
            "calibration": v2_report.to_dict(),
        },
        "conclusion": (
            "The v1 configuration is UNCERTAINTY_OVERDISPERSED by roughly two orders "
            "of magnitude; the v2 configuration recovers std(z) near 1. The v1 mean "
            "function is largely unaffected, which is why the WO-11 hyperparameter "
            "grid saw an identical MAE for hp-no-normalize-y: the defect was confined "
            "to sigma, the one quantity Doctrine 4 makes load-bearing."
        ),
    }

    out = out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"v1 median sigma : {payload['v1']['median_sigma_keV']:12.1f} keV   "
          f"std(z) = {v1_report.std_z:.4f}   {v1_report.dispersion_class}")
    print(f"v2 median sigma : {payload['v2']['median_sigma_keV']:12.1f} keV   "
          f"std(z) = {v2_report.std_z:.4f}   {v2_report.dispersion_class}")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
