"""AME2016 mass-table adapter."""

from __future__ import annotations

from pathlib import Path

from elementzero.data.amdc.common import AME_MAS16_COLUMNS, EditionSpec, parse_ame_mass_table
from elementzero.data.observations import MassObservation

EDITION = EditionSpec(
    edition_id="AME2016",
    release_date="2017-03-01",
    columns=AME_MAS16_COLUMNS,
    filename_hints=("mass16.txt", "mass.mas16", "mass.mas16.txt"),
    year=2016,
)


def load(path: str | Path) -> list[MassObservation]:
    return parse_ame_mass_table(path, EDITION)
