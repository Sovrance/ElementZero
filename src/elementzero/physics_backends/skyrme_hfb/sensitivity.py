"""Which Skyrme parameters the calibration data can actually determine.

Fitting a parameter the data cannot constrain does not fail loudly; it
wanders inside its bounds, absorbs noise, and produces a fit that looks
converged and generalizes badly. So before any tier is frozen, each
candidate is stepped inside its own bounds and the effect on binding
energy is measured across a fixed probe set.

Two things disqualify a parameter: moving nothing (unidentifiable), or
moving the probes in almost exactly the same pattern as another
parameter (collinear — the pair is one degree of freedom wearing two
names, and fitting both invites the optimizer to trade them off forever).
"""

from __future__ import annotations

import concurrent.futures
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.physics_backends.adapters.hfbtho import BASIS_N_SHELLS, namelist
from elementzero.physics_backends.output_parser import parse_hfbtho
from elementzero.physics_backends.skyrme_hfb import (
    FUNCTIONAL_FILE,
    READ_FUNCTIONAL_BINARY,
    SKYRME_BASELINE_INM,
    functional_file_text,
)
from elementzero.physics_backends.skyrme_hfb.prereg import (
    CALIBRATION_TIMEOUT_S,
    CORRELATION_MAX,
    IDENTIFIABILITY_MIN_KEV,
    PARAMETER_BOUNDS,
    RELATIVE_STEP,
    SENSITIVITY_PROBE_IDS,
    TIER_SELECTION_RULE,
    TIERS,
    within_bounds,
)


def readfunc_binary(*, repo_root: str | Path | None = None) -> Path:
    from elementzero.physics_backends.provenance import backend_data_dir

    path = backend_data_dir(repo_root=repo_root) / READ_FUNCTIONAL_BINARY
    if not path.is_file():
        raise ProtocolError(
            f"{path} is missing; build HFBTHO with READ_FUNCTIONAL=1 first"
        )
    return path


