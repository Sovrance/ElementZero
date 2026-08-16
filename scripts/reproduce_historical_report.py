#!/usr/bin/env python3
"""Reproduce and verify the ElementZero Historical Benchmark Report v1 (WO-08 section 7).

    python scripts/reproduce_historical_report.py

Steps, in order:

    1. verify hashes        every committed epoch artifact against its SHA256SUMS.txt,
                            plus the preregistration hash and the protocol code digest
    2. replay scoring       metrics recomputed from the sealed predictions and the raw
                            truth table, without refitting anything
    3. rebuild aggregate    results/EZ-B001/aggregate_v1.json rebuilt from the committed
                            per-epoch comparisons
    4. rebuild report       tables and figures rebuilt into a scratch directory and
                            compared with the committed report, file by file
    5. verify report hashes reports/historical/v1/SHA256SUMS.txt against the committed
                            files and against the rebuild

No model is refit unless ``--refit`` is passed. A refit never writes into
``experiments/``: it seals and scores a copy of the preregistration in a scratch
directory and compares the recomputed metric content hashes with the committed
ones. Step 2 needs the raw AME tables, which are gitignored; without them it
reports itself as skipped instead of quietly passing.

Exit code 0 means every executed step passed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from elementzero.benchmark.model_suite import COMPARISON_JSON_NAME  # noqa: E402
from elementzero.evidence.hashing import canonical_json  # noqa: E402
from elementzero.evidence.ledger import read_json  # noqa: E402
from elementzero.experiments.aggregate import (  # noqa: E402
    AGGREGATE_DIRNAME,
    AGGREGATE_JSON,
    build_aggregate,
    experiment_dirs,
)
from elementzero.experiments.epochs import EPOCH_ORDER, epoch_for  # noqa: E402
from elementzero.experiments.preregister import (  # noqa: E402
    PREREGISTRATION_FILES,
    PREREGISTRATION_HASH_FILE,
    PREREGISTRATION_MARKDOWN,
    assert_protocol_code_unchanged,
    validate_preregistration,
)
from elementzero.experiments.runner import (  # noqa: E402
    SCORE_MANIFEST_FILE,
    replay_experiment,
    score_experiment,
    seal_experiment,
    verify_sha256sums,
)
from elementzero.reporting.historical import (  # noqa: E402
    REPORT_DIRNAME,
    SHA256SUMS_FILE,
    build_report,
    compare_to_committed,
    verify_report_hashes,
    write_report,
)

STEP_PASS = "pass"
STEP_FAIL = "fail"
STEP_SKIPPED = "skipped"
STEP_NOT_EXECUTED = "not_executed"


def _status(ok: bool) -> str:
    return STEP_PASS if ok else STEP_FAIL


def verify_committed_artifacts(root: Path) -> dict[str, Any]:
    """Preregistration hash, protocol code digest, and artifact hashes per epoch."""
    epochs = []
    for experiment_id in EPOCH_ORDER:
        experiment_dir = root / "experiments" / experiment_id
        if not experiment_dir.is_dir():
            epochs.append({"experiment_id": experiment_id, "status": STEP_FAIL, "reason": "missing"})
            continue
        report = validate_preregistration(experiment_dir, root=root)
        digest = assert_protocol_code_unchanged(experiment_dir, root=root)
        hashes = verify_sha256sums(experiment_dir)
        epochs.append(
            {
                "experiment_id": experiment_id,
                "preregistration_status": report["status"],
                "protocol_code_matches": report["protocol_code_matches"],
                "protocol_code_digest": digest,
                "n_files": hashes["n_files"],
                "missing": hashes["missing"],
                "changed": hashes["changed"],
                "extra": hashes["extra"],
                "status": _status(hashes["ok"] and report["protocol_code_matches"]),
            }
        )
    return {
        "step": "verify_hashes",
        "epochs": epochs,
        "status": _status(bool(epochs) and all(e["status"] == STEP_PASS for e in epochs)),
    }


def replay_scoring(root: Path) -> dict[str, Any]:
    """Recompute metrics from the sealed predictions; never refit."""
    epochs = []
    for experiment_id in EPOCH_ORDER:
        experiment_dir = root / "experiments" / experiment_id
        epoch = epoch_for(experiment_id)
        truth_source = root / epoch.truth_relpath
        if not (experiment_dir / COMPARISON_JSON_NAME).is_file():
            epochs.append({"experiment_id": experiment_id, "status": STEP_FAIL, "reason": "not scored"})
            continue
        if not truth_source.is_file():
            epochs.append(
                {
                    "experiment_id": experiment_id,
                    "status": STEP_SKIPPED,
                    "reason": f"{epoch.truth_relpath} is not present in this checkout",
                }
            )
            continue
        replay = replay_experiment(epoch=epoch, experiment_dir=experiment_dir, root=root)
        epochs.append(
            {
                "experiment_id": experiment_id,
                "refit": replay["refit"],
                "models": [
                    {"model_id": m["model_id"], "matches": m["matches"]} for m in replay["models"]
                ],
                "status": _status(all(m["matches"] for m in replay["models"])),
            }
        )
    executed = [e for e in epochs if e["status"] != STEP_SKIPPED]
    if not executed:
        status = STEP_SKIPPED
    else:
        status = _status(all(e["status"] == STEP_PASS for e in executed))
    return {"step": "replay_scoring", "refit": False, "epochs": epochs, "status": status}


def rebuild_aggregate(root: Path) -> dict[str, Any]:
    """Rebuild the longitudinal aggregate from the committed comparisons."""
    relpath = f"{AGGREGATE_DIRNAME}/{AGGREGATE_JSON}"
    committed = root / relpath
    rebuilt = canonical_json(build_aggregate(experiment_dirs(root))) + "\n"
    matches = committed.is_file() and committed.read_text(encoding="utf-8") == rebuilt
    return {
        "step": "rebuild_aggregate",
        "path": relpath,
        "matches_committed": matches,
        "status": _status(matches),
    }


def rebuild_report(root: Path, *, out_dir: Path) -> dict[str, Any]:
    """Rebuild the report tree and diff it against the committed one."""
    report = build_report(root=root)
    written = write_report(out_dir=out_dir, root=root, report=report)
    diff = compare_to_committed(root=root, report=report)
    committed_dir = root / REPORT_DIRNAME
    hashes: dict[str, Any] = {"status": STEP_FAIL, "reason": f"{REPORT_DIRNAME} is missing"}
    manifest_matches = False
    if committed_dir.is_dir():
        hashes = verify_report_hashes(committed_dir)
        committed_manifest = committed_dir / SHA256SUMS_FILE
        manifest_matches = (
            committed_manifest.is_file()
            and committed_manifest.read_text(encoding="utf-8") == written["sha256sums"]
        )
    ok = bool(diff["ok"] and hashes.get("ok") and manifest_matches)
    return {
        "step": "rebuild_report",
        "rebuilt_in": str(out_dir),
        "n_files": len(written["files"]),
        "missing": diff["missing"],
        "differing": diff["differing"],
        "extra": diff["extra"],
        "committed_hashes": {
            "n_files": hashes.get("n_files"),
            "missing": hashes.get("missing"),
            "changed": hashes.get("changed"),
            "extra": hashes.get("extra"),
            "ok": hashes.get("ok"),
        },
        "sha256sums_matches_rebuild": manifest_matches,
        "status": _status(ok),
    }


def refit_epoch(*, root: Path, experiment_id: str, scratch: Path) -> dict[str, Any]:
    """Seal and score a copy of one preregistration, then compare metric hashes.

    The committed experiment directory is never touched: a refit that could
    overwrite a sealed run would destroy the evidence it is supposed to check.
    """
    epoch = epoch_for(experiment_id)
    source = root / "experiments" / experiment_id
    dest = scratch / experiment_id
    dest.mkdir(parents=True, exist_ok=True)
    for name in (*PREREGISTRATION_FILES, PREREGISTRATION_HASH_FILE, PREREGISTRATION_MARKDOWN):
        shutil.copyfile(source / name, dest / name)
    seal_experiment(epoch=epoch, experiment_dir=dest, root=root, subprocess_prediction=False)
    scored = score_experiment(epoch=epoch, experiment_dir=dest, root=root)
    committed = {m["model_id"]: m for m in read_json(source / SCORE_MANIFEST_FILE)["models"]}
    refit = {m["model_id"]: m for m in scored["score_manifest"]["models"]}
    models = [
        {
            "model_id": model_id,
            "committed_metrics_content_hash": committed[model_id]["metrics_content_hash"],
            "refit_metrics_content_hash": refit[model_id]["metrics_content_hash"],
            "matches": committed[model_id]["metrics_content_hash"]
            == refit[model_id]["metrics_content_hash"],
        }
        for model_id in sorted(committed)
    ]
    return {
        "experiment_id": experiment_id,
        "refit_dir": str(dest),
        "models": models,
        "status": _status(all(m["matches"] for m in models)),
    }


def refit_series(root: Path, *, scratch: Path) -> dict[str, Any]:
    epochs = []
    for experiment_id in EPOCH_ORDER:
        epoch = epoch_for(experiment_id)
        if not (root / epoch.training_relpath).is_file() or not (root / epoch.truth_relpath).is_file():
            epochs.append(
                {
                    "experiment_id": experiment_id,
                    "status": STEP_SKIPPED,
                    "reason": "raw AME tables are not present in this checkout",
                }
            )
            continue
        epochs.append(refit_epoch(root=root, experiment_id=experiment_id, scratch=scratch))
    executed = [e for e in epochs if e["status"] != STEP_SKIPPED]
    status = STEP_SKIPPED if not executed else _status(all(e["status"] == STEP_PASS for e in executed))
    return {
        "step": "refit",
        "refit": True,
        "note": "models were refit in a scratch directory; experiments/ was not written",
        "epochs": epochs,
        "status": status,
    }


def reproduce(
    *,
    root: str | Path | None = None,
    refit: bool = False,
    out_dir: str | Path | None = None,
    replay: bool = True,
) -> dict[str, Any]:
    """Run the verification pipeline and return one machine-readable summary."""
    base = Path(root or REPO_ROOT)
    steps: list[dict[str, Any]] = [verify_committed_artifacts(base)]
    if replay:
        steps.append(replay_scoring(base))
    else:
        steps.append({"step": "replay_scoring", "refit": False, "status": STEP_NOT_EXECUTED})
    steps.append(rebuild_aggregate(base))

    scratch: tempfile.TemporaryDirectory[str] | None = None
    if out_dir is None:
        scratch = tempfile.TemporaryDirectory(prefix="ez-report-rebuild-")
        report_out = Path(scratch.name) / "report"
    else:
        report_out = Path(out_dir)
    try:
        steps.append(rebuild_report(base, out_dir=report_out))
        if refit:
            with tempfile.TemporaryDirectory(prefix="ez-refit-") as refit_scratch:
                steps.append(refit_series(base, scratch=Path(refit_scratch)))
        else:
            steps.append(
                {
                    "step": "refit",
                    "refit": False,
                    "status": STEP_NOT_EXECUTED,
                    "note": "no model was refit; pass --refit to fit into a scratch directory",
                }
            )
    finally:
        if scratch is not None:
            scratch.cleanup()

    failed = [s["step"] for s in steps if s["status"] == STEP_FAIL]
    return {
        "root": str(base),
        "report_dir": REPORT_DIRNAME,
        "refit": refit,
        "steps": steps,
        "failed_steps": failed,
        "status": _status(not failed),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reproduce_historical_report.py",
        description=__doc__.splitlines()[0],
    )
    parser.add_argument("--root", default=None, help="repository root; defaults to this checkout")
    parser.add_argument(
        "--out",
        default=None,
        help="directory to rebuild the report into; defaults to a temporary directory",
    )
    parser.add_argument(
        "--refit",
        action="store_true",
        default=False,
        help=(
            "also refit every model in a scratch directory and compare metric hashes; "
            "without this flag nothing is refit"
        ),
    )
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        default=False,
        help="skip the scoring replay even when the raw AME tables are present",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = reproduce(
        root=args.root,
        refit=args.refit,
        out_dir=args.out,
        replay=not args.skip_replay,
    )
    print(canonical_json(summary))
    return 0 if summary["status"] == STEP_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
