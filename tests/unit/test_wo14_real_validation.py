"""WO-14 unit tests: input pins, seal/unlock mechanics, scope discipline,
derived blindness, and the visual claim firewall (spec section 21)."""

from __future__ import annotations

import json

import pytest

from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_file
from elementzero.real_validation.claim_adjudication import build_adjudication
from elementzero.real_validation.derived_blindness import (
    DERIVED_OBSERVABLES,
    audit_summary,
    build_records,
    component_ids,
)
from elementzero.real_validation.input_guard import (
    PINNED_INPUT_HASHES,
    WO12_PROTOCOL_HASH,
    WO12_REGISTRY_HASH,
    verify_inputs,
)
from elementzero.real_validation.prediction_seal import (
    read_seal_hash,
    unlock_truth,
    write_seal,
)
from elementzero.real_validation.run_state import RUN_STATES, RealValidationRun
from elementzero.visuals.status import (
    badges_from_event_types,
    claim_checked_stage_types,
    select_primary_stage,
)

BLIND_12 = (
    "Z48-N83",
    "Z81-N130",
    "Z81-N132",
    "Z81-N95",
    "Z82-N133",
    "Z82-N96",
    "Z82-N97",
    "Z82-N98",
    "Z83-N134",
    "Z83-N135",
    "Z93-N126",
    "Z93-N127",
)


# --------------------------------------------------------------------------- #
# Input integrity                                                             #
# --------------------------------------------------------------------------- #


def test_wo13_input_hashes_unchanged():
    result = verify_inputs(repo_root=REPO_ROOT)
    assert result["status"] == "INPUTS_VERIFIED"
    assert result["v1_inventory_unchanged"] is True
    for relpath, pinned in PINNED_INPUT_HASHES.items():
        assert sha256_file(REPO_ROOT / relpath) == pinned


