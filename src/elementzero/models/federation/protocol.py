"""The common federation model protocol (WO-12 section 5).

Every federation participant — v1 baselines wrapped, external physics tables,
residual-corrected challengers, and combiners — speaks one interface:

    NuclearMassModel
        model_id, family_id, independence_group,
        source_manifest, training_policy, uncertainty_policy
        fit(observations) / predict(nuclide) -> FederationPrediction
        manifest() / provenance() / capabilities()

``FederationPrediction`` carries the decomposed uncertainty of section 14 and
an explicit coverage status (section 16). Missing predictions are values of
``status``, never zeros and never silent imputation. The benchmark pipeline
consumes the same prediction through ``to_benchmark_prediction()``, which
keeps the sealed EZ-B00x machinery untouched.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.errors import ProtocolError
from elementzero.models.protocol import (
    MIN_PREDICTIVE_STD_KEV,
    Prediction,
    gaussian_intervals,
)

# Coverage statuses (WO-12 section 16).
STATUS_AVAILABLE = "AVAILABLE"
STATUS_OUT_OF_TABLE = "OUT_OF_TABLE"
STATUS_UNSUPPORTED_NUCLIDE = "UNSUPPORTED_NUCLIDE"
STATUS_PARSE_ERROR = "PARSE_ERROR"
STATUS_INVALID_SOURCE = "INVALID_SOURCE"

COVERAGE_STATUSES = (
    STATUS_AVAILABLE,
    STATUS_OUT_OF_TABLE,
    STATUS_UNSUPPORTED_NUCLIDE,
    STATUS_PARSE_ERROR,
    STATUS_INVALID_SOURCE,
)

# Out-of-domain vocabulary (section 14). The policy is versioned: changing a
# bucket boundary requires a new policy id, never an in-place edit.
OOD_POLICY_ID = "ez-wo12-ood-policy-v1"
OOD_IN_DOMAIN = "IN_DOMAIN"
OOD_LOCAL = "LOCAL_EXTRAPOLATION"
OOD_REGIONAL = "REGIONAL_EXTRAPOLATION"
OOD_EXTREME = "EXTREME_EXTRAPOLATION"

OOD_POLICY_RULE = (
    f"{OOD_POLICY_ID}: from nearest_training_L1 d — d == 0 -> {OOD_IN_DOMAIN}; "
    f"1 <= d <= 2 -> {OOD_LOCAL}; 3 <= d <= 4 -> {OOD_REGIONAL}; "
    f"d >= 5 -> {OOD_EXTREME}. Unknown d stays unlabeled rather than guessed."
)


def ood_status(nearest_training_L1: int | None) -> str | None:
    if nearest_training_L1 is None:
        return None
    d = int(nearest_training_L1)
    if d <= 0:
        return OOD_IN_DOMAIN
    if d <= 2:
        return OOD_LOCAL
    if d <= 4:
        return OOD_REGIONAL
    return OOD_EXTREME


@dataclass(frozen=True)
class FederationPrediction:
    """One prediction with decomposed uncertainty (WO-12 section 14).

    predictive_std_keV**2 = within_model_std_keV**2
                          + residual_std_keV**2
                          + model_disagreement_std_keV**2

    Components that do not apply to a model class are exactly 0.0 — never
    silently folded into another component.
    """

    nuclide: NuclideIdentity
    status: str
    model_id: str
    point_keV: float | None = None
    within_model_std_keV: float = 0.0
    residual_std_keV: float = 0.0
    model_disagreement_std_keV: float = 0.0
    nearest_training_L1: int | None = None
    contributing_models: tuple[str, ...] = ()
    missing_models: tuple[str, ...] = ()
    contributing_independence_groups: tuple[str, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in COVERAGE_STATUSES:
            raise ProtocolError(f"unknown coverage status {self.status!r}")
        if self.status == STATUS_AVAILABLE and self.point_keV is None:
            raise ProtocolError("an AVAILABLE prediction must carry a point value")
        if self.status != STATUS_AVAILABLE and self.point_keV is not None:
            raise ProtocolError(
                f"a {self.status} prediction must not carry a point value; missing "
                "predictions are statuses, never numbers"
            )

    @property
    def predictive_std_keV(self) -> float:
        total = (
            self.within_model_std_keV**2
            + self.residual_std_keV**2
            + self.model_disagreement_std_keV**2
        ) ** 0.5
        return max(total, MIN_PREDICTIVE_STD_KEV)

    @property
    def ood_status(self) -> str | None:
        return ood_status(self.nearest_training_L1)

    def to_dict(self) -> dict[str, Any]:
        intervals = None
        if self.status == STATUS_AVAILABLE:
            built = gaussian_intervals(self.point_keV, self.predictive_std_keV)
            intervals = {k: [v[0], v[1]] for k, v in built.items()}
        return {
            "nuclide_id": self.nuclide.nuclide_id,
            "model_id": self.model_id,
            "status": self.status,
            "point_keV": self.point_keV,
            "within_model_std_keV": self.within_model_std_keV,
            "residual_std_keV": self.residual_std_keV,
            "model_disagreement_std_keV": self.model_disagreement_std_keV,
            "predictive_std_keV": (
                self.predictive_std_keV if self.status == STATUS_AVAILABLE else None
            ),
            "predictive_interval_90": intervals["p90"] if intervals else None,
            "predictive_interval_95": intervals["p95"] if intervals else None,
            "nearest_training_L1": self.nearest_training_L1,
            "ood_status": self.ood_status,
            "ood_policy_id": OOD_POLICY_ID,
            "contributing_models": list(self.contributing_models),
            "missing_models": list(self.missing_models),
            "contributing_independence_groups": list(self.contributing_independence_groups),
        }

    def to_benchmark_prediction(self, *, uncertainty_method: str) -> Prediction:
        """The sealed-pipeline view: Gaussian mu/sigma, no silent imputation."""
        if self.status != STATUS_AVAILABLE:
            raise ProtocolError(
                f"{self.model_id} has no prediction for {self.nuclide.nuclide_id} "
                f"({self.status}); the sealed pipeline never receives imputed values"
            )
        sigma = self.predictive_std_keV
        return Prediction(
            nuclide=self.nuclide,
            mass_excess_keV=self.point_keV,
            intervals=gaussian_intervals(self.point_keV, sigma),
            model_id=self.model_id,
            std_keV=sigma,
            uncertainty_method=uncertainty_method,
        )


class NuclearMassModel(abc.ABC):
    """Common interface for every federation participant (section 5)."""

    model_id: str
    family_id: str
    independence_group: str
    source_manifest: dict[str, Any] | None
    training_policy: str
    uncertainty_policy: str

    @abc.abstractmethod
    def fit(self, observations: Sequence[MassObservation]) -> None: ...

    @abc.abstractmethod
    def predict(self, nuclide: NuclideIdentity) -> FederationPrediction: ...

    @abc.abstractmethod
    def manifest(self) -> dict[str, Any]: ...

    def provenance(self) -> dict[str, Any]:
        manifest = self.source_manifest or {}
        return {
            "model_id": self.model_id,
            "family_id": self.family_id,
            "independence_group": self.independence_group,
            "source_url": manifest.get("source_url"),
            "publication_doi": manifest.get("publication_doi"),
            "raw_sha256": manifest.get("raw_sha256"),
            "training_policy": self.training_policy,
            "uncertainty_policy": self.uncertainty_policy,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "observables": ["atomic_mass_excess_keV"],
            "uncertainty_decomposed": True,
            "coverage_statuses": list(COVERAGE_STATUSES),
            "ood_policy_id": OOD_POLICY_ID,
        }
