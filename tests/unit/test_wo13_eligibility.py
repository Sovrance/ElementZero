"""WO-13 eligibility engine: provenance, inheritance, subfederation, firewall."""

from __future__ import annotations

import json

import pytest

from elementzero.atlas_pin import REPO_ROOT
from elementzero.eligibility.claim_types import (
    CLAIM_TYPES,
    CONFIDENCE_UNKNOWN,
    HISTORICAL_BLIND,
    INELIGIBLE_UNKNOWN_PROVENANCE,
    NONBLIND_REFERENCE,
    PARTIALLY_BLIND,
    STRICT_BLIND,
    strict_gate_eligible,
    worst_claim,
)
from elementzero.eligibility.historical_sources import (
    CHRONOLOGY_RULE,
    HISTORICAL_SOURCES,
    SourceChronology,
)
from elementzero.eligibility.model_training_provenance import (
    audit_models,
)
from elementzero.eligibility.subfederation import (
    NOT_EVALUABLE,
    TIER_CONTROL,
    TIER_PHYSICS,
    benchmark_blind_status,
    build_manifest,
    build_subfederation,
)
from elementzero.eligibility.target_eligibility import build_matrix
from elementzero.errors import ProtocolError

SCHEMAS = REPO_ROOT / "schemas"


def _fake_chronology(
    *, known_1995: set[str], eligible_2020: set[str]
) -> SourceChronology:
    sources = {}
    for source_id in HISTORICAL_SOURCES:
        if source_id == "AME1995":
            known, eligible = sorted(known_1995), sorted(known_1995)
        elif source_id == "AME2020":
            known = sorted(known_1995 | eligible_2020)
            eligible = sorted(eligible_2020)
        else:
            known, eligible = sorted(known_1995), sorted(known_1995)
        sources[source_id] = {
            "known_nuclide_ids": known,
            "eligible_nuclide_ids": eligible,
        }
    return SourceChronology({"rule": CHRONOLOGY_RULE, "sources": sources})


CHRONOLOGY = _fake_chronology(
    known_1995={"Z50-N70", "Z82-N126"},
    eligible_2020={"Z50-N70", "Z82-N126", "Z90-N150"},
)


def _matrix(targets: list[str]):
    return build_matrix(
        benchmark_id="EZ-B002",
        experiment_id="EZ-B002-v2-real-blind",
        target_ids=targets,
        target_truth_edition="AME2020",
        chronology=CHRONOLOGY,
    )


def _records_for(matrix, nuclide_id: str) -> dict[str, dict]:
    return {
        r["model_id"]: r
        for r in matrix["records"]
        if r["nuclide_id"] == nuclide_id
    }


# -- WO-12 immutability ------------------------------------------------------ #


def test_wo12_protocol_hashes_unchanged():
    for experiment_id in ("EZ-B002-v2", "EZ-B003-v2"):
        protocol = json.loads(
            (REPO_ROOT / "experiments" / experiment_id / "PROTOCOL.json").read_text(
                encoding="utf-8"
            )
        )
        assert protocol["protocol_hash"] == (
            "117b60ccfbde52a3eef1e5e5acdeae8197275d073d122752a8b75b33500cd686"
        )
        assert protocol["state"] == "QUALIFICATION_ONLY"


def test_wo12_thresholds_unchanged():
    from elementzero.evidence.hashing import canonical_json
    from elementzero.experiments.wo12_qualification import (
        B002_V2_GATE,
        B003_V2_CRITERION,
    )

    for experiment_id, constant in (
        ("EZ-B002-v2", B002_V2_GATE),
        ("EZ-B003-v2", B003_V2_CRITERION),
    ):
        protocol = json.loads(
            (REPO_ROOT / "experiments" / experiment_id / "PROTOCOL.json").read_text(
                encoding="utf-8"
            )
        )
        assert protocol["frozen_thresholds"] == json.loads(canonical_json(constant))


def test_v1_artifact_inventory_unchanged():
    from elementzero.adjudication.artifact_audit import (
        assert_v1_evidence_unchanged,
        build_artifact_inventory,
    )

    inventory = build_artifact_inventory()
    assert inventory["all_unchanged"] is True
    assert_v1_evidence_unchanged(inventory)