def test_wo12_protocol_and_registry_hashes_unchanged():
    # The committed WO-12 manifest is the frozen registry record; it must
    # still carry the pinned hash (CI-safe, no raw table needed).
    manifest = json.loads(
        (
            REPO_ROOT / "reports/model_federation/wo12/federation_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["registry_hash"] == WO12_REGISTRY_HASH
    for experiment_id in ("EZ-B002-v2", "EZ-B003-v2"):
        protocol = json.loads(
            (REPO_ROOT / "experiments" / experiment_id / "PROTOCOL.json").read_text(
                encoding="utf-8"
            )
        )
        assert protocol["protocol_hash"] == WO12_PROTOCOL_HASH
    # With the fetched raw tables present (local runs, full qualification
    # jobs), the LIVE registry must also still build to the frozen hash —
    # the WO-14 seal path refuses to run otherwise.
    tables = REPO_ROOT / "data" / "model_tables"
    if (tables / "bskg03.dat").is_file() and (tables / "mass-frdm95.dat").is_file():
        from elementzero.models.federation.registry import build_default_federation

        registry = build_default_federation(repo_root=REPO_ROOT)
        assert registry.manifest()["registry_hash"] == WO12_REGISTRY_HASH


# --------------------------------------------------------------------------- #
# Run state machine and sealing                                               #
# --------------------------------------------------------------------------- #


def _run() -> RealValidationRun:
    return RealValidationRun(
        experiment_id="EZ-TEST",
        run_id="wo14-test-run-v1",
        claim_track="BLIND",
        protocol_hash="p" * 64,
        eligibility_manifest_hash="e" * 64,
    )


def test_truth_unavailable_before_seal():
    run = _run()
    run.advance("INPUTS_VERIFIED")
    run.advance("PREDICTIONS_GENERATED")
    # Cannot skip finalization, and cannot unlock truth without a seal.
    with pytest.raises(ProtocolError):
        run.advance("TRUTH_UNLOCKED")
    run.advance("PREDICTIONS_FINALIZED")
    run.advance("SEALED_COMMIT_RECORDED")
    with pytest.raises(ProtocolError, match="seal"):
        run.advance("TRUTH_UNLOCKED")


def test_prediction_change_after_seal_rejected():
    run = _run()
    for state in RUN_STATES[1:4]:
        run.advance(state)
    run.record_seal("a" * 64)
    with pytest.raises(ProtocolError, match="NEW run id"):
        run.record_seal("b" * 64)


def test_truth_unlock_checks_all_hashes(tmp_path):
    seal_hash = write_seal(tmp_path, {"experiment_id": "EZ-TEST", "predictions": {}})
    assert read_seal_hash(tmp_path) == seal_hash
    good = dict(
        seal_dir=tmp_path,
        expected_seal_hash=seal_hash,
        eligibility_manifest_hash="e1",
        expected_eligibility_hash="e1",
        threshold_hash="t1",
        expected_threshold_hash="t1",
        registry_hash="r1",
        expected_registry_hash="r1",
        protocol_hash="p1",
        expected_protocol_hash="p1",
        target_identity_digest="d1",
        expected_target_identity_digest="d1",
    )
    assert unlock_truth(**good)["truth_unlocked"] is True
    for field, name in (
        ("expected_seal_hash", "prediction_seal_hash"),
        ("expected_eligibility_hash", "eligibility_manifest_hash"),
        ("expected_threshold_hash", "threshold_hash"),
        ("expected_registry_hash", "model_registry_hash"),
        ("expected_protocol_hash", "protocol_hash"),
        ("expected_target_identity_digest", "target_identity_digest"),
    ):
        bad = {**good, field: "tampered"}
        with pytest.raises(ProtocolError, match=name):
            unlock_truth(**bad)
    # A tampered seal file is caught before any field comparison.
    (tmp_path / "SEALED_PREDICTIONS.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ProtocolError, match="CLAIM_INTEGRITY_FAILURE"):
        unlock_truth(**good)


# --------------------------------------------------------------------------- #
# Claim scope discipline                                                      #
# --------------------------------------------------------------------------- #


def _adjudicate(**overrides):
    payload = dict(
        experiment_id="EZ-B002-v2-real-blind",
        run_id="wo14-test",
        benchmark_id="EZ-B002",
        claim_track="BLIND",
        prediction_seal_hash="s" * 64,
        eligible_model_ids=["EZ-SEMF-LS-v1"],
        excluded_model_ids=[],
        physics_independence_groups=[],
        claim_type="STRICT_BLIND",
        scientific_scope="CONTROL_BLIND_GEOGRAPHIC",
        inherited_criterion_status="CONTROL_BLIND_CRITERION_MET",
        blind_gate_status="CONTROL_BLIND_EVALUABLE",
        visual_stage_permission="BADGE_CB_ONLY_NO_STAGE_PROMOTION",
        next_gate="WO-15",
    )
    payload.update(overrides)
    return build_adjudication(**payload)


def test_b002_blind_never_claims_physics_validation():
    # The only admissible B002 blind scope is control-blind geographic.
    record = _adjudicate()
    assert record["scientific_scope"] == "CONTROL_BLIND_GEOGRAPHIC"
    for prohibited in (
        "PHYSICS_BLIND_GEOGRAPHIC_VALIDATION",
        "FEDERATED_BLIND_GEOGRAPHIC_VALIDATION",
        "FRONTIER_RIGHT_TO_EXTRAPOLATE",
    ):
        with pytest.raises(ProtocolError):
            _adjudicate(scientific_scope=prohibited)
    with pytest.raises(ProtocolError, match="control-only"):
        _adjudicate(scientific_scope="PHYSICS_BLIND_MASS_EDGE")


def test_recon_track_never_takes_blind_scope():
    with pytest.raises(ProtocolError, match="reconstruction scopes"):
        _adjudicate(
            experiment_id="EZ-B002-v2-real-recon",
            claim_track="RECONSTRUCTION",
            scientific_scope="CONTROL_BLIND_GEOGRAPHIC",
        )
    with pytest.raises(ProtocolError, match="never adjudicates"):
        _adjudicate(
            experiment_id="EZ-B003-v2-real-blind",
            benchmark_id="EZ-B003",
            scientific_scope="RECONSTRUCTION_SHELL_STRUCTURE",
        )


def test_full_shell_gate_not_evaluable_is_valid():
    # NOT_EVALUABLE is an honest, recordable outcome for edge evidence...
    record = _adjudicate(
        experiment_id="EZ-B003-v2-real-blind",
        benchmark_id="EZ-B003",
        claim_type="HISTORICAL_BLIND",
        scientific_scope="PHYSICS_BLIND_EDGE_STRUCTURE",
        physics_independence_groups=["macroscopic_microscopic_frdm"],
        inherited_criterion_status="PHYSICS_BLIND_EDGE_VALIDATION",
        blind_gate_status="FULL_SHELL_BLIND_NOT_EVALUABLE",
        visual_stage_permission="BADGE_HB_ONLY_NO_STAGE_PROMOTION",
    )
    assert record["blind_gate_status"] == "FULL_SHELL_BLIND_NOT_EVALUABLE"
    # ...but the full-shell scope itself demands the criterion be met.
    with pytest.raises(ProtocolError, match="FULL_BLIND_SHELL_REDISCOVERY"):
        _adjudicate(
            experiment_id="EZ-B003-v2-real-blind",
            benchmark_id="EZ-B003",
            claim_type="HISTORICAL_BLIND",
            scientific_scope="FULL_BLIND_SHELL_REDISCOVERY",
            blind_gate_status="FULL_SHELL_BLIND_NOT_EVALUABLE",
        )


# --------------------------------------------------------------------------- #
# Derived shell blindness                                                     #
# --------------------------------------------------------------------------- #


def _chronology():
    from elementzero.eligibility.historical_sources import SourceChronology

    return SourceChronology.from_committed(
        REPO_ROOT / "reports/eligibility/wo13/historical_source_chronology.json"
    )


def _records():
    matrix = json.loads(
        (
            REPO_ROOT / "reports/eligibility/wo13/target_eligibility_matrix.json"
        ).read_text(encoding="utf-8")
    )
    truth_available = frozenset(
        record["nuclide_id"]
        for record in matrix["EZ-B003-v2-real-blind"]["records"]
    )
    model_ids = [
        "EZ-SEMF-LS-v1",
        "EZ-GP-DIRECT-v1",
        "EZ-SEMF-GP-RESIDUAL-v1",
        "EZ-GP-OPTIMIZED-CONTROL-v1",
        "EZ-FRDM95-TABLE-v1",
        "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
    ]
    return build_records(
        blind_target_ids=list(BLIND_12),
        model_ids=model_ids,
        chronology=_chronology(),
        truth_available=truth_available,
    )


def test_b003_derived_blindness_dependencies():
    # Component algebra is exact (spec section 8).
    assert component_ids("S2n", "Z81-N132") == ["Z81-N130", "Z81-N132"]
    assert component_ids("S2p", "Z82-N98") == ["Z80-N98", "Z82-N98"]
    assert component_ids("delta2n", "Z81-N130") == [
        "Z81-N128",
        "Z81-N130",
        "Z81-N132",
    ]
    assert component_ids("delta2p", "Z82-N97") == ["Z80-N97", "Z82-N97", "Z84-N97"]

    records = _records()
    assert len(records) == len(BLIND_12) * len(DERIVED_OBSERVABLES)
    by_id = {r["derived_observable_id"]: r for r in records}
    # Adjacent blind pairs make exactly two S2n observables blind-eligible.
    eligible = sorted(
        r["derived_observable_id"]
        for r in records
        if r["all_model_inputs_blind_eligible"]
    )
    assert eligible == ["S2n:Z81-N132", "S2n:Z82-N98"]
    # Central-target blindness never propagates to neighbors: the S2n of a
    # blind target whose N-2 neighbor sat in training is not blind.
    lone = by_id["S2n:Z48-N83"]
    assert lone["all_model_inputs_blind_eligible"] is False
    assert "Z48-N81" in lone["component_nuclide_ids"]
    # A delta2n around a blind pair still needs the third, nonblind mass.
    assert by_id["delta2n:Z81-N130"]["all_model_inputs_blind_eligible"] is False


def test_b003_edge_not_equal_full_shell_rediscovery():
    records = _records()
    summary = audit_summary(records)
    assert summary["edge_structure_evaluable"] is True
    assert summary["full_shell_blind_evaluable"] is False
    # S2n edges never open the full-shell gate; only blind
    # delta2n/delta2p/local_peak_rank could, and none is blind here.
    for record in records:
        if record["observable"] in ("S2n", "S2p"):
            assert record["full_shell_gate_eligible"] is False


# --------------------------------------------------------------------------- #
# Visual claim firewall                                                       #
# --------------------------------------------------------------------------- #


def test_visual_cb_does_not_promote_geographic_stage():
    payload = {
        "experiment_id": "EZ-B002-v2-real-blind",
        "claim_type": "STRICT_BLIND",
        "control_blind_status": "CONTROL_BLIND_CRITERION_MET",
    }
    assert (
        claim_checked_stage_types(
            "REAL_CONTROL_BLIND_SCORED", payload, "EZ-B002-v2-real-blind"
        )
        == []
    )
    stage = select_primary_stage(
        ["DATA_INGESTED", "REAL_CONTROL_BLIND_SCORED"], z=50
    )
    assert stage == "data_ingested"
    assert "CB" in badges_from_event_types(["REAL_CONTROL_BLIND_SCORED"])


def test_visual_hb_does_not_promote_shell_stage():
    payload = {
        "experiment_id": "EZ-B003-v2-real-blind",
        "claim_type": "HISTORICAL_BLIND",
        "blind_gate_status": "FULL_SHELL_BLIND_NOT_EVALUABLE",
    }
    assert (
        claim_checked_stage_types(
            "REAL_HISTORICAL_BLIND_EDGE_SCORED", payload, "EZ-B003-v2-real-blind"
        )
        == []
    )
    stage = select_primary_stage(
        ["DATA_INGESTED", "REAL_HISTORICAL_BLIND_EDGE_SCORED"], z=82
    )
    assert stage == "data_ingested"
    assert "HB" in badges_from_event_types(["REAL_HISTORICAL_BLIND_EDGE_SCORED"])


def test_visual_full_shell_pass_can_promote_shell_stage():
    payload = {
        "blind_gate_passed": True,
        "claim_type": "HISTORICAL_BLIND",
        "blind_gate_status": "FULL_SHELL_BLIND_CRITERION_MET",
    }
    assert claim_checked_stage_types(
        "REAL_BLIND_VALIDATION_SCORED", payload, "EZ-B003-v2-real-blind"
    ) == ["SHELL_VALIDATION_SCORED"]
    # Without the independently met full-shell criterion, no promotion.
    weaker = {**payload, "blind_gate_status": "FULL_SHELL_BLIND_NOT_EVALUABLE"}
    assert (
        claim_checked_stage_types(
            "REAL_BLIND_VALIDATION_SCORED", weaker, "EZ-B003-v2-real-blind"
        )
        == []
    )


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #


def _schema(name: str) -> dict:
    return json.loads((REPO_ROOT / "schemas" / name).read_text(encoding="utf-8"))


def test_wo14_schemas_are_closed_and_complete():
    for name, required in (
        (
            "real_validation_run.schema.json",
            {
                "experiment_id",
                "run_id",
                "claim_track",
                "state",
                "protocol_hash",
                "eligibility_manifest_hash",
                "prediction_seal_hash",
                "truth_unlocked",
                "claim_adjudicated",
            },
        ),
        (
            "derived_blindness_record.schema.json",
            {
                "derived_observable_id",
                "observable",
                "central_nuclide_id",
                "component_nuclide_ids",
                "component_model_claim_types",
                "truth_dependency_ids",
                "model_dependency_ids",
                "all_model_inputs_blind_eligible",
                "claim_type",
                "full_shell_gate_eligible",
                "reason",
            },
        ),
        (
            "claim_adjudication.schema.json",
            {
                "experiment_id",
                "run_id",
                "benchmark_id",
                "claim_track",
                "prediction_seal_hash",
                "eligible_model_ids",
                "excluded_model_ids",
                "physics_independence_groups",
                "claim_type",
                "scientific_scope",
                "inherited_criterion_status",
                "blind_gate_status",
                "visual_stage_permission",
                "next_gate",
            },
        ),
        (
            "wo14_status.schema.json",
            {
                "work_order",
                "status",
                "b002_blind_status",
                "b002_recon_status",
                "b003_blind_mass_status",
                "b003_blind_edge_status",
                "b003_full_shell_blind_status",
                "b003_recon_status",
                "next_gate",
            },
        ),
    ):
        schema = _schema(name)
        assert set(schema["required"]) == required, name
        assert schema["additionalProperties"] is False, name
        assert set(schema["properties"]) == required, name
    scopes = _schema("claim_adjudication.schema.json")["properties"][
        "scientific_scope"
    ]["enum"]
    assert sorted(scopes) == sorted(
        [
            "CONTROL_BLIND_GEOGRAPHIC",
            "RECONSTRUCTION_GEOGRAPHIC",
            "PHYSICS_BLIND_MASS_EDGE",
            "PHYSICS_BLIND_EDGE_STRUCTURE",
            "FULL_BLIND_SHELL_REDISCOVERY",
            "RECONSTRUCTION_SHELL_STRUCTURE",
        ]
    )
