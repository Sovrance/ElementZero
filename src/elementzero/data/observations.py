"""Normalized nuclear mass observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from elementzero.data.identity import NuclideIdentity, validate_a
from elementzero.physics.constants import NORMALIZER_VERSION

# Conservative AME evaluation-status vocabulary (WO-01).
# AME "#" marks estimated (non-experimental) evaluated values; that alone does
# not prove a single direct measurement. Reserve direct_measurement for later
# sources with explicit measurement provenance.
RECORD_STATUS_EVALUATED_NON_ESTIMATED = "evaluated_non_estimated"
RECORD_STATUS_EVALUATED_ESTIMATED = "evaluated_estimated"
RECORD_STATUS_EXTRAPOLATED = "extrapolated"
RECORD_STATUS_DIRECT_MEASUREMENT = "direct_measurement"

# Legacy aliases kept only so older call sites fail loudly if misused.
RECORD_STATUS_EXPERIMENTAL = RECORD_STATUS_EVALUATED_NON_ESTIMATED  # deprecated name
RECORD_STATUS_EVALUATED = RECORD_STATUS_EVALUATED_NON_ESTIMATED  # deprecated name
RECORD_STATUS_ESTIMATED = RECORD_STATUS_EVALUATED_ESTIMATED  # deprecated name

GROUND_TRUTH_ELIGIBLE_STATUSES = frozenset({RECORD_STATUS_EVALUATED_NON_ESTIMATED})


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
    estimated_mass: bool = False
    estimated_uncertainty: bool = False
    source_origin: str = ""
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
        return self.source_record_status in GROUND_TRUTH_ELIGIBLE_STATUSES

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
            "estimated_mass": self.estimated_mass,
            "estimated_uncertainty": self.estimated_uncertainty,
            "source_origin": self.source_origin,
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
