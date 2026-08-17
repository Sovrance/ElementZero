"""The broader Skyrme mass refit (WO-15B stream A).

An N-dimensional Nelder-Mead over the frozen parameter subset, written
here rather than reusing the WO-15 optimizer because that one is fixed
at two dimensions and its artifacts must stay byte-reproducible. Same
discipline though: no library optimizer with hidden restarts, a hard
evaluation budget, box constraints that are never widened, and every
evaluation logged so the path is inspectable after the fact.

Non-converged solves take a fixed infeasible penalty instead of being
dropped. Dropping them would let the optimizer improve its score by
wandering into regions where the solver quietly fails — the objective
would fall while the physics got worse.
"""

from __future__ import annotations

import concurrent.futures
import math
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.amdc import load_edition
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.physics.conversion import mass_excess_keV_from_binding
from elementzero.physics_backends.skyrme_hfb import SKYRME_BASELINE_INM
from elementzero.physics_backends.skyrme_hfb.prereg import (
    INFEASIBLE_PENALTY_KEV,
    MAX_OBJECTIVE_EVALUATIONS,
    MIN_CONVERGED_FRACTION,
    PARAMETER_BOUNDS,
    PREREG_ID,
)
from elementzero.physics_backends.skyrme_hfb.sensitivity import solve_with_vector

AME1995_RELPATH = "data/amdc/mass_rmd.mas95"

# Nelder-Mead coefficients, the standard values, fixed here so no
# tuning of the optimizer itself can be mistaken for tuning the physics.
ALPHA, GAMMA, RHO, SIGMA = 1.0, 2.0, 0.5, 0.5

FIT_STATUS_CONVERGED = "FIT_CONVERGED"
FIT_STATUS_BUDGET = "FIT_BUDGET_EXHAUSTED"
FIT_STATUS_INFEASIBLE = "FIT_INFEASIBLE_NO_USABLE_EVALUATION"


def calibration_truth(
    *, nuclide_ids: list[str], repo_root: str | Path | None = None
) -> dict[str, float]:
    """Training-era mass excesses for the calibration set, AME1995 only."""
    root = Path(repo_root or REPO_ROOT)
    wanted = set(nuclide_ids)
    truth = {
        o.nuclide_id: o.mass_excess_keV
        for o in load_edition("AME1995", str(root / AME1995_RELPATH))
        if o.ground_truth_eligible and o.nuclide_id in wanted
    }
    missing = sorted(wanted - set(truth))
    if missing:
        raise ProtocolError(
            f"SKYRME_REFIT_CALIBRATION_MISSING: {missing} have no "
            "ground-truth-eligible AME1995 mass; the calibration set must "
            "come entirely from inside the freeze"
        )
    return truth


def _evaluate(
    vector: dict[str, float],
    *,
    nuclide_ids: list[str],
    truth: dict[str, float],
    work_dir: Path,
    repo_root: str | Path | None,
    max_workers: int,
) -> dict[str, Any]:
    """RMS mass-excess residual for one parameter vector."""
    results: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                solve_with_vector,
                nuclide_id=nuclide_id,
                values=vector,
                work_dir=work_dir / nuclide_id,
                repo_root=repo_root,
            ): nuclide_id
            for nuclide_id in nuclide_ids
        }
        for future in concurrent.futures.as_completed(futures):
            results[futures[future]] = future.result()

    residuals: dict[str, float] = {}
    for nuclide_id in nuclide_ids:
        parsed = results[nuclide_id]
        if not parsed["solver_ok"] or parsed["energy_MeV"] is None:
            continue
        z, n = parse_nuclide_id(nuclide_id)
        predicted = mass_excess_keV_from_binding(
            z=z, n=n, binding_MeV=-parsed["energy_MeV"]
        )
        residuals[nuclide_id] = predicted - truth[nuclide_id]

    fraction = len(residuals) / len(nuclide_ids) if nuclide_ids else 0.0
    if fraction < MIN_CONVERGED_FRACTION:
        # Too few solves to judge: infeasible, not "a good score on the
        # handful that happened to work".
        return {
            "objective_keV": INFEASIBLE_PENALTY_KEV,
            "rms_keV": None,
            "n_converged": len(residuals),
            "n_requested": len(nuclide_ids),
            "converged_fraction": fraction,
            "feasible": False,
            "residuals_keV": residuals,
        }
    rms = math.sqrt(sum(r**2 for r in residuals.values()) / len(residuals))
    return {
        "objective_keV": rms,
        "rms_keV": rms,
        "n_converged": len(residuals),
        "n_requested": len(nuclide_ids),
        "converged_fraction": fraction,
        "feasible": True,
        "residuals_keV": residuals,
    }


def _clip(point: list[float], names: list[str]) -> list[float]:
    out = []
    for value, name in zip(point, names, strict=True):
        low, high = PARAMETER_BOUNDS[name]
        out.append(min(max(value, low), high))
    return out


