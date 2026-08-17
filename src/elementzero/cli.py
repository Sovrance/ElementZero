"""ElementZero command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from elementzero import (
    BENCHMARK_EZ_B001,
    BENCHMARK_EZ_B001_TITLE,
    BENCHMARK_EZ_B002,
    BENCHMARK_EZ_B003,
    __version__,
)
from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training, load_freeze
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.benchmark.b002_finalize import finalize_region_run
from elementzero.benchmark.b002_freeze import freeze_geographic_split, load_geographic_freeze
from elementzero.benchmark.b002_predict import load_region_targets, run_region_suite
from elementzero.benchmark.b002_prepare import prepare_geographic_split
from elementzero.benchmark.b002_score import score_region_suite
from elementzero.benchmark.b003_finalize import finalize_shell_run
from elementzero.benchmark.b003_freeze import freeze_shell_split, load_shell_freeze
from elementzero.benchmark.b003_predict import load_shell_targets, run_shell_suite
from elementzero.benchmark.b003_prepare import PROFILE_DISCOVERY, PROFILES, prepare_shell_split
from elementzero.benchmark.b003_score import SCOPE_SYNTHETIC, score_shell_suite
from elementzero.benchmark.model_suite import run_suite, score_suite
from elementzero.benchmark.regions import Region
from elementzero.evidence.hashing import canonical_json
from elementzero.experiments.aggregate import write_aggregate
from elementzero.experiments.b002_runner import (
    read_regions,
    score_b002,
    seal_b002,
    select_regions_for_source,
)
from elementzero.experiments.b003_runner import (
    read_challenges,
    score_b003,
    seal_b003,
    select_challenges_for_source,
)
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
from elementzero.reporting.historical import REPORT_DIRNAME, write_report
from elementzero.visuals import DEFAULT_LAYOUT
from elementzero.visuals.build import aggregate_from_events_file, build_visual_table
from elementzero.visuals.ingest import extract_events, write_events_jsonl
from elementzero.visuals.render_html import write_html
from elementzero.visuals.render_svg import write_svg


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

    # ------------------------------------------------------------------ #
    # EZ-B002 geographic nuclear-chart holdout (WO-09)                    #
    # ------------------------------------------------------------------ #

    b002_regions = bsub.add_parser(
        "b002-select-regions",
        help="deterministically select EZ-B002 regions from one snapshot and write regions.json",
    )
    b002_regions.add_argument("--source", required=True, help="frozen mass snapshot")
    b002_regions.add_argument("--edition", default="AME2020")
    b002_regions.add_argument("--output", required=True, help="regions.json to write")
    b002_regions.add_argument("--candidates-output", default=None, help="full candidate report")
    b002_regions.add_argument("--source-relpath", default=None)
    b002_regions.add_argument("--z-span", type=int, default=None)
    b002_regions.add_argument("--n-span", type=int, default=None)
    b002_regions.add_argument("--min-targets", type=int, default=None)
    b002_regions.add_argument("--min-supported-sides", type=int, default=None)
    b002_regions.add_argument("--per-band", type=int, default=None)
    b002_regions.add_argument(
        "--allow-missing-bands",
        action="store_true",
        help="report a band with no candidate instead of refusing (diagnostics only)",
    )

    b002_prepare = bsub.add_parser(
        "b002-prepare",
        help="split one snapshot around one region into identity-only targets plus a split manifest",
    )
    b002_prepare.add_argument("--source", required=True)
    b002_prepare.add_argument("--edition", default="AME2020")
    b002_prepare.add_argument("--regions", required=True, help="preregistered regions.json")
    b002_prepare.add_argument("--region-id", required=True)
    b002_prepare.add_argument("--out", required=True, help="region directory")

    b002_freeze = bsub.add_parser(
        "b002-freeze", help="build the KnowledgeFreeze for one geographic split"
    )
    b002_freeze.add_argument("--source", required=True)
    b002_freeze.add_argument("--edition", default="AME2020")
    b002_freeze.add_argument("--split-manifest", required=True)
    b002_freeze.add_argument("--output", required=True)

    b002_predict = bsub.add_parser(
        "b002-predict",
        help="fit outside one region and predict inside it, one sealed run per model",
    )
    b002_predict.add_argument("--source", required=True)
    b002_predict.add_argument("--edition", default="AME2020")
    b002_predict.add_argument("--freeze", required=True)
    b002_predict.add_argument("--targets", required=True)
    b002_predict.add_argument("--out", required=True, help="suite directory")

    b002_finalize = bsub.add_parser("b002-finalize", help="seal one EZ-B002 region run")
    b002_finalize.add_argument("--run", required=True)

    b002_score = bsub.add_parser(
        "b002-score", help="score every sealed model run of one region and compare them"
    )
    b002_score.add_argument("--suite", required=True, help="region runs directory")
    b002_score.add_argument("--source", required=True, help="the frozen snapshot")
    b002_score.add_argument("--edition", default="AME2020")
    b002_score.add_argument("--out", default=None)

    b002_seal = bsub.add_parser(
        "b002-seal-experiment",
        help="split, freeze, predict, and seal every preregistered region (no region truth read)",
    )
    b002_seal.add_argument("--source", required=True)
    b002_seal.add_argument("--edition", default="AME2020")
    b002_seal.add_argument("--regions", required=True)
    b002_seal.add_argument("--dir", required=True, help="experiment directory")
    b002_seal.add_argument("--created-at", default=None, help="pin timestamps for reproducibility")

    b002_score_exp = bsub.add_parser(
        "b002-score-experiment",
        help="score every sealed region and write the all-region aggregate",
    )
    b002_score_exp.add_argument("--source", required=True)
    b002_score_exp.add_argument("--edition", default="AME2020")
    b002_score_exp.add_argument("--dir", required=True, help="experiment directory")
    b002_score_exp.add_argument("--created-at", default=None)

    # ------------------------------------------------------------------ #
    # EZ-B003 hidden shell rediscovery challenge (WO-10)                   #
    # ------------------------------------------------------------------ #

    b003_challenges = bsub.add_parser(
        "b003-select-challenges",
        help=(
            "apply the availability and support rules to one snapshot and write "
            "challenges.json (every closure, EVALUABLE or NOT_EVALUABLE)"
        ),
    )
    b003_challenges.add_argument("--source", required=True, help="frozen mass snapshot")
    b003_challenges.add_argument("--edition", default="AME2020")
    b003_challenges.add_argument("--output", required=True, help="challenges.json to write")
    b003_challenges.add_argument("--source-relpath", default=None)

    b003_prepare = bsub.add_parser(
        "b003-prepare",
        help="split one snapshot around one hidden closure neighborhood",
    )
    b003_prepare.add_argument("--source", required=True)
    b003_prepare.add_argument("--edition", default="AME2020")
    b003_prepare.add_argument("--challenges", required=True, help="preregistered challenges.json")
    b003_prepare.add_argument("--challenge-id", required=True, help="e.g. neutron-N82")
    b003_prepare.add_argument("--profile", default=PROFILE_DISCOVERY, choices=list(PROFILES))
    b003_prepare.add_argument("--out", required=True, help="challenge directory")

    b003_freeze = bsub.add_parser(
        "b003-freeze", help="build the KnowledgeFreeze for one hidden-shell split"
    )
    b003_freeze.add_argument("--source", required=True)
    b003_freeze.add_argument("--edition", default="AME2020")
    b003_freeze.add_argument("--split-manifest", required=True)
    b003_freeze.add_argument("--output", required=True)

    b003_predict = bsub.add_parser(
        "b003-predict",
        help="fit outside one closure neighborhood and predict inside it, one run per model",
    )
    b003_predict.add_argument("--source", required=True)
    b003_predict.add_argument("--edition", default="AME2020")
    b003_predict.add_argument("--freeze", required=True)
    b003_predict.add_argument("--targets", required=True)
    b003_predict.add_argument("--out", required=True, help="suite directory")

    b003_finalize = bsub.add_parser("b003-finalize", help="seal one EZ-B003 shell run")
    b003_finalize.add_argument("--run", required=True)

    b003_score = bsub.add_parser(
        "b003-score",
        help="score every sealed model run of one closure and compare them",
    )
    b003_score.add_argument("--suite", required=True, help="closure runs directory")
    b003_score.add_argument("--source", required=True, help="the frozen snapshot")
    b003_score.add_argument("--edition", default="AME2020")
    b003_score.add_argument(
        "--scope",
        default=SCOPE_SYNTHETIC,
        help="what is being scored, e.g. synthetic or AME2020; recorded in every verdict",
    )
    b003_score.add_argument("--out", default=None)

    b003_seal = bsub.add_parser(
        "b003-seal-experiment",
        help=(
            "split, freeze, predict, and seal every evaluable closure, and freeze the "
            "rediscovery thresholds (no closure truth read)"
        ),
    )
    b003_seal.add_argument("--source", required=True)
    b003_seal.add_argument("--edition", default="AME2020")
    b003_seal.add_argument("--challenges", required=True)
    b003_seal.add_argument("--dir", required=True, help="experiment directory")
    b003_seal.add_argument("--scope", default=SCOPE_SYNTHETIC)
    b003_seal.add_argument("--profile", default=PROFILE_DISCOVERY, choices=list(PROFILES))
    b003_seal.add_argument("--created-at", default=None, help="pin timestamps for reproducibility")

    b003_score_exp = bsub.add_parser(
        "b003-score-experiment",
        help="score every sealed closure and write the all-closure aggregate",
    )
    b003_score_exp.add_argument("--source", required=True)
    b003_score_exp.add_argument("--edition", default="AME2020")
    b003_score_exp.add_argument("--dir", required=True, help="experiment directory")
    b003_score_exp.add_argument("--created-at", default=None)

    report = sub.add_parser("report", help="build repository reports from committed artifacts")
    rsub = report.add_subparsers(dest="report_command", required=True)

    historical = rsub.add_parser(
        "historical",
        help="build the historical benchmark report over every scored epoch (no refit)",
    )
    historical.add_argument("--out", default=None, help=f"defaults to {REPORT_DIRNAME}")

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
    build.add_argument(
        "--update-readme",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="replace the README visual snapshot (default: yes when --input-root is the repo root)",
    )


    adjudicate = sub.add_parser(
        "adjudicate", help="WO-11 evidence adjudication over the frozen v1 benchmarks"
    )
    asub = adjudicate.add_subparsers(dest="adjudicate_command", required=True)
    wo11 = asub.add_parser(
        "wo11",
        help="full WO-11 pipeline: inventory, replay, diagnostics, controls, "
        "ablations, taxonomy, readiness, report",
    )
    wo11.add_argument("--b002", default=None, help="EZ-B002-v1 experiment dir (informational)")
    wo11.add_argument("--b003", default=None, help="EZ-B003-v1 experiment dir (informational)")
    wo11.add_argument("--output", default=None, help="defaults to reports/adjudication/wo11")
    wo11.add_argument("--workspace", default=None, help="scratch dir (default: temp dir)")
    asub.add_parser("audit", help="WO-11.1 frozen evidence inventory only")
    asub.add_parser("replay", help="WO-11.2 sealed replay only (no refitting)")
    asub.add_parser("diagnose", help="WO-11.4-11.6 diagnostics from sealed predictions")
    asub.add_parser("controls", help="WO-11.7 benchmark oracle controls")
    asub.add_parser("readiness", help="print the committed WO-11 readiness verdict")

    eligibility = sub.add_parser(
        "eligibility", help="WO-13 real-data blindness and claim integrity"
    )
    esub = eligibility.add_subparsers(dest="eligibility_command", required=True)
    esub.add_parser("audit-models", help="model training provenance audit")
    esub.add_parser("build-chronology", help="historical AME source chronology")
    matrix = esub.add_parser("matrix", help="target-by-model eligibility matrix")
    matrix.add_argument("--experiment", required=True)
    subfed = esub.add_parser(
        "subfederation", help="target-specific strict-blind subfederation"
    )
    subfed.add_argument("--experiment", required=True)
    subfed.add_argument("--target", required=True)
    esub.add_parser("report", help="print the committed WO-13 gate status")
    wo13 = esub.add_parser(
        "wo13", help="full WO-13 pipeline: chronology, matrix, subfederations, "
        "claim plans, gate status, report"
    )
    wo13.add_argument("--output", default=None, help="defaults to reports/eligibility/wo13")
    wo13.add_argument("--workspace", default=None, help="scratch dir (default: temp dir)")

    real = sub.add_parser(
        "real-validation", help="WO-14 evaluated-data v2 validation"
    )
    rsub = real.add_subparsers(dest="real_command", required=True)
    seal = rsub.add_parser(
        "seal", help="verify inputs and seal predictions; reads no truth"
    )
    seal.add_argument(
        "--experiment",
        default=None,
        help="one track only (default: all four)",
    )
    record = rsub.add_parser(
        "record-seal-commit",
        help="record the git commit that contains every seal",
    )
    record.add_argument("--commit", required=True)
    rsub.add_parser(
        "score", help="unlock truth (hash-verified), score, adjudicate"
    )
    rsub.add_parser(
        "report", help="build the committed WO-14 report bundle"
    )
    rsub.add_parser("status", help="print the committed WO-14 status")

    physics = sub.add_parser(
        "physics", help="WO-15 refittable physics backends and EZ-B004"
    )
    psub = physics.add_subparsers(dest="physics_command", required=True)
    psub.add_parser(
        "qualify", help="verify solver archives, builds, and golden cases"
    )
    psub.add_parser("provenance", help="print the backend provenance summary")
    psub.add_parser(
        "independence", help="print the committed independence adjudication"
    )
    psub.add_parser("targets", help="print the deterministic B004 target manifest")
    report = psub.add_parser("report", help="rebuild the committed WO-15 bundle")
    report.add_argument("--output", default=None)
    psub.add_parser("status", help="print the committed WO-15 status")
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
            update_readme=args.update_readme,
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


def _adjudicate(args: argparse.Namespace) -> int:
    import tempfile

    from elementzero.adjudication import REPORTS_RELPATH
    from elementzero.adjudication.artifact_audit import build_artifact_inventory, replay_all
    from elementzero.adjudication.benchmark_controls import run_benchmark_controls
    from elementzero.adjudication.diagnostics import build_uncertainty_diagnostics
    from elementzero.adjudication.report import run_wo11
    from elementzero.atlas_pin import REPO_ROOT
    from elementzero.evidence.ledger import read_json

    cmd = args.adjudicate_command
    if cmd == "wo11":
        result = run_wo11(out_dir=args.output, workspace_dir=args.workspace)
        print(canonical_json(result["adjudication"]))
        return 0
    if cmd == "audit":
        inventory = build_artifact_inventory()
        print(
            canonical_json(
                {
                    "all_unchanged": inventory["all_unchanged"],
                    "experiments": sorted(inventory["experiments"]),
                }
            )
        )
        return 0
    if cmd == "replay":
        with tempfile.TemporaryDirectory(prefix="wo11-replay-") as tmp:
            replay = replay_all(workspace_root=tmp)
        print(
            canonical_json(
                {
                    "replay_status": replay["replay_status"],
                    "EZ-B002-v1": replay["EZ-B002-v1"]["replay_status"],
                    "EZ-B003-v1": replay["EZ-B003-v1"]["replay_status"],
                }
            )
        )
        return 0
    if cmd == "diagnose":
        diagnostics = build_uncertainty_diagnostics(
            b002_dir=REPO_ROOT / "experiments" / "EZ-B002-v1",
            b003_dir=REPO_ROOT / "experiments" / "EZ-B003-v1",
        )
        print(
            canonical_json(
                {
                    bench: {
                        model: payload["calibration"]
                        for model, payload in diagnostics[bench]["by_model"].items()
                    }
                    for bench in ("EZ-B002-v1", "EZ-B003-v1")
                }
            )
        )
        return 0
    if cmd == "controls":
        with tempfile.TemporaryDirectory(prefix="wo11-controls-") as tmp:
            controls = run_benchmark_controls(workspace_root=tmp, repo_root=REPO_ROOT)
        print(
            canonical_json(
                {
                    "benchmark_control_status": controls["benchmark_control_status"],
                    "EZ-B002": controls["EZ-B002"]["status"],
                    "EZ-B003": controls["EZ-B003"]["status"],
                }
            )
        )
        return 0
    if cmd == "readiness":
        readiness = read_json(REPO_ROOT / REPORTS_RELPATH / "model_readiness.json")
        print(
            canonical_json(
                {
                    "model_readiness_verdict": readiness["model_readiness_verdict"],
                    "reasons": readiness["reasons"],
                }
            )
        )
        return 0
    raise SystemExit(f"unknown adjudicate command {cmd!r}")


def _eligibility(args: argparse.Namespace) -> int:
    from elementzero.atlas_pin import REPO_ROOT
    from elementzero.eligibility import REPORTS_RELPATH as WO13_REPORTS
    from elementzero.eligibility.historical_sources import build_chronology
    from elementzero.eligibility.model_training_provenance import audit_models
    from elementzero.eligibility.report import run_wo13
    from elementzero.eligibility.subfederation import build_subfederation
    from elementzero.evidence.ledger import read_json

    cmd = args.eligibility_command
    if cmd == "wo13":
        result = run_wo13(out_dir=args.output, workspace_dir=args.workspace)
        print(canonical_json(result))
        return 0
    if cmd == "audit-models":
        manifest = read_json(
            REPO_ROOT / "reports" / "model_federation" / "wo12" / "federation_manifest.json"
        )
        audit = audit_models(registry_manifest=manifest)
        print(canonical_json({"status": audit["status"], "n_models": audit["n_models"]}))
        return 0
    if cmd == "build-chronology":
        chronology = build_chronology()
        print(
            canonical_json(
                {
                    source_id: {
                        "n_known": entry["n_known"],
                        "n_eligible": entry["n_eligible"],
                        "raw_sha256": entry["raw_sha256"],
                    }
                    for source_id, entry in chronology["sources"].items()
                }
            )
        )
        return 0
    if cmd == "matrix":
        matrices = read_json(REPO_ROOT / WO13_REPORTS / "target_eligibility_matrix.json")
        matrix = matrices[args.experiment]
        print(
            canonical_json(
                {
                    "experiment_id": matrix["experiment_id"],
                    "n_targets": matrix["n_targets"],
                    "n_models": matrix["n_models"],
                }
            )
        )
        return 0
    if cmd == "subfederation":
        matrices = read_json(REPO_ROOT / WO13_REPORTS / "target_eligibility_matrix.json")
        entry = build_subfederation(
            target_id=args.target,
            matrix_records=matrices[args.experiment]["records"],
        )
        print(canonical_json(entry))
        return 0
    if cmd == "report":
        status = read_json(REPO_ROOT / WO13_REPORTS / "wo13_gate_status.json")
        print(canonical_json(status))
        return 0
    raise SystemExit(f"unknown eligibility command {cmd!r}")


def _real_validation(args: argparse.Namespace) -> int:
    from elementzero.atlas_pin import REPO_ROOT
    from elementzero.evidence.ledger import read_json
    from elementzero.real_validation import REPORTS_RELPATH as WO14_REPORTS
    from elementzero.real_validation.report import (
        WO14_EXPERIMENTS,
        build_wo14_report,
        record_seal_commit_wo14,
        score_wo14,
        seal_wo14,
    )

    cmd = args.real_command
    if cmd == "seal":
        experiments = (
            (args.experiment,) if args.experiment else WO14_EXPERIMENTS
        )
        result = seal_wo14(experiments=experiments)
        print(canonical_json(result["seals"]))
        return 0
    if cmd == "record-seal-commit":
        result = record_seal_commit_wo14(commit=args.commit)
        print(canonical_json(result))
        return 0
    if cmd == "score":
        result = score_wo14()
        print(canonical_json(result))
        return 0
    if cmd == "report":
        result = build_wo14_report()
        print(canonical_json(result["status"]))
        return 0
    if cmd == "status":
        status = read_json(REPO_ROOT / WO14_REPORTS / "wo14_status.json")
        print(canonical_json(status))
        return 0
    raise SystemExit(f"unknown real-validation command {cmd!r}")


def _physics(args: argparse.Namespace) -> int:
    from elementzero.atlas_pin import REPO_ROOT
    from elementzero.b004.targets import select_targets
    from elementzero.evidence.ledger import read_json
    from elementzero.physics_backends import REPORTS_RELPATH as WO15_REPORTS

    cmd = args.physics_command
    if cmd == "qualify":
        from elementzero.physics_backends.adapters.dirhb import dirhb_backend
        from elementzero.physics_backends.adapters.hfbtho import skyrme_backend

        skyrme = skyrme_backend(functional="SKM*")
        covariant = dirhb_backend(force="DD-ME2")
        print(
            canonical_json(
                {
                    "HFBTHO": skyrme.verify_golden_cases(),
                    "DIRHB": covariant.verify_golden_cases(),
                }
            )
        )
        return 0
    if cmd == "provenance":
        payload = read_json(REPO_ROOT / WO15_REPORTS / "backend_provenance.json")
        print(
            canonical_json(
                {
                    "solvers": sorted(payload["solvers"]),
                    "qualifications": {
                        q["backend_id"]: q["status"]
                        for q in payload["qualifications"]
                    },
                }
            )
        )
        return 0
    if cmd == "independence":
        payload = read_json(
            REPO_ROOT / "experiments/EZ-B004-v1/independence_adjudication.json"
        )
        print(canonical_json(payload["gate"]))
        return 0
    if cmd == "targets":
        manifest = select_targets()
        print(
            canonical_json(
                {
                    "n_targets": manifest["n_targets"],
                    "target_identity_digest": manifest["target_identity_digest"],
                    "strata": manifest["strata"],
                    "evaluable": manifest["evaluable"],
                }
            )
        )
        return 0
    if cmd == "report":
        from elementzero.physics_backends.build_report import build_wo15_report

        result = build_wo15_report(out_dir=args.output)
        print(canonical_json(result["status"]))
        return 0
    if cmd == "status":
        print(canonical_json(read_json(REPO_ROOT / WO15_REPORTS / "wo15_status.json")))
        return 0
    raise SystemExit(f"unknown physics command {cmd!r}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "report":
        if args.report_command == "historical":
            result = write_report(out_dir=args.out)
            payload = result["report"]["metrics"]
            print(
                canonical_json(
                    {
                        "out_dir": result["out_dir"],
                        "report_version": payload["report_version"],
                        "experiment_ids": payload["experiment_ids"],
                        "model_ids": payload["model_ids"],
                        "n_files": len(result["files"]),
                        "n_known_failures": len(payload["known_failures"]),
                    }
                )
            )
            return 0
        parser.error(f"unknown report command {args.report_command}")
        return 2
    if args.command == "visual":
        return _run_visual(args)
    if args.command == "adjudicate":
        return _adjudicate(args)
    if args.command == "eligibility":
        return _eligibility(args)
    if args.command == "real-validation":
        return _real_validation(args)
    if args.command == "physics":
        return _physics(args)
    if args.command != "benchmark":
        parser.error(
            "only the benchmark, report, visual, adjudicate, eligibility, "
            "and real-validation commands are implemented"
        )
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
    if cmd == "b002-select-regions":
        overrides = {
            "z_span": args.z_span,
            "n_span": args.n_span,
            "min_targets": args.min_targets,
            "min_supported_sides": args.min_supported_sides,
            "per_band": args.per_band,
        }
        result = select_regions_for_source(
            source=args.source,
            edition_id=args.edition,
            output=args.output,
            candidates_output=args.candidates_output,
            source_relpath=args.source_relpath,
            allow_missing_bands=args.allow_missing_bands,
            **{k: v for k, v in overrides.items() if v is not None},
        )
        manifest = result["manifest"]
        print(
            canonical_json(
                {
                    "benchmark_id": BENCHMARK_EZ_B002,
                    "n_candidates": result["generated"]["n_candidates"],
                    "region_ids": manifest["region_ids"],
                    "region_manifest_hash": manifest["region_manifest_hash"],
                }
            )
        )
        return 0
    if cmd == "b002-prepare":
        regions = read_regions(args.regions)
        region = _region_by_id(regions, args.region_id)
        result = prepare_geographic_split(
            source=args.source,
            edition_id=args.edition,
            region=region,
            region_manifest_hash=regions["region_manifest_hash"],
            out_dir=args.out,
        )
        manifest = result["split_manifest"]
        print(
            canonical_json(
                {
                    "region_id": manifest["region_id"],
                    "n_targets": manifest["n_targets"],
                    "n_training": manifest["n_training"],
                    "split_digest": manifest["split_digest"],
                }
            )
        )
        return 0
    if cmd == "b002-freeze":
        geographic = freeze_geographic_split(
            source=args.source,
            edition_id=args.edition,
            split_manifest=args.split_manifest,
            output=args.output,
        )
        print(
            canonical_json(
                {
                    "freeze_id": geographic.freeze_id,
                    "region_id": geographic.region_id,
                    "n_train": len(geographic.freeze.training_nuclide_ids),
                    "split_digest": geographic.split_digest,
                }
            )
        )
        return 0
    if cmd == "b002-predict":
        suite = run_region_suite(
            geographic_freeze=load_geographic_freeze(args.freeze),
            targets=load_region_targets(args.targets),
            source=args.source,
            edition_id=args.edition,
            suite_dir=args.out,
        )
        print(
            canonical_json(
                {
                    "model_suite_id": suite["model_suite_id"],
                    "model_ids": suite["model_ids"],
                    "region_id": suite["region_id"],
                    "suite_dir": suite["suite_dir"],
                }
            )
        )
        return 0
    if cmd == "b002-finalize":
        marker = finalize_region_run(args.run)
        print(canonical_json({"marker": marker["marker"], "region_id": marker["region_id"]}))
        return 0
    if cmd == "b002-score":
        comparison = score_region_suite(
            suite_dir=args.suite,
            truth_source=args.source,
            truth_edition_id=args.edition,
            out_dir=args.out,
        )
        print(
            canonical_json(
                {
                    "region_id": comparison["region_id"],
                    "columns": comparison["columns"],
                    "rows": [
                        {c: row[c] for c in comparison["columns"]} for row in comparison["rows"]
                    ],
                }
            )
        )
        return 0
    if cmd == "b002-seal-experiment":
        result = seal_b002(
            source=args.source,
            edition_id=args.edition,
            regions_path=args.regions,
            experiment_dir=args.dir,
            created_at=args.created_at,
        )
        print(
            canonical_json(
                {
                    "experiment_dir": result["experiment_dir"],
                    "region_ids": result["region_ids"],
                    "sealed_predictions_sha256": result["sealed_predictions_sha256"],
                    "state": result["sealed"]["state"],
                }
            )
        )
        return 0
    if cmd == "b002-score-experiment":
        result = score_b002(
            source=args.source,
            edition_id=args.edition,
            experiment_dir=args.dir,
            created_at=args.created_at,
        )
        aggregate = result["aggregate"]
        print(
            canonical_json(
                {
                    "experiment_dir": result["experiment_dir"],
                    "region_ids": aggregate["region_ids"],
                    "model_ids": aggregate["model_ids"],
                    "n_scored_targets": aggregate["n_scored_targets"],
                    "columns": aggregate["columns"],
                    "rows": [
                        {c: row[c] for c in aggregate["columns"]} for row in aggregate["rows"]
                    ],
                }
            )
        )
        return 0
    if cmd == "b003-select-challenges":
        result = select_challenges_for_source(
            source=args.source,
            edition_id=args.edition,
            output=args.output,
            source_relpath=args.source_relpath,
        )
        manifest = result["manifest"]
        print(
            canonical_json(
                {
                    "benchmark_id": BENCHMARK_EZ_B003,
                    "n_challenges": manifest["n_challenges"],
                    "evaluable_challenge_ids": manifest["evaluable_challenge_ids"],
                    "not_evaluable_challenge_ids": manifest["not_evaluable_challenge_ids"],
                    "challenge_manifest_hash": manifest["challenge_manifest_hash"],
                }
            )
        )
        return 0
    if cmd == "b003-prepare":
        challenges = read_challenges(args.challenges)
        mask = _mask_by_challenge_id(challenges, args.challenge_id)
        result = prepare_shell_split(
            source=args.source,
            edition_id=args.edition,
            mask=mask,
            challenge_manifest_hash=challenges["challenge_manifest_hash"],
            out_dir=args.out,
            profile=args.profile,
        )
        manifest = result["split_manifest"]
        print(
            canonical_json(
                {
                    "challenge_id": manifest["challenge_id"],
                    "mask_id": manifest["mask_id"],
                    "profile": manifest["profile"],
                    "n_targets": manifest["n_targets"],
                    "n_training": manifest["n_training"],
                    "n_supported_chains": manifest["n_supported_chains"],
                    "split_digest": manifest["split_digest"],
                }
            )
        )
        return 0
    if cmd == "b003-freeze":
        shell = freeze_shell_split(
            source=args.source,
            edition_id=args.edition,
            split_manifest=args.split_manifest,
            output=args.output,
        )
        print(
            canonical_json(
                {
                    "freeze_id": shell.freeze_id,
                    "challenge_id": shell.challenge_id,
                    "mask_id": shell.mask_id,
                    "profile": shell.profile,
                    "n_train": len(shell.freeze.training_nuclide_ids),
                    "split_digest": shell.split_digest,
                }
            )
        )
        return 0
    if cmd == "b003-predict":
        suite = run_shell_suite(
            shell_freeze=load_shell_freeze(args.freeze),
            targets=load_shell_targets(args.targets),
            source=args.source,
            edition_id=args.edition,
            suite_dir=args.out,
        )
        print(
            canonical_json(
                {
                    "model_suite_id": suite["model_suite_id"],
                    "model_ids": suite["model_ids"],
                    "challenge_id": suite["challenge_id"],
                    "mask_id": suite["mask_id"],
                    "suite_dir": suite["suite_dir"],
                }
            )
        )
        return 0
    if cmd == "b003-finalize":
        marker = finalize_shell_run(args.run)
        print(
            canonical_json(
                {
                    "marker": marker["marker"],
                    "challenge_id": marker["challenge_id"],
                    "mask_id": marker["mask_id"],
                }
            )
        )
        return 0
    if cmd == "b003-score":
        comparison = score_shell_suite(
            suite_dir=args.suite,
            truth_source=args.source,
            truth_edition_id=args.edition,
            scope=args.scope,
            out_dir=args.out,
        )
        print(
            canonical_json(
                {
                    "challenge_id": comparison["challenge_id"],
                    "scope": comparison["scope"],
                    "columns": comparison["columns"],
                    "rows": [
                        {c: row[c] for c in comparison["columns"]} for row in comparison["rows"]
                    ],
                }
            )
        )
        return 0
    if cmd == "b003-seal-experiment":
        result = seal_b003(
            source=args.source,
            edition_id=args.edition,
            challenges_path=args.challenges,
            experiment_dir=args.dir,
            scope=args.scope,
            profile=args.profile,
            created_at=args.created_at,
        )
        print(
            canonical_json(
                {
                    "experiment_dir": result["experiment_dir"],
                    "challenge_ids": result["challenge_ids"],
                    "not_evaluable_challenge_ids": result["sealed"][
                        "not_evaluable_challenge_ids"
                    ],
                    "criterion_sha256": result["sealed"]["criterion_sha256"],
                    "sealed_predictions_sha256": result["sealed_predictions_sha256"],
                    "state": result["sealed"]["state"],
                }
            )
        )
        return 0
    if cmd == "b003-score-experiment":
        result = score_b003(
            source=args.source,
            edition_id=args.edition,
            experiment_dir=args.dir,
            created_at=args.created_at,
        )
        aggregate = result["aggregate"]
        print(
            canonical_json(
                {
                    "experiment_dir": result["experiment_dir"],
                    "scope": aggregate["scope"],
                    "challenge_ids": aggregate["challenge_ids"],
                    "not_evaluable_closures": [
                        entry["challenge_id"] for entry in aggregate["not_evaluable_closures"]
                    ],
                    "model_ids": aggregate["model_ids"],
                    "n_scored_targets": aggregate["n_scored_targets"],
                    "verdicts": {
                        model_id: aggregate["by_model"][model_id]["criterion"]["verdict"]
                        for model_id in aggregate["model_ids"]
                    },
                    "columns": aggregate["columns"],
                    "rows": [
                        {c: row[c] for c in aggregate["columns"]} for row in aggregate["rows"]
                    ],
                }
            )
        )
        return 0
    parser.error(f"unknown benchmark command {cmd}")
    return 2


def _mask_by_challenge_id(challenges: dict, challenge_id: str):
    masks = challenges["masks"]
    if challenge_id in masks:
        return masks[challenge_id]
    known = sorted(masks)
    raise SystemExit(
        f"challenge {challenge_id!r} has no mask; evaluable challenges are {known}"
    )


def _region_by_id(regions: dict, region_id: str) -> Region:
    for region in regions["regions"]:
        if region.region_id == region_id:
            return region
    known = [r.region_id for r in regions["regions"]]
    raise SystemExit(f"region {region_id!r} is not in the manifest; declared regions are {known}")


if __name__ == "__main__":
    raise SystemExit(main())
