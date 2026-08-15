"""ElementZero command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from elementzero import BENCHMARK_EZ_B001, BENCHMARK_EZ_B001_TITLE, __version__
from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training, load_freeze
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.benchmark.model_suite import run_suite, score_suite
from elementzero.evidence.hashing import canonical_json
from elementzero.experiments.aggregate import write_aggregate
from elementzero.experiments.epochs import epoch_for
from elementzero.experiments.preregister import (
    validate_preregistration,
    write_preregistration,
)
from elementzero.experiments.runner import (
    replay_experiment,
    score_experiment,
    seal_experiment,
)
from elementzero.models.gp_residual import MODEL_ID_SEMF_GP


def _require_benchmark(value: str) -> str:
    if value in {BENCHMARK_EZ_B001, "EZ-B001"}:
        return BENCHMARK_EZ_B001
    raise SystemExit(f"unsupported benchmark {value!r}; new code uses {BENCHMARK_EZ_B001}")


def _forbidden_source_hashes(args: argparse.Namespace) -> list[str]:
    """Freeze-forbidden hashes from a preregistered protocol and/or the CLI."""
    hashes = list(getattr(args, "forbidden_source_hash", []) or [])
    protocol_path = getattr(args, "protocol", None)
    if protocol_path:
        protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
        hashes.extend(protocol.get("forbidden_source_hashes", []))
    ordered = sorted(set(hashes))
    for value in ordered:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
            raise SystemExit(f"forbidden source hash {value!r} is not a sha256 hex digest")
    return ordered


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="elementzero", description=BENCHMARK_EZ_B001_TITLE)
    parser.add_argument("--version", action="version", version=f"elementzero {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    bench = sub.add_parser("benchmark", help="run EZ-B001 stages")
    bsub = bench.add_subparsers(dest="benchmark_command", required=True)

    prepare = bsub.add_parser("prepare-targets", help="identity-only targets from a later source")
    prepare.add_argument("--benchmark", default=BENCHMARK_EZ_B001)
    prepare.add_argument("--later-source", required=True)
    prepare.add_argument("--edition", default="AME2020")
    prepare.add_argument("--known-source", default=None, help="old edition used only for identity subtraction")
    prepare.add_argument("--known-edition", default="AME2003")
    prepare.add_argument("--output", required=True)

    freeze = bsub.add_parser("freeze", help="build a KnowledgeFreeze from an old source")
    freeze.add_argument("--benchmark", default=BENCHMARK_EZ_B001)
    freeze.add_argument("--training-source", required=True)
    freeze.add_argument("--edition", default="AME2003")
    freeze.add_argument("--targets", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument(
        "--protocol",
        default=None,
        help="preregistered protocol.json; its forbidden_source_hashes enter the freeze",
    )
    freeze.add_argument(
        "--forbidden-source-hash",
        action="append",
        default=[],
        metavar="SHA256",
        help="later-truth source hash the freeze must refuse (repeatable)",
    )

    prereg = bsub.add_parser(
        "preregister",
        help="write an immutable preregistration for a declared epoch",
    )
    prereg.add_argument("--experiment", required=True, help="experiment id, e.g. EZ-B001-A")
    prereg.add_argument("--out", default=None, help="defaults to experiments/<experiment>")
    prereg.add_argument("--training-source", default=None, help="defaults to the declared relpath")
    prereg.add_argument("--truth-source", default=None, help="defaults to the declared relpath")

    validate = bsub.add_parser(
        "validate-preregistration",
        help="recompute the preregistration hash and check every WO-05 gate",
    )
    validate.add_argument("--experiment", required=True, help="experiment directory")

    seal = bsub.add_parser(
        "seal-experiment",
        help="audit, target, freeze, blind-predict, finalize, and seal one epoch (no truth read)",
    )
    seal.add_argument("--experiment", required=True, help="experiment id, e.g. EZ-B001-A")
    seal.add_argument("--dir", default=None, help="defaults to experiments/<experiment>")
    seal.add_argument(
        "--verify",
        action="store_true",
        help="run ruff and pytest first and record the result in environment.json",
    )
    seal.add_argument(
        "--in-process",
        action="store_true",
        help="predict in this process instead of a separate blind-workspace process",
    )

    score_exp = bsub.add_parser(
        "score-experiment",
        help="unlock truth for a sealed epoch, score every model, and compare them",
    )
    score_exp.add_argument("--experiment", required=True, help="experiment id, e.g. EZ-B001-A")
    score_exp.add_argument("--dir", default=None, help="defaults to experiments/<experiment>")

    replay = bsub.add_parser(
        "replay",
        help="recompute metrics from sealed predictions and truth without refitting",
    )
    replay.add_argument("--experiment", required=True, help="experiment id, e.g. EZ-B001-B")
    replay.add_argument("--dir", default=None, help="defaults to experiments/<experiment>")

    aggregate = bsub.add_parser(
        "aggregate",
        help="longitudinal aggregate over every scored epoch of one protocol version",
    )
    aggregate.add_argument("--out", default=None, help="defaults to results/EZ-B001")

    predict = bsub.add_parser("predict", help="blind prediction (no later-truth argument)")
    predict.add_argument("--benchmark", default=BENCHMARK_EZ_B001)
    predict.add_argument("--freeze", required=True)
    predict.add_argument("--targets", required=True)
    predict.add_argument("--training-source", required=True)
    predict.add_argument("--edition", default="AME2003")
    predict.add_argument("--out", required=True)
    predict.add_argument("--model", default=MODEL_ID_SEMF_GP)

    suite_predict = bsub.add_parser(
        "suite-predict",
        help="blind prediction for the frozen three-model suite (one sealed run per model)",
    )
    suite_predict.add_argument("--benchmark", default=BENCHMARK_EZ_B001)
    suite_predict.add_argument("--freeze", required=True)
    suite_predict.add_argument("--targets", required=True)
    suite_predict.add_argument("--training-source", required=True)
    suite_predict.add_argument("--edition", default="AME2003")
    suite_predict.add_argument("--out", required=True, help="suite directory")

    fin = bsub.add_parser("finalize", help="write LEDGER_FINALIZED")
    fin.add_argument("--run", required=True)

    score = bsub.add_parser("score", help="unlock later truth after finalization")
    score.add_argument("--run", required=True)
    score.add_argument("--truth-source", required=True)
    score.add_argument("--edition", default="AME2020")
    score.add_argument("--out", required=True)

    suite_score = bsub.add_parser(
        "suite-score",
        help="score every sealed suite run and write model_comparison.json/.md",
    )
    suite_score.add_argument("--suite", required=True, help="suite directory")
    suite_score.add_argument("--truth-source", required=True)
    suite_score.add_argument("--edition", default="AME2020")
    suite_score.add_argument("--out", default=None, help="defaults to the suite directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "benchmark":
        parser.error("only the benchmark command is implemented in v0.2")
    cmd = args.benchmark_command
    if cmd == "prepare-targets":
        _require_benchmark(args.benchmark)
        manifest = prepare_targets(
            later_source=args.later_source,
            edition_id=args.edition,
            output=args.output,
            benchmark_id=BENCHMARK_EZ_B001,
            known_source=args.known_source,
            known_edition_id=args.known_edition if args.known_source else None,
        )
        print(canonical_json({"benchmark_id": BENCHMARK_EZ_B001, "n_targets": len(manifest["targets"])}))
        return 0
    if cmd == "freeze":
        _require_benchmark(args.benchmark)
        forbidden = _forbidden_source_hashes(args)
        freeze = freeze_training(
            training_source=args.training_source,
            training_edition_id=args.edition,
            targets_path=args.targets,
            output=args.output,
            benchmark_id=BENCHMARK_EZ_B001,
            forbidden_source_hashes=forbidden,
        )
        print(
            canonical_json(
                {
                    "freeze_id": freeze.freeze_id,
                    "n_train": len(freeze.training_nuclide_ids),
                    "forbidden_source_hashes": list(freeze.forbidden_source_hashes),
                }
            )
        )
        return 0
    if cmd == "preregister":
        epoch = epoch_for(args.experiment)
        out = Path(args.out) if args.out else Path("experiments") / epoch.experiment_id
        result = write_preregistration(
            epoch=epoch,
            experiment_dir=out,
            training_source=args.training_source or epoch.training_relpath,
            truth_source=args.truth_source or epoch.truth_relpath,
        )
        report = validate_preregistration(out)
        print(
            canonical_json(
                {
                    "experiment_id": result["experiment_id"],
                    "experiment_dir": result["experiment_dir"],
                    "preregistration_hash": result["preregistration_hash"],
                    "status": report["status"],
                }
            )
        )
        return 0
    if cmd == "validate-preregistration":
        print(canonical_json(validate_preregistration(args.experiment)))
        return 0
    if cmd == "seal-experiment":
        epoch = epoch_for(args.experiment)
        result = seal_experiment(
            epoch=epoch,
            experiment_dir=args.dir,
            verify=args.verify,
            subprocess_prediction=not args.in_process,
        )
        print(
            canonical_json(
                {
                    "experiment_id": epoch.experiment_id,
                    "experiment_dir": result["experiment_dir"],
                    "n_targets": result["n_targets"],
                    "sealed_predictions_sha256": result["sealed_predictions_sha256"],
                    "state": result["sealed"]["state"],
                }
            )
        )
        return 0
    if cmd == "score-experiment":
        epoch = epoch_for(args.experiment)
        result = score_experiment(epoch=epoch, experiment_dir=args.dir)
        print(
            canonical_json(
                {
                    "experiment_id": epoch.experiment_id,
                    "columns": result["comparison"]["columns"],
                    "rows": [
                        {c: row[c] for c in result["comparison"]["columns"]}
                        for row in result["comparison"]["rows"]
                    ],
                }
            )
        )
        return 0
    if cmd == "replay":
        epoch = epoch_for(args.experiment)
        print(canonical_json(replay_experiment(epoch=epoch, experiment_dir=args.dir)))
        return 0
    if cmd == "aggregate":
        result = write_aggregate(out_dir=args.out)
        payload = result["aggregate"]
        print(
            canonical_json(
                {
                    "out_dir": result["out_dir"],
                    "experiment_ids": payload["experiment_ids"],
                    "model_ids": payload["model_ids"],
                    "n_rows": len(payload["rows"]),
                }
            )
        )
        return 0
    if cmd == "predict":
        _require_benchmark(args.benchmark)
        if hasattr(args, "truth_source") or "--truth" in (argv or sys.argv):
            raise SystemExit("predict must not accept a later-truth file argument")
        result = predict_run(
            freeze=load_freeze(args.freeze),
            targets=load_targets(args.targets),
            training_source=args.training_source,
            training_edition_id=args.edition,
            run_dir=args.out,
            model_id=args.model,
        )
        print(canonical_json({"run": result["run_dir"], "n": len(result["predictions"])}))
        return 0
    if cmd == "suite-predict":
        _require_benchmark(args.benchmark)
        if hasattr(args, "truth_source") or "--truth" in (argv or sys.argv):
            raise SystemExit("suite-predict must not accept a later-truth file argument")
        suite = run_suite(
            freeze=load_freeze(args.freeze),
            targets=load_targets(args.targets),
            training_source=args.training_source,
            training_edition_id=args.edition,
            suite_dir=args.out,
        )
        print(
            canonical_json(
                {
                    "model_suite_id": suite["model_suite_id"],
                    "model_ids": suite["model_ids"],
                    "suite_dir": suite["suite_dir"],
                }
            )
        )
        return 0
    if cmd == "finalize":
        marker = finalize(args.run)
        print(canonical_json({"marker": marker["marker"]}))
        return 0
    if cmd == "score":
        report = score_run(
            run_dir=args.run,
            truth_source=args.truth_source,
            truth_edition_id=args.edition,
            out_dir=args.out,
        )
        print(canonical_json({"metrics": report["metrics"]}))
        return 0
    if cmd == "suite-score":
        comparison = score_suite(
            suite_dir=args.suite,
            truth_source=args.truth_source,
            truth_edition_id=args.edition,
            out_dir=args.out,
        )
        print(
            canonical_json(
                {
                    "columns": comparison["columns"],
                    "rows": [
                        {c: row[c] for c in comparison["columns"]} for row in comparison["rows"]
                    ],
                }
            )
        )
        return 0
    parser.error(f"unknown benchmark command {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
