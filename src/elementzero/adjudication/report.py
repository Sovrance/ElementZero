"""WO-11 report assembly.

``run_wo11`` executes the whole adjudication in the required order —
inventory, replay, diagnostics, controls, ablations, taxonomy, readiness,
registry — and writes every committed artifact under
``reports/adjudication/wo11/``:

    README.md
    artifact_inventory.json
    replay_verification.json
    uncertainty_diagnostics.json
    benchmark_controls.json
    ablation_matrix.json
    failure_records.json
    model_readiness.json
    frontier_model_candidates.json
    wo11_adjudication_report.json      (validates the adjudication schema)
    WO11_Evidence_Adjudication_Report.md
    SHA256SUMS.txt

Every artifact is deterministic: rebuilding the bundle from the same frozen
baseline yields the same bytes, which is what
``tests/integration/test_wo11_report_reproducible.py`` asserts.

If the sealed replay fails, the pipeline records INFRASTRUCTURE_REPAIR_REQUIRED
and stops before any scientific diagnosis, per WO-11.2.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from elementzero.adjudication import INPUT_RELEASE, REPORTS_RELPATH, WO11_ID
from elementzero.adjudication.ablations import write_ablation_matrix
from elementzero.adjudication.artifact_audit import (
    assert_v1_evidence_unchanged,
    replay_all,
    write_artifact_inventory,
)
from elementzero.adjudication.benchmark_controls import write_benchmark_controls
from elementzero.adjudication.diagnostics import write_uncertainty_diagnostics
from elementzero.adjudication.failure_taxonomy import write_failure_records
from elementzero.adjudication.model_readiness import (
    write_frontier_registry,
    write_model_readiness,
)
from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import SchemaError
from elementzero.evidence.hashing import canonical_json, sha256_file
from elementzero.evidence.ledger import read_json
from elementzero.experiments.runner import write_sha256sums

REPORT_MARKDOWN = "WO11_Evidence_Adjudication_Report.md"
ADJUDICATION_REPORT_FILE = "wo11_adjudication_report.json"
REPLAY_VERIFICATION_FILE = "replay_verification.json"

ADJUDICATION_REQUIRED_FIELDS = (
    "work_order",
    "input_release",
    "artifact_inventory_hash",
    "replay_status",
    "benchmark_control_status",
    "failures",
    "model_readiness_verdict",
    "wo12_prerequisites",
)


def validate_adjudication_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Enforce schemas/wo11_adjudication_report.schema.json in code."""
    missing = [f for f in ADJUDICATION_REQUIRED_FIELDS if f not in payload]
    if missing:
        raise SchemaError(f"adjudication report is missing required fields: {missing}")
    extra = sorted(set(payload) - set(ADJUDICATION_REQUIRED_FIELDS))
    if extra:
        raise SchemaError(f"adjudication report carries unknown fields: {extra}")
    if payload["work_order"] != WO11_ID:
        raise SchemaError(f"adjudication report work_order must be {WO11_ID!r}")
    if payload["replay_status"] not in ("PASS", "FAIL"):
        raise SchemaError("replay_status must be PASS or FAIL")
    if payload["benchmark_control_status"] not in ("PASS", "FAIL", "INDETERMINATE"):
        raise SchemaError("benchmark_control_status must be PASS, FAIL, or INDETERMINATE")
    for field in ("failures", "wo12_prerequisites"):
        if not isinstance(payload[field], list) or any(
            not isinstance(v, str) for v in payload[field]
        ):
            raise SchemaError(f"{field} must be a list of strings")
    return payload


# --------------------------------------------------------------------------- #
# Pipeline                                                                    #
# --------------------------------------------------------------------------- #


def run_wo11(
    *,
    repo_root: str | Path | None = None,
    out_dir: str | Path | None = None,
    workspace_dir: str | Path | None = None,
) -> dict[str, Any]:
    """The full WO-11 adjudication, in the required implementation order."""
    root = Path(repo_root or REPO_ROOT)
    out = Path(out_dir) if out_dir is not None else root / REPORTS_RELPATH
    out.mkdir(parents=True, exist_ok=True)

    if workspace_dir is None:
        with tempfile.TemporaryDirectory(prefix="wo11-workspace-") as tmp:
            return _run_pipeline(root=root, out=out, workspace=Path(tmp))
    return _run_pipeline(root=root, out=out, workspace=Path(workspace_dir))


