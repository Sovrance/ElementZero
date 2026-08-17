"""Combine raw physics with its discrepancy term, keeping components apart.

A calibrated prediction is the raw physics mass plus the discrepancy
posterior mean, with an uncertainty built from named components added in
quadrature:

    sigma^2 = numerical^2 + parameter^2 + model_discrepancy^2

Cross-family disagreement is carried alongside and never inside. The
components are kept as separate fields rather than collapsed, because a
single number cannot be audited: if a family later looks calibrated, the
question is always *which* term did the work.
"""

from __future__ import annotations

import math
from typing import Any

from elementzero.errors import ProtocolError
from elementzero.model_discrepancy.gp import apply_scaling, fit_gp, predict_gp
from elementzero.model_discrepancy.protocol import features_for

CALIBRATION_RULE = (
    "ez-wo15b-calibration-v1: calibrated mass = raw physics mass + "
    "discrepancy posterior mean. Sigma is the quadrature sum of the "
    "numerical, parameter and model-discrepancy components, each recorded "
    "by name. No scalar multiplier is applied to sigma at any point after "
    "predictions are generated"
)

SIGMA_FLOOR_KEV = 1.0


def rebuild_model(
    artifact: dict[str, Any], training_set: dict[str, Any]
) -> dict[str, Any]:
    """Refit the GP exactly as the artifact describes it.

    The artifact stores hyperparameters and scaling rather than a
    pickled model, so reconstruction is deterministic and inspectable:
    the same training rows and the same three numbers give the same
    posterior, in this process or any future one.
    """
    from elementzero.model_discrepancy.dataset import design_matrix

    x_raw, y, names = design_matrix(training_set)
    if names != list(artifact["feature_names"]):
        raise ProtocolError(
            "WO15B_FEATURE_DRIFT: the training set's feature order no longer "
            f"matches the artifact ({names} vs {artifact['feature_names']})"
        )
    scaling = artifact["feature_scaling"]
    x = apply_scaling(x_raw, scaling["means"], scaling["stds"])
    hyper = artifact["hyperparameters"]
    return fit_gp(
        x,
        y,
        length_scale=float(hyper["length_scale"]),
        signal_std=float(hyper["signal_std_keV"]),
        noise_std=float(hyper["noise_std_keV"]),
    )


def calibrate_rows(
    *,
    model: dict[str, Any],
    artifact: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply the discrepancy term to raw physics rows.

    ``rows`` carry ``nuclide_id``, ``prediction_keV`` (raw physics) and
    the numerical/parameter components already measured by the sealing
    stage. Rows without a raw prediction stay uncalibrated: a failed
    solve is a failed solve, and the discrepancy model has nothing to
    correct.
    """
    from elementzero.data.identity import parse_nuclide_id

    scaling = artifact["feature_scaling"]
    names = list(artifact["feature_names"])

    usable = [r for r in rows if r.get("prediction_keV") is not None]
    if usable:
        x_raw = []
        for row in usable:
            z, n = parse_nuclide_id(row["nuclide_id"])
            feats = features_for(z, n)
            x_raw.append([feats[name] for name in names])
        posterior = predict_gp(
            model, apply_scaling(x_raw, scaling["means"], scaling["stds"])
        )
    else:
        posterior = []

    by_id = {
        row["nuclide_id"]: (mean, std)
        for row, (mean, std) in zip(usable, posterior, strict=True)
    }

    out = []
    for row in rows:
        if row.get("prediction_keV") is None:
            out.append({**row, "calibrated": False})
            continue
        mean, std = by_id[row["nuclide_id"]]
        raw = float(row["prediction_keV"])
        numerical = _component(row.get("numerical_sigma_keV"))
        parameter = _component(row.get("parameter_sigma_keV"))
        sigma = math.sqrt(numerical**2 + parameter**2 + std**2)
        out.append(
            {
                **row,
                "calibrated": True,
                "raw_prediction_keV": raw,
                "discrepancy_mean_keV": mean,
                "discrepancy_sigma_keV": std,
                "prediction_keV": raw + mean,
                "sigma_keV": max(sigma, SIGMA_FLOOR_KEV),
                "sigma_components_keV": {
                    "numerical": numerical,
                    "parameter": parameter,
                    "model_discrepancy": std,
                },
                "calibration_rule": CALIBRATION_RULE,
            }
        )
    return out


def _component(value: Any) -> float:
    """A missing or failed component contributes nothing, not a guess.

    It is still visible as ``None`` in the row it came from, so a family
    built on failed probes cannot look identical to one built on
    measurements.
    """
    return float(value) if value is not None else 0.0


def assert_no_sigma_scaling(
    *, before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> None:
    """Refuse a uniform post-hoc multiplier on sigma.

    The signature of scalar inflation is every ratio being the same
    number; component-wise recomputation moves each row differently.
    """
    ratios = []
    for a, b in zip(before, after, strict=True):
        sa, sb = a.get("sigma_keV"), b.get("sigma_keV")
        if sa and sb and float(sa) > 0:
            ratios.append(float(sb) / float(sa))
    if len(ratios) < 3:
        return
    spread = max(ratios) - min(ratios)
    if spread < 1e-9 and abs(ratios[0] - 1.0) > 1e-9:
        raise ProtocolError(
            f"WO15B_SIGMA_SCALED: every sigma moved by the identical factor "
            f"{ratios[0]:.6f}; that is a scalar inflation, not a "
            f"recomputed decomposition. {CALIBRATION_RULE}"
        )


__all__ = [
    "CALIBRATION_RULE",
    "assert_no_sigma_scaling",
    "calibrate_rows",
    "rebuild_model",
]
