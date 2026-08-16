"""WO-14 committed result trees: sealed-before-scored ordering, roster
eligibility, honest statuses, atlas lineage, and byte reproducibility."""

from __future__ import annotations

import json

from elementzero.atlas_pin import REPO_ROOT
from elementzero.evidence.hashing import sha256_file
from elementzero.real_validation import REPORTS_RELPATH
from elementzero.real_validation.prediction_seal import read_seal_hash

RESULTS = REPO_ROOT / "results"
WO14_REPORTS = REPO_ROOT / REPORTS_RELPATH

B002_BLIND = RESULTS / "EZ-B002-v2-real-blind"
B002_RECON = RESULTS / "EZ-B002-v2-real-recon"
B003_BLIND = RESULTS / "EZ-B003-v2-real-blind"
B003_RECON = RESULTS / "EZ-B003-v2-real-recon"
ALL_TRACKS = (B002_BLIND, B002_RECON, B003_BLIND, B003_RECON)

CONTROLS = {
    "EZ-SEMF-LS-v1",
    "EZ-GP-DIRECT-v1",
    "EZ-SEMF-GP-RESIDUAL-v1",
    "EZ-GP-OPTIMIZED-CONTROL-v1",
}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Required trees, sealing order                                               #
# --------------------------------------------------------------------------- #


def test_required_result_trees_exist():
    required = {
        B002_BLIND: ("aggregate.json", "model_comparison.json"),
        B002_RECON: ("aggregate.json", "model_comparison.json"),
        B003_BLIND: (
            "mass_results.json",
            "derived_results.json",
            "derived_blindness.json",
        ),
        B003_RECON: ("closure_results.json", "model_comparison.json"),
    }
    for tree, names in required.items():
        for name in names + (
            "claim_adjudication.json",
            "SEALED_PREDICTIONS.json",
            "SHA256SUMS.txt",
            "wo14_run_state.json",
            "wo14_seal_record.json",
            "truth_unlock.json",
        ):
            assert (tree / name).is_file(), f"{tree.name}/{name}"


def test_recon_predictions_still_sealed():
    # Every track's sealed predictions still hash to their recorded value,
    # and the run state carries that same hash end-to-end.
    for tree in ALL_TRACKS:
        seal_hash = read_seal_hash(tree)
        run_state = _load(tree / "wo14_run_state.json")
        assert run_state["prediction_seal_hash"] == seal_hash
        assert run_state["state"] == "REPORTED"
        assert run_state["truth_unlocked"] is True
        assert run_state["claim_adjudicated"] is True
        for record in _load(tree / "claim_adjudication.json")["records"]:
            assert record["prediction_seal_hash"] == seal_hash


def test_seal_commit_recorded_before_scoring():
    for tree in ALL_TRACKS:
        seal_record = _load(tree / "wo14_seal_record.json")
        commit = seal_record["seal_commit"]
        assert isinstance(commit, str) and len(commit) == 40, tree.name
        unlock = _load(tree / "truth_unlock.json")
        assert unlock["truth_unlocked"] is True
        assert (
            unlock["verified"]["prediction_seal_hash"]
            == _load(tree / "wo14_run_state.json")["prediction_seal_hash"]
        )


def test_blind_workspaces_contain_no_target_truth():
    # B002 blind: every committed targets.json is identity-only.
    for targets_path in sorted(B002_BLIND.glob("regions/*/targets.json")):
        for target in _load(targets_path)["targets"]:
            assert "mass_excess_keV" not in target
            assert set(target) <= {"nuclide_id", "Z", "N", "A", "element"}
    # B003 blind: the sealed payload carries predictions and identities only.
    sealed = _load(B003_BLIND / "SEALED_PREDICTIONS.json")
    assert "truth" not in json.dumps(sorted(sealed)).lower()
    assert sealed["state"] == "PREDICTIONS_SEALED_TARGET_TRUTH_UNREAD"


# --------------------------------------------------------------------------- #
# B002 rosters and claims                                                     #
# --------------------------------------------------------------------------- #


def test_b002_blind_uses_only_eligible_controls():
    sealed = _load(B002_BLIND / "SEALED_PREDICTIONS.json")
    assert set(sealed["model_ids"]) == CONTROLS
    aggregate = _load(B002_BLIND / "aggregate.json")
    assert set(aggregate["by_model"]) == CONTROLS
    assert aggregate["federation_improved_over_baseline"] == (
        "NOT_EVALUABLE_FOR_BLIND_B002"
    )


def test_b002_blind_has_zero_physics_groups():
    records = _load(B002_BLIND / "claim_adjudication.json")["records"]
    assert len(records) == 1
    record = records[0]
    assert record["physics_independence_groups"] == []
    assert record["scientific_scope"] == "CONTROL_BLIND_GEOGRAPHIC"
    assert record["claim_type"] == "STRICT_BLIND"
    assert record["visual_stage_permission"] == (
        "BADGE_CB_ONLY_NO_STAGE_PROMOTION"
    )