def _run_pipeline(*, root: Path, out: Path, workspace: Path) -> dict[str, Any]:
    # WO-11.1 — freeze/inventory, and stop on any moved hash.
    inventory = write_artifact_inventory(out_dir=out, repo_root=root)
    assert_v1_evidence_unchanged(inventory)

    # WO-11.2 — replay without refitting.
    replay = replay_all(workspace_root=workspace / "replay", repo_root=root)
    (out / REPLAY_VERIFICATION_FILE).write_text(canonical_json(replay) + "\n", encoding="utf-8")

    if replay["replay_status"] != "PASS":
        # Stop scientific diagnosis: infrastructure first.
        failure_records = {
            "work_order": WO11_ID,
            "records": [],
            "primary_classes_by_benchmark": {},
            "classification_rule": "replay failed; scientific diagnosis stopped",
        }
        controls = {"benchmark_control_status": "INDETERMINATE"}
        readiness = write_model_readiness(
            out_dir=out,
            inventory=inventory,
            replay=replay,
            controls=controls,
            failure_records=failure_records,
        )
        payload = _finalize(
            out=out,
            inventory=inventory,
            replay=replay,
            controls=controls,
            failure_records=failure_records,
            readiness=readiness,
            diagnostics=None,
            ablations=None,
            registry=None,
        )
        return payload

    # WO-11.4/11.5/11.6 — diagnostics from sealed predictions.
    diagnostics = write_uncertainty_diagnostics(
        out_dir=out,
        b002_dir=root / "experiments" / "EZ-B002-v1",
        b003_dir=root / "experiments" / "EZ-B003-v1",
    )

    # WO-11.7 — benchmark oracle controls.
    controls = write_benchmark_controls(
        out_dir=out, workspace_root=workspace / "controls", repo_root=root
    )

    # WO-11.8/11.9 — development-only ablations on new fixtures.
    ablations = write_ablation_matrix(out_dir=out, workspace_dir=workspace / "dev-fixtures")

    # WO-11.3 — failure taxonomy, with all evidence available.
    b003_aggregate = read_json(root / "experiments" / "EZ-B003-v1" / "shell_aggregate.json")
    failure_records = write_failure_records(
        out_dir=out,
        inventory=inventory,
        b003_aggregate=b003_aggregate,
        diagnostics=diagnostics,
        controls=controls,
        ablations=ablations,
    )

    # WO-11.10 — readiness verdict and candidate registry.
    readiness = write_model_readiness(
        out_dir=out,
        inventory=inventory,
        replay=replay,
        controls=controls,
        failure_records=failure_records,
    )
    registry = write_frontier_registry(out_dir=out)

    return _finalize(
        out=out,
        inventory=inventory,
        replay=replay,
        controls=controls,
        failure_records=failure_records,
        readiness=readiness,
        diagnostics=diagnostics,
        ablations=ablations,
        registry=registry,
    )


def _finalize(
    *,
    out: Path,
    inventory: dict[str, Any],
    replay: dict[str, Any],
    controls: dict[str, Any],
    failure_records: dict[str, Any],
    readiness: dict[str, Any],
    diagnostics: dict[str, Any] | None,
    ablations: dict[str, Any] | None,
    registry: dict[str, Any] | None,
) -> dict[str, Any]:
    adjudication = validate_adjudication_report(
        {
            "work_order": WO11_ID,
            "input_release": INPUT_RELEASE,
            "artifact_inventory_hash": sha256_file(out / "artifact_inventory.json"),
            "replay_status": replay["replay_status"],
            "benchmark_control_status": controls["benchmark_control_status"],
            "failures": [r["failure_id"] for r in failure_records["records"]],
            "model_readiness_verdict": readiness["model_readiness_verdict"],
            "wo12_prerequisites": list(readiness["wo12_prerequisites"]),
        }
    )
    (out / ADJUDICATION_REPORT_FILE).write_text(
        canonical_json(adjudication) + "\n", encoding="utf-8"
    )
    (out / REPORT_MARKDOWN).write_text(
        render_report(
            inventory=inventory,
            replay=replay,
            controls=controls,
            failure_records=failure_records,
            readiness=readiness,
            diagnostics=diagnostics,
            ablations=ablations,
            registry=registry,
        ),
        encoding="utf-8",
    )
    (out / "README.md").write_text(_readme(), encoding="utf-8")
    write_sha256sums(out)
    return {
        "out_dir": str(out),
        "adjudication": adjudication,
        "readiness": readiness,
        "replay": replay,
        "controls": controls,
    }


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, f".{digits}f") if abs(value) < 1.0e5 else format(value, ".4e")
    return str(value)


