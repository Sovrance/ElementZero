"""WO-15 committed artifacts: qualification, fits, B004, and reproducibility."""

from __future__ import annotations

import json

import pytest

from elementzero.atlas_pin import REPO_ROOT
from elementzero.evidence.hashing import sha256_file, sha256_hex
from elementzero.physics_backends import REPORTS_RELPATH

WO15_REPORTS = REPO_ROOT / REPORTS_RELPATH
FITS = WO15_REPORTS / "fits"
EXPERIMENT = REPO_ROOT / "experiments/EZ-B004-v1"
RESULTS = REPO_ROOT / "results/EZ-B004-v1"

pytestmark = pytest.mark.skipif(
    not (WO15_REPORTS / "wo15_status.json").is_file(),
    reason="WO-15 bundle is not committed in this tree",
)


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Backend qualification                                                       #
# --------------------------------------------------------------------------- #


def test_backend_qualification_recorded():
    provenance = _load(WO15_REPORTS / "backend_provenance.json")
    assert set(provenance["solvers"]) == {"HFBTHO", "DIRHB"}
    for record in provenance["solvers"].values():
        assert len(record["archive_sha256"]) == 64
        assert record["license"]
    for qualification in provenance["qualifications"]:
        assert qualification["status"] in (
            "PHYSICS_BACKEND_QUALIFIED",
            "PHYSICS_BACKEND_REFERENCE_ONLY",
            "PHYSICS_BACKEND_NOT_REFITTABLE",
            "PHYSICS_BACKEND_PROVENANCE_INCOMPLETE",
            "PHYSICS_BACKEND_NUMERICALLY_UNSTABLE",
        )
        assert qualification["reason"]


def test_golden_cases_reproduced():
    """Both solvers reproduce their upstream-published reference output."""
    provenance = _load(WO15_REPORTS / "backend_provenance.json")
    golden = provenance["golden"]
    assert golden["HFBTHO"]["solver_ok"] is True
    assert golden["HFBTHO"]["energy_MeV"] is not None
    # DIRHB ships its own reference output; ours must match it exactly.
    assert golden["DIRHB"]["reproduced_exactly"] is True
    assert golden["DIRHB"]["expected_total_energy_MeV"] == (
        golden["DIRHB"]["observed_total_energy_MeV"]
    )


# --------------------------------------------------------------------------- #
# Historical fit integrity                                                    #
# --------------------------------------------------------------------------- #


def test_freeze_and_objective_locked():
    freeze = _load(FITS / "historical_fit_freeze.json")
    objective = _load(FITS / "objective_manifest.json")
    assert freeze["cutoff_date"] == "1995-12-01"
    assert set(freeze["allowed_dataset_hashes"]) == {"AME1995"}
    assert freeze["wo14_truth_forbidden_hashes"]
    assert objective["locked_before_fitting"] is True
    assert objective["freeze_id"] == freeze["freeze_id"]
    # The freeze hash covers its own content.
    payload = {k: v for k, v in freeze.items() if k != "freeze_hash"}
    assert sha256_hex(payload) == freeze["freeze_hash"]


def test_fit_membership_and_fit_log_hash():
    """Each refit consumed exactly the frozen calibration set."""
    freeze = _load(FITS / "historical_fit_freeze.json")
    for path in sorted(FITS.glob("parameter_artifact_*.json")):
        artifact = _load(path)
        if artifact["provenance_class"] != "REFIT_STRICT":
            continue
        assert artifact["calibration_identity_digest"] == (
            freeze["calibration_identity_digest"]
        )
        assert artifact["freeze_id"] == freeze["freeze_id"]
        backend_id = artifact["backend_id"]
        log = _load(FITS / f"fit_log_{backend_id}.json")
        assert sha256_hex(log) == artifact["fit_log_hash"]
        # Every evaluation scored the frozen calibration set and nothing else.
        for evaluation in log["evaluations"]:
            assert sorted(evaluation["residuals_keV"]) == [
                i
                for i in freeze["calibration_nuclide_ids"]
                if i not in evaluation["nonconverged_ids"]
            ]


