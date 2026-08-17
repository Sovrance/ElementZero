#!/usr/bin/env python3
"""Solve each family over the training-era set and record its residuals.

This is the evidence the discrepancy models learn from, so what may
enter is fenced twice: the identity must be ground-truth-eligible inside
the AME1995 freeze, and it must be absent from every blind holdout. Both
checks live in build_training_set and both raise rather than skip.

Only converged solves contribute. A last iterate parses exactly like a
converged one, and a discrepancy model trained on last iterates would
learn the solver's failure modes and call them physics.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elementzero.data.amdc import load_edition  # noqa: E402
from elementzero.data.identity import NuclideIdentity, parse_nuclide_id  # noqa: E402
from elementzero.evidence.hashing import canonical_json  # noqa: E402
from elementzero.model_discrepancy.dataset import (  # noqa: E402
    AME1995_RELPATH,
    build_training_set,
    excluded_identities,
)
from elementzero.physics.conversion import (  # noqa: E402
    mass_excess_keV_from_binding,
)
from elementzero.physics_backends.adapters.hfbtho import (  # noqa: E402
    _classify,
    gogny_backend,
)
from elementzero.physics_backends.output_parser import parse_hfbtho  # noqa: E402
from elementzero.physics_backends.protocol import SOLVER_OK  # noqa: E402
from elementzero.physics_backends.skyrme_hfb.sensitivity import (  # noqa: E402
    solve_with_vector,
)

READINESS = Path("reports/readiness/wo15b")
CHRONOLOGY = Path("reports/eligibility/wo13/historical_source_chronology.json")

# Compute budget, declared before the campaign runs. The eligible
# training population is far larger than a GP over eight identity
# features needs; the cap takes an even stride through each Z band in
# canonical order so coverage stays broad and the choice stays
# reproducible from identity alone.
TRAINING_CAP = 240
Z_BANDS = ((8, 40), (40, 70), (70, 100), (100, 140))
TRAINING_CAP_RULE = (
    f"ez-wo15b-training-cap-v1: at most {TRAINING_CAP} training nuclides per "
    "family, allocated across Z bands in proportion to the eligible "
    "population and drawn by an even stride in canonical (Z, N) order. A "
    "compute budget fixed before any solve; it consults no model output and "
    "no residual"
)


def _band(z: int) -> str:
    for low, high in Z_BANDS:
        if low <= z < high:
            return f"Z{low}-{high}"
    return f"Z{Z_BANDS[-1][1]}+"


def training_candidates(repo_root: Path) -> list[str]:
    chronology = json.loads(CHRONOLOGY.read_text(encoding="utf-8"))
    eligible = set(chronology["sources"]["AME1995"]["eligible_nuclide_ids"])
    excluded = excluded_identities(repo_root=repo_root)
    forbidden = {i for ids in excluded.values() for i in ids}

    rows = []
    for nuclide_id in sorted(eligible - forbidden):
        z, n = parse_nuclide_id(nuclide_id)
        if z < 8 or z % 2 or n % 2:
            continue
        rows.append((nuclide_id, z, n))
    if len(rows) <= TRAINING_CAP:
        return [r[0] for r in rows]

    by_band: dict[str, list[tuple[str, int, int]]] = {}
    for row in rows:
        by_band.setdefault(_band(row[1]), []).append(row)
    chosen: list[tuple[str, int, int]] = []
    for band in sorted(by_band):
        members = sorted(by_band[band], key=lambda r: (r[1], r[2]))
        share = max(1, round(TRAINING_CAP * len(members) / len(rows)))
        stride = max(1, len(members) // share)
        chosen.extend(members[::stride][:share])
    return [r[0] for r in sorted(chosen, key=lambda r: (r[1], r[2]))]


def _solve_skyrme(args):
    nuclide_id, values, work_root, repo_root = args
    parsed = solve_with_vector(
        nuclide_id=nuclide_id,
        values=values,
        work_dir=Path(work_root) / nuclide_id,
        repo_root=repo_root,
    )
    return nuclide_id, parsed


def _solve_gogny(args):
    nuclide_id, backend, work_root = args
    z, n = parse_nuclide_id(nuclide_id)
    work_dir = Path(work_root) / nuclide_id
    backend.solve_one(
        NuclideIdentity.from_zn(z, n),
        work_dir=work_dir,
        vpair_n=None,
        vpair_p=None,
        shells=backend.base_shells,
    )
    return nuclide_id, parse_hfbtho(work_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True, choices=("skyrme", "gogny"))
    parser.add_argument("--work", default="data/physics_backends/wo15b_training")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    root = Path(".")
    ids = training_candidates(root)
    print(f"{len(ids)} training candidates after cap", flush=True)

    truth = {
        o.nuclide_id: o.mass_excess_keV
        for o in load_edition("AME1995", str(root / AME1995_RELPATH))
        if o.ground_truth_eligible
    }

    work_root = Path(args.work) / args.family
    if args.family == "skyrme":
        artifact = json.loads(
            (READINESS / "parameter_artifact_EZ-PHYS-SKYRME-HFB-v2.json").read_text(
                encoding="utf-8"
            )
        )
        values = dict(
            zip(
                artifact["parameter_names"],
                [float(v) for v in artifact["parameter_values"]],
                strict=True,
            )
        )
        from elementzero.physics_backends.skyrme_hfb import SKYRME_BASELINE_INM

        values = {**SKYRME_BASELINE_INM, **values}
        jobs = [(i, values, work_root, ".") for i in ids]
        worker, family_id = _solve_skyrme, "skyrme_hfb_edf"
        artifact_id = artifact["artifact_id"]
    else:
        backend = gogny_backend(functional="D1S", repo_root=".")
        jobs = [(i, backend, work_root) for i in ids]
        worker, family_id = _solve_gogny, "gogny_finite_range_hfb"
        artifact_id = json.loads(
            (
                Path("reports/physics_backends/wo15/fits")
                / "parameter_artifact_EZ-PHYS-GOGNY-HFB-v1.json"
            ).read_text(encoding="utf-8")
        )["artifact_id"]

    rows, failures = [], 0
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for nuclide_id, parsed in pool.map(worker, jobs):
            done += 1
            status, _ = _classify(parsed)
            if status != SOLVER_OK or parsed.get("energy_MeV") is None:
                failures += 1
            else:
                z, n = parse_nuclide_id(nuclide_id)
                predicted = mass_excess_keV_from_binding(
                    z=z, n=n, binding_MeV=-parsed["energy_MeV"]
                )
                rows.append(
                    {
                        "nuclide_id": nuclide_id,
                        "residual_keV": truth[nuclide_id] - predicted,
                        "solver_status": status,
                        "raw_prediction_keV": predicted,
                        "output_hash": parsed["output_hash"],
                    }
                )
            if done % 20 == 0:
                print(f"  {done}/{len(jobs)} solved, {failures} failed", flush=True)

    chronology = json.loads(CHRONOLOGY.read_text(encoding="utf-8"))
    training = build_training_set(
        family_id=family_id,
        freeze_id="ez-wo15-historical-fit-freeze-v1",
        rows=rows,
        eligible_ids=set(chronology["sources"]["AME1995"]["eligible_nuclide_ids"]),
        excluded=excluded_identities(repo_root=root),
        repo_root=root,
    )
    training["parameter_artifact_id"] = artifact_id
    training["training_cap_rule"] = TRAINING_CAP_RULE
    training["n_requested"] = len(ids)
    training["n_failed_solves"] = failures
    out = READINESS / f"training_set_{family_id}.json"
    out.write_text(canonical_json(training) + "\n", encoding="utf-8")

    residuals = [float(r) for r in training["residuals_keV"]]
    mean = sum(residuals) / len(residuals)
    print(f"kept {training['n_rows']}/{len(ids)} rows, {failures} failed")
    print(f"residual mean {mean:.1f} keV, "
          f"range {min(residuals):.1f} .. {max(residuals):.1f} keV")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
