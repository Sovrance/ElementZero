"""AME2012 mass-table adapter."""

from __future__ import annotations

from pathlib import Path

from elementzero.data.amdc.common import AME_MAS20_COLUMNS, EditionSpec, parse_ame_mass_table
from elementzero.data.observations import MassObservation

EDITION = EditionSpec(
    edition_id="AME2012",
    release_date="2012-12-01",
    columns=AME_MAS20_COLUMNS,
    filename_hints=("mass.mas12", "mass.mas12.txt"),
)


def load(path: str | Path) -> list[MassObservation]:
    return parse_ame_mass_table(path, EDITION)
