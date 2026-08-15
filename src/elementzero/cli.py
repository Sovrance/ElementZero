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
from elementzero.evidence.hashing import canonical_json
from elementzero.models.gp_residual import MODEL_ID_SEMF_GP
from elementzero.visuals import DEFAULT_LAYOUT
from elementzero.visuals.build import aggregate_from_events_file, build_visual_table
from elementzero.visuals.ingest import extract_events, write_events_jsonl
from elementzero.visuals.render_html import write_html
from elementzero.visuals.render_svg import write_svg


def _require_benchmark(value: str) -> str:
    if value in {BENCHMARK_EZ_B001, "EZ-B001"}:
        return BENCHMARK_EZ_B001
    raise SystemExit(f"unsupported benchmark {value!r}; new code uses {BENCHMARK_EZ_B001}")


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

    predict = bsub.add_parser("predict", help="blind prediction (no later-truth argument)")
    predict.add_argument("--benchmark", default=BENCHMARK_EZ_B001)
    predict.add_argument("--freeze", required=True)
    predict.add_argument("--targets", required=True)
    predict.add_argument("--training-source", required=True)
    predict.add_argument("--edition", default="AME2003")
    predict.add_argument("--out", required=True)
    predict.add_argument("--model", default=MODEL_ID_SEMF_GP)

    fin = bsub.add_parser("finalize", help="write LEDGER_FINALIZED")
    fin.add_argument("--run", required=True)

    score = bsub.add_parser("score", help="unlock later truth after finalization")
    score.add_argument("--run", required=True)
    score.add_argument("--truth-source", required=True)
    score.add_argument("--edition", default="AME2020")
    score.add_argument("--out", required=True)

    visual = sub.add_parser("visual", help="build the artifact-derived element table")
    vsub = visual.add_subparsers(dest="visual_command", required=True)

    extract = vsub.add_parser("extract-events", help="normalize tests and benchmark artifacts to events")
    extract.add_argument("--input-root", required=True)
    extract.add_argument("--output", default="reports/visuals/element_progress_events.jsonl")

    agg = vsub.add_parser("aggregate", help="aggregate events into element table state")
    agg.add_argument("--events", required=True)
    agg.add_argument("--layout", default=DEFAULT_LAYOUT)
    agg.add_argument("--output", default="reports/visuals/element_table_state.json")

    html = vsub.add_parser("render-html", help="render a self-contained HTML table")
    html.add_argument("--state", required=True)
    html.add_argument("--output", default="reports/visuals/element_table.html")

    svg = vsub.add_parser("render-svg", help="render a deterministic SVG table")
    svg.add_argument("--state", required=True)
    svg.add_argument("--output", default="reports/visuals/element_table.svg")

    build = vsub.add_parser("build", help="extract, aggregate, and render the visual table")
    build.add_argument("--input-root", default=".")
    build.add_argument("--layout", default=DEFAULT_LAYOUT)
    build.add_argument("--output-root", default="reports/visuals/")
    return parser


def _load_state(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _run_visual(args: argparse.Namespace) -> int:
    cmd = args.visual_command
    if cmd == "extract-events":
        events, _health, hashes = extract_events(args.input_root)
        dest = write_events_jsonl(events, args.output)
        print(canonical_json({"events": str(dest), "n_events": len(events), "n_sources": len(hashes)}))
        return 0
    if cmd == "aggregate":
        dest = aggregate_from_events_file(args.events, output=args.output, layout_profile=args.layout)
        print(canonical_json({"state": str(dest)}))
        return 0
    if cmd == "render-html":
        dest = write_html(_load_state(args.state), args.output)
        print(canonical_json({"html": str(dest)}))
        return 0
    if cmd == "render-svg":
        dest = write_svg(_load_state(args.state), args.output)
        print(canonical_json({"svg": str(dest)}))
        return 0
    if cmd == "build":
        result = build_visual_table(
            input_root=args.input_root,
            output_root=args.output_root,
            layout_profile=args.layout,
        )
        print(
            canonical_json(
                {
                    "events": str(result["events"]),
                    "state": str(result["state"]),
                    "html": str(result["html"]),
                    "svg": str(result["svg"]),
                    "n_events": result["n_events"],
                    "test_health": result["test_health"],
                }
            )
        )
        return 0
    raise SystemExit(f"unknown visual command {cmd}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "visual":
        return _run_visual(args)
    if args.command != "benchmark":
        parser.error("only the benchmark and visual commands are implemented")
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
        freeze = freeze_training(
            training_source=args.training_source,
            training_edition_id=args.edition,
            targets_path=args.targets,
            output=args.output,
            benchmark_id=BENCHMARK_EZ_B001,
        )
        print(canonical_json({"freeze_id": freeze.freeze_id, "n_train": len(freeze.training_nuclide_ids)}))
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
    parser.error(f"unknown benchmark command {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
