"""A small, explicit Gaussian process for the discrepancy term.

The model is deliberately plain — zero mean, RBF kernel, white noise —
because the claim rests on where the training data came from, not on
kernel cleverness. It is written out rather than delegated to a library
optimizer for the same reason the WO-15 refit was: the hyperparameter
search has to be a preregistered grid whose every evaluation is
inspectable, not whatever an optimizer with random restarts happens to
land on. NumPy does the linear algebra; the protocol stays here.

The posterior variance is the point of using a GP at all: it grows away
from the training lattice, which is exactly the behaviour a mass model
extrapolating toward the frontier needs its uncertainty to have.

Selection is two-stage and fixed before any blind target exists:
marginal likelihood first, then — among candidates statistically
indistinguishable from the best — the one whose training-era
cross-validated 90% coverage sits closest to 0.90. The second stage
exists because a discrepancy model that is merely *wide* passes no
calibration gate worth having; Gate B is two-sided.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from elementzero.errors import ProtocolError

# Preregistered hyperparameter grid, fixed before any fit runs so the
# search cannot be widened after seeing a result.
LENGTH_SCALE_GRID = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
SIGNAL_STD_GRID_KEV = (250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0)
NOISE_STD_GRID_KEV = (25.0, 50.0, 150.0, 500.0, 1500.0)
CV_FOLDS = 5

# Stage two considers every candidate within this much log-likelihood of
# the best. A flat tolerance, declared up front, rather than a cut chosen
# once the shortlist was visible.
LOG_LIKELIHOOD_TOLERANCE = 2.0
TARGET_CV_COVERAGE_90 = 0.90

SELECTION_RULE = (
    "ez-wo15b-gp-selection-v1: hyperparameters are chosen from a fixed grid "
    "by training-era marginal log-likelihood; among candidates within "
    f"{LOG_LIKELIHOOD_TOLERANCE} log-likelihood of the maximum, the one whose "
    f"{CV_FOLDS}-fold cross-validated coverage_90 is nearest "
    f"{TARGET_CV_COVERAGE_90} wins. Folds are index-modulo-k, so the split is "
    "reproducible and cannot be re-rolled. No blind truth enters either stage"
)

JITTER = 1e-8


def standardize(rows: Any) -> tuple[Any, list[float], list[float]]:
    """Zero-mean unit-variance columns; constant columns stay at zero."""
    x = np.asarray(rows, dtype=float)
    if x.size == 0:
        return x, [], []
    means = x.mean(axis=0)
    stds = x.std(axis=0)
    stds = np.where(stds > 0, stds, 1.0)
    return (x - means) / stds, means.tolist(), stds.tolist()


def apply_scaling(rows: Any, means: list[float], stds: list[float]) -> Any:
    x = np.asarray(rows, dtype=float)
    return (x - np.asarray(means)) / np.asarray(stds)


def rbf(xa: Any, xb: Any, *, length_scale: float, signal_std: float) -> Any:
    a = np.asarray(xa, dtype=float)
    b = np.asarray(xb, dtype=float)
    sq = (
        (a**2).sum(axis=1)[:, None]
        + (b**2).sum(axis=1)[None, :]
        - 2.0 * a @ b.T
    )
    np.maximum(sq, 0.0, out=sq)
    return signal_std**2 * np.exp(-sq / (2.0 * length_scale**2))


def fit_gp(
    x: Any,
    y: Any,
    *,
    length_scale: float,
    signal_std: float,
    noise_std: float,
) -> dict[str, Any]:
    """Cholesky factor and weights for one hyperparameter triple."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    k = rbf(x, x, length_scale=length_scale, signal_std=signal_std)
    k[np.diag_indices(n)] += noise_std**2 + JITTER
    try:
        low = np.linalg.cholesky(k)
    except np.linalg.LinAlgError as exc:
        raise ProtocolError(
            "GP_NUMERICAL_FAILURE: the covariance matrix is not positive "
            "definite; the fit is refused rather than nudged into working"
        ) from exc
    alpha = np.linalg.solve(low.T, np.linalg.solve(low, y))
    log_det = 2.0 * float(np.log(np.diag(low)).sum())
    log_marginal = -0.5 * (
        float(y @ alpha) + log_det + n * math.log(2.0 * math.pi)
    )
    return {
        "x": x,
        "y": y,
        "alpha": alpha,
        "chol": low,
        "length_scale": length_scale,
        "signal_std": signal_std,
        "noise_std": noise_std,
        "log_marginal_likelihood": log_marginal,
    }


def predict_gp(model: dict[str, Any], x_star: Any) -> list[tuple[float, float]]:
    """Posterior mean and standard deviation at each query point."""
    x_star = np.asarray(x_star, dtype=float)
    ks = rbf(
        x_star,
        model["x"],
        length_scale=model["length_scale"],
        signal_std=model["signal_std"],
    )
    mean = ks @ model["alpha"]
    v = np.linalg.solve(model["chol"], ks.T)
    var = model["signal_std"] ** 2 - (v**2).sum(axis=0)
    # Round-off can push a near-zero variance negative; the honest floor
    # is the noise level, not zero.
    var = np.maximum(var, 0.0) + model["noise_std"] ** 2
    return [(float(m), float(math.sqrt(s))) for m, s in zip(mean, var, strict=True)]