def test_b002_recon_claims_reference_only():
    sealed = _load(B002_RECON / "SEALED_PREDICTIONS.json")
    assert set(sealed["model_ids"]) == {
        "EZ-BSKG3-TABLE-v1",
        "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",
    }
    records = _load(B002_RECON / "claim_adjudication.json")["records"]
    assert len(records) == 1
    record = records[0]
    assert record["claim_track"] == "RECONSTRUCTION"
    assert record["claim_type"] == "RECONSTRUCTION_REFERENCE"
    assert record["scientific_scope"] == "RECONSTRUCTION_GEOGRAPHIC"
    # The FRDM lineage and both combiners are recorded exclusions.
    assert {
        "EZ-FRDM95-TABLE-v1",
        "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
        "EZ-FED-UNIFORM-ENSEMBLE-v1",
        "EZ-FED-VALIDATION-WEIGHTED-v1",
    } <= set(record["excluded_model_ids"])


def test_b002_improvement_flag_not_fabricated():
    aggregate = _load(B002_RECON / "aggregate.json")
    blind = _load(B002_BLIND / "aggregate.json")
    baseline_mae = min(
        float(payload["pooled"]["MAE_keV"]) for payload in blind["by_model"].values()
    )
    recon_mae = min(
        float(payload["pooled"]["MAE_keV"])
        for payload in aggregate["by_model"].values()
    )
    expected = recon_mae < baseline_mae
    assert (
        aggregate["reconstruction_federation_improved_over_best_baseline"]
        == expected
    )
    comparison = aggregate["improvement_comparison"]
    assert float(comparison["reconstruction_MAE_keV"]) == recon_mae
    assert float(comparison["baseline_MAE_keV"]) == baseline_mae
    # No eligible combiner exists on this track; the report must say so
    # rather than invent a value.
    assert aggregate["best_combined_model"]["status"] == (
        "NOT_RUN_NO_ELIGIBLE_COMBINER"
    )


# --------------------------------------------------------------------------- #
# B003 blind targets, family, and derived audit                               #
# --------------------------------------------------------------------------- #


def test_b003_blind_uses_only_historical_blind_targets():
    subfed = _load(
        REPO_ROOT / "reports/eligibility/wo13/subfederation_summary.json"
    )
    expected = sorted(
        t["target_id"]
        for t in subfed["manifests"]["EZ-B003-v2-real-blind"]["targets"]
        if t["tier"] == "PHYSICS_BLIND_EVALUABLE"
    )
    sealed = _load(B003_BLIND / "SEALED_PREDICTIONS.json")
    assert sealed["target_nuclide_ids"] == expected
    assert len(expected) == 12
    # The training corpus excluded every target.
    assert sealed["n_training"] > 0
    for rows in sealed["predictions"].values():
        assert sorted(rows) == expected


def test_b003_blind_physics_group_is_frdm():
    records = _load(B003_BLIND / "claim_adjudication.json")["records"]
    for record in records:
        assert record["physics_independence_groups"] == [
            "macroscopic_microscopic_frdm"
        ]
        assert record["claim_type"] == "HISTORICAL_BLIND"
        assert record["visual_stage_permission"] == (
            "BADGE_HB_ONLY_NO_STAGE_PROMOTION"
        )
    scopes = {record["scientific_scope"] for record in records}
    assert "PHYSICS_BLIND_MASS_EDGE" in scopes
    assert "FULL_BLIND_SHELL_REDISCOVERY" not in scopes


def test_b003_edge_not_equal_full_shell_rediscovery():
    derived = _load(B003_BLIND / "derived_results.json")
    assert derived["edge_structure_blind_result"] == (
        "PHYSICS_BLIND_EDGE_VALIDATION"
    )
    assert derived["full_shell_blind_result"] == "FULL_SHELL_BLIND_NOT_EVALUABLE"
    audit = _load(B003_BLIND / "derived_blindness.json")
    assert audit["summary"]["full_shell_blind_evaluable"] is False
    assert audit["summary"]["blind_eligible_ids"] == [
        "S2n:Z81-N132",
        "S2n:Z82-N98",
    ]
    # Every edge row scored used only blind-predicted components.
    for row in derived["edge_rows"]:
        assert row["all_components_predicted_blind"] is True
    # The sealed derived-blindness audit is the one that was scored.
    sealed = _load(B003_BLIND / "SEALED_PREDICTIONS.json")
    assert sealed["derived_blindness_hash"] == sha256_file(
        B003_BLIND / "derived_blindness.json"
    )


def test_b003_recon_never_claims_blind_rediscovery():
    closure = _load(B003_RECON / "closure_results.json")
    assert closure["status"] in (
        "B003_RECON_CRITERION_MET",
        "B003_RECON_CRITERION_NOT_MET",
    )
    assert "BLIND" not in closure["status"]
    for payload in closure["by_model"].values():
        assert payload["recon_status"] in (
            "RECONSTRUCTION_CRITERION_MET",
            "RECONSTRUCTION_CRITERION_NOT_MET",
        )
    records = _load(B003_RECON / "claim_adjudication.json")["records"]
    assert records[0]["scientific_scope"] == "RECONSTRUCTION_SHELL_STRUCTURE"
    assert records[0]["claim_type"] == "RECONSTRUCTION_REFERENCE"