def _table(columns: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(v) for v in row) + " |")
    return lines


def _readme() -> str:
    return (
        "# WO-11 — Evidence Adjudication artifacts\n\n"
        "Machine-readable adjudication of the frozen EZ-B002-v1 and EZ-B003-v1\n"
        "results. The v1 experiments under `experiments/` are immutable inputs;\n"
        "nothing in this directory reruns, relaxes, or relabels them.\n\n"
        "Read `WO11_Evidence_Adjudication_Report.md` first; every table in it is\n"
        "derived from the JSON artifacts committed next to it. Rebuild with:\n\n"
        "    elementzero adjudicate wo11\n\n"
        "The rebuild is deterministic: it reproduces every file in this\n"
        "directory byte for byte from the frozen evidence baseline.\n"
    )


def render_report(
    *,
    inventory: dict[str, Any],
    replay: dict[str, Any],
    controls: dict[str, Any],
    failure_records: dict[str, Any],
    readiness: dict[str, Any],
    diagnostics: dict[str, Any] | None,
    ablations: dict[str, Any] | None,
    registry: dict[str, Any] | None,
) -> str:
    lines: list[str] = [
        "# WO-11 — Evidence Adjudication Report",
        "",
        f"Work order: {WO11_ID}",
        f"Input release: {INPUT_RELEASE}",
        f"Baseline commit: {inventory['baseline_commit']}",
        f"Verdict: **{readiness['model_readiness_verdict']}**",
        "",
        "All numbers in this report are derived from the committed, sealed v1",
        "artifacts and from WO-11 control/development runs. The v1 experiments",
        "are synthetic-chart software evidence; nothing here is a statement",
        "about real nuclei, and nothing here changes a frozen v1 result.",
        "",
    ]

    # 1. Frozen evidence baseline
    lines += ["## 1. Frozen evidence baseline", ""]
    b002 = inventory["experiments"]["EZ-B002-v1"]
    b003 = inventory["experiments"]["EZ-B003-v1"]
    lines += _table(
        ["experiment", "sealed predictions unchanged", "checksums verify", "status"],
        [
            [
                epoch,
                inventory["experiments"][epoch]["sealed_predictions"]["unchanged"],
                inventory["experiments"][epoch]["sha256sums_ok"],
                "scored",
            ]
            for epoch in ("EZ-B001-A", "EZ-B001-B", "EZ-B001-C")
        ]
        + [
            ["EZ-B002-v1", b002["sealed_predictions"]["unchanged"], b002["sha256sums_ok"], b002["status"]],
            ["EZ-B003-v1", b003["sealed_predictions"]["unchanged"], b003["sha256sums_ok"], b003["status"]],
        ],
    )
    lines += [
        "",
        f"EZ-B003-v1 frozen criterion: `{b003['frozen_criterion']['criterion_id']}` "
        f"(digest `{b003['frozen_criterion']['criterion_digest'][:16]}…`), verdicts: "
        + ", ".join(f"{m} = {v}" for m, v in sorted(b003["verdicts"].items())),
        "",
        "EZ-B002-v1 froze no accuracy criterion: v1 is characterization, and the",
        "observed weaknesses below are adjudicated without inventing one.",
        "",
    ]

    # 2. Replay verification
    lines += ["## 2. Replay verification", ""]
    for name in ("EZ-B002-v1", "EZ-B003-v1"):
        entry = replay[name]
        comparison = entry["comparison"]
        if comparison["strict_byte_identical"]:
            strict_note = (
                f"strict byte level: all {comparison['n_files']} regenerated files identical"
            )
        else:
            strict_note = (
                f"strict byte level: {comparison['n_identical']}/{comparison['n_files']} files; "
                "the rest are raw-float Atlas fact payloads that move by one ULP "
                "on a different libm, plus any files under documented defects"
            )
        defects = entry.get("known_defects") or []
        if defects:
            aggregate_note = (
                "aggregates identical after volatile evidence ids are stripped, "
                "except the documented defect "
                + ", ".join(
                    f"{d['defect_id']} ({', '.join(d['models'])})" for d in defects
                )
            )
        else:
            aggregate_note = "aggregates identical after volatile evidence ids are stripped"
        lines.append(
            f"- {name}: **{entry['replay_status']}** — "
            f"{comparison['metrics_files_identical']}/{comparison['metrics_files']} metric files "
            f"byte-identical, {aggregate_note} "
            f"({strict_note})."
        )
    lines += [
        "",
        replay["no_refit_rule"],
        "",
    ]

    # 3./4. failure decomposition
    decompositions = (
        ("EZ-B002", "3. EZ-B002 failure decomposition"),
        ("EZ-B003", "4. EZ-B003 failure decomposition"),
    )
    for benchmark, title in decompositions:
        lines += [f"## {title}", ""]
        rows = [
            [
                r["failure_id"],
                r["model_id"],
                r["criterion_id"].rsplit(":", 1)[-1],
                r["observed_value"],
                r["frozen_threshold"] if r["frozen_threshold"] is not None else "none frozen",
                r["primary_class"],
                ", ".join(r["secondary_classes"]) or "—",
                r["confidence"],
            ]
            for r in failure_records["records"]
            if r["benchmark_id"] == benchmark
        ]
        columns = [
            "failure id",
            "model",
            "check",
            "observed",
            "frozen threshold",
            "primary class",
            "secondary",
            "confidence",
        ]
        lines += _table(columns, rows)
        lines.append("")

    # 5. Calibration diagnostics
    lines += ["## 5. Calibration diagnostics", ""]
    if diagnostics is not None:
        rows = []
        for bench in ("EZ-B002-v1", "EZ-B003-v1"):
            for model_id, payload in sorted(diagnostics[bench]["by_model"].items()):
                calibration = payload["calibration"]
                rows.append(
                    [
                        bench,
                        model_id,
                        calibration["mean_z"],
                        calibration["std_z"],
                        calibration["fraction_abs_z_le_1"],
                        calibration["fraction_abs_z_le_1p645"],
                        calibration["fraction_abs_z_le_1p96"],
                        calibration["fraction_abs_z_gt_3"],
                    ]
                )
        lines += _table(
            [
                "benchmark",
                "model",
                "mean(z)",
                "std(z)",
                "abs(z)<=1",
                "abs(z)<=1.645",
                "abs(z)<=1.96",
                "abs(z)>3",
            ],
            rows,
        )
        lines += [
            "",
            "Readout: the GP models are drastically overdispersed (std(z) near 0:",
            "reported sigma is orders of magnitude wider than realized error), so",
            "their intervals are uninformative rather than dishonest. SEMF-LS is",
            "biased (mean(z) near -1.6 on EZ-B002): its misses come from a shifted",
            "mean, not a narrow sigma. These are diagnostics, not causal proof.",
            "",
        ]

    # 6. Extrapolation depth
    lines += ["## 6. Extrapolation-depth diagnostics", ""]
    if diagnostics is not None:
        rows = []
        for bench in ("EZ-B002-v1", "EZ-B003-v1"):
            for model_id, payload in sorted(diagnostics[bench]["by_model"].items()):
                depth = payload["depth"]
                for bucket, summary in depth["buckets"].items():
                    if summary["n"]:
                        rows.append(
                            [bench, model_id, bucket, summary["n"], summary["MAE_keV"], summary["coverage_90"]]
                        )
        lines += _table(["benchmark", "model", "bucket", "n", "MAE (keV)", "coverage 90"], rows)
        slopes = []
        for bench in ("EZ-B002-v1", "EZ-B003-v1"):
            for model_id, payload in sorted(diagnostics[bench]["by_model"].items()):
                slope = payload["depth"]["descriptive_slope"]["slope_keV_per_L1"]
                slopes.append(f"{bench}/{model_id}: {_fmt(slope, 1)} keV per L1 step")
        lines += [
            "",
            "Descriptive slopes (no significance claim; v1 depth reaches only L1 = 3): "
            + "; ".join(slopes)
            + ".",
            "",
            "Depth effects exist but are shallow and cannot explain failures that",
            "are already present at L1 = 1, so EXTRAPOLATION_DEPTH stays a",
            "secondary, not primary, cause at these depths.",
            "",
        ]

    # 7. Controls
    lines += ["## 7. Benchmark oracle controls", ""]
    if "EZ-B002" in controls:
        lines.append(f"Overall control status: **{controls['benchmark_control_status']}**")
        lines.append("")
        b2 = controls["EZ-B002"]
        lines += _table(
            ["EZ-B002 control", "MAE (keV)", "coverage 90"],
            [
                [m, s["MAE_keV"], s["coverage_90"]]
                for m, s in sorted(b2["by_model"].items())
            ],
        )
        lines.append("")
        b3 = controls["EZ-B003"]
        lines += _table(
            ["EZ-B003 control", "verdict", "sign", "top-3", "rank-1", "cal. error"],
            [
                [
                    m,
                    s["verdict"],
                    s["sign_fraction"],
                    s["top_k_fraction"],
                    s["rank_1_fraction"],
                    s["calibration_error_90"],
                ]
                for m, s in sorted(b3["by_model"].items())
            ],
        )
        sensitivity = b3["threshold_sensitivity"]
        lines += [
            "",
            f"Threshold sensitivity: {_fmt(sensitivity['noise_small_keV'], 0)} keV of "
            f"unstructured noise → {sensitivity['noise_small_verdict']}; "
            f"{_fmt(sensitivity['noise_large_keV'], 0)} keV → {sensitivity['noise_large_verdict']}. "
            "Even 2 MeV of *random* mass error keeps the criterion met, while the",
            "baselines fail with sub-MeV *smooth structured* error: the criterion",
            "punishes the inability to localize a discontinuity, not error",
            "magnitude, so the v1 failures are not a knife-edge threshold effect.",
            "",
        ]

    # 8./9. Ablations
    lines += ["## 8. Feature ablations (development fixtures only)", ""]
    if ablations is not None:
        summary = ablations["summary"]
        for fixture, entry in sorted(summary.items()):
            lines.append(f"- {fixture}: baseline MAE {_fmt(entry['baseline_MAE_keV'], 1)} keV; "
                         f"max MAE change across feature policies "
                         f"{_fmt(100 * entry['max_feature_MAE_change_fraction'], 1)}%.")
        shell = summary["EZ-B003-dev"].get("feature_policy_shell_metric", {})
        lines += [
            "",
            "Dev shell localization (rank-1 fraction) by feature policy: "
            + ", ".join(f"{k} = {_fmt(v)}" for k, v in sorted(shell.items()))
            + ".",
            "",
            "Adding parity, isospin, and local coordinate features moves mass MAE",
            "by under twenty percent and leaves localization at zero: with this",
            "model family, FEATURE_INSUFFICIENCY is not the dominant cause.",
            "",
        ]

    lines += ["## 9. Hyperparameter sensitivity (development fixtures only)", ""]
    if ablations is not None:
        summary = ablations["summary"]
        rows = []
        for fixture, entry in sorted(summary.items()):
            for variant, mae in sorted(entry["hyperparameter_MAE_keV"].items()):
                shell_metric = entry.get("hyperparameter_shell_metric", {}).get(variant)
                rows.append([fixture, variant, mae, shell_metric])
        lines += _table(["fixture", "variant", "MAE (keV)", "shell rank-1"], rows)
        lines += [
            "",
            "The family is highly configuration-sensitive: on EZ-B002-dev the",
            "optimizer-enabled variant drops MAE from hundreds of keV to under",
            "10 keV, and on EZ-B003-dev it is the only variant with non-zero",
            "rank-1 localization from the smooth-kernel grid. The frozen v1",
            "fixed-kernel configuration understates what even this family can do,",
            "which is recorded as HYPERPARAMETER_SENSITIVITY evidence — and it",
            "was preregistered, so the v1 results stand as they are.",
            "",
        ]

    # 10. Model-family diagnosis
    lines += [
        "## 10. Model-family diagnosis",
        "",
        "- EZ-SEMF-LS-v1: structurally unable to express a shell discontinuity",
        "  (no shell term); resolves H0 where truth resolves H1; global sigma",
        "  cannot absorb its structured bias (undercoverage on both benchmarks).",
        "- EZ-GP-DIRECT-v1: physics-free mean function reverts toward the",
        "  training mean inside holdouts (MAE ~40x the residual model on",
        "  EZ-B002-v1); smooth kernel smears the indicator spike; sigma",
        "  overdispersed to the point of being uninformative.",
        "- EZ-SEMF-GP-RESIDUAL-v1: best mass surface of the three and recovers",
        "  the *presence* of the injected gap (sign 1.0, top-3 0.8) but not its",
        "  *location* (rank-1 0.086): a squared-exponential prior has no kink",
        "  bias. This is the physically expected failure of a smooth",
        "  interpolator on a discontinuity.",
        "",
        "Primary failure classes: "
        + "; ".join(
            f"{k}: {', '.join(v)}"
            for k, v in sorted(failure_records["primary_classes_by_benchmark"].items())
        )
        + ".",
        "",
    ]

    # 11. Registry
    lines += ["## 11. Frontier-model candidate registry", ""]
    if registry is not None:
        lines += _table(
            ["candidate", "class", "role", "independence group", "status"],
            [
                [
                    c["candidate_id"],
                    c["physics_class"],
                    c["recommended_role"],
                    c["scientific_independence_group"],
                    c["status"],
                ]
                for c in registry["candidates"]
            ],
        )
        lines += ["", registry["selection_rule"], ""]

    # 12. Verdict
    lines += [
        "## 12. WO-11 verdict",
        "",
        f"**{readiness['model_readiness_verdict']}**",
        "",
    ]
    lines += [f"- {reason}" for reason in readiness["reasons"]]
    lines.append("")

    # 13. WO-12 prerequisites
    lines += ["## 13. Exact prerequisites for WO-12", ""]
    lines += [f"{i}. {p}" for i, p in enumerate(readiness["wo12_prerequisites"], start=1)]
    lines.append("")

    # 14. Deviations / limitations
    lines += [
        "## 14. Deviations / limitations",
        "",
        "- The WO-11 handoff described EZ-B002-v1 as `CRITERION_NOT_MET`; the",
        "  frozen v1 record shows that protocol deliberately froze *no* accuracy",
        "  criterion (characterization, engineering PASS). WO-11 adjudicates the",
        "  observed EZ-B002-v1 weaknesses without inventing a threshold after",
        "  the fact, and treats `frozen-threshold failure` as accurate for",
        "  EZ-B003-v1 only.",
        "- Strict byte-level replay (including raw-float Atlas fact payloads) is",
        "  achieved under the recorded interpreter line (CPython 3.12). Under",
        "  3.11 every 12-significant-digit metric and every verdict still",
        "  reproduces exactly; only content-addressed ids over raw IEEE floats",
        "  shift by one ULP. WO-12 should pin the interpreter minor version.",
        "- The committed-seal *refit* reproducibility tests require the recorded",
        "  library stack (numpy 2.4.4, scipy 1.18.0, Python 3.12.3); scipy",
        "  1.18.0 was not installable in the WO-11 environment, so refit",
        "  reproducibility remains verified only in the recording environment.",
        "  This is environment sensitivity of the *fit* path, not of the sealed",
        "  evidence, and it is additional HYPERPARAMETER_SENSITIVITY-adjacent",
        "  evidence for WO-12's environment-pinning prerequisite.",
        "- All v1 evidence is synthetic-chart software evidence. Every",
        "  conclusion here is about protocol and model behavior on those",
        "  synthetic surfaces; none of it is scientific evidence about real",
        "  nuclei, about any real closure, or about any island of stability.",
        "- Dev-fixture results are development diagnostics only and are never",
        "  comparable to v1 numbers.",
        "",
    ]
    return "\n".join(lines)