def cross_validate(
    x: Any,
    y: Any,
    *,
    length_scale: float,
    signal_std: float,
    noise_std: float,
    folds: int = CV_FOLDS,
) -> dict[str, float]:
    """Deterministic k-fold CV: fold membership is index modulo k.

    No shuffling, so the split is reproducible without carrying a seed
    and cannot be re-rolled until it flatters a hyperparameter choice.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    folds = min(folds, n)
    errors: list[float] = []
    z_scores: list[float] = []
    for fold in range(folds):
        mask = np.arange(n) % folds == fold
        if not mask.any() or mask.all():
            continue
        model = fit_gp(
            x[~mask],
            y[~mask],
            length_scale=length_scale,
            signal_std=signal_std,
            noise_std=noise_std,
        )
        for (mean, std), truth in zip(
            predict_gp(model, x[mask]), y[mask], strict=True
        ):
            errors.append(abs(mean - float(truth)))
            z_scores.append((float(truth) - mean) / std if std > 0 else 0.0)
    if not errors:
        raise ProtocolError("GP_CV_EMPTY: cross-validation produced no folds")
    err = np.asarray(errors)
    z = np.asarray(z_scores)
    return {
        "cv_MAE_keV": float(err.mean()),
        "cv_RMSE_keV": float(math.sqrt((err**2).mean())),
        "cv_standardized_mean": float(z.mean()),
        "cv_standardized_std": float(z.std()),
        "cv_coverage_68": float((np.abs(z) <= 0.9944578832097535).mean()),
        "cv_coverage_90": float((np.abs(z) <= 1.6448536269514722).mean()),
        "cv_coverage_95": float((np.abs(z) <= 1.959963984540054).mean()),
        "cv_n": float(len(errors)),
    }


def select_hyperparameters(x: Any, y: Any) -> dict[str, Any]:
    """Two-stage grid selection on training-era evidence alone."""
    candidates: list[dict[str, Any]] = []
    for length_scale in LENGTH_SCALE_GRID:
        for signal_std in SIGNAL_STD_GRID_KEV:
            for noise_std in NOISE_STD_GRID_KEV:
                try:
                    model = fit_gp(
                        x,
                        y,
                        length_scale=length_scale,
                        signal_std=signal_std,
                        noise_std=noise_std,
                    )
                except ProtocolError:
                    continue
                candidates.append(
                    {
                        "length_scale": length_scale,
                        "signal_std_keV": signal_std,
                        "noise_std_keV": noise_std,
                        "log_marginal_likelihood": model[
                            "log_marginal_likelihood"
                        ],
                    }
                )
    if not candidates:
        raise ProtocolError(
            "GP_SELECTION_FAILED: no hyperparameter triple in the "
            "preregistered grid produced a usable fit"
        )

    best_ll = max(c["log_marginal_likelihood"] for c in candidates)
    shortlist = [
        c
        for c in candidates
        if best_ll - c["log_marginal_likelihood"] <= LOG_LIKELIHOOD_TOLERANCE
    ]
    scored = []
    for candidate in shortlist:
        cv = cross_validate(
            x,
            y,
            length_scale=candidate["length_scale"],
            signal_std=candidate["signal_std_keV"],
            noise_std=candidate["noise_std_keV"],
        )
        scored.append(
            {
                **candidate,
                "cv": cv,
                "coverage_gap": abs(cv["cv_coverage_90"] - TARGET_CV_COVERAGE_90),
            }
        )
    # Ties broken by likelihood, then by the grid's own order, so the
    # choice is a function of the data rather than of dict iteration.
    scored.sort(
        key=lambda c: (
            round(c["coverage_gap"], 6),
            -c["log_marginal_likelihood"],
            c["length_scale"],
            c["signal_std_keV"],
            c["noise_std_keV"],
        )
    )
    chosen = scored[0]
    chosen["selection_rule"] = SELECTION_RULE
    chosen["n_grid_points_total"] = (
        len(LENGTH_SCALE_GRID) * len(SIGNAL_STD_GRID_KEV) * len(NOISE_STD_GRID_KEV)
    )
    chosen["n_grid_points_evaluated"] = len(candidates)
    chosen["n_shortlisted"] = len(shortlist)
    chosen["best_log_marginal_likelihood"] = best_ll
    return chosen


__all__ = [
    "CV_FOLDS",
    "LENGTH_SCALE_GRID",
    "LOG_LIKELIHOOD_TOLERANCE",
    "NOISE_STD_GRID_KEV",
    "SELECTION_RULE",
    "SIGNAL_STD_GRID_KEV",
    "TARGET_CV_COVERAGE_90",
    "apply_scaling",
    "cross_validate",
    "fit_gp",
    "predict_gp",
    "rbf",
    "select_hyperparameters",
    "standardize",
]
