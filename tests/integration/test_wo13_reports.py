"""WO-13 committed artifacts: chronology, claim tracks, firewall, lineage,
and byte reproducibility (stage B needs no raw tables)."""

from __future__ import annotations

import json

from elementzero.atlas_pin import REPO_ROOT
from elementzero.eligibility import REPORTS_RELPATH
from elementzero.eligibility.historical_sources import (
    HISTORICAL_SOURCES,
    SOURCE_ORDER,
    SourceChronology,
    snapshots_available,
)
from elementzero.evidence.hashing import sha256_file

WO13_REPORTS = REPO_ROOT / REPORTS_RELPATH

COMMITTED_FILES = (
    "input_baseline.json",
    "historical_source_chronology.json",
    "model_training_provenance.json",
    "target_eligibility_matrix.json",
    "subfederation_summary.json",
    "b002_real_claim_plan.json",
    "b003_real_claim_plan.json",
    "wo13_gate_status.json",
    "WO13_Real_Data_Blindness_Report.md",
)


def _load(name: str):
    return json.loads((WO13_REPORTS / name).read_text(encoding="utf-8"))


def test_historical_source_chronology():
    payload = _load("historical_source_chronology.json")
    assert payload["source_order"] == list(SOURCE_ORDER)
    from elementzero.evidence.freezes import identity_digest

    for source_id in SOURCE_ORDER:
        entry = payload["sources"][source_id]
        assert entry["raw_sha256"] == HISTORICAL_SOURCES[source_id]["raw_sha256"]
        assert entry["release_date"] == HISTORICAL_SOURCES[source_id]["release_date"]
        # The committed digests re-derive from the committed identity lists.
        assert entry["normalized_identity_digest"] == identity_digest(
            entry["known_nuclide_ids"]
        )
        assert entry["eligible_identity_digest"] == identity_digest(
            entry["eligible_nuclide_ids"]
        )
        assert entry["n_eligible"] <= entry["n_known"]
    chronology = SourceChronology(payload)
    # 208Pb was evaluated evidence in every snapshot; chronology answers
    # from parsed membership, never from Z/A ranges.
    for source_id in SOURCE_ORDER:
        assert chronology.was_target_eligible_by("Z82-N126", source_id)
    # Evidence grows across editions.
    counts = [payload["sources"][s]["n_eligible"] for s in SOURCE_ORDER]
    assert counts == sorted(counts)
    # When the raw snapshots are present, the committed chronology must be
    # exactly what re-parsing produces.
    if snapshots_available():
        from elementzero.eligibility.historical_sources import build_chronology
        from elementzero.evidence.hashing import canonical_json

        assert canonical_json(build_chronology()) == canonical_json(payload)


def test_b002_blind_recon_tracks_separated():
    plan = _load("b002_real_claim_plan.json")
    blind, recon = plan["blind"], plan["reconstruction"]
    assert blind["claim_track"] == "BLIND" and blind["strict_gate"] is True
    assert recon["claim_track"] == "RECONSTRUCTION" and recon["strict_gate"] is False
    assert set(blind["allowed_claim_types"]) == {"STRICT_BLIND", "HISTORICAL_BLIND"}
    assert set(blind["allowed_claim_types"]).isdisjoint(recon["allowed_claim_types"])
    for experiment_id in ("EZ-B002-v2-real-blind", "EZ-B002-v2-real-recon"):
        directory = REPO_ROOT / "experiments" / experiment_id
        assert (directory / "claim_manifest.json").is_file()
        assert (directory / "PREREGISTRATION.md").is_file()
        assert (directory / "regions.json").is_file()


def test_b003_blind_recon_tracks_separated():
    plan = _load("b003_real_claim_plan.json")
    assert plan["blind"]["claim_track"] == "BLIND"
    assert plan["reconstruction"]["claim_track"] == "RECONSTRUCTION"
    for experiment_id in ("EZ-B003-v2-real-blind", "EZ-B003-v2-real-recon"):
        directory = REPO_ROOT / "experiments" / experiment_id
        assert (directory / "claim_manifest.json").is_file()
        assert (directory / "challenges.json").is_file()
    # Both tracks pin the SAME frozen thresholds and the same selection.
    blind_regions = (
        REPO_ROOT / "experiments" / "EZ-B003-v2-real-blind" / "challenges.json"
    )
    recon_regions = (
        REPO_ROOT / "experiments" / "EZ-B003-v2-real-recon" / "challenges.json"
    )
    assert sha256_file(blind_regions) == sha256_file(recon_regions)


