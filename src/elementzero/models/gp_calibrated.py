"""Repaired Gaussian-process residual models (v2).

WHAT WAS WRONG IN v1
--------------------
The frozen v1 kernel was

    ConstantKernel(constant_value=1.0e6, bounds="fixed")
      * RBF(length_scale=8.0, bounds="fixed")
      + WhiteKernel(noise_level=1.0e4, bounds="fixed")

used with ``optimizer=None`` and ``normalize_y=True``.

In scikit-learn, ``ConstantKernel.constant_value`` is a VARIANCE, so the prior
amplitude is sqrt(1.0e6) = 1000. With ``normalize_y=True`` the targets are
standardised to unit variance before the kernel is applied, and the returned
sigma is multiplied back by ``y_train_std``. The amplitude was evidently chosen
as if the targets were in keV, but it is applied to already-normalised targets:

    sigma_reported ~= 1000 * y_train_std

With residual scatter of a few hundred keV this yields sigma of order 10^5 keV
(hundreds of MeV) against sub-MeV errors, which is exactly the v1 signature:
coverage_90 = coverage_95 = 1.000 and std(z) ~ 0.

Because ``optimizer=None``, nothing could ever correct this from the data.
The v1 mean function was barely affected (hence hp-no-normalize-y showing an
identical MAE in the WO-11 grid), so the defect is confined to sigma - which is
precisely the quantity Doctrine 4 makes load-bearing.

WHAT v2 DOES
------------
    - amplitude and length scales are LEARNED, not frozen, with bounded priors
    - anisotropic (ARD) length scales over (Z, N, A): the chart is not isotropic
    - amplitude initialised at 1.0 in normalised units, which is the only
      self-consistent choice when normalize_y=True
    - deterministic: fixed random_state, fixed restart count, sorted inputs
    - every fit records the learned kernel in the manifest, so a silently
      degenerate fit is visible in the evidence graph instead of hidden

Determinism note: L-BFGS restarts are seeded from ``random_state``; with sorted
training input and a pinned library stack the learned kernel is reproducible.
The protocol pins interpreter and library versions (WO-201) for this reason;
see `protocol/protocol.json` and `tools/check_environment_pin.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

GP_MODULE_VERSION = "ez-gp-v2.0.0"

MIN_PREDICTIVE_STD_KEV = 1.0e-3

# Bounded, learnable hyperparameters. Bounds are part of the frozen protocol.
AMPLITUDE_INIT = 1.0
AMPLITUDE_BOUNDS = (1.0e-3, 1.0e3)
LENGTH_SCALE_INIT = (8.0, 8.0, 16.0)  # Z, N, A
LENGTH_SCALE_BOUNDS = (1.0e-1, 1.0e4)
NOISE_INIT = 1.0e-2
NOISE_BOUNDS = (1.0e-8, 1.0e1)
N_RESTARTS = 3
RANDOM_STATE = 0


def build_kernel_v2() -> Any:
    """The v2 kernel: learnable amplitude, ARD length scales, learnable noise."""
    return ConstantKernel(AMPLITUDE_INIT, AMPLITUDE_BOUNDS) * RBF(
        list(LENGTH_SCALE_INIT), LENGTH_SCALE_BOUNDS
    ) + WhiteKernel(NOISE_INIT, NOISE_BOUNDS)


def features_zna(z: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Identity-only feature block (Z, N, A).

    Deliberately free of magic-number or shell-distance features so that this
    model class is admissible under a `discovery` feature profile. Accuracy-
    profile models may extend this; they may never be pooled with discovery
    results (see models/shell_aware.py).
    """
    z = np.asarray(z, dtype=float)
    n = np.asarray(n, dtype=float)
    return np.column_stack([z, n, z + n])


class Backbone(Protocol):
    """A physics mass model that supplies the mean function.

    v2 treats the backbone as an injected dependency instead of hard-coding
    SEMF. A backbone may be a fitted SEMF, a published table (FRDM-2012, WS4,
    BSkG), or a historically refitted EDF build. Blindness tier travels with
    the backbone, not with the residual wrapper.
    """

    backbone_id: str

    def mass_excess_keV(self, z: np.ndarray, n: np.ndarray) -> np.ndarray: ...

    def manifest(self) -> dict[str, Any]: ...


@dataclass
class CallableBackbone:
    """Adapter turning any (Z,N)->mass-excess callable into a Backbone."""

    backbone_id: str
    fn: Callable[[np.ndarray, np.ndarray], np.ndarray]
    blindness_tier: str = "E_INELIGIBLE_UNKNOWN"
    independence_group: str = "unspecified"
    fit_data_cutoff: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def mass_excess_keV(self, z: np.ndarray, n: np.ndarray) -> np.ndarray:
        return np.asarray(self.fn(np.asarray(z), np.asarray(n)), dtype=float)

    def manifest(self) -> dict[str, Any]:
        return {
            "backbone_id": self.backbone_id,
            "blindness_tier": self.blindness_tier,
            "independence_group": self.independence_group,
            "fit_data_cutoff": self.fit_data_cutoff,
            **self.extra,
        }


