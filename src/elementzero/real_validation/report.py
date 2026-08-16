"""WO-14 orchestration: seal -> commit -> score -> report bundle.

The work order is executed in the spec's order (section 3):

    seal_wo14()                 verify every immutable input, then seal all
                                four tracks — no truth read, no scoring
    <git commit of the seals>   recorded by record_seal_commit_wo14()
    score_wo14()                unlock truth per track (hash-verified),
                                score, adjudicate
    build_wo14_report()         deterministic report bundle from the
                                committed result trees — CI re-runs it
                                byte-for-byte

``build_wo14_report`` reads only committed artifacts, so the
wo14-reproducibility CI job can rebuild the bundle without any raw
snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.evidence.ledger import read_json
from elementzero.real_validation import REPORTS_RELPATH
from elementzero.real_validation.input_guard import verify_inputs
from elementzero.real_validation.protocol import (
    B002_BLIND_ID,
    B002_RECON_ID,
    B003_BLIND_ID,
    B003_RECON_ID,
    BLIND_PHYSICS_FAMILY,
    NO_POST_TRUTH_TUNING_RULE,
    WO14_CREATED_AT,
)
from elementzero.real_validation.runs import (
    RESULTS_DIRNAME,
    RUN_STATE_FILE,
    SEAL_RECORD_FILE,
    TRUTH_UNLOCK_FILE,
    finalize_run_state,
    record_seal_commit,
    score_b002_track,
    score_b003_blind,
    score_b003_recon,
    seal_b002_track,
    seal_b003_blind,
    seal_b003_recon,
)

WO14_EXPERIMENTS = (B002_BLIND_ID, B002_RECON_ID, B003_BLIND_ID, B003_RECON_ID)

REPORT_MARKDOWN = "WO14_Evaluated_Data_v2_Validation_Report.md"
STATUS_FILE = "wo14_status.json"
EVENTS_FILE = "real_validation_progress_events.jsonl"


# --------------------------------------------------------------------------- #
# Phase 1: seal                                                               #
# --------------------------------------------------------------------------- #


def seal_wo14(
    *,
    root: str | Path | None = None,
    experiments: tuple[str, ...] = WO14_EXPERIMENTS,
) -> dict[str, Any]:
    """Verify inputs, then seal every requested track. No truth is read."""
    root = Path(root or REPO_ROOT)
    guard = verify_inputs(repo_root=root)
    seals = {}
    for experiment_id in experiments:
        if experiment_id in (B002_BLIND_ID, B002_RECON_ID):
            seals[experiment_id] = seal_b002_track(
                root=root, experiment_id=experiment_id
            )
        elif experiment_id == B003_BLIND_ID:
            seals[experiment_id] = seal_b003_blind(root=root)
        elif experiment_id == B003_RECON_ID:
            seals[experiment_id] = seal_b003_recon(root=root)
        else:
            raise ProtocolError(f"unknown WO-14 experiment {experiment_id!r}")
    return {"input_guard": guard, "seals": seals}


def record_seal_commit_wo14(
    *, root: str | Path | None = None, commit: str
) -> dict[str, Any]:
    root = Path(root or REPO_ROOT)
    return {
        experiment_id: record_seal_commit(
            root=root, experiment_id=experiment_id, commit=commit
        )
        for experiment_id in WO14_EXPERIMENTS
    }


# --------------------------------------------------------------------------- #
# Phase 2: score                                                              #
# --------------------------------------------------------------------------- #


def score_wo14(*, root: str | Path | None = None) -> dict[str, Any]:
    """Unlock and score every track. B002-blind scores first: the recon
    track cross-references its aggregate instead of re-running baselines."""
    root = Path(root or REPO_ROOT)
    results = {
        B002_BLIND_ID: score_b002_track(root=root, experiment_id=B002_BLIND_ID),
        B002_RECON_ID: score_b002_track(root=root, experiment_id=B002_RECON_ID),
        B003_BLIND_ID: score_b003_blind(root=root),
        B003_RECON_ID: score_b003_recon(root=root),
    }
    # Terminal state before the report is built: the committed bundle then
    # embeds REPORTED, and the CI rebuild (read-only) reproduces it.
    for experiment_id in WO14_EXPERIMENTS:
        finalize_run_state(root=root, experiment_id=experiment_id)
    return results


# --------------------------------------------------------------------------- #
# Status                                                                      #
# --------------------------------------------------------------------------- #


def _results(root: Path, experiment_id: str) -> Path:
    return root / RESULTS_DIRNAME / experiment_id


def build_wo14_status(*, root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or REPO_ROOT)
    b002_blind = read_json(_results(root, B002_BLIND_ID) / "aggregate.json")
    b002_recon = read_json(_results(root, B002_RECON_ID) / "aggregate.json")
    b003_mass = read_json(_results(root, B003_BLIND_ID) / "mass_results.json")
    b003_derived = read_json(_results(root, B003_BLIND_ID) / "derived_results.json")
    b003_recon = read_json(_results(root, B003_RECON_ID) / "closure_results.json")

    met = {
        "b002_blind": b002_blind["control_blind_status"]
        == "CONTROL_BLIND_CRITERION_MET",
        "b003_mass": b003_mass["individual_mass_blind_result"]
        == "PHYSICS_BLIND_MASS_CRITERION_MET",
        "b003_recon": b003_recon["status"] == "B003_RECON_CRITERION_MET",
    }
    if all(met.values()):
        status = "ENGINEERING_PASS_SCIENTIFIC_PASS"
    elif any(met.values()):
        status = "ENGINEERING_PASS_SCIENTIFIC_MIXED"
    else:
        status = "ENGINEERING_PASS_SCIENTIFIC_NOT_MET"
    return {
        "work_order": "WO-14",
        "status": status,
        "b002_blind_status": b002_blind["control_blind_status"],
        "b002_recon_status": b002_recon["status"],
        "b003_blind_mass_status": b003_mass["individual_mass_blind_result"],
        "b003_blind_edge_status": b003_derived["edge_structure_blind_result"],
        "b003_full_shell_blind_status": b003_derived["full_shell_blind_result"],
        "b003_recon_status": b003_recon["status"],
        "next_gate": (
            "WO-15 Refittable Physics Backends and Historical Physics Fits: "
            "at least two independent physics families whose "
            "fitting/calibration can exclude benchmark targets; WO-14 alone "
            "does not authorize prediction of unknown elements"
        ),
    }


# --------------------------------------------------------------------------- #
# Visual events                                                               #
# --------------------------------------------------------------------------- #


def _write_wo14_events(out: Path, *, root: Path, status: dict[str, Any]) -> None:
    from elementzero.visuals.event_types import (
        ProgressEvent,
        make_event_id,
        validate_event,
    )

    status_hash = sha256_hex(status)
    events: list[ProgressEvent] = []

    def _emit(event_type: str, z: int, benchmark_id: str, payload: dict[str, Any]) -> None:
        event = ProgressEvent(
            event_id=make_event_id(
                event_type=event_type,
                source_hash=status_hash,
                element_Z=z,
                benchmark_id=benchmark_id,
            ),
            event_type=event_type,
            event_time=WO14_CREATED_AT,
            project_version="wo14-real-validation-v1",
            source_kind="wo14_real_validation",
            source_path=f"{REPORTS_RELPATH}/{STATUS_FILE}",
            source_hash=status_hash,
            element_Z=z,
            status="info",
            benchmark_id=benchmark_id,
            payload=payload,
        )
        validate_event(event.to_dict())
        events.append(event)

    def _target_zs(experiment_id: str) -> list[int]:
        prereg = root / "experiments" / experiment_id
        for name in ("region_targets.json", "challenge_targets.json"):
            if (prereg / name).is_file():
                groups = read_json(prereg / name)["targets"]
                ids = {t for group in groups.values() for t in group}
                return sorted(
                    {parse_nuclide_id(i)[0] for i in ids if 1 <= parse_nuclide_id(i)[0] <= 200}
                )
        raise ProtocolError(f"no preregistered targets for {experiment_id}")

    # B002 control-blind: badge CB, never a stage.
    for z in _target_zs(B002_BLIND_ID):
        _emit(
            "REAL_CONTROL_BLIND_SCORED",
            z,
            B002_BLIND_ID,
            {
                "experiment_id": B002_BLIND_ID,
                "claim_type": "STRICT_BLIND",
                "scientific_scope": "CONTROL_BLIND_GEOGRAPHIC",
                "control_blind_status": status["b002_blind_status"],
                "stage_rule": (
                    "control-only evidence: statistical baselines, zero blind "
                    "physics groups; never geographic_holdout_validated"
                ),
            },
        )
    # Reconstruction: badge R, never a stage.
    for experiment_id in (B002_RECON_ID, B003_RECON_ID):
        for z in _target_zs(experiment_id):
            _emit(
                "REAL_RECONSTRUCTION_SCORED",
                z,
                experiment_id,
                {
                    "experiment_id": experiment_id,
                    "claim_type": "RECONSTRUCTION_REFERENCE",
                    "stage_rule": "reconstruction is not rediscovery; badge only",
                },
            )
    # B003 historical-blind edge evidence: badge HB, never a stage without
    # FULL_SHELL_BLIND_CRITERION_MET.
    blind_targets = read_json(
        _results(root, B003_BLIND_ID) / "SEALED_PREDICTIONS.json"
    )["target_nuclide_ids"]
    for z in sorted({parse_nuclide_id(i)[0] for i in blind_targets}):
        _emit(
            "REAL_HISTORICAL_BLIND_EDGE_SCORED",
            z,
            B003_BLIND_ID,
            {
                "experiment_id": B003_BLIND_ID,
                "claim_type": "HISTORICAL_BLIND",
                "blind_physics_family": BLIND_PHYSICS_FAMILY,
                "mass_status": status["b003_blind_mass_status"],
                "edge_status": status["b003_blind_edge_status"],
                "blind_gate_status": status["b003_full_shell_blind_status"],
                "stage_rule": (
                    "edge evidence never promotes shell_rediscovery_validated "
                    "unless FULL_SHELL_BLIND_CRITERION_MET"
                ),
            },
        )
    lines = [json.dumps(e.to_dict(), sort_keys=True) for e in events]
    (out / EVENTS_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Atlas provenance chain (spec section 17)                                    #
# --------------------------------------------------------------------------- #


def _build_atlas_lineage(
    *, root: Path, out_dir: Path, status: dict[str, Any]
) -> dict[str, str]:
    from elementzero.evidence.atlas_adapter import (
        NUCLEAR_MASS_INTERFACE,
        AtlasEvidenceAdapter,
        EvidenceLevel,
        Fact,
        FactStatus,
        Layer,
        Namespace,
        PirLevel,
        Warning_,
        _heuristic_analyzer,
        compute_fact_id,
        write_atlas_bundle,
    )

    adapter = AtlasEvidenceAdapter(created_at=WO14_CREATED_AT)
    facts: list[Fact] = []
    provenance_records: list[Any] = []

    warning = (
        "WO-14 real validation: claims are bounded by the committed WO-13 "
        "eligibility; reconstruction is never rediscovery and control-only "
        "evidence is never physics validation"
    )

    def _fact(content: dict[str, Any], assumptions: tuple[str, ...]) -> Fact:
        analyzer = _heuristic_analyzer()
        fact = Fact(
            fact_id=compute_fact_id(content, analyzer, assumptions=assumptions),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E3,
            layer=Layer.MEASUREMENT,
            namespace=Namespace.analyst,
            status=FactStatus.SUPPORTED,
            analyzer=analyzer,
            content=content,
            created_at=WO14_CREATED_AT,
            assumptions=assumptions,
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=(
                Warning_(
                    location=f"real_validation:{content['experiment_id']}",
                    message=warning,
                ),
            ),
        )
        adapter.append_fact(fact)
        facts.append(fact)
        provenance_records.append(
            adapter.append_provenance(
                entity=fact.fact_id,
                activity_type="ANALYZE",
                used=tuple(
                    a.split("fact:", 1)[1]
                    for a in assumptions
                    if a.startswith("fact:")
                ),
                generated=(fact.fact_id,),
            )
        )
        return fact

    for experiment_id in WO14_EXPERIMENTS:
        dest = _results(root, experiment_id)
        run_state = read_json(dest / RUN_STATE_FILE)
        seal_record = read_json(dest / SEAL_RECORD_FILE)
        unlock = read_json(dest / TRUTH_UNLOCK_FILE)
        adjudications = read_json(dest / "claim_adjudication.json")["records"]
        derived_hash = seal_record.get("derived_blindness_hash")

        protocol_fact = _fact(
            {
                "kind": "RealValidationProtocolFact",
                "experiment_id": experiment_id,
                "claim_track": run_state["claim_track"],
                "run_id": run_state["run_id"],
                "protocol_hash": run_state["protocol_hash"],
                "roster": seal_record["roster"],
                "seal_input_rule": seal_record["seal_input_rule"],
                "no_post_truth_tuning_rule": NO_POST_TRUTH_TUNING_RULE,
            },
            (f"experiment:{experiment_id}",),
        )
        eligibility_fact = _fact(
            {
                "kind": "EligibilityManifestFact",
                "experiment_id": experiment_id,
                "eligibility_manifest_hash": run_state["eligibility_manifest_hash"],
            },
            (f"fact:{protocol_fact.fact_id}",),
        )
        subfed_fact = _fact(
            {
                "kind": "BlindSubfederationFact",
                "experiment_id": experiment_id,
                "claim_track": run_state["claim_track"],
                "roster": seal_record["roster"],
                "coverage_excluded_models": seal_record["coverage_audit"][
                    "excluded_models"
                ],
            },
            (f"fact:{eligibility_fact.fact_id}",),
        )
        prediction_fact = _fact(
            {
                "kind": "PredictionSetFact",
                "experiment_id": experiment_id,
                "prediction_seal_hash": run_state["prediction_seal_hash"],
            },
            (f"fact:{subfed_fact.fact_id}",),
        )
        finalization_fact = _fact(
            {
                "kind": "FinalizationFact",
                "experiment_id": experiment_id,
                "seal_commit": seal_record["seal_commit"],
                "state": run_state["state"],
            },
            (f"fact:{prediction_fact.fact_id}",),
        )
        unlock_fact = _fact(
            {
                "kind": "TruthUnlockFact",
                "experiment_id": experiment_id,
                "verified": unlock["verified"],
            },
            (f"fact:{finalization_fact.fact_id}",),
        )
        score_fact = _fact(
            {
                "kind": "ScoreFact",
                "experiment_id": experiment_id,
                "status": {
                    B002_BLIND_ID: status["b002_blind_status"],
                    B002_RECON_ID: status["b002_recon_status"],
                    B003_BLIND_ID: status["b003_blind_mass_status"],
                    B003_RECON_ID: status["b003_recon_status"],
                }[experiment_id],
            },
            (f"fact:{unlock_fact.fact_id}",),
        )
        upstream = score_fact
        if experiment_id == B003_BLIND_ID:
            upstream = _fact(
                {
                    "kind": "DerivedBlindnessFact",
                    "experiment_id": experiment_id,
                    "derived_blindness_hash": derived_hash,
                    "edge_status": status["b003_blind_edge_status"],
                    "full_shell_status": status["b003_full_shell_blind_status"],
                },
                (f"fact:{score_fact.fact_id}",),
            )
        for adjudication in adjudications:
            _fact(
                {
                    "kind": "ClaimAdjudicationFact",
                    "experiment_id": experiment_id,
                    "claim_type": adjudication["claim_type"],
                    "scientific_scope": adjudication["scientific_scope"],
                    "eligibility_manifest_hash": run_state[
                        "eligibility_manifest_hash"
                    ],
                    "derived_blindness_hash": derived_hash,
                    "prediction_seal_hash": adjudication["prediction_seal_hash"],
                    "blind_gate_status": adjudication["blind_gate_status"],
                    "visual_stage_permission": adjudication[
                        "visual_stage_permission"
                    ],
                },
                (f"fact:{upstream.fact_id}",),
            )

    return write_atlas_bundle(
        out_dir,
        stage="predict",
        facts=facts,
        provenance=provenance_records,
        artifacts=(),
        events=(),
    )


# --------------------------------------------------------------------------- #
# Report bundle                                                               #
# --------------------------------------------------------------------------- #


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def _model_table(by_model: dict[str, Any], *, key: str = "pooled") -> list[str]:
    columns = (
        "n",
        "MAE_keV",
        "MedAE_keV",
        "RMSE_keV",
        "NLPD",
        "coverage_90",
        "coverage_95",
        "cal_error_90",
    )
    lines = [
        "| model_id | " + " | ".join(columns) + " |",
        "| --- | " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for model_id, payload in sorted(by_model.items()):
        pooled = payload[key] if key in payload else payload
        lines.append(
            f"| {model_id} | "
            + " | ".join(_fmt(pooled.get(c)) for c in columns)
            + " |"
        )
    return lines


def build_wo14_report(
    *, root: str | Path | None = None, out_dir: str | Path | None = None
) -> dict[str, Any]:
    """The committed report bundle, rebuilt deterministically from results."""
    root = Path(root or REPO_ROOT)
    out = Path(out_dir) if out_dir is not None else root / REPORTS_RELPATH
    out.mkdir(parents=True, exist_ok=True)

    guard = verify_inputs(repo_root=root)
    status = build_wo14_status(root=root)
    (out / STATUS_FILE).write_text(canonical_json(status) + "\n", encoding="utf-8")
    _write_wo14_events(out, root=root, status=status)
    # write_atlas_bundle appends its own atlas/ directory under out.
    atlas_hashes = _build_atlas_lineage(root=root, out_dir=out, status=status)
    (out / "atlas_bundle_hashes.json").write_text(
        canonical_json(atlas_hashes) + "\n", encoding="utf-8"
    )

    b002_blind = read_json(_results(root, B002_BLIND_ID) / "aggregate.json")
    b002_recon = read_json(_results(root, B002_RECON_ID) / "aggregate.json")
    b003_mass = read_json(_results(root, B003_BLIND_ID) / "mass_results.json")
    b003_derived = read_json(_results(root, B003_BLIND_ID) / "derived_results.json")
    b003_audit = read_json(_results(root, B003_BLIND_ID) / "derived_blindness.json")
    b003_recon = read_json(_results(root, B003_RECON_ID) / "closure_results.json")
    seal_records = {
        experiment_id: read_json(_results(root, experiment_id) / SEAL_RECORD_FILE)
        for experiment_id in WO14_EXPERIMENTS
    }
    adjudications = {
        experiment_id: read_json(
            _results(root, experiment_id) / "claim_adjudication.json"
        )["records"]
        for experiment_id in WO14_EXPERIMENTS
    }

    lines: list[str] = [
        "# WO-14 — Evaluated Data v2 Validation",
        "",
        f"Work order status: **{status['status']}**",
        "",
        "## 1. Input integrity",
        "",
        f"Every pinned input re-hashed unchanged ({len(guard['pinned_files'])} "
        "files), the v1 evidence inventory is unchanged, and the WO-12 "
        "registry and protocol hashes match their frozen values.",
        "",
        f"- WO-12 registry hash: `{guard['wo12_registry_hash']}`",
        f"- WO-12 protocol hash: `{guard['wo12_protocol_hash']}`",
        "",
        "## 2. Frozen protocol and threshold confirmation",
        "",
        "The inherited thresholds are the frozen EZ-B002-v2 gate and the "
        "frozen EZ-B003-v2 rediscovery criterion, hash-asserted at truth "
        "unlock on every track. No new real-data threshold was invented; "
        "meeting an inherited criterion on real data is labeled "
        "INHERITED_SYNTHETIC_QUALIFICATION_CRITERION, never a universal "
        "real-world standard.",
        "",
        "## 3. B002 REAL-BLIND protocol",
        "",
        "60 preregistered targets in 3 regions; roster = the 4 "
        "freeze-controlled statistical baselines the committed WO-13 blind "
        "subfederation admits. Zero blind physics groups: control-only "
        "evidence by construction. Predictions were sealed and committed "
        f"(commit `{seal_records[B002_BLIND_ID]['seal_commit']}`) before "
        "any truth was read.",
        "",
        "## 4. B002 REAL-BLIND results",
        "",
        f"Status: **{status['b002_blind_status']}** — best baseline "
        f"`{b002_blind['best_baseline']}`, inherited gate met: "
        f"{b002_blind['inherited_gate_met']}.",
        "",
        *_model_table(b002_blind["by_model"]),
        "",
        "federation_improved_over_baseline: "
        f"{b002_blind['federation_improved_over_baseline']}",
        "",
        "## 5. B002 REAL-RECON results",
        "",
        f"Status: **{b002_recon['status']}**. Roster = the BSkG3 lineage "
        "the committed WO-13 claim facts admit on every target; the FRDM95 "
        "lineage is INELIGIBLE_UNKNOWN_PROVENANCE outside its 12 blind "
        "targets and no combiner can hide that ineligible contributor.",
        "",
        *_model_table(b002_recon["by_model"]),
        "",
        f"- best baseline (cross-referenced from the blind track): "
        f"`{b002_recon['best_baseline_model']['model_id']}` "
        f"(MAE {_fmt(b002_recon['best_baseline_model']['MAE_keV'])} keV)",
        f"- best physics table: `{b002_recon['best_physics_table_model']['model_id']}` "
        f"(MAE {_fmt(b002_recon['best_physics_table_model']['MAE_keV'])} keV)",
        f"- best residual physics: `{b002_recon['best_residual_physics_model']['model_id']}` "
        f"(MAE {_fmt(b002_recon['best_residual_physics_model']['MAE_keV'])} keV)",
        f"- best combined: {b002_recon['best_combined_model']['status']}",
        f"- reconstruction improved over best baseline: "
        f"{b002_recon['reconstruction_federation_improved_over_best_baseline']}",
        "",
        "## 6. B002 claim adjudication",
        "",
        f"- blind: scope `{adjudications[B002_BLIND_ID][0]['scientific_scope']}`, "
        f"claim `{adjudications[B002_BLIND_ID][0]['claim_type']}`, visual "
        f"`{adjudications[B002_BLIND_ID][0]['visual_stage_permission']}`",
        f"- recon: scope `{adjudications[B002_RECON_ID][0]['scientific_scope']}`, "
        f"claim `{adjudications[B002_RECON_ID][0]['claim_type']}`, visual "
        f"`{adjudications[B002_RECON_ID][0]['visual_stage_permission']}`",
        "",
        "## 7. B003 REAL-BLIND eligibility",
        "",
        f"12 historically blind central targets; one blind physics family "
        f"(`{BLIND_PHYSICS_FAMILY}`). The 4 statistical baselines run as "
        "freeze-controlled comparators, not independent physics.",
        "",
        "Targets: " + ", ".join(f"`{t}`" for t in b003_mass["per_target"][
            next(iter(b003_mass["per_target"]))
        ]),
        "",
        "## 8. Derived-observable blindness audit",
        "",
        b003_audit["summary"]["rule"],
        "",
        f"- records: {b003_audit['summary']['n_records']}",
        f"- blind-eligible: {b003_audit['summary']['n_blind_eligible']} "
        f"({', '.join(b003_audit['summary']['blind_eligible_ids']) or 'none'})",
        f"- full-shell eligible: {b003_audit['summary']['n_full_shell_eligible']}",
        "",
        "## 9. B003 blind mass results",
        "",
        f"Status: **{status['b003_blind_mass_status']}** — best blind-family "
        f"model `{b003_mass['best_blind_family_model']}`; criterion "
        f"{_fmt(b003_mass['inherited_criterion']['observed_MAE_keV'])} keV MAE vs "
        f"{_fmt(b003_mass['inherited_criterion']['max_MAE_keV'])} keV allowed "
        f"({b003_mass['inherited_criterion']['label']}).",
        "",
        *_model_table(b003_mass["by_model"], key="metrics"),
        "",
        "## 10. B003 edge-structure results",
        "",
        f"Status: **{status['b003_blind_edge_status']}** over "
        f"{len(b003_derived['edge_rows'])} blind-eligible derived rows.",
        "",
    ]
    if b003_derived["edge_rows"]:
        lines.extend(
            [
                "| observable | central | model | predicted MeV | truth MeV | "
                "error MeV | sign recovered |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in b003_derived["edge_rows"]:
            lines.append(
                f"| {row['observable']} | {row['central_nuclide_id']} | "
                f"{row['model_id']} | {_fmt(row['predicted_MeV'])} | "
                f"{_fmt(row['truth_MeV'])} | {_fmt(row['error_MeV'])} | "
                f"{row['sign_recovered']} |"
            )
    lines.extend(
        [
            "",
            "## 11. Full-shell blind evaluability",
            "",
            f"**{status['b003_full_shell_blind_status']}** — "
            + b003_derived["rule"],
            "",
            "## 12. B003 REAL-RECON results",
            "",
            f"Status: **{status['b003_recon_status']}**; models meeting the "
            f"frozen criterion: "
            f"{', '.join(b003_recon['models_meeting_criterion']) or 'none'}.",
            "",
            "| model_id | verdict | sign | top-k | rank-1 | cal_err_90 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for model_id, payload in sorted(b003_recon["by_model"].items()):
        checks = payload["checks"]
        lines.append(
            f"| {model_id} | {payload['verdict']} | "
            f"{_fmt(checks['sign_fraction']['observed'])} | "
            f"{_fmt(checks['top_k_fraction']['observed'])} | "
            f"{_fmt(checks['rank_1_fraction']['observed'])} | "
            f"{_fmt(checks['calibration_error_90']['observed'])} |"
        )
    lines.extend(
        [
            "",
            b003_recon["rule"],
            "",
            "## 13. Visual-state effects",
            "",
            "- B002 control-blind: badge `CB` only; the primary stage never "
            "becomes geographic_holdout_validated from control-only evidence.",
            "- B002/B003 reconstruction: badge `R` only; no stage promotion.",
            "- B003 historical-blind edge: badge `HB` only; "
            "shell_rediscovery_validated additionally requires "
            "FULL_SHELL_BLIND_CRITERION_MET, which this run did not earn.",
            "",
            "## 14. Atlas provenance",
            "",
            "Each track carries the chain RealValidationProtocolFact -> "
            "EligibilityManifestFact -> BlindSubfederationFact -> "
            "PredictionSetFact -> FinalizationFact -> TruthUnlockFact -> "
            "ScoreFact -> (DerivedBlindnessFact) -> ClaimAdjudicationFact "
            "under reports/real_validation/wo14/atlas.",
            "",
            "## 15. Limitations",
            "",
            "- One blind physics family only; no second independent family.",
            "- The 12 historical-blind targets are a small post-fit subset "
            "around otherwise established shell regions: edge evidence, not "
            "shell rediscovery.",
            "- B002 blind evidence is statistical-baseline extrapolation "
            "on interior holdouts, not physics validation.",
            "- Reconstruction results are reference descriptions of known "
            "structure.",
            f"- {NO_POST_TRUTH_TUNING_RULE}",
            "",
            "## 16. Allowed claims",
            "",
            "- Blind statistical geographic extrapolation on preregistered "
            "real holdout regions (control scope).",
            "- One historical-blind global physics family scored on 12 "
            "post-1995 targets (mass edge, plus 2 blind S2n edge "
            "observables).",
            "- Reconstruction reference quality of the BSkG3 lineage on "
            "known geographic regions and known shell structure.",
            "",
            "## 17. Prohibited claims",
            "",
            "- PHYSICS_BLIND_GEOGRAPHIC_VALIDATION or "
            "FEDERATED_BLIND_GEOGRAPHIC_VALIDATION from B002 control-blind "
            "evidence.",
            "- FULL_BLIND_SHELL_REDISCOVERY (not evaluable with this target "
            "set).",
            "- BLIND_REDISCOVERY_CRITERION_MET from any reconstruction run.",
            "- Any claim about unknown or superheavy elements.",
            "",
            "## 18. Next gate",
            "",
            status["next_gate"] + ".",
            "",
        ]
    )
    (out / REPORT_MARKDOWN).write_text("\n".join(lines), encoding="utf-8")

    from elementzero.experiments.runner import write_sha256sums

    write_sha256sums(out)
    return {"status": status, "out_dir": str(out), "atlas": atlas_hashes}
