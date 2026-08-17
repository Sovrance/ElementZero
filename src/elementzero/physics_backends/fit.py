"""The historical refit driver (WO-15 HISTORICAL_REFIT_CONTRACT).

What is being fitted, precisely: the pairing strengths (V_n, V_p) of a
pre-freeze published EDF, against training-era masses only. The bulk EDF
stays at its published historical values; ElementZero controls, records,
and can reproduce the pairing sector end to end.

That is a deliberately modest scope, and it is stated rather than
dressed up: a full EDF reoptimization is a supercomputer campaign. What
this earns is real — exact calibration membership, a locked objective, a
recorded optimizer path, and an immutable artifact — which is what
REFIT_STRICT means.
"""

from __future__ import annotations

import concurrent.futures
import shutil
from pathlib import Path
from typing import Any

from elementzero.data.identity import NuclideIdentity, parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.physics.conversion import mass_excess_keV_from_binding
from elementzero.physics_backends.objective import (
    INFEASIBLE_OBJECTIVE,
    MIN_CONVERGED_FRACTION,
    assert_objective_locked,
)
from elementzero.physics_backends.output_parser import parse_hfbtho

OPTIMIZER_ID = "ez-wo15-neldermead-pairing-v1"
OPTIMIZER_VERSION = "elementzero-internal-1"

# Preregistered optimizer settings. Fixed before the first solve, and
# identical for every family so no family gets a longer search.
MAX_EVALUATIONS = 24
INITIAL_SIMPLEX = (
    (-250.0, -250.0),
    (-290.0, -250.0),
    (-250.0, -290.0),
)
PARAMETER_BOUNDS = ((-420.0, -140.0), (-420.0, -140.0))
XTOL_KEV = 2.0

OPTIMIZER_RULE = (
    f"{OPTIMIZER_ID}: Nelder-Mead over (vpair_n, vpair_p) with the initial "
    f"simplex {INITIAL_SIMPLEX}, box bounds {PARAMETER_BOUNDS}, at most "
    f"{MAX_EVALUATIONS} objective evaluations, and no early stopping on any "
    "post-freeze signal. Every setting here was frozen before the first "
    "solver call; the optimizer path is logged in full"
)

NO_POST_FREEZE_SIGNAL_RULE = (
    "ez-wo15-no-post-freeze-signal-v1: the objective consumes AME1995 "
    "masses only. WO-14 target truth, WO-14 residual tables, B004 truth, "
    "and every post-1995 edition are absent from this process — not "
    "down-weighted, absent"
)


def _solve_worker(args) -> tuple[str, dict[str, Any]]:
    backend, nuclide_id, work_dir, vpair_n, vpair_p = args
    z, n = parse_nuclide_id(nuclide_id)
    backend.solve_one(
        NuclideIdentity.from_zn(z, n),
        work_dir=work_dir,
        vpair_n=vpair_n,
        vpair_p=vpair_p,
    )
    return nuclide_id, parse_hfbtho(work_dir)


def evaluate_objective(
    *,
    backend,
    calibration: dict[str, float],
    vpair_n: float,
    vpair_p: float,
    work_root: Path,
    max_workers: int = 2,
) -> dict[str, Any]:
    """RMS mass residual over the calibration set for one parameter vector."""
    tag = f"vn{vpair_n:+.3f}_vp{vpair_p:+.3f}".replace(".", "p")
    eval_dir = work_root / tag
    if eval_dir.exists():
        shutil.rmtree(eval_dir)
    jobs = [
        (backend, nuclide_id, eval_dir / nuclide_id, vpair_n, vpair_p)
        for nuclide_id in sorted(calibration)
    ]
    residuals: dict[str, float] = {}
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for nuclide_id, parsed in pool.map(_solve_worker, jobs):
            z, n = parse_nuclide_id(nuclide_id)
            if not parsed["solver_ok"] or parsed["energy_MeV"] is None:
                failures.append(nuclide_id)
                continue
            computed = mass_excess_keV_from_binding(
                z=z, n=n, binding_MeV=-parsed["energy_MeV"]
            )
            residuals[nuclide_id] = computed - calibration[nuclide_id]

    n_total = len(calibration)
    converged_fraction = len(residuals) / n_total if n_total else 0.0
    if converged_fraction < MIN_CONVERGED_FRACTION:
        value = INFEASIBLE_OBJECTIVE
    else:
        value = (sum(r * r for r in residuals.values()) / len(residuals)) ** 0.5
    # The scratch tree is large and reproducible from the log; keep the
    # evidence (residuals, statuses) and drop the bulk output.
    shutil.rmtree(eval_dir, ignore_errors=True)
    return {
        "vpair_n": vpair_n,
        "vpair_p": vpair_p,
        "objective": value,
        "rms_keV": value if value < INFEASIBLE_OBJECTIVE else None,
        "n_converged": len(residuals),
        "n_calibration": n_total,
        "converged_fraction": converged_fraction,
        "nonconverged_ids": sorted(failures),
        "residuals_keV": dict(sorted(residuals.items())),
    }