def test_parameter_artifacts_immutable_and_schema_exact():
    from elementzero.physics_backends.artifact import assert_artifact_unchanged

    schema = _load(REPO_ROOT / "schemas/physics_parameter_artifact.schema.json")
    for path in sorted(FITS.glob("parameter_artifact_*.json")):
        artifact = _load(path)
        assert_artifact_unchanged(artifact, expected_id=artifact["artifact_id"])
        for field in schema["required"]:
            assert field in artifact, field
        assert artifact["provenance_class"] in (
            schema["properties"]["provenance_class"]["enum"]
        )


# --------------------------------------------------------------------------- #
# Independence and the two-family gate                                        #
# --------------------------------------------------------------------------- #


def test_independence_adjudication_committed():
    payload = _load(EXPERIMENT / "independence_adjudication.json")
    schema = _load(
        REPO_ROOT / "schemas/physics_independence_adjudication.schema.json"
    )
    groups = set()
    for record in payload["records"]:
        for field in schema["required"]:
            assert field in record, field
        assert record["independence_verdict"] in (
            schema["properties"]["independence_verdict"]["enum"]
        )
        groups.add(record["group_id"])
        # A shared solver is never silently dropped.
        if record["shared_solver_with"]:
            assert "correlated-numerics caveat" in record["reason"]
    assert len(groups) >= 2
    gate = payload["gate"]
    assert gate["n_blind_independent_families"] == len(
        gate["blind_independent_groups"]
    )


def test_modern_reference_family_is_not_blind_eligible():
    """The covariant family ships only post-freeze forces; it stays reference."""
    payload = _load(EXPERIMENT / "independence_adjudication.json")
    covariant = [
        r for r in payload["records"] if r["group_id"] == "covariant_rhb_edf"
    ]
    if not covariant:
        pytest.skip("covariant family is not in the committed roster")
    assert covariant[0]["blind_eligible"] is False
    assert covariant[0]["provenance_class"] == "MODERN_REFERENCE"


# --------------------------------------------------------------------------- #
# B004                                                                        #
# --------------------------------------------------------------------------- #


def test_b004_protocol_sealed_before_truth():
    protocol = _load(EXPERIMENT / "PROTOCOL.json")
    schema = _load(REPO_ROOT / "schemas/b004_protocol.schema.json")
    for field in schema["required"]:
        assert field in protocol, field
    assert protocol["truth_locked"] is True
    payload = {k: v for k, v in protocol.items() if k != "protocol_hash"}
    assert sha256_hex(payload) == protocol["protocol_hash"]
    # The legacy 150 keV value is carried as reference, never as a gate.
    assert protocol["legacy_reference_status"] == "LEGACY_INHERITED_REFERENCE"
    assert "not a gate" in protocol["performance_interpretation"]


def test_b004_targets_match_protocol():
    protocol = _load(EXPERIMENT / "PROTOCOL.json")
    targets = _load(EXPERIMENT / "target_manifest.json")
    assert targets["target_identity_digest"] == protocol["target_identity_digest"]
    assert targets["n_targets"] == protocol["n_targets"]
    assert targets["target_rule_hash"] == protocol["target_rule_hash"]


def test_b004_sealed_predictions_carry_no_truth():
    if not (RESULTS / "SEALED_PREDICTIONS.json").is_file():
        pytest.skip("B004 predictions are not sealed in this tree")
    sealed = _load(RESULTS / "SEALED_PREDICTIONS.json")
    assert sealed["state"] == "PREDICTIONS_SEALED_TARGET_TRUTH_UNREAD"
    blob = json.dumps(sealed)
    assert "truth_keV" not in blob and "error_keV" not in blob
    recorded = (
        (RESULTS / "SEALED_PREDICTIONS_SHA256").read_text(encoding="utf-8").strip()
    )
    assert recorded == sha256_file(RESULTS / "SEALED_PREDICTIONS.json")


