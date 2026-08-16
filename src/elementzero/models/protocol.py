"""Model protocol for EZ-B001.

Every prediction is an explicit Gaussian predictive distribution:

    mu    = mass_excess_keV
    sigma = std_keV

    interval_90 = [mu - 1.6448536269514722*sigma, mu + 1.6448536269514722*sigma]
    interval_95 = [mu - 1.959963984540054*sigma,  mu + 1.959963984540054*sigma]

sigma is persisted by the model, never reconstructed from rounded intervals or
from later truth during scoring (WO-03 stop condition).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation

# Gaussian two-sided quantiles used to build reported intervals.
Z_90 = 1.6448536269514722
Z_95 = 1.959963984540054

PREDICTIVE_DISTRIBUTION_GAUSSIAN = "gaussian"

# A deterministic baseline wrapper still has to state a positive sigma; this is
# the floor used instead of silently emitting a zero-width predictive density.
MIN_PREDICTIVE_STD_KEV = 1.0e-9

UNCERTAINTY_METHOD_TRAINING_RESIDUAL_STD = "global training residual standard deviation"
UNCERTAINTY_METHOD_GP_RETURN_STD = "GaussianProcessRegressor return_std"


def gaussian_intervals(mu: float, sigma: float) -> dict[str, tuple[float, float]]:
    """Symmetric 90%/95% Gaussian intervals from mu and sigma."""
    return {
        "p90": (mu - Z_90 * sigma, mu + Z_90 * sigma),
        "p95": (mu - Z_95 * sigma, mu + Z_95 * sigma),
    }


@dataclass(frozen=True)
class Prediction:
    nuclide: NuclideIdentity
    mass_excess_keV: float
    intervals: dict[str, tuple[float, float]]
    model_id: str
    std_keV: float
    uncertainty_method: str
    predictive_distribution: str = PREDICTIVE_DISTRIBUTION_GAUSSIAN

    def __post_init__(self) -> None:
        if not self.uncertainty_method:
            raise ValueError("prediction must state how uncertainty was constructed")
        if not (self.std_keV >= MIN_PREDICTIVE_STD_KEV):
            raise ValueError(
                f"std_keV must be >= {MIN_PREDICTIVE_STD_KEV}, got {self.std_keV!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nuclide_id": self.nuclide.nuclide_id,
            "Z": self.nuclide.Z,
            "N": self.nuclide.N,
            "A": self.nuclide.A,
            "mass_excess_keV": self.mass_excess_keV,
            "std_keV": self.std_keV,
            "predictive_distribution": self.predictive_distribution,
            "uncertainty_method": self.uncertainty_method,
            "intervals": {k: [v[0], v[1]] for k, v in self.intervals.items()},
            "model_id": self.model_id,
        }


class MassModel(Protocol):
    model_id: str

    def fit(self, observations: Sequence[MassObservation]) -> None: ...

    def predict(self, nuclide: NuclideIdentity) -> Prediction: ...

    def manifest(self) -> dict[str, Any]: ...
