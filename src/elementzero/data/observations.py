"""Normalized nuclear mass observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from elementzero.data.identity import NuclideIdentity, validate_a
from elementzero.physics.constants import NORMALIZER_VERSION

# Source-record statuses. Extrapolated/model-derived values must not be
# silently promoted to experimental truth.
RECORD_STATUS_EXPERIMENTAL = "experimental"
RECORD_STATUS_EVALUATED = "evaluated"
RECORD_STATUS_EXTRAPOLATED = "extrapolated"
RECORD_STATUS_ESTIMATED = "estimated"

EXPERIMENTAL_LIKE = frozenset({RECORD_STATUS_EXPERIMENTAL, RECORD_STATUS_EVALUATED})


@dataclass(frozen=True)
class MassObservation:
    nuclide: NuclideIdentity
    mass_excess_keV: float
    uncertainty_keV: float
    source_edition: str
    source_release_date: str
    source_record_status: str
    raw_source_hash: str
    element_symbol: str | None = None
    normalizer_version: str = NORMALIZER_VERSION

    def __post_init__(self) -> None:
        validate_a(self.nuclide.Z, self.nuclide.N, self.nuclide.A)
        if self.uncertainty_keV < 0:
            raise ValueError("uncertainty_keV must be non-negative")

    @property
    def nuclide_id(self) -> str:
        return self.nuclide.nuclide_id

    @property
    def Z(self) -> int:
        return self.nuclide.Z

    @property
    def N(self) -> int:
        return self.nuclide.N

    @property
    def A(self) -> int:
        return self.nuclide.A

    @property
    def ground_truth_eligible(self) -> bool:
        return self.source_record_status in EXPERIMENTAL_LIKE

    def to_dict(self) -> dict[str, Any]:
        return {
            "nuclide_id": self.nuclide_id,
            "Z": self.Z,
            "N": self.N,
            "A": self.A,
            "mass_excess_keV": self.mass_excess_keV,
            "uncertainty_keV": self.uncertainty_keV,
            "source_edition": self.source_edition,
            "source_release_date": self.source_release_date,
            "source_record_status": self.source_record_status,
            "ground_truth_eligible": self.ground_truth_eligible,
            "raw_source_hash": self.raw_source_hash,
            "normalizer_version": self.normalizer_version,
            "element_symbol": self.element_symbol,
        }


TRUTH_BEARING_FIELDS = frozenset(
    {
        "mass_excess_keV",
        "uncertainty_keV",
        "binding_energy",
        "binding_energy_MeV",
        "measured_value",
        "truth",
        "atomic_mass",
        "mass_excess",
    }
)
