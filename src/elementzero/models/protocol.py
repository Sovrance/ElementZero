"""Model protocol for EZ-B001."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation


@dataclass(frozen=True)
class Prediction:
    nuclide: NuclideIdentity
    mass_excess_keV: float
    intervals: dict[str, tuple[float, float]]
    model_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "nuclide_id": self.nuclide.nuclide_id,
            "Z": self.nuclide.Z,
            "N": self.nuclide.N,
            "A": self.nuclide.A,
            "mass_excess_keV": self.mass_excess_keV,
            "intervals": {k: [v[0], v[1]] for k, v in self.intervals.items()},
            "model_id": self.model_id,
        }


class MassModel(Protocol):
    model_id: str

    def fit(self, observations: Sequence[MassObservation]) -> None: ...

    def predict(self, nuclide: NuclideIdentity) -> Prediction: ...

    def manifest(self) -> dict[str, Any]: ...