@dataclass
class GPResidualV2:
    """Backbone + learned-GP residual with honest predictive sigma.

    predicted_mass = backbone_mass + gp_residual_mean
    predictive_var = gp_residual_var (+ backbone_var when the backbone
                     supplies one; table backbones generally do not)
    """

    backbone: Backbone
    model_id: str = ""
    gp: GaussianProcessRegressor | None = field(default=None, repr=False)
    learned_kernel: str = ""
    log_marginal_likelihood: float | None = None
    _fitted_ids: tuple[str, ...] = ()
    _y_train_std: float | None = None

    def __post_init__(self) -> None:
        if not self.model_id:
            self.model_id = f"EZ-{self.backbone.backbone_id}-GP-RESIDUAL-v2"

    def fit(
        self,
        z: Sequence[int],
        n: Sequence[int],
        mass_excess_keV: Sequence[float],
        nuclide_ids: Sequence[str] | None = None,
    ) -> GPResidualV2:
        z_arr = np.asarray(z, dtype=float)
        n_arr = np.asarray(n, dtype=float)
        y_arr = np.asarray(mass_excess_keV, dtype=float)
        if not (z_arr.size == n_arr.size == y_arr.size):
            raise ValueError("z, n, and mass_excess_keV must have equal length")
        if z_arr.size < 5:
            raise ValueError("GP residual fit requires at least 5 training nuclides")

        order = np.lexsort((n_arr, z_arr))  # deterministic training order
        z_arr, n_arr, y_arr = z_arr[order], n_arr[order], y_arr[order]

        physics = self.backbone.mass_excess_keV(z_arr, n_arr)
        residual = y_arr - physics
        x = features_zna(z_arr, n_arr)

        self.gp = GaussianProcessRegressor(
            kernel=build_kernel_v2(),
            n_restarts_optimizer=N_RESTARTS,
            normalize_y=True,
            random_state=RANDOM_STATE,
        )
        self.gp.fit(x, residual)
        self.learned_kernel = str(self.gp.kernel_)
        self.log_marginal_likelihood = float(
            self.gp.log_marginal_likelihood(self.gp.kernel_.theta)
        )
        self._y_train_std = float(np.std(residual))
        if nuclide_ids is not None:
            self._fitted_ids = tuple(sorted(str(i) for i in nuclide_ids))
        return self

    def predict(self, z: Sequence[int], n: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
        """Return (mass_excess_keV, sigma_keV)."""
        if self.gp is None:
            raise RuntimeError("model has not been fit")
        z_arr = np.asarray(z, dtype=float)
        n_arr = np.asarray(n, dtype=float)
        physics = self.backbone.mass_excess_keV(z_arr, n_arr)
        mean, std = self.gp.predict(features_zna(z_arr, n_arr), return_std=True)
        sigma = np.maximum(np.asarray(std, dtype=float), MIN_PREDICTIVE_STD_KEV)
        return physics + mean, sigma

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "module_version": GP_MODULE_VERSION,
            "backbone": self.backbone.manifest(),
            "features": ["Z", "N", "A"],
            "feature_profile": "discovery_admissible",
            "kernel_family": "ConstantKernel * RBF(ARD) + WhiteKernel",
            "kernel_learned": self.learned_kernel,
            "amplitude_bounds": list(AMPLITUDE_BOUNDS),
            "length_scale_bounds": list(LENGTH_SCALE_BOUNDS),
            "noise_bounds": list(NOISE_BOUNDS),
            "n_restarts_optimizer": N_RESTARTS,
            "random_state": RANDOM_STATE,
            "normalize_y": True,
            "log_marginal_likelihood": self.log_marginal_likelihood,
            "training_residual_std_keV": self._y_train_std,
            "predictive_distribution": "gaussian",
            "uncertainty_method": "gp_return_std_learned_hyperparameters",
            "fitted_nuclide_ids": list(self._fitted_ids),
        }


def prior_sigma_scale_keV(constant_value: float, y_train_std: float) -> float:
    """The v1 defect, quantified: the prior predictive sigma in keV.

    With ``normalize_y=True`` the amplitude sqrt(constant_value) applies to
    unit-variance targets, and sklearn rescales the returned sigma by
    ``y_train_std``. So the PRIOR predictive standard deviation, in keV, is

        sigma_prior = sqrt(constant_value) * y_train_std

    For the frozen v1 kernel (constant_value = 1.0e6) this is 1000 * y_train_std:
    with residual scatter of a few hundred keV, a prior sigma of order 10^5 keV.

    The POSTERIOR sigma is smaller than this wherever training data constrain
    the fit, so this value is an upper bound on the observed sigma, not a
    prediction of it. The defect is the order of magnitude, not the exact
    number: any posterior sigma within a factor of a few of this bound is
    vacuous, which is what coverage 1.000 and std(z) ~ 0 recorded in v1.
    """
    if constant_value <= 0 or y_train_std <= 0:
        raise ValueError("constant_value and y_train_std must be positive")
    return float(np.sqrt(constant_value) * y_train_std)
