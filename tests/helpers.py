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


# --------------------------------------------------------------------------- #
# EZ-B003 synthetic shell chart with an injected discontinuity                 #
# --------------------------------------------------------------------------- #
# WO-10 section 8 asks for a synthetic mass surface with an injected shell-like
# discontinuity *before* any known closure is scored, so that the benchmark
# mechanics can be validated where the answer is known by construction.
#
# The surface is the same toy SEMF plus smooth ripple as the EZ-B002 chart, with
# two injected kinks added to the binding energy:
#
#     E_shell(Z, N) = -g_n * max(0, N - N0) - g_p * max(0, Z - Z0)
#
# Each kink is exactly the shape a shell closure leaves in a mass surface: the
# two-nucleon separation energy drops by a constant amount once the closure is
# passed. Expanding the indicator shows why the injected feature is a spike of
# known height at exactly one coordinate, and zero everywhere else in the same
# parity class:
#
#     delta2n(Z, N0)   = 2*E(N0) - E(N0-2) - E(N0+2) = 0 - 0 + 2*g_n = +2*g_n
#     delta2n(Z, N0+2) = 2*E(N0+2) - E(N0) - E(N0+4) = -4g + 0 + 4g  = 0
#     delta2n(Z, N0-2) = 2*E(N0-2) - E(N0-4) - E(N0) = 0             = 0
#
# The neutron kink depends only on N and the proton kink only on Z, so the two
# injected features do not contaminate each other's indicator: delta2n sees only
# g_n and delta2p sees only g_p.
#
# The chart is a rectangle rather than a valley band on purpose. Every Z chain
# then holds the whole neutron window and every N chain the whole proton window,
# so the support rule masks *every* occurrence of the injected closure instead of
# leaving edge chains that still carry it.

SYNTHETIC_SHELL_CHART_POLICY = "ez-b003-synthetic-shell-chart-v1"
SHELL_CHART_Z_MIN = 24
SHELL_CHART_Z_MAX = 44
SHELL_CHART_N_MIN = 38
SHELL_CHART_N_MAX = 58

# Both closures are members of the EZ-B003 availability set, so the committed
# fixture exercises the real closure list rather than an invented coordinate.
INJECTED_NEUTRON_CLOSURE = 50
INJECTED_PROTON_CLOSURE = 28

# Gap sizes in MeV. The indicator spike is twice the gap, which puts the injected
# neutron feature at +3.0 MeV against a smooth background of well under 1 MeV.
INJECTED_NEUTRON_GAP_MeV = 1.5
INJECTED_PROTON_GAP_MeV = 1.2

SHELL_CHART_ESTIMATED_MODULUS = 41


def injected_shell_term_MeV(
    z: int,
    n: int,
    *,
    neutron_closure: int = INJECTED_NEUTRON_CLOSURE,
    proton_closure: int = INJECTED_PROTON_CLOSURE,
    neutron_gap_MeV: float = INJECTED_NEUTRON_GAP_MeV,
    proton_gap_MeV: float = INJECTED_PROTON_GAP_MeV,
) -> float:
    """The injected binding-energy kinks, in MeV (negative above each closure)."""
    return -neutron_gap_MeV * max(0, n - neutron_closure) - proton_gap_MeV * max(
        0, z - proton_closure
    )


def synthetic_shell_chart_rows(
    *,
    z_min: int = SHELL_CHART_Z_MIN,
    z_max: int = SHELL_CHART_Z_MAX,
    n_min: int = SHELL_CHART_N_MIN,
    n_max: int = SHELL_CHART_N_MAX,
    neutron_closure: int = INJECTED_NEUTRON_CLOSURE,
    proton_closure: int = INJECTED_PROTON_CLOSURE,
) -> list[tuple[int, int, str, float, float, bool]]:
    """Rows of the synthetic shell chart, in AME mass-table row order."""
    rows = []
    for z in range(z_min, z_max + 1):
        for n in range(n_min, n_max + 1):
            noise = synthetic_shell_residual_MeV(z, n) + injected_shell_term_MeV(
                z, n, neutron_closure=neutron_closure, proton_closure=proton_closure
            )
            estimated = (z + n) % SHELL_CHART_ESTIMATED_MODULUS == 0
            rows.append((z, n, "X", toy_mass_excess(z, n, noise=noise), 11.0 + (z % 2), estimated))
    return rows


def write_synthetic_shell_chart(path: Path) -> Path:
    """Write the synthetic shell chart as an AME2020-format mass table."""
    return write_ame_table(path, synthetic_shell_chart_rows(), AME2020)


def small_synthetic_shell_chart_rows() -> list[tuple[int, int, str, float, float, bool]]:
    """A cheaper shell chart for unit tests: one closure, fewer chains."""
    return synthetic_shell_chart_rows(z_min=26, z_max=32, n_min=42, n_max=58)


def write_small_synthetic_shell_chart(path: Path) -> Path:
    return write_ame_table(path, small_synthetic_shell_chart_rows(), AME2020)


# The same surface with both kinks moved off the chart, which leaves the smooth
# background bit-for-bit untouched. This is the control: whatever the benchmark
# reports here is what it reports when there is no shell structure to find.
UNREACHABLE_CLOSURE = 10_000


def unkinked_synthetic_shell_chart_rows() -> list[tuple[int, int, str, float, float, bool]]:
    return synthetic_shell_chart_rows(
        neutron_closure=UNREACHABLE_CLOSURE, proton_closure=UNREACHABLE_CLOSURE
    )


def write_unkinked_synthetic_shell_chart(path: Path) -> Path:
    """The control chart: identical smooth surface, no injected discontinuity."""
    return write_ame_table(path, unkinked_synthetic_shell_chart_rows(), AME2020)


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


# --------------------------------------------------------------------------- #
# Refit-reproducibility environment guard (WO-11)                             #
# --------------------------------------------------------------------------- #
# Re-*scoring* sealed predictions is environment-independent at the canonical
# 12-significant-digit precision, and WO-11 asserts that everywhere. Re-
# *fitting* the GP models byte-for-byte additionally requires the exact
# library stack the committed run recorded: a different BLAS/LAPACK build
# moves fitted hyperparameters at the ULP level, which moves the fitted-model
# manifest hash without moving any recorded metric. The committed-seal refit
# tests are therefore only meaningful in the recorded environment, and they
# skip — loudly, with the version delta in the reason — anywhere else.


def refit_environment_mismatch(experiment_dir: Path) -> str | None:
    """A skip reason when this runtime cannot reproduce a committed *fit*."""
    import json as _json
    import platform as _platform

    from elementzero.identity_meta import runtime_library_versions

    environment_file = experiment_dir / "environment.json"
    if not environment_file.is_file():
        return None
    recorded = _json.loads(environment_file.read_text(encoding="utf-8"))
    deltas = []
    running = runtime_library_versions()
    for name in ("numpy", "scipy", "sklearn"):
        want = recorded.get("library_versions", {}).get(name)
        have = running.get(name)
        if want is not None and want != have:
            deltas.append(f"{name} {have} != recorded {want}")
    recorded_python = recorded.get("python_version", "")
    if recorded_python.rsplit(".", 1)[0] != _platform.python_version().rsplit(".", 1)[0]:
        deltas.append(
            f"python {_platform.python_version()} != recorded {recorded_python}"
        )
    if not deltas:
        return None
    return (
        "refit reproducibility requires the recorded environment; this runtime "
        "differs (" + "; ".join(deltas) + "). The sealed-scoring replay is "
        "still asserted by tests/integration/test_wo11_reproduce_b002_b003.py."
    )