# -- base eligibility policies ------------------------------------------------ #


def test_bskg3_ame2020_default_nonblind():
    matrix = _matrix(["Z90-N150"])  # unknown in 1995, eligible in 2020
    record = _records_for(matrix, "Z90-N150")["EZ-BSKG3-TABLE-v1"]
    # Even a target ElementZero never saw defaults nonblind for BSkG3:
    # its published fit used AME2020-era masses.
    assert record["claim_type"] == NONBLIND_REFERENCE
    assert record["base_fit_overlap"] is True
    assert record["strict_gate_eligible"] is False


def test_bskg3_residual_inherits_nonblind():
    matrix = _matrix(["Z90-N150"])
    record = _records_for(matrix, "Z90-N150")["EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1"]
    assert record["claim_type"] == NONBLIND_REFERENCE
    assert record["residual_fit_overlap"] is False  # the residual itself is blind
    assert record["strict_gate_eligible"] is False


def test_frdm95_unknown_membership_not_assumed_blind():
    matrix = _matrix(["Z50-N70"])  # known in AME1995
    record = _records_for(matrix, "Z50-N70")["EZ-FRDM95-TABLE-v1"]
    assert record["claim_type"] == INELIGIBLE_UNKNOWN_PROVENANCE
    assert record["strict_gate_eligible"] is False
    # And the honest positive case: unknown in 1995 -> HISTORICAL_BLIND only.
    fresh = _records_for(_matrix(["Z90-N150"]), "Z90-N150")["EZ-FRDM95-TABLE-v1"]
    assert fresh["claim_type"] == HISTORICAL_BLIND
    assert fresh["claim_type"] != STRICT_BLIND


def test_baseline_freeze_proves_blind_exclusion():
    matrix = _matrix(["Z50-N70"])
    for model_id in (
        "EZ-SEMF-LS-v1",
        "EZ-GP-DIRECT-v1",
        "EZ-SEMF-GP-RESIDUAL-v1",
        "EZ-GP-OPTIMIZED-CONTROL-v1",
    ):
        record = _records_for(matrix, "Z50-N70")[model_id]
        assert record["claim_type"] == STRICT_BLIND
        assert record["provenance_confidence"] == "EXACT"
        assert record["strict_gate_eligible"] is True
        assert record["base_fit_overlap"] is False


# -- inheritance --------------------------------------------------------------- #


def test_combiner_inherits_nonblind_contributor():
    records = _records_for(_matrix(["Z90-N150"]), "Z90-N150")
    for combiner in ("EZ-FED-UNIFORM-ENSEMBLE-v1", "EZ-FED-VALIDATION-WEIGHTED-v1"):
        record = records[combiner]
        # FRDM95 lineage is blind here, BSkG3 lineage is not: mixed panels
        # are PARTIALLY_BLIND at best and never strict-gate eligible.
        assert record["claim_type"] in (PARTIALLY_BLIND, NONBLIND_REFERENCE)
        assert record["strict_gate_eligible"] is False
    # An unknown-provenance contributor poisons the combination outright.
    records_known = _records_for(_matrix(["Z50-N70"]), "Z50-N70")
    assert (
        records_known["EZ-FED-UNIFORM-ENSEMBLE-v1"]["claim_type"]
        == INELIGIBLE_UNKNOWN_PROVENANCE
    )


def test_strict_combiner_excludes_nonblind_contributor():
    matrix = _matrix(["Z90-N150"])
    entry = build_subfederation(
        target_id="Z90-N150", matrix_records=matrix["records"]
    )
    excluded = {e["model_id"] for e in entry["excluded_models"]}
    assert "EZ-BSKG3-TABLE-v1" in excluded
    assert "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1" in excluded
    assert "EZ-FED-UNIFORM-ENSEMBLE-v1" in excluded
    assert "EZ-FED-VALIDATION-WEIGHTED-v1" in excluded
    assert "EZ-FRDM95-TABLE-v1" in entry["eligible_models"]
    # Weights cover eligible contributors only.
    assert set(entry["weights"]) == set(entry["eligible_models"])


