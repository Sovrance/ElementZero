from __future__ import annotations

import math
from pathlib import Path

from elementzero.data.amdc.ame2003 import EDITION as AME2003
from elementzero.data.amdc.ame2020 import EDITION as AME2020
from elementzero.data.amdc.common import EditionSpec, format_ame_line
from elementzero.physics.conversion import mass_excess_keV_from_binding
from elementzero.physics.semf import pairing_sign


def toy_mass_excess(z: int, n: int, noise: float = 0.0) -> float:
    a = z + n
    binding = (
        15.8 * a
        - 18.3 * (a ** (2.0 / 3.0))
        - 0.714 * z * (z - 1) / (a ** (1.0 / 3.0))
        - 23.2 * ((n - z) ** 2) / a
        + 12.0 * pairing_sign(z, n) / (a ** 0.5)
    )
    return mass_excess_keV_from_binding(z=z, n=n, binding_MeV=binding + noise)


def write_ame_table(path: Path, rows: list[tuple[int, int, str, float, float, bool]], spec: EditionSpec) -> Path:
    header = "   AME synthetic mass table for ElementZero EZ-B001\n"
    lines = [header]
    for z, n, el, me, unc, estimated in rows:
        lines.append(
            format_ame_line(
                n=n,
                z=z,
                a=z + n,
                el=el,
                mass_excess_keV=me,
                uncertainty_keV=unc,
                estimated=estimated,
                spec=spec,
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# EZ-B002 synthetic nuclear chart                                             #
# --------------------------------------------------------------------------- #
# A smooth, nuclear-like surface over a drifting valley of stability, written in
# AME2020 mass-table format. It is software evidence for the geographic-holdout
# protocol, never scientific evidence: the committed fixture exists so CI can run
# EZ-B002 end to end without the licensed AME tables.

SYNTHETIC_CHART_POLICY = "ez-b002-synthetic-chart-v1"
SYNTHETIC_CHART_Z_MIN = 6
SYNTHETIC_CHART_Z_MAX = 58
SYNTHETIC_CHART_ESTIMATED_MODULUS = 37


def synthetic_shell_residual_MeV(z: int, n: int) -> float:
    """A smooth, deterministic, non-SEMF binding ripple in MeV.

    Without it the surface *is* the SEMF, and a least-squares SEMF recovers a
    withheld block to machine precision, which would make every depth diagnostic
    read as zero. The ripple is smooth in both Z and N (so extrapolation is still
    possible) and carries no randomness (so the fixture is byte-reproducible).
    """
    return (
        0.60 * math.cos(0.42 * n)
        + 0.45 * math.cos(0.37 * z)
        + 0.25 * math.cos(0.11 * (n - z))
    )


def synthetic_chart_rows(
    *,
    z_min: int = SYNTHETIC_CHART_Z_MIN,
    z_max: int = SYNTHETIC_CHART_Z_MAX,
) -> list[tuple[int, int, str, float, float, bool]]:
    """Rows of the synthetic chart: one smooth valley band per Z.

    ``N`` follows ``Z + 0.008 * Z^2`` (a drifting valley) with a band half-width
    that grows slowly with Z, so light, medium, and heavy Z bands all carry
    enough eligible nuclei for a candidate window. Every 37th mass number is
    marked estimated, which keeps the ground-truth-eligibility filter exercised.
    """
    rows = []
    for z in range(z_min, z_max + 1):
        center = round(z + 0.008 * z * z)
        half_width = 2 + z // 15
        for n in range(center - half_width, center + half_width + 1):
            if n < 1:
                continue
            estimated = (z + n) % SYNTHETIC_CHART_ESTIMATED_MODULUS == 0
            mass_excess = toy_mass_excess(z, n, noise=synthetic_shell_residual_MeV(z, n))
            rows.append((z, n, "X", mass_excess, 12.0 + (z % 3), estimated))
    return rows


def write_synthetic_chart(path: Path) -> Path:
    """Write the synthetic chart as an AME2020-format mass table."""
    return write_ame_table(path, synthetic_chart_rows(), AME2020)


def small_synthetic_chart_rows() -> list[tuple[int, int, str, float, float, bool]]:
    """A cheaper chart for unit and reproducibility tests (one Z band)."""
    rows = []
    for z in range(8, 21):
        center = round(z + 0.008 * z * z)
        for n in range(center - 3, center + 4):
            mass_excess = toy_mass_excess(z, n, noise=synthetic_shell_residual_MeV(z, n))
            rows.append((z, n, "X", mass_excess, 14.0, False))
    return rows


def write_small_synthetic_chart(path: Path) -> Path:
    return write_ame_table(path, small_synthetic_chart_rows(), AME2020)


def synthetic_editions(tmp_path: Path) -> tuple[Path, Path]:
    old_rows = []
    later_rows = []
    symbol = "X"
    for z in range(8, 18):
        n = z
        me = toy_mass_excess(z, n)
        old_rows.append((z, n, symbol, me, 15.0, False))
        later_rows.append((z, n, symbol, me + 2.0, 12.0, False))
    for z in range(18, 21):
        n = z + 1
        me = toy_mass_excess(z, n, noise=0.4)
        later_rows.append((z, n, symbol, me, 20.0, False))
    old = write_ame_table(tmp_path / "old.mas03", old_rows, AME2003)
    later = write_ame_table(tmp_path / "later.mas20", later_rows, AME2020)
    return old, later