def run_mass_refit(
    *,
    parameters: list[str],
    calibration_ids: list[str],
    work_root: str | Path,
    repo_root: str | Path | None = None,
    max_workers: int = 4,
    max_evaluations: int = MAX_OBJECTIVE_EVALUATIONS,
) -> dict[str, Any]:
    """Nelder-Mead over the frozen subset, inside the frozen budget."""
    if not parameters:
        raise ProtocolError(
            "SKYRME_REFIT_NO_PARAMETERS: the frozen tier is empty; there is "
            "nothing to fit and the baseline stands"
        )
    root = Path(repo_root or REPO_ROOT)
    work_root = Path(work_root)
    truth = calibration_truth(nuclide_ids=calibration_ids, repo_root=root)

    names = list(parameters)
    baseline = [SKYRME_BASELINE_INM[n] for n in names]
    log: list[dict[str, Any]] = []
    cache: dict[tuple[float, ...], float] = {}

    def objective(point: list[float]) -> float:
        key = tuple(round(v, 10) for v in point)
        if key in cache:
            return cache[key]
        if len(log) >= max_evaluations:
            raise _BudgetExhausted
        vector = {**SKYRME_BASELINE_INM, **dict(zip(names, point, strict=True))}
        label = f"eval{len(log):03d}"
        result = _evaluate(
            vector,
            nuclide_ids=calibration_ids,
            truth=truth,
            work_dir=work_root / label,
            repo_root=root,
            max_workers=max_workers,
        )
        log.append(
            {
                "evaluation": len(log),
                "label": label,
                "point": dict(zip(names, point, strict=True)),
                "objective_keV": result["objective_keV"],
                "rms_keV": result["rms_keV"],
                "n_converged": result["n_converged"],
                "converged_fraction": result["converged_fraction"],
                "feasible": result["feasible"],
            }
        )
        cache[key] = result["objective_keV"]
        return result["objective_keV"]

    # Initial simplex: baseline plus one vertex per parameter, stepped by
    # 10% of its box width so the starting spread is set by the declared
    # bounds rather than by a hand-picked number per parameter.
    simplex = [list(baseline)]
    for i, name in enumerate(names):
        low, high = PARAMETER_BOUNDS[name]
        vertex = list(baseline)
        span = 0.10 * (high - low)
        vertex[i] = vertex[i] + span if vertex[i] + span <= high else vertex[i] - span
        simplex.append(_clip(vertex, names))

    status = FIT_STATUS_BUDGET
    try:
        values = [objective(p) for p in simplex]
        while len(log) < max_evaluations:
            order = sorted(range(len(simplex)), key=lambda i: values[i])
            simplex = [simplex[i] for i in order]
            values = [values[i] for i in order]

            centroid = [
                sum(p[i] for p in simplex[:-1]) / (len(simplex) - 1)
                for i in range(len(names))
            ]
            worst = simplex[-1]
            reflected = _clip(
                [c + ALPHA * (c - w) for c, w in zip(centroid, worst, strict=True)],
                names,
            )
            f_reflected = objective(reflected)
            if values[0] <= f_reflected < values[-2]:
                simplex[-1], values[-1] = reflected, f_reflected
                continue
            if f_reflected < values[0]:
                expanded = _clip(
                    [
                        c + GAMMA * (r - c)
                        for c, r in zip(centroid, reflected, strict=True)
                    ],
                    names,
                )
                f_expanded = objective(expanded)
                if f_expanded < f_reflected:
                    simplex[-1], values[-1] = expanded, f_expanded
                else:
                    simplex[-1], values[-1] = reflected, f_reflected
                continue
            contracted = _clip(
                [
                    c + RHO * (w - c)
                    for c, w in zip(centroid, worst, strict=True)
                ],
                names,
            )
            f_contracted = objective(contracted)
            if f_contracted < values[-1]:
                simplex[-1], values[-1] = contracted, f_contracted
                continue
            best = simplex[0]
            for i in range(1, len(simplex)):
                simplex[i] = _clip(
                    [
                        b + SIGMA * (p - b)
                        for b, p in zip(best, simplex[i], strict=True)
                    ],
                    names,
                )
                values[i] = objective(simplex[i])
    except _BudgetExhausted:
        status = FIT_STATUS_BUDGET

    feasible = [row for row in log if row["feasible"]]
    if not feasible:
        best_row = None
        status = FIT_STATUS_INFEASIBLE
    else:
        best_row = min(feasible, key=lambda row: row["objective_keV"])

    baseline_row = log[0] if log else None
    record = {
        "fit_id": "ez-wo15b-skyrme-mass-refit-v1",
        "prereg_id": PREREG_ID,
        "parameters": names,
        "calibration_nuclide_ids": sorted(calibration_ids),
        "n_calibration": len(calibration_ids),
        "max_evaluations": max_evaluations,
        "n_evaluations": len(log),
        "status": status,
        "baseline_objective_keV": baseline_row["objective_keV"] if baseline_row else None,
        "best_objective_keV": best_row["objective_keV"] if best_row else None,
        "best_point": best_row["point"] if best_row else None,
        "improvement_keV": (
            baseline_row["objective_keV"] - best_row["objective_keV"]
            if baseline_row and best_row
            else None
        ),
        "log": log,
        "at_bounds": _at_bounds(best_row["point"]) if best_row else [],
    }
    record["fit_log_hash"] = sha256_hex(canonical_json(log))
    return record


def _at_bounds(point: dict[str, float]) -> list[str]:
    """Parameters resting on their box edge.

    WO-15's pairing fit ended on a bound and the honest response was to
    report it rather than widen the box. Recording it keeps that
    available to the reader instead of buried in the vector.
    """
    resting = []
    for name, value in point.items():
        low, high = PARAMETER_BOUNDS[name]
        span = high - low
        if abs(value - low) < 1e-9 * span or abs(value - high) < 1e-9 * span:
            resting.append(name)
    return sorted(resting)


class _BudgetExhausted(Exception):
    """Raised inside the optimizer when the evaluation budget is spent."""


__all__ = [
    "FIT_STATUS_BUDGET",
    "FIT_STATUS_CONVERGED",
    "FIT_STATUS_INFEASIBLE",
    "calibration_truth",
    "run_mass_refit",
]
