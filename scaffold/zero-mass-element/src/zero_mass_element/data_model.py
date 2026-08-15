from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class MassObservation:
    nuclide_id: str
    Z: int
    N: int
    A: int
    mass_excess_keV: float
    uncertainty_keV: Optional[float]
    source_edition: str
    source_release_date: str
    source_record_status: str
    ground_truth_eligible: bool
    raw_source_hash: str
    normalizer_version: str

    def __post_init__(self):
        if self.A != self.Z + self.N:
            raise ValueError("A must equal Z+N")
        if self.nuclide_id != f"Z{self.Z}-N{self.N}":
            raise ValueError("nuclide_id must be canonical Z{Z}-N{N}")
