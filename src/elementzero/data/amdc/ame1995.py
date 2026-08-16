"""AME1995 mass-table adapter (historical evidence support, WO-13).

The 1995 Audi-Wapstra evaluation ("The 1995 update to the atomic mass
evaluation", Nuclear Physics A 595, 409) is ingested as an explicit
historical edition: it anchors the earliest snapshot of the WO-13 source
chronology, so target-eligibility questions like "was this nuclide already
evaluated evidence in 1995?" are answered from a hashed, parsed source
instead of a Z/A guess.

AME1995 is historical evidence support. It is NOT automatically the FRDM95
exact fit set — the FRDM95 constants were adjusted to a 1989-era mass set,
and WO-13 never substitutes edition membership for exact fit membership
without an explicit approximation flag.
"""

from __future__ import annotations

from pathlib import Path

from elementzero.data.amdc.common import ColumnMap, EditionSpec, parse_ame_mass_table
from elementzero.data.observations import MassObservation

# AME1995 (mass_rmd.mas95, Audi-Wapstra round-off table): narrower f11.3
# mass excess and f9.3 uncertainty columns; the binding-energy field starts
# immediately after the uncertainty with no separating space, so the slice
# boundaries are load-bearing. '#' replaces the decimal point for values
# derived from systematics (integer-valued in the published file).
#
# The column map lives HERE, not in common.py: the shared module is part of
# the frozen EZ-B001 protocol-code identity (ez-b001-protocol-code-v1) and
# adding a historical edition must not invalidate those preregistrations.
AME_MAS95_COLUMNS = ColumnMap(
    n=(4, 9),
    z=(9, 14),
    a=(14, 19),
    el=(20, 23),
    origin=(23, 27),
    mass_excess=(28, 39),
    mass_excess_unc=(39, 48),
    mass_precision=3,
    uncertainty_precision=3,
)

EDITION = EditionSpec(
    edition_id="AME1995",
    release_date="1995-12-01",
    columns=AME_MAS95_COLUMNS,
    filename_hints=("mass_rmd.mas95", "mass_rmd.mas95.txt"),
    year=1995,
)


def load(path: str | Path) -> list[MassObservation]:
    return parse_ame_mass_table(path, EDITION)
