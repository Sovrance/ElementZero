#!/usr/bin/env python3
"""Run the WO-15 historical refit campaigns and seal their artifacts.

Order is load-bearing: the freeze and the objective are written to disk
before the first solver call, and the parameter artifacts are written
after. Nothing here reads WO-14 truth, B004 truth, or any post-1995
edition.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elementzero.evidence.hashing import canonical_json  # noqa: E402
from elementzero.physics_backends.campaign import (  # noqa: E402
    prepare_campaign,
    refit_family,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/physics_backends/wo15/fits")
    parser.add_argument("--work", default="data/physics_backends/fitwork")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-evaluations", type=int, default=24)
    parser.add_argument(
        "--families",
        default="EZ-PHYS-SKYRME-HFB-v1,EZ-PHYS-GOGNY-HFB-v1",
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    campaign = prepare_campaign(repo_root=".")
    (out / "historical_fit_freeze.json").write_text(
        canonical_json(campaign["freeze"]) + "\n", encoding="utf-8"
    )
    (out / "objective_manifest.json").write_text(
        canonical_json(campaign["objective"]) + "\n", encoding="utf-8"
    )
    print(
        "freeze",
        campaign["freeze"]["freeze_hash"][:16],
        "objective",
        campaign["objective"]["objective_manifest_hash"][:16],
        flush=True,
    )

    for backend_id in args.families.split(","):
        print(f"=== refit {backend_id}", flush=True)
        result = refit_family(
            backend_id=backend_id,
            campaign=campaign,
            work_root=Path(args.work) / backend_id,
            log_path=out / f"fit_log_{backend_id}.json",
            max_workers=args.workers,
            max_evaluations=args.max_evaluations,
            repo_root=".",
        )
        best = result["fit"]["best"]
        print(
            f"{backend_id}: status={result['fit']['status']} "
            f"evals={result['fit']['n_evaluations']} "
            f"rms={best['rms_keV']:.1f} keV "
            f"vpair_n={best['vpair_n']:.2f} vpair_p={best['vpair_p']:.2f}",
            flush=True,
        )
        (out / f"parameter_artifact_{backend_id}.json").write_text(
            canonical_json(result["artifact"]) + "\n", encoding="utf-8"
        )
        (out / f"fit_result_{backend_id}.json").write_text(
            canonical_json(
                {k: v for k, v in result["fit"].items() if k != "evaluations"}
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
