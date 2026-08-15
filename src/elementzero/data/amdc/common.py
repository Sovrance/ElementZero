"""Shared AME mass-table parsing.

Edition adapters supply column maps. Values marked with ``#`` in the source
are treated as extrapolated/estimated and are not ground-truth eligible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import (
    RECORD_STATUS_ESTIMATED,
    RECORD_STATUS_EVALUATED,
    RECORD_STATUS_EXPERIMENTAL,
    RECORD_STATUS_EXTRAPOLATED,
    MassObservation,
)
from elementzero.evidence.hashing import sha256_hex


@dataclass(frozen=True)
class ColumnMap:
    n: tuple[int, int]
    z: tuple[int, int]
    a: tuple[int, int]
    el: tuple[int, int]
    mass_excess: tuple[int, int]
    mass_excess_unc: tuple[int, int]


# Audi / AMDC mass.mas20-style 1-based columns converted to 0-based slices.
AME_MAS20_COLUMNS = ColumnMap(
    n=(4, 9),
    z=(9, 14),
    a=(14, 19),
    el=(20, 23),
    mass_excess=(28, 41),
    mass_excess_unc=(41, 52),
)

# AME2003 mass.mas03 uses the same leading N/Z/A/el block as later tables.
AME_MAS03_COLUMNS = AME_MAS20_COLUMNS


@dataclass(frozen=True)
class EditionSpec:
    edition_id: str
    release_date: str
    columns: ColumnMap
    filename_hints: tuple[str, ...] = ()


def _slice(line: str, span: tuple[int, int]) -> str:
    start, end = span
    if len(line) < start:
        return ""
    return line[start:end]


def _parse_ame_number(raw: str) -> tuple[float, bool]:
    text = raw.strip()
    if not text or text in {"*", ""}:
        raise ValueError(f"empty AME numeric field: {raw!r}")
    estimated = "#" in text
    cleaned = text.replace("#", "").replace("*", "").strip()
    return float(cleaned), estimated


def classify_record_status(*, estimated: bool, origin: str = "") -> str:
    if estimated:
        origin_l = origin.lower()
        if "x" in origin_l or "sys" in origin_l:
            return RECORD_STATUS_EXTRAPOLATED
        return RECORD_STATUS_ESTIMATED
    if origin.strip() in {"", "p", "u"}:
        return RECORD_STATUS_EXPERIMENTAL
    return RECORD_STATUS_EVALUATED


def parse_ame_line(line: str, spec: EditionSpec, raw_source_hash: str) -> MassObservation | None:
    stripped = line.rstrip("\n")
    if not stripped.strip() or stripped.lstrip().startswith(("1", "0", "A", "a", "#")):
        # Header / pagination lines often start with a digit flag or letters.
        # Real data lines have N/Z/A in the fixed columns; validate below.
        pass
    try:
        n = int(_slice(stripped, spec.columns.n).strip())
        z = int(_slice(stripped, spec.columns.z).strip())
        a = int(_slice(stripped, spec.columns.a).strip())
        el = _slice(stripped, spec.columns.el).strip() or None
        mass_excess, est_me = _parse_ame_number(_slice(stripped, spec.columns.mass_excess))
        unc, est_unc = _parse_ame_number(_slice(stripped, spec.columns.mass_excess_unc))
    except (ValueError, IndexError):
        return None
    if z + n != a:
        return None
    if not el or not el[0].isalpha():
        return None
    status = classify_record_status(estimated=est_me or est_unc)
    return MassObservation(
        nuclide=NuclideIdentity.from_zn(z, n),
        mass_excess_keV=mass_excess,
        uncertainty_keV=unc,
        source_edition=spec.edition_id,
        source_release_date=spec.release_date,
        source_record_status=status,
        raw_source_hash=raw_source_hash,
        element_symbol=el,
    )


def parse_ame_mass_table(path: str | Path, spec: EditionSpec) -> list[MassObservation]:
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8", errors="replace")
    digest = sha256_hex(raw)
    observations: list[MassObservation] = []
    seen: set[str] = set()
    for line in text.splitlines():
        obs = parse_ame_line(line, spec, digest)
        if obs is None:
            continue
        if obs.nuclide_id in seen:
            continue
        seen.add(obs.nuclide_id)
        observations.append(obs)
    if not observations:
        raise ValueError(f"no AME mass records parsed from {path}")
    return observations


def format_ame_line(
    *,
    n: int,
    z: int,
    a: int,
    el: str,
    mass_excess_keV: float,
    uncertainty_keV: float,
    estimated: bool = False,
    spec: EditionSpec | None = None,
) -> str:
    """Format one Audi-style mass-table line for fixtures and round-trips."""
    spec = spec or EditionSpec("AME2020", "2021-03-01", AME_MAS20_COLUMNS)
    mark = "#" if estimated else " "
    line = [" "] * 80
    def put(span: tuple[int, int], value: str, align: str = ">") -> None:
        start, end = span
        width = end - start
        text = f"{value:{align}{width}}"[:width]
        line[start:end] = list(text)

    put(spec.columns.n, str(n))
    put(spec.columns.z, str(z))
    put(spec.columns.a, str(a))
    put(spec.columns.el, el, align="<")
    me = f"{mass_excess_keV:13.5f}".replace(" ", "")
    unc = f"{uncertainty_keV:11.5f}".replace(" ", "")
    if estimated:
        me = me[:-1] + mark if len(me) >= 1 else mark
        unc = unc[:-1] + mark if len(unc) >= 1 else mark
    put(spec.columns.mass_excess, f"{mass_excess_keV:13.5f}")
    put(spec.columns.mass_excess_unc, f"{uncertainty_keV:11.5f}")
    text = "".join(line)
    if estimated:
        start, end = spec.columns.mass_excess
        text = text[: end - 1] + "#" + text[end:]
    return text.rstrip()
