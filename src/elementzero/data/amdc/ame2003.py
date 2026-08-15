"""AME2003 mass-table adapter."""

from __future__ import annotations

from pathlib import Path

from elementzero.data.amdc.common import AME_MAS03_COLUMNS, EditionSpec, parse_ame_mass_table
from elementzero.data.observations import MassObservation

EDITION = EditionSpec(
    edition_id="AME2003",
    release_date="2003-12-22",
    columns=AME_MAS03_COLUMNS,
    filename_hints=("mass.mas03", "mass.mas03.txt"),
    year=2003,
)


def load(path: str | Path) -> list[MassObservation]:
    return parse_ame_mass_table(path, EDITION)
