"""Federation registry, baseline wrappers, and the license gate.

The registry is the frozen roster of a v2 protocol: participants, roles,
independence groups, and the license/availability gate. Its manifest hash
enters the qualification protocol, so a roster change after freezing is
visible as a hash change.

Baselines are never removed (WO-12 governing rule): the three v1 models
participate through thin wrappers that adapt them to the federation
protocol without touching their frozen implementations, and the fourth
control is the optimizer-enabled GP configuration WO-11 identified, frozen
here as EZ-GP-OPTIMIZED-CONTROL-v1.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

from elementzero.benchmark.distance import nearest_training, training_lattice
from elementzero.data.identity import NuclideIdentity
from elementzero.data.model_tables.manifests import STATUS_APPROVED
from elementzero.data.observations import MassObservation
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_hex
from elementzero.models.federation import (
    FEDERATION_PROTOCOL_VERSION,
    GROUP_LIQUID_DROP,
    GROUP_STATISTICAL_GP,
)
from elementzero.models.federation.capabilities import (
    ROLE_COMBINER,
    ROLE_CONTROL,
    ROLE_PHYSICS_BACKBONE,
    ROLE_RESIDUAL_CHALLENGER,
    ROLES,
    ModelCapabilities,
)
from elementzero.models.federation.protocol import (
    STATUS_AVAILABLE,
    FederationPrediction,
    NuclearMassModel,
)
from elementzero.models.gp_residual import (
    MODEL_ID_GP_DIRECT,
    MODEL_ID_SEMF_GP,
    MODEL_ID_SEMF_LS,
    build_model,
)
from elementzero.physics.semf import fit_semf, mass_excess_keV

MODEL_ID_GP_OPTIMIZED = "EZ-GP-OPTIMIZED-CONTROL-v1"

# Frozen before any v2 qualification is scored (WO-12 section 11).
GP_OPTIMIZED_CONFIG_ID = "ez-wo12-gp-optimized-control-v1"
GP_OPTIMIZED_CONFIG = {
    "formulation": "SEMF least squares + GP on the residual",
    "kernel": "ConstantKernel(1e6) * RBF(length_scale=8.0) + WhiteKernel(noise_level=1e4)",
    "optimizer": "fmin_l_bfgs_b",
    "n_restarts_optimizer": 2,
    "normalize_y": True,
    "random_state": 0,
    "features": ["Z", "N", "A"],
}

_BASELINE_GROUPS = {
    MODEL_ID_SEMF_LS: GROUP_LIQUID_DROP,
    MODEL_ID_GP_DIRECT: GROUP_STATISTICAL_GP,
    MODEL_ID_SEMF_GP: GROUP_STATISTICAL_GP,
}


class WrappedBaselineModel(NuclearMassModel):
    """A frozen v1 baseline speaking the federation protocol unchanged."""

    def __init__(self, baseline_model_id: str) -> None:
        if baseline_model_id not in _BASELINE_GROUPS:
            raise ProtocolError(f"{baseline_model_id!r} is not a v1 baseline")
        self.model_id = baseline_model_id
        self.family_id = "v1_baseline"
        self.independence_group = _BASELINE_GROUPS[baseline_model_id]
        self.source_manifest = None
        self.training_policy = "unchanged v1 baseline fit on the freeze-approved training set"
        self.uncertainty_policy = "the v1 baseline's own sigma, reported as within-model"
        self._inner = build_model(baseline_model_id)
        self._lattice: tuple[tuple[int, int], ...] = ()

    def fit(self, observations: Sequence[MassObservation]) -> None:
        self._inner.fit(observations)
        self._lattice = training_lattice(o.nuclide_id for o in observations)

    def predict(self, nuclide: NuclideIdentity) -> FederationPrediction:
        inner = self._inner.predict(nuclide)
        distance = None
        if self._lattice:
            distance = int(
                nearest_training(z=nuclide.Z, n=nuclide.N, lattice=self._lattice)[
                    "nearest_training_L1"
                ]
            )
        return FederationPrediction(
            nuclide=nuclide,
            status=STATUS_AVAILABLE,
            model_id=self.model_id,
            point_keV=inner.mass_excess_keV,
            within_model_std_keV=inner.std_keV,
            nearest_training_L1=distance,
        )

    def manifest(self) -> dict[str, Any]:
        inner = self._inner.manifest()
        return {
            **inner,
            "family_id": self.family_id,
            "independence_group": self.independence_group,
            "training_policy": self.training_policy,
        }


class OptimizedGPControl(NuclearMassModel):
    """EZ-GP-OPTIMIZED-CONTROL-v1: a configuration control, not physics."""

    def __init__(self) -> None:
        self.model_id = MODEL_ID_GP_OPTIMIZED
        self.family_id = "v1_baseline_family_optimized_configuration"
        self.independence_group = GROUP_STATISTICAL_GP
        self.source_manifest = None
        self.training_policy = (
            "SEMF least squares + optimizer-enabled GP residual on the "
            "freeze-approved training set; hyperparameters frozen as "
            f"{GP_OPTIMIZED_CONFIG_ID} before any v2 qualification was scored"
        )
        self.uncertainty_policy = "GP posterior sigma, reported as within-model"
        self._coeffs = None
        self._gp: GaussianProcessRegressor | None = None
        self._mean = None
        self._scale = None
        self._fitted_ids: tuple[str, ...] = ()
        self._lattice: tuple[tuple[int, int], ...] = ()

    @staticmethod
    def _features(z: int, n: int) -> np.ndarray:
        return np.array([float(z), float(n), float(z + n)], dtype=float)

    def fit(self, observations: Sequence[MassObservation]) -> None:
        self._coeffs = fit_semf(observations)
        x = np.vstack([self._features(o.Z, o.N) for o in observations])
        physics = np.array([mass_excess_keV(o.Z, o.N, self._coeffs) for o in observations])
        residual = np.array([o.mass_excess_keV for o in observations]) - physics
        self._mean = x.mean(axis=0)
        scale = x.std(axis=0)
        scale[scale == 0.0] = 1.0
        self._scale = scale
        kernel = ConstantKernel(1.0e6) * RBF(length_scale=8.0) + WhiteKernel(noise_level=1.0e4)
        self._gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=GP_OPTIMIZED_CONFIG["n_restarts_optimizer"],
            normalize_y=True,
            random_state=GP_OPTIMIZED_CONFIG["random_state"],
        )
        self._gp.fit((x - self._mean) / self._scale, residual)
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))
        self._lattice = training_lattice(self._fitted_ids)

    def predict(self, nuclide: NuclideIdentity) -> FederationPrediction:
        if self._gp is None:
            raise ProtocolError(f"{self.model_id} has not been fit")
        physics = mass_excess_keV(nuclide.Z, nuclide.N, self._coeffs)
        x = (self._features(nuclide.Z, nuclide.N) - self._mean) / self._scale
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
            point_keV=physics + float(mean[0]),
            within_model_std_keV=max(float(std[0]), 1.0e-9),
            nearest_training_L1=distance,
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "family_id": self.family_id,
            "independence_group": self.independence_group,
            "features": list(GP_OPTIMIZED_CONFIG["features"]),
            "configuration_id": GP_OPTIMIZED_CONFIG_ID,
            "configuration": dict(GP_OPTIMIZED_CONFIG),
            "fitted_kernel": str(self._gp.kernel_) if self._gp is not None else None,
            "physics": self._coeffs.to_dict() if self._coeffs else None,
            "predictive_distribution": "gaussian",
            "uncertainty_method": self.uncertainty_policy,
            "training_policy": self.training_policy,
            "fitted_nuclide_ids": list(self._fitted_ids),
        }


# --------------------------------------------------------------------------- #
# Registry                                                                    #
# --------------------------------------------------------------------------- #


@dataclass
class Participant:
    model_id: str
    role: str
    independence_group: str
    builder: Callable[[], NuclearMassModel]
    license_status: str | None = None  # None: internal model, no external source
    capabilities: ModelCapabilities = field(default=None)  # type: ignore[assignment]


class FederationRegistry:
    """The frozen participant roster of one federation protocol version."""

    def __init__(self, *, protocol_version: str = FEDERATION_PROTOCOL_VERSION) -> None:
        self.protocol_version = protocol_version
        self._participants: dict[str, Participant] = {}

    def register(
        self,
        *,
        model_id: str,
        role: str,
        independence_group: str,
        builder: Callable[[], NuclearMassModel],
        license_status: str | None = None,
        full_chart_coverage: bool = False,
    ) -> None:
        if role not in ROLES:
            raise ProtocolError(f"unknown federation role {role!r}")
        if model_id in self._participants:
            raise ProtocolError(f"duplicate federation participant {model_id!r}")
        # License/availability gate (WO-12 section 24): an external source
        # participates in a frozen protocol only when APPROVED outright.
        if license_status is not None and license_status != STATUS_APPROVED:
            raise ProtocolError(
                f"{model_id} has license status {license_status!r}; a model that "
                "is not APPROVED cannot participate in a frozen v2 protocol"
            )
        self._participants[model_id] = Participant(
            model_id=model_id,
            role=role,
            independence_group=independence_group,
            builder=builder,
            license_status=license_status,
            capabilities=ModelCapabilities(
                model_id=model_id,
                role=role,
                full_chart_coverage=full_chart_coverage,
            ),
        )

    def build(self, model_id: str) -> NuclearMassModel:
        if model_id not in self._participants:
            raise ProtocolError(f"unknown federation participant {model_id!r}")
        return self._participants[model_id].builder()

    @property
    def model_ids(self) -> tuple[str, ...]:
        return tuple(self._participants)

    @property
    def model_count(self) -> int:
        return len(self._participants)

    @property
    def independence_groups(self) -> tuple[str, ...]:
        return tuple(sorted({p.independence_group for p in self._participants.values()}))

    @property
    def independence_group_count(self) -> int:
        return len(self.independence_groups)

    def physics_backbone_groups(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    p.independence_group
                    for p in self._participants.values()
                    if p.role == ROLE_PHYSICS_BACKBONE
                }
            )
        )

    def manifest(self) -> dict[str, Any]:
        payload = {
            "federation_protocol_version": self.protocol_version,
            "model_count": self.model_count,
            "independence_group_count": self.independence_group_count,
            "independence_groups": list(self.independence_groups),
            "physics_backbone_groups": list(self.physics_backbone_groups()),
            "participants": {
                model_id: {
                    "role": p.role,
                    "independence_group": p.independence_group,
                    "license_status": p.license_status,
                    "capabilities": p.capabilities.to_dict(),
                }
                for model_id, p in sorted(self._participants.items())
            },
        }
        payload["registry_hash"] = sha256_hex(payload)
        return payload


def build_default_federation(*, repo_root=None) -> FederationRegistry:
    """The WO-12 v1 roster: 4 controls, 2 backbones, 2 residuals, 2 combiners."""
    from elementzero.models.federation.adapters.bskg5 import build_bskg_backbone
    from elementzero.models.federation.adapters.frdm2012 import build_frdm_backbone
    from elementzero.models.federation.combination import (
        EBMACompatibleCombiner,
        UniformEnsemble,
    )
    from elementzero.models.federation.residual_wrapper import ResidualCorrectedModel

    registry = FederationRegistry()
    for baseline_id in (MODEL_ID_SEMF_LS, MODEL_ID_GP_DIRECT, MODEL_ID_SEMF_GP):
        registry.register(
            model_id=baseline_id,
            role=ROLE_CONTROL,
            independence_group=_BASELINE_GROUPS[baseline_id],
            builder=lambda b=baseline_id: WrappedBaselineModel(b),
            full_chart_coverage=True,
        )
    registry.register(
        model_id=MODEL_ID_GP_OPTIMIZED,
        role=ROLE_CONTROL,
        independence_group=GROUP_STATISTICAL_GP,
        builder=OptimizedGPControl,
        full_chart_coverage=True,
    )

    bskg = build_bskg_backbone(repo_root=repo_root)
    frdm = build_frdm_backbone(repo_root=repo_root)
    for backbone in (bskg, frdm):
        manifest = backbone.review["selected_manifest"]
        registry.register(
            model_id=manifest["model_id"],
            role=ROLE_PHYSICS_BACKBONE,
            independence_group=manifest["independence_group"],
            builder=backbone.builder,
            license_status=manifest["license_status"],
        )
        registry.register(
            model_id=f"{manifest['model_id']}+GP-RESIDUAL-v1",
            role=ROLE_RESIDUAL_CHALLENGER,
            independence_group="residual_ml",
            builder=lambda make=backbone.builder: ResidualCorrectedModel(make()),
        )

    combination_component_ids = [
        bskg.review["selected_manifest"]["model_id"],
        frdm.review["selected_manifest"]["model_id"],
        f"{bskg.review['selected_manifest']['model_id']}+GP-RESIDUAL-v1",
        f"{frdm.review['selected_manifest']['model_id']}+GP-RESIDUAL-v1",
    ]

    def _components() -> list[NuclearMassModel]:
        return [registry.build(model_id) for model_id in combination_component_ids]

    registry.register(
        model_id="EZ-FED-UNIFORM-ENSEMBLE-v1",
        role=ROLE_COMBINER,
        independence_group="model_combination",
        builder=lambda: UniformEnsemble(_components(), model_id="EZ-FED-UNIFORM-ENSEMBLE-v1"),
    )
    registry.register(
        model_id="EZ-FED-VALIDATION-WEIGHTED-v1",
        role=ROLE_COMBINER,
        independence_group="model_combination",
        builder=lambda: EBMACompatibleCombiner(
            _components(), model_id="EZ-FED-VALIDATION-WEIGHTED-v1"
        ),
    )
    return registry
