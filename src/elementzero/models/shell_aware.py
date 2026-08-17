"""Shell-capable residual models (v2).

WHY THIS MODULE EXISTS
----------------------
EZ-B003 v1 produced a clean, interpretable negative result: the SEMF+GP
residual model recovered the SIGN of a hidden shell gap in every scored chain
and placed the true closure in the top 3 in 80% of them, but ranked it first in
only 8.6%. That is not a tuning failure. A squared-exponential GP is infinitely
differentiable; a shell closure is a near-discontinuity in the first derivative
of the binding energy (S2n drops abruptly across it). A smooth interpolator can
see that something is there and cannot say where. No amount of hyperparameter
search fixes a representational gap.

v2 therefore adds a model class that CAN represent a kink, without being told
where the kink is.

THE DISCOVERY FIREWALL
----------------------
Two feature profiles, never pooled:

    accuracy   may use magic-number distance, shell-gap, and closure features
    discovery  may NOT: knots are found from data on a preregistered grid

`FeatureProfileError` is raised rather than silently dropping a forbidden
feature, because a silent drop is how a firewall becomes decoration.

THE METHOD
----------
Given backbone residuals, fit a design matrix that is linear in the smooth part
and adds a hinge (rectified-linear) basis at a candidate knot k:

    hinge_plus(x; k)  = max(x - k, 0)
    hinge_minus(x; k) = max(k - x, 0)

    residual ~ b0 + b1*Z + b2*N + b3*A + b4*hinge_plus(N;k) + b5*hinge_minus(N;k)

Every candidate k on the grid is fitted by ordinary least squares and scored by
BIC. The knot ranking IS the localization output, so `rank_1_fraction` and
`top_k_fraction` fall out of the same object that makes the prediction.

Piecewise-linear bases are the standard remedy in the literature for exactly
this representational limit; smooth activations and smooth kernels cannot
express the kink, ReLU-type bases can.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

SHELL_MODULE_VERSION = "ez-shell-v2.0.0"

PROFILE_ACCURACY = "accuracy"
PROFILE_DISCOVERY = "discovery"

# Features that encode the answer. Forbidden under the discovery profile.
FORBIDDEN_DISCOVERY_FEATURES = frozenset(
    {
        "magic_number_distance",
        "nearest_magic_z",
        "nearest_magic_n",
        "shell_gap",
        "delta2n_known",
        "delta2p_known",
        "closure_flag",
        "valence_nucleons_to_magic",
    }
)


class FeatureProfileError(RuntimeError):
    """Raised when a discovery-profile model is handed a shell-aware feature."""


def assert_discovery_admissible(feature_names: Sequence[str]) -> None:
    bad = sorted(set(feature_names) & FORBIDDEN_DISCOVERY_FEATURES)
    if bad:
        raise FeatureProfileError(
            f"discovery profile forbids shell-aware features: {bad}; "
            "use PROFILE_ACCURACY and report it in a separate, unpooled section"
        )


def _hinge_design(
    z: np.ndarray, n: np.ndarray, knot: float, axis: str
) -> np.ndarray:
    """Smooth linear block plus a two-sided hinge at `knot` along `axis`."""
    z = np.asarray(z, dtype=float)
    n = np.asarray(n, dtype=float)
    a = z + n
    x = n if axis == "N" else z
    return np.column_stack(
        [
            np.ones_like(z),
            z,
            n,
            a,
            np.maximum(x - knot, 0.0),
            np.maximum(knot - x, 0.0),
        ]
    )


def _ols_bic(design: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray, float]:
    """Least squares fit; returns (BIC, coefficients, residual_variance).

    The design is rank-deficient by construction on a single isotopic or
    isotonic chain (with Z held fixed, the Z and A columns are collinear with
    the intercept and N). lstsq handles that via the minimum-norm solution; the
    BIC penalty uses the effective rank so that chains and full-chart fits are
    scored on the same footing.
    """
    n_obs = design.shape[0]
    n_par = int(np.linalg.matrix_rank(design))
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ coef
    rss = float(resid @ resid)
    sigma2 = max(rss / max(n_obs - n_par, 1), 1.0e-12)
    # Gaussian BIC up to an additive constant
    bic = n_obs * np.log(max(rss / n_obs, 1.0e-12)) + n_par * np.log(n_obs)
    return float(bic), coef, sigma2


@dataclass
class KinkLocalization:
    axis: str
    ranked_knots: tuple[int, ...]
    bic_by_knot: dict[int, float]
    best_knot: int
    delta_bic_to_runner_up: float

    def rank_of(self, knot: int) -> int | None:
        """1-based rank of `knot` in the ranking, or None if not on the grid."""
        try:
            return self.ranked_knots.index(int(knot)) + 1
        except ValueError:
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "ranked_knots": list(self.ranked_knots),
            "best_knot": self.best_knot,
            "delta_bic_to_runner_up": self.delta_bic_to_runner_up,
            "bic_by_knot": {str(k): v for k, v in sorted(self.bic_by_knot.items())},
        }


@dataclass
class KinkResidualModel:
    """Backbone-residual model with a free-knot hinge basis.

    Admissible under the discovery profile: the knot grid is preregistered and
    contains no magic-number information, and the winning knot is selected by
    BIC on training data only.
    """

    axis: str = "N"
    feature_profile: str = PROFILE_DISCOVERY
    knot_grid: tuple[int, ...] = ()
    model_id: str = "EZ-KINK-RESIDUAL-v2"
    coef: np.ndarray | None = field(default=None, repr=False)
    sigma2: float | None = None
    localization: KinkLocalization | None = None
    _n_train: int = 0

    def __post_init__(self) -> None:
        if self.axis not in ("N", "Z"):
            raise ValueError("axis must be 'N' or 'Z'")
        if self.feature_profile == PROFILE_DISCOVERY:
            assert_discovery_admissible(["Z", "N", "A", "hinge_plus", "hinge_minus"])

    def fit(
        self,
        z: Sequence[int],
        n: Sequence[int],
        residual_keV: Sequence[float],
        knot_grid: Sequence[int] | None = None,
    ) -> KinkResidualModel:
        z_arr = np.asarray(z, dtype=float)
        n_arr = np.asarray(n, dtype=float)
        y = np.asarray(residual_keV, dtype=float)
        if not (z_arr.size == n_arr.size == y.size):
            raise ValueError("z, n, and residual_keV must have equal length")

        axis_vals = n_arr if self.axis == "N" else z_arr
        if knot_grid is not None:
            grid = tuple(int(k) for k in knot_grid)
        elif self.knot_grid:
            grid = self.knot_grid
        else:
            lo, hi = int(np.min(axis_vals)) + 2, int(np.max(axis_vals)) - 2
            grid = tuple(range(lo, hi + 1))
        if len(grid) < 2:
            raise ValueError("knot grid needs at least two candidates")
        self.knot_grid = grid

        bics: dict[int, float] = {}
        best: tuple[float, int, np.ndarray, float] | None = None
        axis_min, axis_max = float(np.min(axis_vals)), float(np.max(axis_vals))
        for k in grid:
            # A knot outside the data range makes one hinge identically zero:
            # there is no kink to fit, so the candidate is not evaluable.
            if not (axis_min < float(k) < axis_max):
                continue
            design = _hinge_design(z_arr, n_arr, float(k), self.axis)
            bic, coef, sigma2 = _ols_bic(design, y)
            bics[k] = bic
            if best is None or bic < best[0]:
                best = (bic, k, coef, sigma2)
        if best is None:
            raise RuntimeError(
                "no admissible knot: every candidate lies outside the data range along "
                f"axis {self.axis}"
            )

        ranked = tuple(sorted(bics, key=lambda k: bics[k]))
        runner_up = bics[ranked[1]] - bics[ranked[0]] if len(ranked) > 1 else float("inf")

        self.localization = KinkLocalization(
            axis=self.axis,
            ranked_knots=ranked,
            bic_by_knot=bics,
            best_knot=ranked[0],
            delta_bic_to_runner_up=float(runner_up),
        )
        _, _, self.coef, self.sigma2 = best
        self._n_train = int(y.size)
        return self

    def predict(self, z: Sequence[int], n: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
        """Return (residual_correction_keV, sigma_keV) for the fitted knot."""
        if self.coef is None or self.localization is None or self.sigma2 is None:
            raise RuntimeError("model has not been fit")
        design = _hinge_design(
            np.asarray(z, dtype=float),
            np.asarray(n, dtype=float),
            float(self.localization.best_knot),
            self.axis,
        )
        mean = design @ self.coef
        sigma = np.full(mean.shape, float(np.sqrt(self.sigma2)))
        return mean, sigma

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "module_version": SHELL_MODULE_VERSION,
            "axis": self.axis,
            "feature_profile": self.feature_profile,
            "basis": "linear(Z,N,A) + two-sided hinge at free knot",
            "knot_grid": list(self.knot_grid),
            "selection_criterion": "BIC",
            "localization": self.localization.to_dict() if self.localization else None,
            "n_train": self._n_train,
            "predictive_distribution": "gaussian_homoscedastic",
            "uncertainty_method": "ols_residual_variance",
        }


def localization_metrics(
    localizations: Sequence[KinkLocalization], truth_knots: Sequence[int], top_k: int = 3
) -> dict[str, float]:
    """rank-1 and top-k fractions across scored chains.

    These are the same quantities EZ-B003 v1 reported (rank_1_fraction 0.086,
    top_k_fraction 0.800 for the v1 residual model), so v2 numbers drop into
    the same comparison without redefining the metric.
    """
    if len(localizations) != len(truth_knots):
        raise ValueError("localizations and truth_knots must have equal length")
    if not localizations:
        return {"n": 0.0, "rank_1_fraction": 0.0, "top_k_fraction": 0.0, "top_k": float(top_k)}
    ranks = [loc.rank_of(int(t)) for loc, t in zip(localizations, truth_knots)]
    scored = [r for r in ranks if r is not None]
    n = float(len(scored))
    if n == 0:
        return {"n": 0.0, "rank_1_fraction": 0.0, "top_k_fraction": 0.0, "top_k": float(top_k)}
    return {
        "n": n,
        "rank_1_fraction": float(sum(1 for r in scored if r == 1) / n),
        "top_k_fraction": float(sum(1 for r in scored if r <= top_k) / n),
        "top_k": float(top_k),
    }