def _clip(point: tuple[float, float]) -> tuple[float, float]:
    return tuple(
        min(max(v, lo), hi) for v, (lo, hi) in zip(point, PARAMETER_BOUNDS, strict=True)
    )


def run_refit(
    *,
    backend,
    calibration: dict[str, float],
    objective_manifest: dict[str, Any],
    work_root: str | Path,
    max_evaluations: int = MAX_EVALUATIONS,
    max_workers: int = 2,
    log_path: str | Path | None = None,
) -> dict[str, Any]:
    """Nelder-Mead over the pairing sector; the full path is the evidence."""
    assert_objective_locked(
        objective_manifest,
        expected_hash=objective_manifest["objective_manifest_hash"],
    )
    if sorted(calibration) != sorted(objective_manifest["calibration_nuclide_ids"]):
        raise ProtocolError(
            "HISTORICAL_FIT_INTEGRITY_FAILURE: the calibration set handed to "
            "the optimizer is not the set the objective locked"
        )
    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    history: list[dict[str, Any]] = []
    cache: dict[tuple[float, float], dict[str, Any]] = {}

    def f(point: tuple[float, float]) -> float:
        key = (round(point[0], 4), round(point[1], 4))
        if key in cache:
            return cache[key]["objective"]
        if len(history) >= max_evaluations:
            return INFEASIBLE_OBJECTIVE
        record = evaluate_objective(
            backend=backend,
            calibration=calibration,
            vpair_n=key[0],
            vpair_p=key[1],
            work_root=work_root,
            max_workers=max_workers,
        )
        record["evaluation_index"] = len(history)
        cache[key] = record
        history.append(record)
        if log_path is not None:
            Path(log_path).write_text(
                canonical_json({"evaluations": history}) + "\n", encoding="utf-8"
            )
        return record["objective"]

    # Textbook Nelder-Mead, written out so the path is auditable rather
    # than delegated to a library whose defaults could drift.
    simplex = [_clip(p) for p in INITIAL_SIMPLEX]
    values = [f(p) for p in simplex]
    while len(history) < max_evaluations:
        order = sorted(range(len(simplex)), key=lambda i: values[i])
        simplex = [simplex[i] for i in order]
        values = [values[i] for i in order]
        spread = max(
            abs(a - b)
            for best, worst in ((simplex[0], simplex[-1]),)
            for a, b in zip(best, worst, strict=True)
        )
        if spread < XTOL_KEV:
            break
        centroid = tuple(
            sum(p[i] for p in simplex[:-1]) / (len(simplex) - 1) for i in range(2)
        )
        worst = simplex[-1]
        reflected = _clip(tuple(c + (c - w) for c, w in zip(centroid, worst, strict=True)))
        f_reflected = f(reflected)
        if f_reflected < values[0]:
            expanded = _clip(
                tuple(c + 2.0 * (c - w) for c, w in zip(centroid, worst, strict=True))
            )
            f_expanded = f(expanded)
            simplex[-1], values[-1] = (
                (expanded, f_expanded)
                if f_expanded < f_reflected
                else (reflected, f_reflected)
            )
        elif f_reflected < values[-2]:
            simplex[-1], values[-1] = reflected, f_reflected
        else:
            contracted = _clip(
                tuple(c + 0.5 * (w - c) for c, w in zip(centroid, worst, strict=True))
            )
            f_contracted = f(contracted)
            if f_contracted < values[-1]:
                simplex[-1], values[-1] = contracted, f_contracted
            else:
                for i in range(1, len(simplex)):
                    simplex[i] = _clip(
                        tuple(
                            b + 0.5 * (p - b)
                            for b, p in zip(simplex[0], simplex[i], strict=True)
                        )
                    )
                    values[i] = f(simplex[i])

    feasible = [h for h in history if h["objective"] < INFEASIBLE_OBJECTIVE]
    if not feasible:
        return {
            "status": "FIT_INFEASIBLE",
            "optimizer_id": OPTIMIZER_ID,
            "optimizer_rule": OPTIMIZER_RULE,
            "n_evaluations": len(history),
            "evaluations": history,
            "best": None,
            "fit_log_hash": sha256_hex({"evaluations": history}),
        }
    best = min(feasible, key=lambda h: h["objective"])
    return {
        "status": "FIT_CONVERGED" if len(history) < max_evaluations else "FIT_BUDGET_EXHAUSTED",
        "optimizer_id": OPTIMIZER_ID,
        "optimizer_version": OPTIMIZER_VERSION,
        "optimizer_rule": OPTIMIZER_RULE,
        "no_post_freeze_signal_rule": NO_POST_FREEZE_SIGNAL_RULE,
        "n_evaluations": len(history),
        "evaluations": history,
        "best": best,
        "calibration_identity_digest": identity_digest(sorted(calibration)),
        "fit_log_hash": sha256_hex({"evaluations": history}),
    }