def solve_with_vector(
    *,
    nuclide_id: str,
    values: dict[str, float],
    work_dir: str | Path,
    repo_root: str | Path | None = None,
    shells: int = BASIS_N_SHELLS,
    timeout_s: int = CALIBRATION_TIMEOUT_S,
) -> dict[str, Any]:
    """One solve under an arbitrary INM vector, in a clean directory."""
    if not within_bounds(values):
        raise ProtocolError(
            "SKYRME_VECTOR_OUT_OF_BOUNDS: a parameter left its declared box; "
            "the bound is not widened to accommodate it"
        )
    z, n = parse_nuclide_id(nuclide_id)
    work_dir = Path(work_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    (work_dir / "hfbtho_NAMELIST.dat").write_text(
        namelist(
            z=z,
            n=n,
            functional="SKM*",
            vpair_n=values["CpV0_0"],
            vpair_p=values["CpV0_1"],
            shells=shells,
        ),
        encoding="utf-8",
    )
    (work_dir / FUNCTIONAL_FILE).write_text(
        functional_file_text(values), encoding="utf-8"
    )
    binary = readfunc_binary(repo_root=repo_root).resolve()
    env = {
        **os.environ,
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    try:
        completed = subprocess.run(
            [str(binary)],
            cwd=work_dir,
            capture_output=True,
            timeout=timeout_s,
            check=False,
            env=env,
        )
        (work_dir / "run.log").write_bytes(
            completed.stdout + b"\n" + completed.stderr
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        (work_dir / "run.log").write_text(
            f"TIMEOUT after {timeout_s}s\n", encoding="utf-8"
        )
        timed_out = True
    parsed = parse_hfbtho(work_dir)
    return {**parsed, "timed_out": timed_out, "nuclide_id": nuclide_id}


def _probe_vector(
    values: dict[str, float],
    probe_ids: tuple[str, ...],
    work_root: Path,
    label: str,
    repo_root: str | Path | None,
    max_workers: int,
) -> dict[str, float | None]:
    """Binding energies across the probe set for one parameter vector."""
    out: dict[str, float | None] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                solve_with_vector,
                nuclide_id=nuclide_id,
                values=values,
                work_dir=work_root / label / nuclide_id,
                repo_root=repo_root,
            ): nuclide_id
            for nuclide_id in probe_ids
        }
        for future in concurrent.futures.as_completed(futures):
            nuclide_id = futures[future]
            parsed = future.result()
            out[nuclide_id] = (
                parsed["energy_MeV"] if parsed["solver_ok"] else None
            )
    return out


def run_sensitivity(
    *,
    work_root: str | Path,
    repo_root: str | Path | None = None,
    max_workers: int = 4,
    probe_ids: tuple[str, ...] = SENSITIVITY_PROBE_IDS,
) -> dict[str, Any]:
    """Step every candidate parameter and record what the probes do."""
    root = Path(repo_root or REPO_ROOT)
    work_root = Path(work_root)
    baseline = dict(SKYRME_BASELINE_INM)

    base_energies = _probe_vector(
        baseline, probe_ids, work_root, "baseline", root, max_workers
    )
    records = []
    for name in sorted(PARAMETER_BOUNDS):
        low, high = PARAMETER_BOUNDS[name]
        step = RELATIVE_STEP * (high - low)
        stepped = dict(baseline)
        # Step toward the interior so the probe never leaves the box.
        direction = 1.0 if baseline[name] + step <= high else -1.0
        stepped[name] = baseline[name] + direction * step
        energies = _probe_vector(
            stepped, probe_ids, work_root, f"step_{name}", root, max_workers
        )
        deltas: dict[str, float | None] = {}
        usable = []
        for nuclide_id in probe_ids:
            base = base_energies.get(nuclide_id)
            moved = energies.get(nuclide_id)
            if base is None or moved is None:
                deltas[nuclide_id] = None
                continue
            delta_keV = (moved - base) * 1000.0
            deltas[nuclide_id] = delta_keV
            usable.append(delta_keV)
        mean_abs = sum(abs(d) for d in usable) / len(usable) if usable else 0.0
        records.append(
            {
                "parameter": name,
                "baseline_value": baseline[name],
                "stepped_value": stepped[name],
                "step": direction * step,
                "delta_keV": deltas,
                "n_usable_probes": len(usable),
                "mean_abs_delta_keV": mean_abs,
                "identifiable": mean_abs >= IDENTIFIABILITY_MIN_KEV
                and len(usable) == len(probe_ids),
            }
        )
    return {
        "sensitivity_id": "ez-wo15b-skyrme-sensitivity-v1",
        "probe_ids": list(probe_ids),
        "baseline_energies_MeV": base_energies,
        "relative_step": RELATIVE_STEP,
        "identifiability_min_keV": IDENTIFIABILITY_MIN_KEV,
        "records": records,
    }


def _correlation(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return 0.0
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    var_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
    var_b = math.sqrt(sum((y - mean_b) ** 2 for y in b))
    if var_a == 0.0 or var_b == 0.0:
        return 0.0
    return cov / (var_a * var_b)


def select_tier(sensitivity: dict[str, Any]) -> dict[str, Any]:
    """Freeze the identifiable, non-collinear subset of the fittable set.

    Selection is on identifiability alone. It can only remove parameters
    from the declared fittable set, never add them, so the frozen subset
    is always at most as flexible as what was preregistered.
    """
    from elementzero.physics_backends.skyrme_hfb.prereg import (
        FITTABLE_PARAMETERS,
    )

    probe_ids = list(sensitivity["probe_ids"])
    by_name = {r["parameter"]: r for r in sensitivity["records"]}
    # Canonical JSON renders floats as strings on the way out, so a
    # record read back from disk needs coercing before any arithmetic.
    vectors = {
        name: [
            float(r["delta_keV"][p])
            for p in probe_ids
            if r["delta_keV"].get(p) is not None
        ]
        for name, r in by_name.items()
    }
    strength = {
        name: float(by_name[name]["mean_abs_delta_keV"]) for name in by_name
    }

    candidates = [p for p in FITTABLE_PARAMETERS if by_name[p]["identifiable"]]
    excluded_unidentifiable = [
        {
            "parameter": p,
            "mean_abs_delta_keV": strength[p],
            "threshold_keV": IDENTIFIABILITY_MIN_KEV,
        }
        for p in FITTABLE_PARAMETERS
        if not by_name[p]["identifiable"]
    ]

    # Drop the weaker member of any collinear pair: the survivor is the
    # one the calibration data constrains better.
    dropped_collinear: list[dict[str, Any]] = []
    kept: list[str] = []
    for name in candidates:
        clash = None
        for other in kept:
            va, vb = vectors[name], vectors[other]
            if len(va) != len(vb) or len(va) < 2:
                continue
            if abs(_correlation(va, vb)) > CORRELATION_MAX:
                clash = other
                break
        if clash is None:
            kept.append(name)
            continue
        weaker = name if strength[name] < strength[clash] else clash
        stronger = clash if weaker == name else name
        dropped_collinear.append(
            {
                "dropped": weaker,
                "kept": stronger,
                "correlation": abs(_correlation(vectors[name], vectors[clash])),
            }
        )
        if weaker == clash:
            kept.remove(clash)
            kept.append(name)

    selected = [p for p in FITTABLE_PARAMETERS if p in kept]
    label = None
    for tier_name in ("S1", "S2", "S3"):
        if set(selected) == set(TIERS[tier_name]):
            label = tier_name
            break
    if label is None and selected:
        smallest = next(
            (
                t
                for t in ("S1", "S2", "S3")
                if set(selected) <= set(TIERS[t])
            ),
            "S3",
        )
        label = f"PARTIAL_{smallest}"

    return {
        "tier_selection_rule": TIER_SELECTION_RULE,
        "fittable_parameters": list(FITTABLE_PARAMETERS),
        "selected_tier": label,
        "selected_parameters": selected,
        "n_selected": len(selected),
        "excluded_unidentifiable": excluded_unidentifiable,
        "dropped_collinear": dropped_collinear,
        "parameter_strength_keV": dict(sorted(strength.items())),
        "status": (
            f"TIER_{label}_FROZEN"
            if selected
            else "NO_PARAMETER_IDENTIFIABLE_BASELINE_STANDS"
        ),
    }


__all__ = [
    "readfunc_binary",
    "run_sensitivity",
    "select_tier",
    "solve_with_vector",
]
