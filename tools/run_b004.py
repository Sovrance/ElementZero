#!/usr/bin/env python3
"""Drive EZ-B004: preregister, seal predictions, then (after a commit) score.

    prereg  build the target manifest, independence adjudications, and the
            hash-sealed PROTOCOL.json — no solver runs, no truth
    seal     run every family over the preregistered targets and write
            SEALED_PREDICTIONS.json — still no truth
    score    verify every governing hash, unlock AME2020, score, adjudicate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elementzero.b004 import (  # noqa: E402
    B004_ID,
    EXPERIMENT_RELPATH,
    RESULTS_RELPATH,
)
from elementzero.b004.adjudication import build_adjudication_records  # noqa: E402
from elementzero.b004.bind import (  # noqa: E402
    PREREG_BINDING_RULE,
    SEAL_BINDING_RULE,
    assert_adjudication_bound,
    assert_target_manifest_bound,
    seal_hash_from_commit,
)
from elementzero.b004.protocol import (  # noqa: E402
    MIN_COVERAGE_FRACTION,
    build_protocol,
)
from elementzero.b004.runs import (  # noqa: E402
    SEALED_FILE,
    predict_family,
    score_b004,
    seal_predictions,
    unlock_truth,
)
from elementzero.b004.targets import select_targets  # noqa: E402
from elementzero.evidence.hashing import canonical_json  # noqa: E402
from elementzero.evidence.ledger import read_json  # noqa: E402
from elementzero.physics_backends import (  # noqa: E402
    BACKEND_COVARIANT,
    BACKEND_GOGNY,
    BACKEND_SKYRME,
)
from elementzero.physics_backends.campaign import FAMILY_PARAMETERIZATION  # noqa: E402
from elementzero.physics_backends.independence import (  # noqa: E402
    count_blind_families,
)

FITS_DIR = Path("reports/physics_backends/wo15/fits")
EXPERIMENT = Path(EXPERIMENT_RELPATH)
RESULTS = Path(RESULTS_RELPATH)


def _load_artifacts() -> dict[str, dict]:
    artifacts = {}
    for backend_id in (BACKEND_SKYRME, BACKEND_GOGNY, BACKEND_COVARIANT):
        path = FITS_DIR / f"parameter_artifact_{backend_id}.json"
        if path.is_file():
            artifacts[backend_id] = read_json(path)
    return artifacts


def cmd_prereg(args: argparse.Namespace) -> int:
    artifacts = _load_artifacts()
    if not artifacts:
        print("no parameter artifacts yet; run tools/run_wo15_fits.py first")
        return 1
    targets = select_targets(repo_root=".")
    adjudications = build_adjudication_records(artifacts)
    gate = count_blind_families(adjudications)
    freeze = read_json(FITS_DIR / "historical_fit_freeze.json")
    protocol = build_protocol(
        freeze_id=freeze["freeze_id"],
        freeze_hash=freeze["freeze_hash"],
        target_manifest=targets,
        parameter_artifacts={
            b: a["artifact_id"] for b, a in sorted(artifacts.items())
        },
        independence_groups=sorted(
            {r["group_id"] for r in adjudications}
        ),
    )
    EXPERIMENT.mkdir(parents=True, exist_ok=True)
    (EXPERIMENT / "PROTOCOL.json").write_text(
        canonical_json(protocol) + "\n", encoding="utf-8"
    )
    (EXPERIMENT / "target_manifest.json").write_text(
        canonical_json(targets) + "\n", encoding="utf-8"
    )
    (EXPERIMENT / "independence_adjudication.json").write_text(
        canonical_json({"records": adjudications, "gate": gate}) + "\n",
        encoding="utf-8",
    )
    print(
        canonical_json(
            {
                "protocol_hash": protocol["protocol_hash"],
                "n_targets": targets["n_targets"],
                "gate": gate["status"],
                "blind_groups": gate["blind_independent_groups"],
            }
        )
    )
    return 0


def cmd_seal(args: argparse.Namespace) -> int:
    protocol = read_json(EXPERIMENT / "PROTOCOL.json")
    targets = read_json(EXPERIMENT / "target_manifest.json")
    artifacts = _load_artifacts()
    families = []
    for backend_id, artifact in sorted(artifacts.items()):
        if backend_id == BACKEND_COVARIANT and args.skip_covariant:
            continue
        print(f"=== predicting {backend_id}", flush=True)
        families.append(
            predict_family(
                backend_id=backend_id,
                functional=FAMILY_PARAMETERIZATION[backend_id],
                artifact=artifact,
                target_ids=targets["target_nuclide_ids"],
                work_root=Path(args.work) / backend_id,
                max_workers=args.workers,
                repo_root=".",
            )
        )
        summary = families[-1]["convergence_summary"]
        print(
            f"    converged {summary['n_converged']}/{summary['n_records']}",
            flush=True,
        )
    sealed = seal_predictions(
        dest=RESULTS,
        protocol=protocol,
        target_manifest=targets,
        families=families,
        artifacts=artifacts,
    )
    print(canonical_json(sealed))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    protocol = read_json(EXPERIMENT / "PROTOCOL.json")
    targets = read_json(EXPERIMENT / "target_manifest.json")
    artifacts = _load_artifacts()
    sealed = read_json(RESULTS / SEALED_FILE)

    # The expected seal hash comes from the committed blob, not from the
    # companion file that sits next to the seal and moves with it.
    seal_hash = seal_hash_from_commit(
        ".", commit=args.seal_commit, relpath=f"{RESULTS.as_posix()}/{SEALED_FILE}"
    )
    assert_target_manifest_bound(
        target_manifest=targets,
        protocol=protocol,
        sealed=sealed,
        recomputed=select_targets(repo_root="."),
    )
    adjudications = read_json(EXPERIMENT / "independence_adjudication.json")
    assert_adjudication_bound(
        adjudication=adjudications,
        protocol=protocol,
        recomputed_records=build_adjudication_records(artifacts),
    )

    unlock_truth(
        dest=RESULTS,
        expected_seal_hash=seal_hash,
        protocol=protocol,
        artifacts=artifacts,
        repo_root=".",
    )
    scores = score_b004(
        dest=RESULTS, protocol=protocol, target_manifest=targets, repo_root="."
    )
    (RESULTS / "b004_scores.json").write_text(
        canonical_json(scores) + "\n", encoding="utf-8"
    )

    blind_backends = {
        r["group_id"]
        for r in adjudications["records"]
        if r["blind_eligible"] and r["independence_verdict"] == "INDEPENDENT"
    }
    qualifying = [
        model
        for model, entry in scores["by_model"].items()
        if entry["physics_family"] in blind_backends
        and float(entry["coverage_fraction"]) >= MIN_COVERAGE_FRACTION
    ]
    families_met = sorted(
        {scores["by_model"][m]["physics_family"] for m in qualifying}
    )
    if len(families_met) >= 2:
        claim = "MULTI_FAMILY_BLIND_EVIDENCE_ESTABLISHED"
    elif len(families_met) == 1:
        claim = "SINGLE_FAMILY_BLIND_EVIDENCE_ONLY"
    else:
        claim = "NO_BLIND_FAMILY_EVIDENCE"
    record = {
        "experiment_id": B004_ID,
        "claim": claim,
        "scientific_scope": "MULTI_FAMILY_HISTORICAL_BLIND_MASS_CHALLENGE",
        "blind_eligible_families_meeting_coverage": families_met,
        "qualifying_backends": sorted(qualifying),
        "min_coverage_fraction": MIN_COVERAGE_FRACTION,
        "criterion": protocol["blind_evidence_criterion"],
        "performance_interpretation": protocol["performance_interpretation"],
        "visual_stage_permission": "BADGE_PB_ONLY_NO_STAGE_PROMOTION",
        "seal_commit": args.seal_commit,
        "seal_hash_from_commit": seal_hash,
        "seal_binding_rule": SEAL_BINDING_RULE,
        "prereg_binding_rule": PREREG_BINDING_RULE,
        "next_gate": (
            "WO-16 known-superheavy historical challenge"
            if claim == "MULTI_FAMILY_BLIND_EVIDENCE_ESTABLISHED"
            else "remain at WO-15"
        ),
    }
    (RESULTS / "claim_adjudication.json").write_text(
        canonical_json({"records": [record]}) + "\n", encoding="utf-8"
    )
    print(canonical_json({"claim": claim, "families": families_met}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prereg")
    seal = sub.add_parser("seal")
    seal.add_argument("--work", default="data/physics_backends/b004work")
    seal.add_argument("--workers", type=int, default=4)
    seal.add_argument("--skip-covariant", action="store_true")
    score = sub.add_parser("score")
    score.add_argument("--seal-commit", required=True)
    args = parser.parse_args()
    return {"prereg": cmd_prereg, "seal": cmd_seal, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
