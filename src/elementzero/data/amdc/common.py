"""Shared AME mass-table parsing.

Edition adapters supply explicit column maps. Values marked with ``#`` in the
source are estimated (non-experimental) evaluated quantities and are not
ground-truth eligible for EZ-B001 v1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import (
    RECORD_STATUS_EVALUATED_ESTIMATED,
    RECORD_STATUS_EVALUATED_NON_ESTIMATED,
    RECORD_STATUS_EXTRAPOLATED,
    MassObservation,
)
from elementzero.evidence.hashing import sha256_hex

PARSER_VERSION = "ame-parser-v2"
DEFAULT_MALFORMED_FRACTION_LIMIT = 0.5


@dataclass(frozen=True)
class ColumnMap:
    n: tuple[int, int]
    z: tuple[int, int]
    a: tuple[int, int]
    el: tuple[int, int]
    origin: tuple[int, int]
    mass_excess: tuple[int, int]
    mass_excess_unc: tuple[int, int]
    mass_precision: int = 5
    uncertainty_precision: int = 5
    line_length_expected: int | None = None


# AME2003 / AME2012 / AME2016 share f13.5 / f11.5 mass columns.
AME_MAS03_COLUMNS = ColumnMap(
    n=(4, 9),
    z=(9, 14),
    a=(14, 19),
    el=(20, 23),
    origin=(23, 27),
    mass_excess=(28, 41),
    mass_excess_unc=(41, 52),
    mass_precision=5,
    uncertainty_precision=5,
)
AME_MAS12_COLUMNS = ColumnMap(
    n=(4, 9),
    z=(9, 14),
    a=(14, 19),
    el=(20, 23),
    origin=(23, 27),
    mass_excess=(28, 41),
    mass_excess_unc=(41, 52),
    mass_precision=5,
    uncertainty_precision=5,
)
AME_MAS16_COLUMNS = ColumnMap(
    n=(4, 9),
    z=(9, 14),
    a=(14, 19),
    el=(20, 23),
    origin=(23, 27),
    mass_excess=(28, 41),
    mass_excess_unc=(41, 52),
    mass_precision=5,
    uncertainty_precision=5,
)

# AME2020 widens mass excess / uncertainty (f14.6 / f12.6).
AME_MAS20_COLUMNS = ColumnMap(
    n=(4, 9),
    z=(9, 14),
    a=(14, 19),
    el=(20, 23),
    origin=(23, 27),
    mass_excess=(28, 42),
    mass_excess_unc=(42, 54),
    mass_precision=6,
    uncertainty_precision=6,
)


@dataclass(frozen=True)
class EditionSpec:
    edition_id: str
    release_date: str
    columns: ColumnMap
    filename_hints: tuple[str, ...] = ()
    year: int = 0


@dataclass
class ParserReport:
    edition_id: str
    raw_source_hash: str
    total_lines: int = 0
    parsed_records: int = 0
    skipped_headers: int = 0
    malformed_candidate_rows: int = 0
    estimated_records: int = 0
    eligible_records: int = 0
    duplicate_ids: int = 0
    invalid_A_equals_Z_plus_N: int = 0
    parser_version: str = PARSER_VERSION
    candidate_rows: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def malformed_fraction(self) -> float:
        if self.candidate_rows <= 0:
            return 0.0
        return self.malformed_candidate_rows / self.candidate_rows


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
    """Map AME markers to conservative evaluation statuses.

    Never emits ``direct_measurement`` from AME tables.
    """
    if estimated:
        origin_l = origin.lower()
        if "x" in origin_l or "sys" in origin_l:
            return RECORD_STATUS_EXTRAPOLATED
        return RECORD_STATUS_EVALUATED_ESTIMATED
    return RECORD_STATUS_EVALUATED_NON_ESTIMATED


def _looks_like_candidate(line: str, spec: EditionSpec) -> bool:
    n_raw = _slice(line, spec.columns.n).strip()
    z_raw = _slice(line, spec.columns.z).strip()
    a_raw = _slice(line, spec.columns.a).strip()
    if not (n_raw.lstrip("-").isdigit() and z_raw.lstrip("-").isdigit() and a_raw.isdigit()):
        return False
    return True


def parse_ame_line(
    line: str, spec: EditionSpec, raw_source_hash: str
) -> tuple[MassObservation | None, str | None]:
    """Parse one line.

    Returns ``(observation, failure_reason)`` where failure_reason is one of
    ``None``, ``header``, ``malformed``, or ``invalid_A``.
    """
    stripped = line.rstrip("\n")
    if not stripped.strip():
        return None, "header"
    if not _looks_like_candidate(stripped, spec):
        return None, "header"
    try:
        n = int(_slice(stripped, spec.columns.n).strip())
        z = int(_slice(stripped, spec.columns.z).strip())
        a = int(_slice(stripped, spec.columns.a).strip())
        el = _slice(stripped, spec.columns.el).strip() or None
        origin = _slice(stripped, spec.columns.origin).strip()
        mass_excess, est_me = _parse_ame_number(_slice(stripped, spec.columns.mass_excess))
        unc, est_unc = _parse_ame_number(_slice(stripped, spec.columns.mass_excess_unc))
    except (ValueError, IndexError):
        return None, "malformed"
    if z + n != a:
        return None, "invalid_A"
    if not el or not el[0].isalpha():
        return None, "malformed"
    status = classify_record_status(estimated=est_me or est_unc, origin=origin)
    obs = MassObservation(
        nuclide=NuclideIdentity.from_zn(z, n),
        mass_excess_keV=mass_excess,
        uncertainty_keV=unc,
        source_edition=spec.edition_id,
        source_release_date=spec.release_date,
        source_record_status=status,
        raw_source_hash=raw_source_hash,
        element_symbol=el,
        estimated_mass=est_me,
        estimated_uncertainty=est_unc,
        source_origin=origin,
    )
    return obs, None


def parse_ame_mass_table_detailed(
    path: str | Path,
    spec: EditionSpec,
    *,
    malformed_fraction_limit: float = DEFAULT_MALFORMED_FRACTION_LIMIT,
) -> tuple[list[MassObservation], ParserReport]:
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8", errors="replace")
    digest = sha256_hex(raw)
    report = ParserReport(edition_id=spec.edition_id, raw_source_hash=digest)
    observations: list[MassObservation] = []
    seen: set[str] = set()
    for line in text.splitlines():
        report.total_lines += 1
        obs, reason = parse_ame_line(line, spec, digest)
        if reason == "header":
            report.skipped_headers += 1
            continue
        report.candidate_rows += 1
        if reason == "invalid_A":
            report.invalid_A_equals_Z_plus_N += 1
            report.malformed_candidate_rows += 1
            continue
        if reason == "malformed" or obs is None:
            report.malformed_candidate_rows += 1
            continue
        if obs.nuclide_id in seen:
            report.duplicate_ids += 1
            continue
        seen.add(obs.nuclide_id)
        observations.append(obs)
        report.parsed_records += 1
        if obs.estimated_mass or obs.estimated_uncertainty:
            report.estimated_records += 1
        if obs.ground_truth_eligible:
            report.eligible_records += 1
    if not observations:
        raise ValueError(f"no AME mass records parsed from {path}")
    if report.malformed_fraction > malformed_fraction_limit:
        raise ValueError(
            f"AME parse malformed fraction {report.malformed_fraction:.3f} "
            f"exceeds limit {malformed_fraction_limit} for {path}"
        )
    return observations, report


def parse_ame_mass_table(path: str | Path, spec: EditionSpec) -> list[MassObservation]:
    observations, _report = parse_ame_mass_table_detailed(path, spec)
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
    origin: str = "",
    spec: EditionSpec | None = None,
) -> str:
    """Format one Audi-style mass-table line for fixtures and round-trips."""
    if spec is None:
        spec = EditionSpec("AME2020", "2021-03-01", AME_MAS20_COLUMNS, year=2020)
    cols = spec.columns
    width = max(80, cols.mass_excess_unc[1] + 4)
    line = [" "] * width

    def put(span: tuple[int, int], value: str, align: str = ">") -> None:
        start, end = span
        w = end - start
        text = f"{value:{align}{w}}"[:w]
        line[start:end] = list(text)

    put(cols.n, str(n))
    put(cols.z, str(z))
    put(cols.a, str(a))
    put(cols.el, el, align="<")
    put(cols.origin, origin[: cols.origin[1] - cols.origin[0]], align="<")
    me_fmt = f"{{:{cols.mass_excess[1] - cols.mass_excess[0]}.{cols.mass_precision}f}}"
    unc_fmt = (
        f"{{:{cols.mass_excess_unc[1] - cols.mass_excess_unc[0]}.{cols.uncertainty_precision}f}}"
    )
    put(cols.mass_excess, me_fmt.format(mass_excess_keV))
    put(cols.mass_excess_unc, unc_fmt.format(uncertainty_keV))
    text = "".join(line)
    if estimated:
        end = cols.mass_excess[1]
        text = text[: end - 1] + "#" + text[end:]
        uend = cols.mass_excess_unc[1]
        text = text[: uend - 1] + "#" + text[uend:]
    return text.rstrip()