def test_b002_improvement_flag_not_assumed_true():
    plan = _load("b002_real_claim_plan.json")
    flags = plan["improvement_flags"]
    qualification = json.loads(
        (
            REPO_ROOT
            / "reports"
            / "model_federation"
            / "wo12"
            / "synthetic_qualification.json"
        ).read_text(encoding="utf-8")
    )
    by_model = qualification["EZ-B002-v2-qual"]["by_model"]
    best_baseline = min(
        float(by_model[m]["MAE_keV"])
        for m in (
            "EZ-SEMF-LS-v1",
            "EZ-GP-DIRECT-v1",
            "EZ-SEMF-GP-RESIDUAL-v1",
            "EZ-GP-OPTIMIZED-CONTROL-v1",
        )
    )
    best_other = min(
        float(p["MAE_keV"])
        for m, p in by_model.items()
        if m.startswith(("EZ-BSKG3", "EZ-FRDM95", "EZ-FED-"))
    )
    assert flags["federation_improved_over_baseline"] is (best_other < best_baseline)
    assert flags["protocol_qualified"] is True
    assert {"best_baseline_model", "best_physics_model", "best_combined_model"} <= set(
        flags
    )


def test_b003_reconstruction_not_equal_rediscovery():
    plan = _load("b003_real_claim_plan.json")
    recon = plan["reconstruction"]
    assert "STRICT_BLIND" not in recon["allowed_claim_types"]
    assert "HISTORICAL_BLIND" not in recon["allowed_claim_types"]
    markdown = (
        REPO_ROOT / "experiments" / "EZ-B003-v2-real-recon" / "PREREGISTRATION.md"
    ).read_text(encoding="utf-8")
    assert "never called rediscovery" in markdown or "not rediscovery" in markdown
    flags = plan["improvement_flags"]
    for key in (
        "structure_localization_improved",
        "calibration_improved",
        "federation_criterion_met",
        "blind_claim_eligible",
    ):
        assert key in flags


def _claim_event(event_type: str, payload: dict, benchmark_id: str = "EZ-B002-v2-real-blind"):
    from elementzero.visuals.event_types import ProgressEvent, make_event_id

    return ProgressEvent(
        event_id=make_event_id(
            event_type=event_type, source_hash="e" * 64, element_Z=50
        ),
        event_type=event_type,
        event_time="2026-08-16T15:00:00Z",
        project_version="test",
        source_kind="test",
        source_path="test",
        source_hash="e" * 64,
        element_Z=50,
        status="info",
        benchmark_id=benchmark_id,
        payload=payload,
    )


def test_real_recon_never_grants_geographic_validated_stage():
    from elementzero.visuals.aggregate import aggregate_events

    events = [
        _claim_event(
            "REAL_RECONSTRUCTION_SCORED",
            {"claim_type": "RECONSTRUCTION_REFERENCE"},
            benchmark_id="EZ-B002-v2-real-recon",
        )
    ]
    state = aggregate_events(events)
    element = next(e for e in state["elements"] if e["Z"] == 50)
    assert element["project_primary_stage"] == "not_touched"
    assert "R" in element["badges"]


def test_real_recon_never_grants_shell_rediscovery_stage():
    from elementzero.visuals.aggregate import aggregate_events

    events = [
        _claim_event(
            "REAL_RECONSTRUCTION_SCORED",
            {"claim_type": "RECONSTRUCTION_REFERENCE", "blind_gate_passed": True},
            benchmark_id="EZ-B003-v2-real-recon",
        )
    ]
    state = aggregate_events(events)
    element = next(e for e in state["elements"] if e["Z"] == 50)
    assert element["project_primary_stage"] == "not_touched"


def test_blind_validation_promotes_only_with_allowed_claim():
    from elementzero.visuals.aggregate import aggregate_events

    granted = aggregate_events(
        [
            _claim_event(
                "REAL_BLIND_VALIDATION_SCORED",
                {"claim_type": "STRICT_BLIND", "blind_gate_passed": True},
            )
        ]
    )
    element = next(e for e in granted["elements"] if e["Z"] == 50)
    assert element["project_primary_stage"] == "geographic_holdout_validated"

    for payload in (
        {"claim_type": "NONBLIND_REFERENCE", "blind_gate_passed": True},
        {"claim_type": "STRICT_BLIND"},  # no gate attestation
        {"claim_type": "PARTIALLY_BLIND", "blind_gate_passed": True},
    ):
        state = aggregate_events(
            [_claim_event("REAL_BLIND_VALIDATION_SCORED", payload)]
        )
        element = next(e for e in state["elements"] if e["Z"] == 50)
        assert element["project_primary_stage"] == "not_touched", payload


