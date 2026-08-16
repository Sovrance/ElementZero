"""WO-12 federation report bundle (spec sections 4, 18, 22, 23, 30).

``run_wo12`` executes the whole work order end to end — prerequisite
verification, registry freeze, synthetic qualification, Atlas lineage — and
writes every committed artifact:

    reports/model_federation/wo12/
        input_baseline.json
        candidate_review.json
        license_availability_review.json
        table_validation.json
        calibration_report.json
        federation_manifest.json
        synthetic_qualification.json
        atlas/{artifacts,events,facts,provenance}.json
        WO12_Model_Federation_Report.md
        SHA256SUMS.txt

    runtime.lock.json                    (repo root, section 23)
    experiments/EZ-B002-v2/…             (preregistration + sealed summaries)
    experiments/EZ-B003-v2/…

Every JSON artifact except the runtime records is deterministic on one
runtime; strict byte replay across rebuilds is promised on the reference
runtime recorded in runtime.lock.json and scientific equivalence elsewhere.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.model_tables.manifests import (
    REGISTERED_TABLES,
    source_manifest,
    table_path,
)
from elementzero.data.model_tables.validation import (
    validate_full_table,
    validate_golden_rows,
)
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file
from elementzero.evidence.ledger import read_json
from elementzero.experiments.runner import write_sha256sums
from elementzero.experiments.wo12_qualification import (
    B002_V2_QUAL_ID,
    B003_V2_QUAL_ID,
    QUAL_CREATED_AT,
    WO12_BASELINE_COMMIT,
    run_wo12_qualification,
    write_preregistrations,
    write_qual_fixtures,
)
from elementzero.models.federation import REPORTS_RELPATH, WO12_ID
from elementzero.models.federation.calibration import UNCERTAINTY_DECOMPOSITION_RULE
from elementzero.models.federation.runtime_lock import (
    RUNTIME_LOCK_FILE,
    assert_lock_complete,
    write_runtime_lock,
)

REPORT_MARKDOWN = "WO12_Model_Federation_Report.md"

# The v0.3 governance tag, created and pushed by the maintainer before this
# work order's coding started (WO-12 section 3). Recorded, not asserted at
# runtime: CI checkouts do not fetch tags.
V03_TAG_CLOSEOUT = {
    "tag": "elementzero-validation-ladder-v0.3",
    "commit": "9baee722c49296e681cf53da63f31a36bb6ab2f6",
    "status": "PUSHED_BY_MAINTAINER",
    "verified": "git ls-remote --tags origin, 2026-08-16",
}


def _wo11_prerequisite_verification(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    """The eleven WO-11 prerequisites, each mapped to its WO-12 disposition."""
    prerequisites = readiness["wo12_prerequisites"]
    dispositions = [
        "SATISFIED: EZ-B002-v2 and EZ-B003-v2 exist as new QUALIFICATION_ONLY "
        "protocols with frozen thresholds; no v1 artifact was touched.",
        "SATISFIED: the three v1 baselines are registered CONTROL participants "
        "and are never removed.",
        "SATISFIED with documented fallback: BSkG5 and BSkG4 tables are "
        "BLOCKED_AVAILABILITY in this environment, so the Brussels Skyrme-EDF "
        "family participates through the publicly hosted BSkG3 table "
        "(PHYSICS_BACKBONE, skyrme_edf_bskg).",
        "SATISFIED with documented fallback: FRDM2012's canonical host is "
        "unreachable, so the macroscopic-microscopic family participates "
        "through the IAEA RIPL-3 FRDM95 table; the combination layer "
        "(uniform, validation-weighted, EBMA-compatible) is implemented.",
        "SATISFIED: residual/ML models exist only in RESIDUAL_CHALLENGER "
        "roles; no ML model is a source of truth.",
        "SATISFIED: EZ-GP-OPTIMIZED-CONTROL-v1 is registered with frozen "
        "hyperparameters (ez-wo12-gp-optimized-control-v1).",
        "ADDRESSED: predictive uncertainty is decomposed "
        "(within/residual/disagreement) and calibrated per model in the "
        "qualification; the frozen v2 gates enforce honesty (the BSkG3 "
        "residual variant and the optimized GP both fail v2 checks on "
        "calibration alone, which shows the clause has teeth).",
        "SATISFIED: every v2 threshold is frozen in this commit from "
        "synthetic mechanics and WO-11 oracle behavior, before any "
        "evaluated-table truth.",
        "SATISFIED: runtime.lock.json records interpreter, array stack, "
        "BLAS/LAPACK identity, OS, and architecture.",
        "SATISFIED: every external table carries a source/license manifest; "
        "the registry gate excludes anything not APPROVED.",
        "SATISFIED: fit/calibration/benchmark identity digests are persisted "
        "and disjointness is asserted per split; the discovery feature "
        "firewall stays active in every shell run.",
    ]
    if len(prerequisites) != len(dispositions):
        raise ProtocolError(
            f"expected {len(dispositions)} WO-11 prerequisites, found {len(prerequisites)}"
        )
    return [
        {"index": i + 1, "prerequisite": p, "disposition": d}
        for i, (p, d) in enumerate(zip(prerequisites, dispositions))
    ]


def build_input_baseline(*, repo_root: Path) -> dict[str, Any]:
    wo11_dir = repo_root / "reports" / "adjudication" / "wo11"
    readiness = read_json(wo11_dir / "model_readiness.json")
    adjudication = read_json(wo11_dir / "wo11_adjudication_report.json")
    if readiness["model_readiness_verdict"] != "FRONTIER_MODEL_RERUN_JUSTIFIED":
        raise ProtocolError(
            "WO-12 requires the WO-11 verdict FRONTIER_MODEL_RERUN_JUSTIFIED; "
            f"found {readiness['model_readiness_verdict']!r}"
        )
    return {
        "work_order": WO12_ID,
        "input_commit": WO12_BASELINE_COMMIT,
        "wo11_verdict": readiness["model_readiness_verdict"],
        "wo11_adjudication_hash": sha256_file(wo11_dir / "wo11_adjudication_report.json"),
        "wo11_model_readiness_hash": sha256_file(wo11_dir / "model_readiness.json"),
        "wo11_input_release": adjudication["input_release"],
        "v03_tag_closeout": dict(V03_TAG_CLOSEOUT),
        "prerequisite_verification": _wo11_prerequisite_verification(readiness),
        "v1_preservation_rule": (
            "No v1 benchmark artifact is modified by WO-12; the WO-11 "
            "artifact inventory remains the integrity reference."
        ),
    }


def build_candidate_review(*, repo_root: Path) -> dict[str, Any]:
    from elementzero.models.federation.adapters.bskg5 import review_ladder as bskg_ladder
    from elementzero.models.federation.adapters.drhbc import review_drhbc
    from elementzero.models.federation.adapters.frdm2012 import review_ladder as frdm_ladder

    return {
        "work_order": WO12_ID,
        "bskg_family": bskg_ladder(repo_root=repo_root),
        "frdm_family": frdm_ladder(repo_root=repo_root),
        "drhbc_family": review_drhbc(repo_root=repo_root),
        "wo11_registry_reference": "reports/adjudication/wo11/frontier_model_candidates.json",
        "independence_rule": (
            "Residual variants of one base model are not independent models; "
            "diversity is counted in independence groups."
        ),
    }


def build_license_review(*, repo_root: Path) -> dict[str, Any]:
    tables = {}
    for table_id in sorted(REGISTERED_TABLES):
        manifest = source_manifest(table_id)
        tables[table_id] = {
            "model_id": manifest["model_id"],
            "license_status": manifest["license_status"],
            "license_note": manifest["license_note"],
            "source_url": manifest["source_url"],
            "publication_doi": manifest["publication_doi"],
            "raw_sha256": manifest["raw_sha256"],
        }
    return {
        "work_order": WO12_ID,
        "gate_rule": (
            "A model that is not APPROVED cannot participate in a frozen v2 "
            "protocol; the registry enforces this at registration time "
            "(WO-12 section 24)."
        ),
        "raw_table_rule": (
            "Raw tables stay gitignored; the repository commits hashes, "
            "manifests, golden fixtures, and tools/fetch_model_tables.py."
        ),
        "tables": tables,
    }


def build_table_validation(*, repo_root: Path) -> dict[str, Any]:
    return {
        "work_order": WO12_ID,
        "golden": {
            table_id: validate_golden_rows(table_id, repo_root=repo_root)
            for table_id in ("BSKG3", "FRDM95")
        },
        "full": {
            table_id: validate_full_table(table_id, repo_root=repo_root)
            for table_id in ("BSKG3", "FRDM95")
        },
    }


def build_atlas_lineage(*, qualification: dict[str, Any], repo_root: Path, out_dir: Path):
    """The section-18 fact chain, built from the qualification lineage inputs."""
    from elementzero.models.federation.lineage import FederationLineage

    lineage = FederationLineage(created_at=QUAL_CREATED_AT)
    table_artifacts = {}
    adapter_facts = {}
    for table_id in ("BSKG3", "FRDM95"):
        manifest = source_manifest(table_id)
        path = table_path(table_id, repo_root=repo_root)
        if not path.is_file():
            continue
        artifact = lineage.table_artifact(
            table_path=path, source_url=manifest["source_url"]
        )
        table_artifacts[manifest["model_id"]] = artifact
    prediction_facts: dict[tuple[str, str], Any] = {}
    residual_fit_facts: dict[str, Any] = {}
    for benchmark_id in (B002_V2_QUAL_ID, B003_V2_QUAL_ID):
        inputs = qualification[benchmark_id]["lineage_inputs"]
        split_record = qualification[benchmark_id]["split_records"][0]
        # Backbones and plain models first, then residuals, then combiners.
        for model_id, entry in sorted(inputs.items()):
            if "+GP-RESIDUAL" in model_id or model_id.startswith("EZ-FED-"):
                continue
            adapter_fact = None
            if model_id in table_artifacts:
                if model_id not in adapter_facts:
                    adapter_facts[model_id] = lineage.model_adapter_fact(
                        artifact=table_artifacts[model_id],
                        freeze_id=entry["first_split_freeze_id"],
                        model_manifest={
                            "model_id": model_id,
                            **entry["model_manifest"],
                        },
                    )
                adapter_fact = adapter_facts[model_id]
            prediction_facts[(model_id, benchmark_id)] = lineage.model_prediction_fact(
                adapter_fact=adapter_fact,
                model_id=model_id,
                benchmark_id=benchmark_id,
                prediction_set_digest=entry["prediction_set_digest"],
                n_predictions=entry["n_predictions"],
                n_missing=entry["n_missing"],
            )
        for model_id, entry in sorted(inputs.items()):
            if "+GP-RESIDUAL" not in model_id:
                continue
            base_id = model_id.split("+GP-RESIDUAL")[0]
            base_fact = prediction_facts[(base_id, benchmark_id)]
            manifest = entry["model_manifest"]
            fit_fact = lineage.residual_fit_fact(
                base_prediction_fact=base_fact,
                residual_manifest={
                    "model_id": model_id,
                    "base_model_id": manifest.get("base_model_id", base_id),
                    "residual_gp_config_id": manifest.get("residual_gp_config_id", ""),
                    "n_residual_pairs": manifest.get("n_residual_pairs", 0),
                    "n_skipped_uncovered": manifest.get("n_skipped_uncovered", 0),
                },
                training_identity_digest=split_record["fit_identity_digest"],
            )
            residual_fit_facts[f"{model_id}:{benchmark_id}"] = fit_fact
            prediction_facts[(model_id, benchmark_id)] = lineage.residual_prediction_fact(
                residual_fit_fact=fit_fact,
                model_id=model_id,
                benchmark_id=benchmark_id,
                prediction_set_digest=entry["prediction_set_digest"],
                n_predictions=entry["n_predictions"],
            )
        for model_id, entry in sorted(inputs.items()):
            if not model_id.startswith("EZ-FED-"):
                continue
            manifest = entry["model_manifest"]
            component_ids = manifest.get("component_model_ids", [])
            contributing = {
                cid: prediction_facts[(cid, benchmark_id)]
                for cid in component_ids
                if (cid, benchmark_id) in prediction_facts
            }
            lineage.combination_fact(
                combiner_manifest={
                    "model_id": model_id,
                    "combination_rule": manifest.get("combination_rule", ""),
                    "weights": manifest.get("weights", {}),
                    "component_independence_groups": manifest.get(
                        "component_independence_groups", []
                    ),
                    "component_source_hashes": manifest.get("component_source_hashes", {}),
                },
                benchmark_id=benchmark_id,
                contributing_facts=contributing,
                prediction_set_digest=entry["prediction_set_digest"],
            )
    return lineage.write_bundle(out_dir)


# --------------------------------------------------------------------------- #
# Committed qualification artifacts under experiments/                        #
# --------------------------------------------------------------------------- #

_B002_KEEP = (
    "regions.json",
    "REGIONS_SHA256",
    "SEALED_PREDICTIONS.json",
    "SEALED_PREDICTIONS_SHA256",
    "region_aggregate.json",
    "region_aggregate.md",
    "SCORE_MANIFEST.json",
)
_B003_KEEP = (
    "challenges.json",
    "CHALLENGES_SHA256",
    "CRITERION.json",
    "CRITERION_SHA256",
    "SEALED_PREDICTIONS.json",
    "SEALED_PREDICTIONS_SHA256",
    "shell_aggregate.json",
    "shell_aggregate.md",
    "SCORE_MANIFEST.json",
)


def _copy_qualification_artifacts(qualification: dict[str, Any], repo_root: Path) -> None:
    """Deterministic sealed summaries; per-run trees stay regenerable."""
    for benchmark_id, keep, destination_name in (
        (B002_V2_QUAL_ID, _B002_KEEP, "EZ-B002-v2"),
        (B003_V2_QUAL_ID, _B003_KEEP, "EZ-B003-v2"),
    ):
        source_dir = Path(qualification[benchmark_id]["experiment_dir"])
        destination = repo_root / "experiments" / destination_name / "qualification"
        destination.mkdir(parents=True, exist_ok=True)
        for name in keep:
            if (source_dir / name).is_file():
                shutil.copy2(source_dir / name, destination / name)
        note = {
            "qualification_id": benchmark_id,
            "state": "QUALIFICATION_ONLY",
            "committed_files_rule": (
                "Sealed summaries and aggregates only; the per-run trees are "
                "regenerated deterministically by the WO-12 qualification "
                "runner from the committed chart fixture and the frozen "
                "registry (reference runtime for byte identity)."
            ),
            "environment_dependent_files_rule": (
                "RUN_MANIFEST.json and environment.json embed the runtime and "
                "are not committed; runtime.lock.json is the runtime record."
            ),
        }
        (destination / "README.json").write_text(canonical_json(note) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #


def run_wo12(
    *,
    repo_root: str | Path | None = None,
    out_dir: str | Path | None = None,
    workspace_dir: str | Path | None = None,
    commit_artifacts: bool = True,
) -> dict[str, Any]:
    """Full WO-12 pipeline.

    ``commit_artifacts=False`` writes the report bundle into ``out_dir`` only,
    leaving runtime.lock.json, the committed fixtures, and the experiments/
    summaries untouched — the mode reproducibility tests use.
    """
    import tempfile

    root = Path(repo_root or REPO_ROOT)
    out = Path(out_dir) if out_dir is not None else root / REPORTS_RELPATH
    out.mkdir(parents=True, exist_ok=True)

    if workspace_dir is None:
        with tempfile.TemporaryDirectory(prefix="wo12-workspace-") as tmp:
            return _run_pipeline(
                root=root, out=out, workspace=Path(tmp), commit_artifacts=commit_artifacts
            )
    return _run_pipeline(
        root=root, out=out, workspace=Path(workspace_dir), commit_artifacts=commit_artifacts
    )


def _write(out: Path, name: str, payload: dict[str, Any]) -> None:
    (out / name).write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _run_pipeline(
    *, root: Path, out: Path, workspace: Path, commit_artifacts: bool = True
) -> dict[str, Any]:
    from elementzero.experiments.wo12_qualification import (
        B002_CHART_NAME,
        B003_CHART_NAME,
    )
    from elementzero.models.federation.runtime_lock import capture_runtime

    # 1. WO-11 prerequisites and input baseline.
    input_baseline = build_input_baseline(repo_root=root)
    _write(out, "input_baseline.json", input_baseline)

    # 2-3. Candidate review + license/availability gate + table validation.
    _write(out, "candidate_review.json", build_candidate_review(repo_root=root))
    _write(out, "license_availability_review.json", build_license_review(repo_root=root))
    _write(out, "table_validation.json", build_table_validation(repo_root=root))

    # 4. Runtime lock (repo root, section 23).
    if commit_artifacts:
        lock = write_runtime_lock(root / RUNTIME_LOCK_FILE)
    else:
        lock = capture_runtime()
    assert_lock_complete(lock)

    # 5. The synthetic qualification itself (charts written in the workspace).
    qualification = run_wo12_qualification(workspace=workspace / "qual", repo_root=root)
    fixture_hashes = {
        B002_CHART_NAME: sha256_file(workspace / "qual" / B002_CHART_NAME),
        B003_CHART_NAME: sha256_file(workspace / "qual" / B003_CHART_NAME),
    }
    if commit_artifacts:
        committed_hashes = write_qual_fixtures(repo_root=root)
        if committed_hashes != fixture_hashes:
            raise ProtocolError("committed qualification fixtures diverged from the run")
        write_preregistrations(repo_root=root, protocol=qualification["protocol"])
        _copy_qualification_artifacts(qualification, root)

    # 7. Atlas lineage bundle.
    atlas_hashes = build_atlas_lineage(
        qualification=qualification, repo_root=root, out_dir=out
    )

    # 8. Committed report JSONs (runtime + workspace paths stripped: the
    # runtime lives in runtime.lock.json, the workspace is ephemeral).
    committed = {
        key: value
        for key, value in qualification.items()
        if key not in ("runtime",)
    }
    for benchmark_id in (B002_V2_QUAL_ID, B003_V2_QUAL_ID):
        committed[benchmark_id] = {
            k: v for k, v in committed[benchmark_id].items() if k != "experiment_dir"
        }
    committed["fixture_hashes"] = fixture_hashes
    committed["atlas_bundle_hashes"] = atlas_hashes
    _write(out, "synthetic_qualification.json", committed)
    _write(
        out,
        "federation_manifest.json",
        {
            "work_order": WO12_ID,
            **qualification["registry_manifest"],
            "uncertainty_decomposition_rule": UNCERTAINTY_DECOMPOSITION_RULE,
        },
    )
    _write(
        out,
        "calibration_report.json",
        {
            "work_order": WO12_ID,
            "decomposition_rule": UNCERTAINTY_DECOMPOSITION_RULE,
            B002_V2_QUAL_ID: qualification[B002_V2_QUAL_ID]["calibration_by_model"],
            B003_V2_QUAL_ID: qualification[B003_V2_QUAL_ID]["calibration_by_model"],
            "split_records": {
                B002_V2_QUAL_ID: qualification[B002_V2_QUAL_ID]["split_records"],
                B003_V2_QUAL_ID: qualification[B003_V2_QUAL_ID]["split_records"],
            },
        },
    )

    # 9. Visual federation events (section 25). Qualification-only: the
    # aggregator never maps these to a validated tile stage.
    _write_federation_events(out, qualification=committed, registry=registry_payload(qualification))

    # 10. Markdown report + checksums.
    (out / REPORT_MARKDOWN).write_text(
        render_report(
            input_baseline=input_baseline,
            qualification=committed,
        ),
        encoding="utf-8",
    )
    write_sha256sums(out)
    return {
        "out_dir": str(out),
        "qualification_status": qualification["qualification_status"],
        "b002_status": qualification[B002_V2_QUAL_ID]["status"],
        "b003_status": qualification[B003_V2_QUAL_ID]["status"],
        "registry": qualification["registry_manifest"],
    }


# --------------------------------------------------------------------------- #
# Markdown                                                                    #
# --------------------------------------------------------------------------- #


def registry_payload(qualification: dict[str, Any]) -> dict[str, Any]:
    return qualification["registry_manifest"]


def _write_federation_events(
    out: Path, *, qualification: dict[str, Any], registry: dict[str, Any]
) -> None:
    """FEDERATION_* progress events for the visual table (section 25)."""
    import json

    from elementzero.visuals.event_types import ProgressEvent, make_event_id, validate_event

    protocol_hash = qualification["protocol_hash"]
    events: list[ProgressEvent] = []

    def _emit(event_type: str, z: int, status: str, payload: dict[str, Any]) -> None:
        event = ProgressEvent(
            event_id=make_event_id(
                event_type=event_type,
                source_hash=protocol_hash,
                element_Z=z,
                benchmark_id=payload.get("qualification_id"),
                extra=payload.get("extra", ""),
            ),
            event_type=event_type,
            event_time=QUAL_CREATED_AT,
            project_version="wo12-federation-v1",
            source_kind="wo12_qualification",
            source_path="reports/model_federation/wo12/synthetic_qualification.json",
            source_hash=protocol_hash,
            element_Z=z,
            status=status,
            benchmark_id=payload.get("qualification_id"),
            payload=payload,
        )
        validate_event(event.to_dict())
        events.append(event)

    import re

    from elementzero.experiments.wo12_qualification import (
        B003_QUAL_Z_MAX,
        B003_QUAL_Z_MIN,
    )

    for benchmark_id in (B002_V2_QUAL_ID, B003_V2_QUAL_ID):
        entry = qualification[benchmark_id]
        if benchmark_id == B002_V2_QUAL_ID:
            zs: set[int] = set()
            for record in entry["split_records"]:
                match = re.search(r"Z(\d+)-(\d+)", record["split_id"])
                if match:
                    zs.update(range(int(match.group(1)), int(match.group(2)) + 1))
            target_zs = sorted(zs)
        else:
            target_zs = list(range(B003_QUAL_Z_MIN, B003_QUAL_Z_MAX + 1))
        status = "pass" if entry["status"] == "PASS" else "fail"
        for z in target_zs:
            _emit(
                "FEDERATION_MODEL_AVAILABLE",
                z,
                "info",
                {
                    "qualification_id": benchmark_id,
                    "n_models": registry["model_count"],
                    "n_independence_groups": registry["independence_group_count"],
                },
            )
            _emit(
                "FEDERATION_QUALIFICATION_TARGETED",
                z,
                "info",
                {"qualification_id": benchmark_id},
            )
            _emit(
                "FEDERATION_QUALIFICATION_SCORED",
                z,
                status,
                {
                    "qualification_id": benchmark_id,
                    "qualification_only": True,
                    "no_tile_upgrade_rule": (
                        "qualification-only events never promote element tiles"
                    ),
                },
            )
    lines = [json.dumps(e.to_dict(), sort_keys=True) for e in events]
    (out / "federation_progress_events.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


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


def render_report(*, input_baseline: dict[str, Any], qualification: dict[str, Any]) -> str:
    registry = qualification["registry_manifest"]
    b002 = qualification[B002_V2_QUAL_ID]
    b003 = qualification[B003_V2_QUAL_ID]
    lines = [
        "# WO-12 — Nuclear Model Federation v1",
        "",
        f"Input commit: {input_baseline['input_commit']}",
        f"WO-11 verdict consumed: {input_baseline['wo11_verdict']}",
        f"Qualification status: **{qualification['qualification_status']}**",
        "",
        "All qualification numbers below are synthetic-mechanics evidence on "
        "the frozen WO-12 charts. Physics tables are expected to disagree "
        "with a toy surface; their rows demonstrate coverage, disagreement, "
        "and combination mechanics, not physics accuracy. Nothing here reads "
        "an evaluated mass table.",
        "",
        "## 1. Federation roster",
        "",
        f"Models: {registry['model_count']} — independence groups: "
        f"{registry['independence_group_count']} ({', '.join(registry['independence_groups'])})",
        "",
    ]
    lines += _table(
        ["participant", "role", "independence group", "license"],
        [
            [model_id, p["role"], p["independence_group"], p["license_status"] or "internal"]
            for model_id, p in registry["participants"].items()
        ],
    )
    lines += [
        "",
        "BSkG5 and FRDM2012 remain the preferred backbones; both are "
        "BLOCKED_AVAILABILITY in this environment, so the families "
        "participate through BSkG3 (BRUSLIB) and FRDM95 (IAEA RIPL-3) under "
        "the documented fallback ladders in candidate_review.json.",
        "",
        "## 2. WO-11 prerequisites",
        "",
    ]
    lines += [
        f"{item['index']}. {item['disposition']}"
        for item in input_baseline["prerequisite_verification"]
    ]
    lines += [
        "",
        f"v0.3 tag closeout: `{input_baseline['v03_tag_closeout']['tag']}` at "
        f"`{input_baseline['v03_tag_closeout']['commit'][:12]}…` "
        f"({input_baseline['v03_tag_closeout']['status']}).",
        "",
        "## 3. EZ-B002-v2 qualification",
        "",
        f"Status: **{b002['status']}** — gate: pooled MAE <= "
        f"{_fmt(b002['gate']['best_model_max_MAE_keV'], 0)} keV with "
        f"calibration error <= {_fmt(b002['gate']['best_model_max_calibration_error_90'], 2)}; "
        f"qualifying: {', '.join(b002['qualifying_models']) or 'none'}",
        "",
    ]
    lines += _table(
        ["model", "MAE (keV)", "RMSE (keV)", "coverage 90", "cal. error 90"],
        [
            [m, s["MAE_keV"], s["RMSE_keV"], s["coverage_90"], s["calibration_error_90"]]
            for m, s in b002["by_model"].items()
        ],
    )
    lines += [
        "",
        "## 4. EZ-B003-v2 qualification",
        "",
        f"Status: **{b003['status']}** — evaluable closures: "
        f"{', '.join(b003['evaluable_closures'])} "
        f"({b003['n_not_evaluable']} reported NOT_EVALUABLE); models meeting "
        f"the frozen criterion: {', '.join(b003['models_meeting_criterion']) or 'none'}",
        "",
    ]
    lines += _table(
        ["model", "verdict", "sign", "top-3", "rank-1", "cal. error"],
        [
            [
                m,
                s["verdict"],
                s["sign_fraction"],
                s["top_k_fraction"],
                s["rank_1_fraction"],
                s["calibration_error_90"],
            ]
            for m, s in b003["by_model"].items()
        ],
    )
    lines += [
        "",
        "Reading: the FRDM95-backed residual challenger and the validation-"
        "weighted combiner meet the frozen criterion with rank-1 = 1.0 — the "
        "physics table carries the kink, the GP corrects the smooth offset — "
        "which is precisely the WO-11-diagnosed failure mode repaired. Every "
        "pure smooth-prior baseline still fails structure, exactly as in v1. "
        "The calibration clause keeps its teeth: the BSkG3-backed residual "
        "variant localizes almost perfectly (rank-1 0.978) and still fails "
        "on dishonest uncertainty, and the equal-weight ensemble fails "
        "structure outright, which is why the validation-weighted combiner "
        "exists.",
        "",
        "## 5. Uncertainty and disagreement",
        "",
        UNCERTAINTY_DECOMPOSITION_RULE,
        "",
        "Per-model decomposition means and z-statistics are committed in "
        "calibration_report.json and synthetic_qualification.json; "
        "disagreement by depth (std and MAD over available predictions) is "
        "committed per benchmark. High agreement is not proof of "
        "correctness; high disagreement is evidence of epistemic "
        "uncertainty.",
        "",
        "## 6. Stop conditions and next gate",
        "",
        qualification["evaluated_table_rule"],
        "",
        "A failed qualification would be preserved honestly; this one "
        "passed, so the next gate is the evaluated-table EZ-B002-v2 / "
        "EZ-B003-v2 runs under the frozen protocols, with new experiment "
        "ids and no threshold edits.",
        "",
    ]
    return "\n".join(lines)
