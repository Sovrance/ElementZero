from __future__ import annotations

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
