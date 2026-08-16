"""Combination layer (WO-12 section 13).

Three combiners, all preserving component identity:

    UniformEnsemble             equal weights over available component
                                predictions — the combination control
    ValidationWeightedEnsemble  weights learned only from the calibration
                                split of the *training* data, never from
                                hidden benchmark truth
    EBMACompatibleCombiner      the Ensemble-Bayesian-Model-Averaging
                                interface: component identities, weights,
                                calibration dataset digest, per-component
                                uncertainty contributions, and source hashes
                                all travel in the manifest. The posterior is
                                the weighted Gaussian mixture's first two
                                moments; full MCMC weight inference is staged
                                for a later work order behind this interface.

Coverage: a target some component cannot cover is combined over the
contributors only, and the record lists contributing_models, missing_models,
and contributing_independence_groups (section 16). Nothing is imputed.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.errors import ProtocolError
from elementzero.models.federation import GROUP_COMBINATION
from elementzero.models.federation.calibration import (
    CALIBRATION_SPLIT_POLICY_ID,
    split_fit_calibration,
)
from elementzero.models.federation.protocol import (
    STATUS_AVAILABLE,
    STATUS_OUT_OF_TABLE,
    FederationPrediction,
    NuclearMassModel,
)

TRAINING_POLICY_UNIFORM = (
    "components fit on the full freeze-approved training set; weights are "
    "constant and equal — no data enters the weights at all"
)
TRAINING_POLICY_VALIDATION_WEIGHTED = (
    "components fit on the fit split; weights = 1/(MSE + eps) on the "
    "calibration split, normalized; components then refit on the full "
    "training set. Hidden benchmark truth never enters the weights."
)


def _mixture_moments(
    predictions: Sequence[FederationPrediction], weights: Sequence[float]
) -> tuple[float, float, float]:
    """Weighted Gaussian mixture: mean, within part, between part (keV)."""
    total = sum(weights)
    normalized = [w / total for w in weights]
    mean = sum(w * p.point_keV for w, p in zip(normalized, predictions))
    within_var = sum(w * p.predictive_std_keV**2 for w, p in zip(normalized, predictions))
    between_var = sum(w * (p.point_keV - mean) ** 2 for w, p in zip(normalized, predictions))
    return mean, within_var**0.5, between_var**0.5


class _CombinationBase(NuclearMassModel):
    combination_rule = "override"

    def __init__(
        self,
        components: Sequence[NuclearMassModel],
        *,
        model_id: str,
        min_contributors: int = 1,
    ) -> None:
        if len({c.model_id for c in components}) != len(components):
            raise ProtocolError("combination components must have unique model ids")
        self.components = list(components)
        self.model_id = model_id
        self.family_id = "federation_combination"
        self.independence_group = GROUP_COMBINATION
        self.source_manifest = None
        self.training_policy = TRAINING_POLICY_UNIFORM
        self.uncertainty_policy = (
            "within_model_std = weighted rms of component predictive sigmas; "
            "model_disagreement_std = weighted between-component spread"
        )
        self.min_contributors = min_contributors
        self._weights: dict[str, float] = {}
        self._calibration_record: dict[str, Any] = {}
        self._fitted_ids: tuple[str, ...] = ()

    # -- weights ----------------------------------------------------------- #

    def _learn_weights(self, observations: Sequence[MassObservation]) -> dict[str, float]:
        raise NotImplementedError

    def fit(self, observations: Sequence[MassObservation]) -> None:
        self._weights = self._learn_weights(observations)
        for component in self.components:
            component.fit(observations)
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))

    def predict(self, nuclide: NuclideIdentity) -> FederationPrediction:
        component_predictions = [c.predict(nuclide) for c in self.components]
        contributing = [p for p in component_predictions if p.status == STATUS_AVAILABLE]
        missing = tuple(
            p.model_id for p in component_predictions if p.status != STATUS_AVAILABLE
        )
        if len(contributing) < self.min_contributors:
            return FederationPrediction(
                nuclide=nuclide,
                status=STATUS_OUT_OF_TABLE,
                model_id=self.model_id,
                missing_models=missing,
            )
        weights = [self._weights.get(p.model_id, 0.0) for p in contributing]
        if sum(weights) <= 0.0:
            weights = [1.0] * len(contributing)
        mean, within, between = _mixture_moments(contributing, weights)
        groups = tuple(
            sorted(
                {
                    next(c for c in self.components if c.model_id == p.model_id).independence_group
                    for p in contributing
                }
            )
        )
        distances = [
            p.nearest_training_L1 for p in contributing if p.nearest_training_L1 is not None
        ]
        return FederationPrediction(
            nuclide=nuclide,
            status=STATUS_AVAILABLE,
            model_id=self.model_id,
            point_keV=mean,
            within_model_std_keV=within,
            model_disagreement_std_keV=between,
            nearest_training_L1=min(distances) if distances else None,
            contributing_models=tuple(p.model_id for p in contributing),
            missing_models=missing,
            contributing_independence_groups=groups,
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "family_id": self.family_id,
            "independence_group": self.independence_group,
            "features": ["Z", "N", "A"],
            "combination_rule": self.combination_rule,
            "component_model_ids": [c.model_id for c in self.components],
            "component_independence_groups": sorted(
                {c.independence_group for c in self.components}
            ),
            "component_source_hashes": {
                c.model_id: (c.source_manifest or {}).get("raw_sha256")
                for c in self.components
            },
            "weights": dict(sorted(self._weights.items())),
            "calibration": dict(self._calibration_record),
            "min_contributors": self.min_contributors,
            "predictive_distribution": "gaussian (mixture moments)",
            "uncertainty_method": self.uncertainty_policy,
            "training_policy": self.training_policy,
            "fitted_nuclide_ids": list(self._fitted_ids),
        }


class UniformEnsemble(_CombinationBase):
    combination_rule = "ez-wo12-uniform-ensemble-v1: equal weights over contributors"

    def _learn_weights(self, observations: Sequence[MassObservation]) -> dict[str, float]:
        self._calibration_record = {"rule": "uniform: no data enters the weights"}
        return {c.model_id: 1.0 for c in self.components}


class ValidationWeightedEnsemble(_CombinationBase):
    combination_rule = (
        "ez-wo12-validation-weighted-v1: weights = 1/(MSE + eps) on the "
        "calibration split of the training data, normalized"
    )
    EPS_KEV2 = 1.0

    def __init__(self, components: Sequence[NuclearMassModel], *, model_id: str) -> None:
        super().__init__(components, model_id=model_id)
        self.training_policy = TRAINING_POLICY_VALIDATION_WEIGHTED

    def _learn_weights(self, observations: Sequence[MassObservation]) -> dict[str, float]:
        from elementzero.evidence.freezes import identity_digest

        fit_set, calibration_set = split_fit_calibration(observations)
        weights: dict[str, float] = {}
        component_errors: dict[str, dict[str, Any]] = {}
        for component in self.components:
            component.fit(fit_set)
            squared = []
            skipped = 0
            for obs in calibration_set:
                prediction = component.predict(NuclideIdentity.from_zn(obs.Z, obs.N))
                if prediction.status != STATUS_AVAILABLE:
                    skipped += 1
                    continue
                squared.append((prediction.point_keV - obs.mass_excess_keV) ** 2)
            mse = statistics.fmean(squared) if squared else float("inf")
            weights[component.model_id] = (
                0.0 if mse == float("inf") else 1.0 / (mse + self.EPS_KEV2)
            )
            component_errors[component.model_id] = {
                "calibration_mse_keV2": None if mse == float("inf") else mse,
                "n_calibration_used": len(squared),
                "n_calibration_uncovered": skipped,
            }
        total = sum(weights.values())
        if total <= 0.0:
            raise ProtocolError(
                f"{self.model_id}: no component produced calibration predictions"
            )
        weights = {k: v / total for k, v in weights.items()}
        self._calibration_record = {
            "split_policy_id": CALIBRATION_SPLIT_POLICY_ID,
            "calibration_identity_digest": identity_digest(
                sorted(o.nuclide_id for o in calibration_set)
            ),
            "n_fit": len(fit_set),
            "n_calibration": len(calibration_set),
            "component_errors": component_errors,
            "truth_rule": (
                "weights learned from training-side calibration data only; "
                "hidden benchmark truth never enters"
            ),
        }
        return weights


class EBMACompatibleCombiner(ValidationWeightedEnsemble):
    combination_rule = (
        "ez-wo12-ebma-interface-v1: Ensemble Bayesian Model Averaging "
        "interface (component identity, weights, calibration dataset, "
        "uncertainty contributions, source hashes). Weight inference is the "
        "validation-weighted estimate for now; full MCMC EBMA is staged "
        "behind this same interface."
    )

    def manifest(self) -> dict[str, Any]:
        manifest = super().manifest()
        manifest["ebma_interface"] = {
            "component_identity_preserved": True,
            "weights_field": "weights",
            "calibration_dataset_field": "calibration.calibration_identity_digest",
            "uncertainty_contribution_rule": (
                "per-component contribution = weight * (predictive_std**2 + "
                "(point - mixture_mean)**2), the mixture-variance identity"
            ),
            "source_hashes_field": "component_source_hashes",
            "mcmc_status": "STAGED",
        }
        return manifest
