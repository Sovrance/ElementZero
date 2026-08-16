"""Parsers for published mass-model tables.

Two formats are supported in WO-12 v1:

    BSkG series      the BRUSLIB ``bskgNN-dat`` layout: whitespace-separated
                     columns headed ``Z A bet2 bet4 Rch gamma Sn Sp Qbet Mcal
                     Mexp-Mcal ...``; ``Mcal`` is the calculated atomic mass
                     excess in MeV.

    FRDM (RIPL-3)    the IAEA RIPL-3 ``mass-frdm95.dat`` layout, Fortran
                     format ``(2i4,1x,a2,1x,i1,4f10.3,4f8.3)`` with columns
                     Z, A, s, fl, Mexp, Err, Mth, Emic, beta2..beta6; ``Mth``
                     is the calculated atomic mass excess in MeV and may be
                     blank for rows that only carry experimental data.

Both parsers normalize into ElementZero's canonical internal observable,
``atomic_mass_excess_keV``, through the single shared conversion below —
adapter-specific ad hoc conversions are forbidden (WO-12 section 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from elementzero.errors import SchemaError

MODEL_TABLE_PARSER_VERSION = "ez-model-table-parser-v1"

# The one audited conversion: published tables in this work order tabulate the
# atomic mass excess in MeV; the canonical internal unit is keV.
MEV_TO_KEV = 1000.0

# BSkG tables mark unavailable quantities with sentinels, and the sentinel
# set is column-specific: the Mcal column uses +999.99 (a real superheavy
# mass excess can legitimately sit near +99.99 MeV), while the Mexp-Mcal
# deviation column uses +99.99 (no experimental mass; real deviations stay
# within a few MeV).
_BSKG_MASS_SENTINELS = {999.99, -999.99}
_BSKG_DEVIATION_SENTINELS = {999.99, -999.99, 99.99, -99.99}


def table_value_to_mass_excess_keV(value_MeV: float) -> float:
    """The shared conversion layer: published MeV mass excess -> keV."""
    return float(value_MeV) * MEV_TO_KEV


@dataclass(frozen=True)
class TableRow:
    Z: int
    N: int
    A: int
    mass_excess_keV: float
    experimental_minus_calculated_keV: float | None


@dataclass(frozen=True)
class ParsedTable:
    table_id: str
    rows: dict[tuple[int, int], TableRow]
    n_rows: int
    empirical_rms_keV: float | None
    parser_version: str = MODEL_TABLE_PARSER_VERSION

    def get(self, z: int, n: int) -> TableRow | None:
        return self.rows.get((int(z), int(n)))


def _empirical_rms_keV(deviations_keV: list[float]) -> float | None:
    """RMS of (experimental - calculated) over rows that carry both.

    This is the table's own honesty statement about itself, computed from the
    file rather than quoted from memory, and it seeds the table model's
    within-model sigma.
    """
    if not deviations_keV:
        return None
    return (sum(d * d for d in deviations_keV) / len(deviations_keV)) ** 0.5


def parse_bskg_table(path: str | Path, *, table_id: str = "BSKG3") -> ParsedTable:
    rows: dict[tuple[int, int], TableRow] = {}
    deviations: list[float] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 11:
            raise SchemaError(f"{path}:{line_number}: BSkG row has {len(parts)} columns, needs 11+")
        try:
            z, a = int(parts[0]), int(parts[1])
            mcal_MeV = float(parts[9])
            dev_field = float(parts[10])
        except ValueError as error:
            raise SchemaError(f"{path}:{line_number}: unparseable BSkG row: {error}") from error
        if abs(mcal_MeV) in _BSKG_MASS_SENTINELS:
            raise SchemaError(f"{path}:{line_number}: sentinel value in the Mcal column")
        n = a - z
        if n < 0:
            raise SchemaError(f"{path}:{line_number}: A < Z")
        deviation_keV = None
        if abs(dev_field) not in _BSKG_DEVIATION_SENTINELS:
            deviation_keV = table_value_to_mass_excess_keV(dev_field)
            deviations.append(deviation_keV)
        rows[(z, n)] = TableRow(
            Z=z,
            N=n,
            A=a,
            mass_excess_keV=table_value_to_mass_excess_keV(mcal_MeV),
            experimental_minus_calculated_keV=deviation_keV,
        )
    if not rows:
        raise SchemaError(f"{path}: no BSkG data rows parsed")
    return ParsedTable(
        table_id=table_id,
        rows=rows,
        n_rows=len(rows),
        empirical_rms_keV=_empirical_rms_keV(deviations),
    )


def parse_frdm_ripl_table(path: str | Path, *, table_id: str = "FRDM95") -> ParsedTable:
    rows: dict[tuple[int, int], TableRow] = {}
    deviations: list[float] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#") or line.lstrip().startswith("-"):
            continue
        # (2i4,1x,a2,1x,i1,4f10.3,4f8.3)
        try:
            z = int(line[0:4])
            a = int(line[4:8])
        except ValueError as error:
            raise SchemaError(f"{path}:{line_number}: unparseable FRDM identity: {error}") from error
        mexp_text = line[13:23].strip()
        mth_text = line[33:43].strip()
        if not mth_text:
            # Experimental-only record: the model has no prediction here, so
            # the nuclide is simply absent from the parsed prediction table.
            continue
        try:
            mth_MeV = float(mth_text)
        except ValueError as error:
            raise SchemaError(f"{path}:{line_number}: unparseable FRDM Mth: {error}") from error
        n = a - z
        if n < 0:
            raise SchemaError(f"{path}:{line_number}: A < Z")
        deviation_keV = None
        if mexp_text:
            deviation_keV = table_value_to_mass_excess_keV(float(mexp_text) - mth_MeV)
            deviations.append(deviation_keV)
        rows[(z, n)] = TableRow(
            Z=z,
            N=n,
            A=a,
            mass_excess_keV=table_value_to_mass_excess_keV(mth_MeV),
            experimental_minus_calculated_keV=deviation_keV,
        )
    if not rows:
        raise SchemaError(f"{path}: no FRDM data rows parsed")
    return ParsedTable(
        table_id=table_id,
        rows=rows,
        n_rows=len(rows),
        empirical_rms_keV=_empirical_rms_keV(deviations),
    )
