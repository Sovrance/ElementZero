"""Gaussian-process residual model around SEMF.

    residual = observed_mass - physics_mass
    predicted_mass = physics_mass + predicted_residual

Features are Z, N, A only. No magic-number-distance features.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.models.protocol import Prediction
from elementzero.physics.semf import SEMFCoefficients, fit_semf, mass_excess_keV

MODEL_ID_GP_DIRECT = "EZ-GP-DIRECT-v1"
MODEL_ID_SEMF_GP = "EZ-SEMF-GP-RESIDUAL-v1"

# Fixed kernel: no optimizer restarts, deterministic across clean runs.
_KERNEL = (
    ConstantKernel(constant_value=1.0e6, constant_value_bounds="fixed")
    * RBF(length_scale=8.0, length_scale_bounds="fixed")
    + WhiteKernel(noise_level=1.0e4, noise_level_bounds="fixed")
)


def _features(z: int, n: int) -> np.ndarray:
    return np.array([[float(z), float(n), float(z + n)]], dtype=float)


@dataclass
class SEMFGPResidualModel:
    model_id: str = MODEL_ID_SEMF_GP
    coeffs: SEMFCoefficients | None = None
    gp: GaussianProcessRegressor | None = field(default=None, repr=False)
    _fitted_ids: tuple[str, ...] = ()

    def fit(self, observations: Sequence[MassObservation]) -> None:
        self.coeffs = fit_semf(observations)
        x = np.vstack([_features(o.Z, o.N) for o in observations])
        physics = np.array([mass_excess_keV(o.Z, o.N, self.coeffs) for o in observations])
        residual = np.array([o.mass_excess_keV for o in observations]) - physics
        self.gp = GaussianProcessRegressor(
            kernel=_KERNEL,
            optimizer=None,
            normalize_y=True,
            random_state=0,
        )
        self.gp.fit(x, residual)
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))

    def predict(self, nuclide: NuclideIdentity) -> Prediction:
        if self.coeffs is None or self.gp is None:
            raise RuntimeError("model has not been fit")
        physics = mass_excess_keV(nuclide.Z, nuclide.N, self.coeffs)
        mean, std = self.gp.predict(_features(nuclide.Z, nuclide.N), return_std=True)
        pred = float(physics + mean[0])
        sigma = float(std[0])
        return Prediction(
            nuclide=nuclide,
            mass_excess_keV=pred,
            intervals={
                "p90": (pred - 1.6448536269514722 * sigma, pred + 1.6448536269514722 * sigma),
                "p95": (pred - 1.959963984540054 * sigma, pred + 1.959963984540054 * sigma),
            },
            model_id=self.model_id,
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "physics": self.coeffs.to_dict() if self.coeffs else None,
            "features": ["Z", "N", "A"],
            "kernel": "fixed RBF + white",
            "optimizer": None,
            "random_state": 0,
            "fitted_nuclide_ids": list(self._fitted_ids),
        }


@dataclass
class GPDirectModel:
    """Optional control: GP on mass excess directly, same identity features."""

    model_id: str = MODEL_ID_GP_DIRECT
    gp: GaussianProcessRegressor | None = field(default=None, repr=False)
    _fitted_ids: tuple[str, ...] = ()

    def fit(self, observations: Sequence[MassObservation]) -> None:
        x = np.vstack([_features(o.Z, o.N) for o in observations])
        y = np.array([o.mass_excess_keV for o in observations], dtype=float)
        self.gp = GaussianProcessRegressor(
            kernel=_KERNEL,
            optimizer=None,
            normalize_y=True,
            random_state=0,
        )
        self.gp.fit(x, y)
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))

    def predict(self, nuclide: NuclideIdentity) -> Prediction:
        if self.gp is None:
            raise RuntimeError("model has not been fit")
        mean, std = self.gp.predict(_features(nuclide.Z, nuclide.N), return_std=True)
        pred = float(mean[0])
        sigma = float(std[0])
        return Prediction(
            nuclide=nuclide,
            mass_excess_keV=pred,
            intervals={
                "p90": (pred - 1.6448536269514722 * sigma, pred + 1.6448536269514722 * sigma),
                "p95": (pred - 1.959963984540054 * sigma, pred + 1.959963984540054 * sigma),
            },
            model_id=self.model_id,
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "features": ["Z", "N", "A"],
            "kernel": "fixed RBF + white",
            "optimizer": None,
            "random_state": 0,
            "fitted_nuclide_ids": list(self._fitted_ids),
        }


@dataclass
class SEMFLeastSquaresModel:
    model_id: str = "EZ-SEMF-LS-v1"
    coeffs: SEMFCoefficients | None = None
    residual_std: float = 1000.0
    _fitted_ids: tuple[str, ...] = ()

    def fit(self, observations: Sequence[MassObservation]) -> None:
        self.coeffs = fit_semf(observations)
        preds = [mass_excess_keV(o.Z, o.N, self.coeffs) for o in observations]
        resid = np.array([o.mass_excess_keV - p for o, p in zip(observations, preds)])
        self.residual_std = float(np.std(resid)) if len(resid) else 1000.0
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))

    def predict(self, nuclide: NuclideIdentity) -> Prediction:
        if self.coeffs is None:
            raise RuntimeError("model has not been fit")
        pred = mass_excess_keV(nuclide.Z, nuclide.N, self.coeffs)
        sigma = self.residual_std
        return Prediction(
            nuclide=nuclide,
            mass_excess_keV=pred,
            intervals={
                "p90": (pred - 1.6448536269514722 * sigma, pred + 1.6448536269514722 * sigma),
                "p95": (pred - 1.959963984540054 * sigma, pred + 1.959963984540054 * sigma),
            },
            model_id=self.model_id,
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "physics": self.coeffs.to_dict() if self.coeffs else None,
            "residual_std_keV": self.residual_std,
            "features": ["Z", "N", "A"],
            "fitted_nuclide_ids": list(self._fitted_ids),
        }


def build_model(model_id: str):
    if model_id == MODEL_ID_SEMF_GP:
        return SEMFGPResidualModel()
    if model_id == MODEL_ID_GP_DIRECT:
        return GPDirectModel()
    if model_id == "EZ-SEMF-LS-v1":
        return SEMFLeastSquaresModel()
    raise ValueError(f"unknown model_id {model_id!r}")
