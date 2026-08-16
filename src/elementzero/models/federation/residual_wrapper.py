"""Residual-corrected federation models (WO-12 section 10).

    ResidualCorrectedModel(base_model, ...)

    training target: residual = evaluated_mass - base_model_mass

The residual GP may only see freeze-approved training observations for which
the base model has an AVAILABLE prediction; pairs the base cannot cover are
skipped *and counted*, never imputed. Hidden benchmark targets never appear
in fit ids, calibration ids, or optimizer selection — the wrapper receives
only the training observations the sealed pipeline hands every model.

The residual GP configuration is frozen here, before any v2 qualification is
scored (section 11): the optimizer-enabled configuration WO-11 identified,
with fixed restarts and a fixed random state.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

from elementzero.benchmark.distance import nearest_training, training_lattice
from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.errors import ProtocolError
from elementzero.models.federation import GROUP_RESIDUAL_ML
from elementzero.models.federation.protocol import (
    STATUS_AVAILABLE,
    FederationPrediction,
    NuclearMassModel,
)

# Frozen residual-GP configuration (ez-wo12-residual-gp-v1). WO-11's dev grid
# showed the fixed-kernel configuration understates the family; the optimizer-
# enabled configuration is frozen here with every knob pinned.
RESIDUAL_GP_CONFIG_ID = "ez-wo12-residual-gp-v1"
RESIDUAL_GP_CONFIG = {
    "kernel": "ConstantKernel(1e6) * RBF(length_scale=8.0) + WhiteKernel(noise_level=1e4)",
    "optimizer": "fmin_l_bfgs_b",
    "n_restarts_optimizer": 2,
    "normalize_y": True,
    "random_state": 0,
    "features": ["Z", "N", "A"],
    "feature_scaling": "per-feature standardization from the fit set only",
}

TRAINING_POLICY_RESIDUAL = (
    "GP on (evaluated_mass - base_model_mass) over freeze-approved training "
    "observations with an AVAILABLE base prediction; uncovered pairs are "
    "skipped and counted, never imputed"
)

UNCERTAINTY_POLICY_RESIDUAL = (
    "residual_std_keV = correction-GP posterior sigma (includes the fitted "
    "white-noise level); the base model's within-model sigma is not added on "
    "top, because the correction replaces the base error model inside the "
    "fitted domain"
)


def _features(z: int, n: int) -> np.ndarray:
    return np.array([float(z), float(n), float(z + n)], dtype=float)


class ResidualCorrectedModel(NuclearMassModel):
    def __init__(self, base_model: NuclearMassModel, *, model_id: str | None = None) -> None:
        self.base = base_model
        self.model_id = model_id or f"{base_model.model_id}+GP-RESIDUAL-v1"
        self.family_id = f"{base_model.family_id}+gp_residual"
        # A residual variant of one base model is not an independent model
        # (WO-12 section 2): it counts under residual_ml, and its manifest
        # names the base's group so diversity accounting can see through it.
        self.independence_group = GROUP_RESIDUAL_ML
        self.source_manifest = base_model.source_manifest
        self.training_policy = TRAINING_POLICY_RESIDUAL
        self.uncertainty_policy = UNCERTAINTY_POLICY_RESIDUAL
        self._gp: GaussianProcessRegressor | None = None
        self._mean: np.ndarray | None = None
        self._scale: np.ndarray | None = None
        self._fitted_ids: tuple[str, ...] = ()
        self._pair_ids: tuple[str, ...] = ()
        self._skipped_ids: tuple[str, ...] = ()
        self._lattice: tuple[tuple[int, int], ...] = ()

    def fit(self, observations: Sequence[MassObservation]) -> None:
        self.base.fit(observations)
        pairs = []
        skipped = []
        for obs in observations:
            base_prediction = self.base.predict(NuclideIdentity.from_zn(obs.Z, obs.N))
            if base_prediction.status != STATUS_AVAILABLE:
                skipped.append(obs.nuclide_id)
                continue
            pairs.append((obs, obs.mass_excess_keV - base_prediction.point_keV))
        if len(pairs) < 10:
            raise ProtocolError(
                f"{self.model_id}: only {len(pairs)} residual training pairs are "
                "available; refusing to fit a correction on almost nothing"
            )
        x = np.vstack([_features(o.Z, o.N) for o, _ in pairs])
        y = np.array([r for _, r in pairs], dtype=float)
        self._mean = x.mean(axis=0)
        scale = x.std(axis=0)
        scale[scale == 0.0] = 1.0
        self._scale = scale
        kernel = ConstantKernel(1.0e6) * RBF(length_scale=8.0) + WhiteKernel(noise_level=1.0e4)
        self._gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=RESIDUAL_GP_CONFIG["n_restarts_optimizer"],
            normalize_y=True,
            random_state=RESIDUAL_GP_CONFIG["random_state"],
        )
        self._gp.fit((x - self._mean) / self._scale, y)
        # fitted_nuclide_ids is the freeze-approved identity set handed to
        # fit — the leakage boundary the sealed training digest pins — the
        # same convention TableMassModel uses for a model that consumes a
        # subset (or none) of the training VALUES. The pairs whose values
        # actually entered the residual GP, and the uncovered pairs that
        # were skipped-and-counted, are recorded separately.
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))
        self._pair_ids = tuple(sorted(o.nuclide_id for o, _ in pairs))
        self._skipped_ids = tuple(sorted(skipped))
        self._lattice = training_lattice(self._pair_ids)

    def coverage_status(self, nuclide: NuclideIdentity) -> str:
        # No base physics -> no correction target: coverage is the base's,
        # for benchmark targets and residual training pairs alike.
        return self.base.coverage_status(nuclide)

    def predict(self, nuclide: NuclideIdentity) -> FederationPrediction:
        if self._gp is None:
            raise ProtocolError(f"{self.model_id} has not been fit")
        base_prediction = self.base.predict(nuclide)
        if base_prediction.status != STATUS_AVAILABLE:
            # No base physics -> no correction target; the gap is explicit.
            return FederationPrediction(
                nuclide=nuclide,
                status=base_prediction.status,
                model_id=self.model_id,
                nearest_training_L1=base_prediction.nearest_training_L1,
            )
        x = (_features(nuclide.Z, nuclide.N) - self._mean) / self._scale
        mean, std = self._gp.predict(x.reshape(1, -1), return_std=True)
        distance = int(
            nearest_training(z=nuclide.Z, n=nuclide.N, lattice=self._lattice)[
                "nearest_training_L1"
            ]
        )
        return FederationPrediction(
            nuclide=nuclide,
            status=STATUS_AVAILABLE,
            model_id=self.model_id,
            point_keV=base_prediction.point_keV + float(mean[0]),
            residual_std_keV=max(float(std[0]), 1.0e-9),
            nearest_training_L1=distance,
        )

    def manifest(self) -> dict[str, Any]:
        fitted_kernel = str(self._gp.kernel_) if self._gp is not None else None
        payload = {
            "model_id": self.model_id,
            "family_id": self.family_id,
            "independence_group": self.independence_group,
            "base_model_id": self.base.model_id,
            "base_independence_group": self.base.independence_group,
            "features": list(RESIDUAL_GP_CONFIG["features"]),
            "residual_gp_config_id": RESIDUAL_GP_CONFIG_ID,
            "residual_gp_config": dict(RESIDUAL_GP_CONFIG),
            "fitted_kernel": fitted_kernel,
            "n_residual_pairs": len(self._pair_ids),
            "n_skipped_uncovered": len(self._skipped_ids),
            "predictive_distribution": "gaussian",
            "uncertainty_method": self.uncertainty_policy,
            "training_policy": self.training_policy,
            "fitted_nuclide_ids": list(self._fitted_ids),
        }
        if self._skipped_ids:
            # Only present when a coverage gap exists, so fully-covered
            # (synthetic-chart) manifests stay byte-identical to the
            # committed WO-12 evidence.
            payload["residual_pair_nuclide_ids"] = list(self._pair_ids)
            payload["skipped_uncovered_nuclide_ids"] = list(self._skipped_ids)
        return payload