def test_subfederation_target_specific():
    matrix = _matrix(["Z50-N70", "Z90-N150"])
    known = build_subfederation(target_id="Z50-N70", matrix_records=matrix["records"])
    fresh = build_subfederation(target_id="Z90-N150", matrix_records=matrix["records"])
    assert known["eligible_models"] != fresh["eligible_models"]
    assert "EZ-FRDM95-TABLE-v1" not in known["eligible_models"]
    assert "EZ-FRDM95-TABLE-v1" in fresh["eligible_models"]
    assert known["tier"] == TIER_CONTROL
    assert fresh["tier"] == TIER_PHYSICS


def test_residual_variants_not_counted_as_independent_physics():
    matrix = _matrix(["Z90-N150"])
    entry = build_subfederation(target_id="Z90-N150", matrix_records=matrix["records"])
    # FRDM95 and its residual variant are both eligible, but they count as
    # ONE physics family: the residual wrapper lives in residual_ml.
    assert "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1" in entry["eligible_models"]
    assert entry["eligible_physics_independence_groups"] == [
        "macroscopic_microscopic_frdm"
    ]
    assert entry["tier"] == TIER_PHYSICS  # not FEDERATED


def test_blind_gate_not_evaluable_is_valid():
    chronology = _fake_chronology(known_1995={"Z50-N70"}, eligible_2020=set())
    matrix = build_matrix(
        benchmark_id="EZ-B002",
        experiment_id="EZ-B002-v2-real-blind",
        target_ids=["Z50-N70"],
        target_truth_edition="AME2020",
        chronology=chronology,
        model_ids=["EZ-BSKG3-TABLE-v1", "EZ-FRDM95-TABLE-v1"],
    )
    manifest = build_manifest(
        experiment_id="EZ-B002-v2-real-blind", matrix=matrix
    )
    assert manifest["benchmark_blind_status"]["status"] == NOT_EVALUABLE
    summary = benchmark_blind_status(manifest["targets"])
    assert summary["targets_by_tier"][NOT_EVALUABLE] == 1


def test_model_provenance_unknown_blocks_strict_claim():
    assert strict_gate_eligible(STRICT_BLIND, CONFIDENCE_UNKNOWN) is False
    assert strict_gate_eligible(HISTORICAL_BLIND, CONFIDENCE_UNKNOWN) is False
    assert worst_claim(STRICT_BLIND, INELIGIBLE_UNKNOWN_PROVENANCE) == (
        INELIGIBLE_UNKNOWN_PROVENANCE
    )


# -- provenance + schemas ------------------------------------------------------ #


def test_all_models_have_provenance_records():
    manifest = json.loads(
        (
            REPO_ROOT / "reports" / "model_federation" / "wo12" / "federation_manifest.json"
        ).read_text(encoding="utf-8")
    )
    audit = audit_models(registry_manifest=manifest)
    assert audit["status"] == "COMPLETE"
    assert audit["n_models"] == 10
    assert set(audit["records"]) == set(manifest["participants"])
    bskg3 = audit["records"]["EZ-BSKG3-TABLE-v1"]
    assert bskg3["exact_fit_membership_available"] is False
    assert "AME2020" in bskg3["fit_source_editions"]
    frdm = audit["records"]["EZ-FRDM95-TABLE-v1"]
    assert frdm["exact_fit_membership_available"] is False
    assert frdm["provenance_confidence"] == "MEDIUM"


def test_schemas_reject_unknown_claim_types():
    for name, key in (
        ("target_blindness_record.schema.json", "claim_type"),
        ("subfederation_manifest.schema.json", "resulting_claim_type"),
    ):
        schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
        enum = schema["properties"][key]["enum"]
        assert "TOTALLY_BLIND_TRUST_ME" not in enum
        assert set(enum) <= set(CLAIM_TYPES)
    gate = json.loads((SCHEMAS / "wo13_gate_status.schema.json").read_text("utf-8"))
    assert gate["additionalProperties"] is False
    with pytest.raises(ProtocolError):
        worst_claim("TOTALLY_BLIND_TRUST_ME")
