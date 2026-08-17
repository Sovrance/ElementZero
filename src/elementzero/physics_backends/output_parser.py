"""Deterministic parsing of solver output (WO-15 Gate A).

Parsing is where a physics campaign quietly goes wrong: a regex that
matches a diagnostic line instead of the final energy, or that returns
the last of several blocks. Every parser here reports what it found and
refuses to guess.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from elementzero.evidence.hashing import sha256_hex

# HFBTHO writes the converged quasiparticle HFB energy as
#   "  tEnergy: ehfb (qp)...      -1110.347993"
HFBTHO_ENERGY_RE = re.compile(
    r"tEnergy:\s*ehfb\s*\(qp\)\.*\s*(-?\d+\.\d+)"
)
HFBTHO_LN_ENERGY_RE = re.compile(r"tEnergy:\s*ehfb\(qp\)\+LN\s*(-?\d+\.\d+)")
HFBTHO_OK_RE = re.compile(r"HFBTHO_SOLVER ended without errors")
HFBTHO_ERR_RE = re.compile(r"ERRORS IN HFBTHO_SOLVER|error_flag=\s*([1-9])")
HFBTHO_ITER_RE = re.compile(r"^\s*(\d+)\s+\S+\s+", re.MULTILINE)

# DIRHB writes "  Total Energy                     -670.936603"
DIRHB_ENERGY_RE = re.compile(r"Total Energy\s+(-?\d+\.\d+)")
DIRHB_ITER_RE = re.compile(r"(\d+)\.It\. si =")
# DIRHB announces convergence explicitly, and then prints
# "STOP  FINAL STOP OF DIRHBS" on a *normal* exit. Treating the word
# STOP as failure would discard every good solve, so convergence is read
# from the solver's own statement instead.
DIRHB_CONVERGED_RE = re.compile(r"Iteration converged after\s+\d+\s+steps")
DIRHB_ABORT_RE = re.compile(
    r"STOP:\s|NUCLEUS\s+\S+\s+UNKNOWN|Iteration has not converged"
)


def _read(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_hfbtho(run_dir: str | Path) -> dict[str, Any]:
    """Total HFB energy (MeV) and convergence evidence from one run dir."""
    run_dir = Path(run_dir)
    stdout = _read(run_dir / "run.log")
    thoout = _read(run_dir / "thoout.dat")
    blob = thoout + "\n" + stdout

    energies = HFBTHO_ENERGY_RE.findall(thoout) or HFBTHO_ENERGY_RE.findall(stdout)
    ln_energies = HFBTHO_LN_ENERGY_RE.findall(blob)
    ok = bool(HFBTHO_OK_RE.search(blob))
    err = HFBTHO_ERR_RE.search(blob)
    iterations = 0
    iters = re.findall(r"^\s*(\d+)\s+[-\d.E+]+\s+[-\d.E+]+", thoout, re.MULTILINE)
    if iters:
        iterations = int(iters[-1])

    energy = None
    if energies:
        try:
            energy = float(energies[-1])
        except ValueError:
            energy = None
    if energy is not None and (math.isnan(energy) or math.isinf(energy)):
        energy = None

    has_nan = "NaN" in blob or "nan" in thoout.split("tEnergy")[0][-2000:]
    return {
        "energy_MeV": energy,
        "energy_LN_MeV": float(ln_energies[-1]) if ln_energies else None,
        "solver_ok": ok and not err,
        "error_text": err.group(0) if err else "",
        "iterations": iterations,
        "nan_detected": has_nan,
        "output_hash": sha256_hex({"thoout": thoout, "stdout": stdout}),
        "n_energy_matches": len(energies),
    }


def parse_dirhb(run_dir: str | Path) -> dict[str, Any]:
    """Total energy (MeV) and iteration evidence from a DIRHB run dir."""
    run_dir = Path(run_dir)
    out = _read(run_dir / "dirhb.out")
    screen = _read(run_dir / "screen.log")
    blob = out + "\n" + screen
    energies = DIRHB_ENERGY_RE.findall(out)
    iters = DIRHB_ITER_RE.findall(blob)
    energy = float(energies[-1]) if energies else None
    if energy is not None and (math.isnan(energy) or math.isinf(energy)):
        energy = None
    converged = bool(DIRHB_CONVERGED_RE.search(blob))
    aborted = bool(DIRHB_ABORT_RE.search(blob))
    return {
        "energy_MeV": energy,
        "solver_ok": energy is not None and converged and not aborted,
        "converged_statement": converged,
        "aborted": aborted,
        "iterations": int(iters[-1]) if iters else 0,
        "nan_detected": "NaN" in blob,
        "output_hash": sha256_hex({"out": out, "screen": screen}),
        "n_energy_matches": len(energies),
    }