def test_b004_unlock_and_scores_consistent():
    if not (RESULTS / "b004_scores.json").is_file():
        pytest.skip("B004 is not scored in this tree")
    scores = _load(RESULTS / "b004_scores.json")
    protocol = _load(EXPERIMENT / "PROTOCOL.json")
    unlock = _load(RESULTS / "truth_unlock.json")
    assert unlock["truth_unlocked"] is True
    assert scores["protocol_hash"] == protocol["protocol_hash"]
    for entry in scores["by_model"].values():
        n_predicted = entry["n_predicted"]
        assert 0 <= n_predicted <= entry["n_target"]
        assert abs(
            float(entry["coverage_fraction"]) - n_predicted / entry["n_target"]
        ) < 1e-9
        if entry["metrics"]:
            assert entry["metrics"]["n"] == n_predicted


def test_b004_claim_never_overreaches():
    if not (RESULTS / "claim_adjudication.json").is_file():
        pytest.skip("B004 is not adjudicated in this tree")
    record = _load(RESULTS / "claim_adjudication.json")["records"][0]
    protocol = _load(EXPERIMENT / "PROTOCOL.json")
    assert record["claim"] in protocol["claim_vocabulary"]
    assert record["visual_stage_permission"] == "BADGE_PB_ONLY_NO_STAGE_PROMOTION"
    # Only families the adjudication marked blind-eligible may be counted.
    adjudications = _load(EXPERIMENT / "independence_adjudication.json")
    blind = {
        r["group_id"]
        for r in adjudications["records"]
        if r["blind_eligible"] and r["independence_verdict"] == "INDEPENDENT"
    }
    assert set(record["blind_eligible_families_meeting_coverage"]) <= blind


# --------------------------------------------------------------------------- #
# Status, atlas, events, reproducibility                                      #
# --------------------------------------------------------------------------- #


def test_wo14_artifacts_unchanged_by_wo15():
    from elementzero.physics_backends.report import wo14_hashes

    status = _load(WO15_REPORTS / "wo15_status.json")
    live = wo14_hashes(repo_root=REPO_ROOT)
    assert status["wo14_hashes"] == live


def test_atlas_physics_fit_lineage():
    facts = _load(WO15_REPORTS / "atlas/facts.json")
    kinds = {f["content"]["kind"] for f in facts if f.get("content")}
    required = {
        "PhysicsBackendSourceFact",
        "PhysicsBuildFact",
        "PhysicsFitFreezeFact",
        "PhysicsObjectiveFact",
        "PhysicsParameterArtifactFact",
        "PhysicsConvergenceFact",
        "PhysicsFamilyQualificationFact",
        "PhysicsIndependenceAdjudicationFact",
        "B004ClaimAdjudicationFact",
    }
    assert required <= kinds, sorted(required - kinds)


def test_pf_events_are_badge_only():
    from elementzero.visuals.event_types import validate_event
    from elementzero.visuals.status import claim_checked_stage_types

    path = WO15_REPORTS / "physics_progress_events.jsonl"
    lines = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines
    for payload in lines:
        validate_event(payload)
        assert payload["event_type"] in (
            "PHYSICS_FAMILY_QUALIFIED",
            "PHYSICS_BLIND_CHALLENGE_SCORED",
        )
        assert (
            claim_checked_stage_types(
                payload["event_type"], payload["payload"], payload["benchmark_id"]
            )
            == []
        )


def test_wo15_report_reproducible(tmp_path):
    from elementzero.physics_backends.build_report import build_wo15_report

    build_wo15_report(repo_root=REPO_ROOT, out_dir=tmp_path / "out")
    for name in (
        "WO15_Refittable_Physics_Backends_Report.md",
        "wo15_status.json",
        "backend_provenance.json",
        "physics_progress_events.jsonl",
        "atlas_bundle_hashes.json",
    ):
        assert sha256_file(tmp_path / "out" / name) == sha256_file(
            WO15_REPORTS / name
        ), name