def test_atlas_claim_lineage():
    facts = json.loads(
        (WO13_REPORTS / "atlas" / "facts.json").read_text(encoding="utf-8")
    )
    by_kind: dict[str, list[dict]] = {}
    for fact in facts:
        by_kind.setdefault(fact["content"]["kind"], []).append(fact)
    assert len(by_kind["eligibility_model_training_provenance"]) == 10
    assert by_kind["eligibility_target_matrix"]
    assert by_kind["eligibility_exclusion"]
    assert by_kind["eligibility_blind_subfederation"]
    claims = by_kind["eligibility_claim_validation"]
    assert claims
    fact_ids = {f["fact_id"] for f in facts}
    controls = {
        "EZ-SEMF-LS-v1",
        "EZ-GP-DIRECT-v1",
        "EZ-SEMF-GP-RESIDUAL-v1",
        "EZ-GP-OPTIMIZED-CONTROL-v1",
    }
    for fact in claims:
        content = fact["content"]
        assert content["claim_track"] in ("BLIND", "RECONSTRUCTION")
        assert content["eligibility_manifest_hash"]
        parents = [a for a in fact["assumptions"] if a.startswith("fact:")]
        assert parents and all(p.split("fact:", 1)[1] in fact_ids for p in parents)
        eligible = set(content["eligible_contributors"])
        excluded = set(content["excluded_contributors"])
        partial = content["partially_eligible_contributors"]
        # The three buckets partition the roster: no model in two lists.
        assert not (eligible & excluded)
        assert not (eligible & set(partial))
        assert not (excluded & set(partial))
        assert len(eligible) + len(excluded) + len(partial) == 10
        for counts in partial.values():
            assert counts["n_eligible_targets"] > 0
            assert counts["n_excluded_targets"] > 0
            assert (
                counts["n_eligible_targets"] + counts["n_excluded_targets"]
                == content["n_targets"]
            )
        if content["claim_track"] == "RECONSTRUCTION":
            # A STRICT_BLIND control has no admissible row label on the
            # reconstruction track; the nonblind BSkG3 reference does.
            assert not (eligible & controls), content["experiment_id"]
            assert "EZ-BSKG3-TABLE-v1" in eligible
            assert controls <= excluded
        else:
            assert controls <= eligible
            if content["experiment_id"] == "EZ-B003-v2-real-blind":
                # FRDM95 is blind on the 12 post-1995 targets only: partial,
                # with the counts saying exactly how partial.
                assert partial["EZ-FRDM95-TABLE-v1"]["n_eligible_targets"] == 12


def test_wo13_gate_status_valid():
    status = _load("wo13_gate_status.json")
    assert set(status) == {
        "work_order",
        "status",
        "b002_blind_status",
        "b003_blind_status",
        "blind_physics_independence_groups",
        "next_gate",
    }
    allowed = {
        "FEDERATED_BLIND_EVALUABLE",
        "PHYSICS_BLIND_EVALUABLE",
        "CONTROL_BLIND_EVALUABLE",
        "REAL_BLIND_GATE_NOT_EVALUABLE",
        "PROVENANCE_REPAIR_REQUIRED",
        "INFRASTRUCTURE_REPAIR_REQUIRED",
    }
    assert status["status"] in allowed
    assert status["work_order"] == "WO-13"


def test_wo13_report_reproducible(tmp_path):
    """Stage B rebuilds byte-for-byte from committed inputs — no raw tables."""
    from elementzero.eligibility.report import rebuild_wo13

    result = rebuild_wo13(out_dir=tmp_path / "out")
    assert result["status"] == _load("wo13_gate_status.json")["status"]
    for name in COMMITTED_FILES:
        assert sha256_file(tmp_path / "out" / name) == sha256_file(
            WO13_REPORTS / name
        ), name
    for name in ("facts.json", "provenance.json"):
        assert sha256_file(tmp_path / "out" / "atlas" / name) == sha256_file(
            WO13_REPORTS / "atlas" / name
        ), name
    assert sha256_file(tmp_path / "out" / "eligibility_progress_events.jsonl") == (
        sha256_file(WO13_REPORTS / "eligibility_progress_events.jsonl")
    )