# --------------------------------------------------------------------------- #
# Adjudication schema, status, atlas, events                                  #
# --------------------------------------------------------------------------- #


def test_claim_adjudication_schema():
    schema = _load(REPO_ROOT / "schemas/claim_adjudication.schema.json")
    required = set(schema["required"])
    scopes = set(schema["properties"]["scientific_scope"]["enum"])
    tracks = set(schema["properties"]["claim_track"]["enum"])
    for tree in ALL_TRACKS:
        for record in _load(tree / "claim_adjudication.json")["records"]:
            assert set(record) == required, tree.name
            assert record["scientific_scope"] in scopes
            assert record["claim_track"] in tracks
            for key in required:
                assert record[key] is not None


def test_wo14_status_schema_and_honesty():
    schema = _load(REPO_ROOT / "schemas/wo14_status.schema.json")
    status = _load(WO14_REPORTS / "wo14_status.json")
    assert set(status) == set(schema["required"])
    assert status["work_order"] == "WO-14"
    assert status["status"] in (
        "ENGINEERING_PASS_SCIENTIFIC_PASS",
        "ENGINEERING_PASS_SCIENTIFIC_MIXED",
        "ENGINEERING_PASS_SCIENTIFIC_NOT_MET",
        "ENGINEERING_PASS_GATE_NOT_EVALUABLE",
    )
    # Statuses re-derive from the committed result trees.
    assert status["b002_blind_status"] == (
        _load(B002_BLIND / "aggregate.json")["control_blind_status"]
    )
    assert status["b003_blind_mass_status"] == (
        _load(B003_BLIND / "mass_results.json")["individual_mass_blind_result"]
    )
    assert status["b003_full_shell_blind_status"] == (
        _load(B003_BLIND / "derived_results.json")["full_shell_blind_result"]
    )
    assert status["b003_recon_status"] == (
        _load(B003_RECON / "closure_results.json")["status"]
    )


def test_atlas_claim_lineage():
    facts = []
    atlas_dir = WO14_REPORTS / "atlas"
    for path in sorted(atlas_dir.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                facts.append(json.loads(line))
    contents = [f["content"] for f in facts if "content" in f]
    kinds = {c.get("kind") for c in contents}
    assert {
        "RealValidationProtocolFact",
        "EligibilityManifestFact",
        "BlindSubfederationFact",
        "PredictionSetFact",
        "FinalizationFact",
        "TruthUnlockFact",
        "ScoreFact",
        "DerivedBlindnessFact",
        "ClaimAdjudicationFact",
    } <= kinds
    adjudication_facts = [
        c for c in contents if c.get("kind") == "ClaimAdjudicationFact"
    ]
    assert adjudication_facts
    for content in adjudication_facts:
        for key in (
            "claim_type",
            "scientific_scope",
            "eligibility_manifest_hash",
            "prediction_seal_hash",
        ):
            assert content[key], key
        assert "derived_blindness_hash" in content


def test_wo14_events_are_claim_checked():
    from elementzero.visuals.event_types import validate_event
    from elementzero.visuals.status import claim_checked_stage_types

    events_path = WO14_REPORTS / "real_validation_progress_events.jsonl"
    lines = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines
    for payload in lines:
        validate_event(payload)
        assert payload["event_type"] in (
            "REAL_CONTROL_BLIND_SCORED",
            "REAL_RECONSTRUCTION_SCORED",
            "REAL_HISTORICAL_BLIND_EDGE_SCORED",
        )
        # None of the committed WO-14 events may grant a validated stage.
        assert (
            claim_checked_stage_types(
                payload["event_type"], payload["payload"], payload["benchmark_id"]
            )
            == []
        )


def test_real_result_trees_never_feed_generic_visual_hooks():
    from elementzero.visuals.ingest import extract_events

    events, _health, _hashes = extract_events(REPO_ROOT)
    stage_granting = {"REGION_VALIDATION_SCORED", "SHELL_VALIDATION_SCORED"}
    real_trees = tuple(str(tree) for tree in ALL_TRACKS)
    for event in events:
        if event.event_type in stage_granting:
            assert not str(event.source_path).startswith(
                ("results/EZ-B002-v2-real", "results/EZ-B003-v2-real")
            ), event.source_path
        assert not str(event.source_path).startswith(real_trees)


def test_wo14_report_reproducible(tmp_path):
    from elementzero.real_validation.report import build_wo14_report

    build_wo14_report(root=REPO_ROOT, out_dir=tmp_path / "out")
    for name in (
        "WO14_Evaluated_Data_v2_Validation_Report.md",
        "wo14_status.json",
        "real_validation_progress_events.jsonl",
        "atlas_bundle_hashes.json",
    ):
        assert sha256_file(tmp_path / "out" / name) == sha256_file(
            WO14_REPORTS / name
        ), name
