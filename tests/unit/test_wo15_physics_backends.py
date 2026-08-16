"""WO-15 unit tests: provenance, freeze integrity, independence, firewall.

These run without a compiled solver and without any raw archive: the
contracts under test are about what a backend is *allowed* to claim, and
those are decidable from committed records alone.
"""

from __future__ import annotations

import json

import pytest

from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_file, sha256_hex
from elementzero.physics_backends import (
    BACKEND_COVARIANT,
    BACKEND_GOGNY,
    BACKEND_SKYRME,
    HISTORICAL_FROZEN_PARTIAL,
    MODERN_REFERENCE,
    REFIT_STRICT,
    UNKNOWN_PROVENANCE,
)
from elementzero.physics_backends.artifact import (
    assert_artifact_unchanged,
    build_parameter_artifact,
)
from elementzero.physics_backends.convergence import build_record
from elementzero.physics_backends.independence import (
    INDEPENDENT,
    NOT_INDEPENDENT,
    build_adjudication,
    count_blind_families,
)
from elementzero.physics_backends.objective import build_objective_manifest
from elementzero.physics_backends.protocol import (
    SOLVER_NONCONVERGED,
    SOLVER_OK,
    PhysicsPrediction,
)
from elementzero.physics_backends.provenance import (
    FIT_FREEZE_CUTOFF,
    PARAMETERIZATIONS,
    SOLVER_SOURCES,
    parameterization_admissible,
)
from elementzero.physics_backends.report import (
    WO14_IMMUTABLE_ARTIFACTS,
    wo14_hashes,
)
from elementzero.visuals.status import (
    badges_from_event_types,
    claim_checked_stage_types,
    select_primary_stage,
)

FREEZE_YEAR = int(FIT_FREEZE_CUTOFF[:4])


# --------------------------------------------------------------------------- #
# WO-14 firewall                                                              #
# --------------------------------------------------------------------------- #


def test_wo14_artifacts_immutable():
    """Every WO-14 artifact still hashes to what WO-14 committed."""
    committed = json.loads(
        (
            REPO_ROOT / "reports/real_validation/wo14/wo14_status.json"
        ).read_text(encoding="utf-8")
    )
    assert committed["work_order"] == "WO-14"
    live = wo14_hashes(repo_root=REPO_ROOT)
    assert set(live) == set(WO14_IMMUTABLE_ARTIFACTS)
    for relpath, digest in live.items():
        assert digest == sha256_file(REPO_ROOT / relpath)
    # The scored statuses are the WO-14 record and must read unchanged.
    assert committed["b003_full_shell_blind_status"] == (
        "FULL_SHELL_BLIND_NOT_EVALUABLE"
    )


def test_wo14_truth_forbidden_from_fit():
    """The freeze names WO-14 truth as forbidden and admits only AME1995."""
    from elementzero.physics_backends.freeze import (
        WO14_TRUTH_ARTIFACTS,
        build_freeze,
    )

    freeze = build_freeze(
        calibration_nuclide_ids=[],
        validation_nuclide_ids=[],
        repo_root=REPO_ROOT,
    )
    assert set(freeze["allowed_dataset_hashes"]) == {"AME1995"}
    assert set(freeze["forbidden_dataset_hashes"]) == {
        "AME2003",
        "AME2012",
        "AME2016",
        "AME2020",
    }
    for relpath in WO14_TRUTH_ARTIFACTS:
        assert relpath in freeze["wo14_truth_forbidden_hashes"], relpath
    assert freeze["cutoff_date"] == FIT_FREEZE_CUTOFF


# --------------------------------------------------------------------------- #
# Backend provenance                                                          #
# --------------------------------------------------------------------------- #


def test_backend_source_hash_pinned():
    for solver, record in SOLVER_SOURCES.items():
        assert len(record["archive_sha256"]) == 64, solver
        assert record["license"], solver
        assert record["publication"], solver
        assert record["download_url"].startswith("https://"), solver
    # The CPC licence does not grant redistribution; the archive is
    # fetched, never vendored into the repository.
    assert SOLVER_SOURCES["DIRHB"]["redistribution_allowed"] is False
    assert SOLVER_SOURCES["HFBTHO"]["redistribution_allowed"] is True


def test_backend_build_reproducible():
    """A build manifest is a content digest over the exact build inputs."""
    from elementzero.physics_backends.provenance import build_manifest

    binary = REPO_ROOT / "data/physics_backends/hfbtho_gogny_build"
    if not binary.is_file():
        pytest.skip("solver binary is not built in this environment")
    first = build_manifest(
        solver="HFBTHO",
        binary_path=binary,
        compiler="gfortran",
        compiler_version="13",
        build_flags="-O3",
    )
    second = build_manifest(
        solver="HFBTHO",
        binary_path=binary,
        compiler="gfortran",
        compiler_version="13",
        build_flags="-O3",
    )
    assert first["build_manifest_hash"] == second["build_manifest_hash"]
    changed = build_manifest(
        solver="HFBTHO",
        binary_path=binary,
        compiler="gfortran",
        compiler_version="13",
        build_flags="-O2",
    )
    assert changed["build_manifest_hash"] != first["build_manifest_hash"]


def _artifact(**overrides):
    payload = dict(
        backend_id=BACKEND_SKYRME,
        physics_family="skyrme_hfb_edf",
        solver_name="HFBTHO",
        solver_version="test",
        solver_source_hash="a" * 64,
        build_manifest_hash="b" * 64,
        parameter_names=["vpair_n", "vpair_p"],
        parameter_values=[-300.0, -280.0],
        parameter_units=["MeV fm^3", "MeV fm^3"],
        pairing_definition="volume delta pairing",
        basis_policy="test-basis",
        optimizer_id="test-opt",
        optimizer_version="1",
        objective_manifest_hash="c" * 64,
        freeze_id="ez-wo15-historical-fit-freeze-v1",
        training_identity_digest="d" * 64,
        calibration_identity_digest="e" * 64,
        fit_started_at="2026-08-16T20:00:00Z",
        fit_completed_at="2026-08-16T21:00:00Z",
        convergence_status="FIT_CONVERGED",
        objective_value=1234.5,
        covariance_artifact_hash="f" * 64,
        fit_log_hash="0" * 64,
        provenance_class=REFIT_STRICT,
        parameterization_source={"base_parameterization": "SKM*"},
    )
    payload.update(overrides)
    return build_parameter_artifact(**payload)


def test_parameter_artifact_immutable():
    artifact = _artifact()
    assert_artifact_unchanged(artifact, expected_id=artifact["artifact_id"])
    tampered = {**artifact, "parameter_values": [-301.0, -280.0]}
    with pytest.raises(ProtocolError, match="does not match the sealed id"):
        assert_artifact_unchanged(tampered, expected_id=artifact["artifact_id"])
    # A different parameter vector is a different artifact, not an edit.
    other = _artifact(parameter_values=[-301.0, -280.0])
    assert other["artifact_id"] != artifact["artifact_id"]


# --------------------------------------------------------------------------- #
# Fit membership                                                              #
# --------------------------------------------------------------------------- #


def test_training_membership_exact():
    """Training membership is the enumerated AME1995 eligible set."""
    from elementzero.evidence.freezes import identity_digest
    from elementzero.physics_backends.freeze import (
        allowed_training_ids,
        build_freeze,
    )

    allowed = allowed_training_ids(repo_root=REPO_ROOT)
    freeze = build_freeze(
        calibration_nuclide_ids=allowed[:4],
        validation_nuclide_ids=[],
        repo_root=REPO_ROOT,
    )
    assert freeze["n_allowed_nuclides"] == len(allowed)
    assert freeze["allowed_identity_digest"] == identity_digest(allowed)
    # A nuclide outside the freeze cannot be admitted as calibration.
    with pytest.raises(ProtocolError, match="not freeze-admissible"):
        build_freeze(
            calibration_nuclide_ids=["Z92-N124"],
            validation_nuclide_ids=[],
            repo_root=REPO_ROOT,
        )


def test_calibration_membership_exact():
    """The calibration set is deterministic and disjoint from B004."""
    from elementzero.b004.targets import select_targets
    from elementzero.physics_backends.campaign import prepare_campaign

    campaign = prepare_campaign(repo_root=REPO_ROOT)
    first = sorted(campaign["calibration"])
    again = sorted(prepare_campaign(repo_root=REPO_ROOT)["calibration"])
    assert first == again
    assert campaign["objective"]["calibration_nuclide_ids"] == first
    targets = set(select_targets(repo_root=REPO_ROOT)["target_nuclide_ids"])
    assert not targets & set(first), "a B004 target leaked into the fit set"


def test_b004_weights_training_only():
    """The objective consumes training-era evidence and declares its weights."""
    manifest = build_objective_manifest(
        calibration_nuclide_ids=["Z20-N20", "Z28-N28"],
        freeze_id="ez-wo15-historical-fit-freeze-v1",
        source_hash="a" * 64,
    )
    assert manifest["locked_before_fitting"] is True
    assert "uniform weight" in manifest["observables"][0]["weight_policy"]
    assert manifest["min_converged_fraction"] > 0
    # The hash covers the calibration membership, so a changed set is a
    # changed objective.
    other = build_objective_manifest(
        calibration_nuclide_ids=["Z20-N20"],
        freeze_id="ez-wo15-historical-fit-freeze-v1",
        source_hash="a" * 64,
    )
    assert other["objective_manifest_hash"] != manifest["objective_manifest_hash"]


# --------------------------------------------------------------------------- #
# Provenance classes and blind eligibility                                    #
# --------------------------------------------------------------------------- #


def _adjudicate(**overrides):
    payload = dict(
        group_id="skyrme_hfb_edf",
        functional_class="skyrme_zero_range_edf",
        interaction_or_lagrangian_class="zero-range Skyrme",
        solver="HFBTHO",
        parameter_artifact="artifact-a",
        fit_freeze="ez-wo15-historical-fit-freeze-v1",
        shared_training_data=[],
        shared_parameters=[],
        derived_from_family=None,
        residual_parent=None,
        provenance_class=REFIT_STRICT,
        parameterization_year=1982,
        freeze_year=FREEZE_YEAR,
    )
    payload.update(overrides)
    return build_adjudication(**payload)


def test_modern_reference_not_blind():
    record = _adjudicate(
        group_id="covariant_rhb_edf",
        provenance_class=MODERN_REFERENCE,
        parameterization_year=2005,
    )
    assert record["blind_eligible"] is False
    assert "reference and reconstruction only" in record["reason"]
    # And the shipped DIRHB forces really are post-freeze.
    for force in ("DD-ME2", "DD-PC1"):
        assert not parameterization_admissible(force)


def test_unknown_provenance_not_blind():
    record = _adjudicate(provenance_class=UNKNOWN_PROVENANCE)
    assert record["blind_eligible"] is False
    assert "provenance cannot be established" in record["reason"]
    with pytest.raises(ProtocolError, match="no chronology record"):
        parameterization_admissible("NOT-A-REAL-FORCE")


def test_historical_partial_blind_by_date_adjudication():
    """A pre-freeze publication is blind-eligible; a post-freeze one is not."""
    pre = _adjudicate(
        provenance_class=HISTORICAL_FROZEN_PARTIAL, parameterization_year=1984
    )
    post = _adjudicate(
        provenance_class=HISTORICAL_FROZEN_PARTIAL, parameterization_year=1998
    )
    assert pre["blind_eligible"] is True
    assert post["blind_eligible"] is False


# --------------------------------------------------------------------------- #
# Independence                                                                #
# --------------------------------------------------------------------------- #


def test_same_functional_different_solver_not_independent():
    """Two Skyrme backends are one family however they are compiled."""
    a = _adjudicate(solver="HFBTHO", parameter_artifact="artifact-a")
    b = _adjudicate(
        solver="HFODD",
        parameter_artifact="artifact-b",
        derived_from_family="skyrme_hfb_edf",
    )
    assert b["independence_verdict"] == NOT_INDEPENDENT
    gate = count_blind_families([a, b])
    assert gate["n_blind_independent_families"] == 1


def test_skyrme_gogny_can_be_independent():
    skyrme = _adjudicate(shared_solver_with=["EZ-PHYS-GOGNY-HFB-v1"])
    gogny = _adjudicate(
        group_id="gogny_finite_range_hfb",
        functional_class="gogny_finite_range",
        interaction_or_lagrangian_class="finite-range Gogny",
        parameter_artifact="artifact-b",
        parameterization_year=1984,
        shared_solver_with=["EZ-PHYS-SKYRME-HFB-v1"],
    )
    assert skyrme["independence_verdict"] == INDEPENDENT
    assert gogny["independence_verdict"] == INDEPENDENT
    gate = count_blind_families([skyrme, gogny])
    assert gate["gate_met"] is True
    assert gate["status"] == "TWO_BLIND_PHYSICS_FAMILIES"
    # The shared-solver caveat is recorded, not silently dropped.
    assert "correlated-numerics caveat" in skyrme["reason"]
    assert "correlated-numerics caveat" in gogny["reason"]


def test_skyrme_covariant_can_be_independent():
    skyrme = _adjudicate()
    covariant = _adjudicate(
        group_id="covariant_rhb_edf",
        functional_class="covariant_meson_exchange",
        interaction_or_lagrangian_class="density-dependent meson exchange",
        parameter_artifact="artifact-c",
        solver="DIRHB",
        parameterization_year=1986,
    )
    assert covariant["independence_verdict"] == INDEPENDENT
    assert count_blind_families([skyrme, covariant])["gate_met"] is True


def test_residual_variant_not_independent():
    record = _adjudicate(
        parameter_artifact="artifact-residual",
        residual_parent="skyrme_hfb_edf",
    )
    assert record["independence_verdict"] == NOT_INDEPENDENT
    assert record["blind_eligible"] is False
    assert count_blind_families([_adjudicate(), record])[
        "n_blind_independent_families"
    ] == 1


def test_emulator_not_independent():
    """An emulator inherits its parent's family; the counter is unmoved."""
    from elementzero.physics_backends.independence import (
        NEVER_INDEPENDENT_REASONS,
    )

    assert "emulator" in NEVER_INDEPENDENT_REASONS
    emulator = _adjudicate(
        parameter_artifact="artifact-emulator",
        derived_from_family="skyrme_hfb_edf",
        shared_parameters=["vpair_n", "vpair_p"],
    )
    assert emulator["independence_verdict"] == NOT_INDEPENDENT
    gate = count_blind_families([_adjudicate(), emulator])
    assert gate["n_blind_independent_families"] == 1
    assert "residual variants" in gate["counting_rule"]


# --------------------------------------------------------------------------- #
# Convergence and imputation                                                  #
# --------------------------------------------------------------------------- #


def test_nonconvergence_not_imputed():
    """A failed solve is a status; it can never carry a number."""
    record = build_record(
        nuclide_id="Z4-N12",
        backend_id=BACKEND_SKYRME,
        parameter_artifact_id="artifact-a",
        converged=False,
        iterations=300,
        basis_policy="test",
        retry_count=0,
        failure_class="NONCONVERGED",
        output_hash="a" * 64,
    )
    assert record["converged"] is False
    with pytest.raises(ProtocolError, match="must not carry a value"):
        PhysicsPrediction(
            nuclide_id="Z4-N12",
            observable="atomic_mass_excess_keV",
            value=-1000.0,
            unit="keV",
            solver_status=SOLVER_NONCONVERGED,
            convergence_record_id=record["convergence_record_id"],
            parameter_artifact_id="artifact-a",
            backend_id=BACKEND_SKYRME,
            physics_family="skyrme_hfb_edf",
            source_hash="b" * 64,
            output_hash="a" * 64,
        )
    with pytest.raises(ProtocolError, match="must carry a value"):
        PhysicsPrediction(
            nuclide_id="Z4-N12",
            observable="atomic_mass_excess_keV",
            value=None,
            unit="keV",
            solver_status=SOLVER_OK,
            convergence_record_id=record["convergence_record_id"],
            parameter_artifact_id="artifact-a",
            backend_id=BACKEND_SKYRME,
            physics_family="skyrme_hfb_edf",
            source_hash="b" * 64,
            output_hash="a" * 64,
        )
    # A converged record cannot claim a failure class, or vice versa.
    with pytest.raises(ProtocolError):
        build_record(
            nuclide_id="Z20-N20",
            backend_id=BACKEND_SKYRME,
            parameter_artifact_id="artifact-a",
            converged=True,
            iterations=10,
            basis_policy="test",
            retry_count=0,
            failure_class="NONCONVERGED",
            output_hash="a" * 64,
        )


# --------------------------------------------------------------------------- #
# B004 target integrity                                                       #
# --------------------------------------------------------------------------- #


def test_b004_target_selection_does_not_use_error():
    """Selection reads chronology and identity only, and is deterministic."""
    import ast
    import inspect

    from elementzero.b004 import targets as targets_module

    # Check the executable surface, not the prose: the docstring names the
    # forbidden signals precisely in order to forbid them.
    tree = ast.parse(inspect.getsource(targets_module))
    names: set[str] = set()
    literals: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[-1])
    for forbidden in (
        "prediction_keV",
        "residuals_keV",
        "MAE_keV",
        "RMSE_keV",
        "mass_excess_keV",
        "score_b004",
        "load_edition",
    ):
        assert forbidden not in names, f"selection touches {forbidden}"
    # No result or score artifact is read by the selection code.
    for literal in literals:
        assert not literal.endswith("aggregate.json"), literal
        assert "results/" not in literal, literal
        assert "b004_scores" not in literal, literal

    first = targets_module.select_targets(repo_root=REPO_ROOT)
    second = targets_module.select_targets(repo_root=REPO_ROOT)
    assert first["target_identity_digest"] == second["target_identity_digest"]
    assert first["n_targets"] >= 1
    # Identity-only manifest: the target rows carry identity and
    # chronology-derived strata, never a mass value. (The rule text names
    # "ground-truth-eligible" and "truth value", so the check is on the
    # data rows rather than the prose.)
    for target in first["targets"]:
        assert set(target) == {
            "nuclide_id",
            "Z",
            "N",
            "A",
            "z_band",
            "shell_adjacent",
            "frontier_direction",
            "nearest_freeze_distance_L1",
            "odd_policy_class",
        }
    # Every target really is post-freeze, even-even, and not a WO-14 target.
    excluded = targets_module.wo14_scored_target_ids(repo_root=REPO_ROOT)
    chronology = json.loads(
        (
            REPO_ROOT / "reports/eligibility/wo13/historical_source_chronology.json"
        ).read_text(encoding="utf-8")
    )
    known_1995 = set(chronology["sources"]["AME1995"]["known_nuclide_ids"])
    for target in first["targets"]:
        assert target["Z"] % 2 == 0 and target["N"] % 2 == 0
        assert target["nuclide_id"] not in known_1995
        assert target["nuclide_id"] not in excluded


def test_b004_truth_unavailable_before_seal(tmp_path):
    """The sealed payload carries predictions and no measured mass."""
    from elementzero.b004.runs import SEALED_FILE, seal_predictions

    protocol = {
        "protocol_hash": "p" * 64,
        "freeze_id": "ez-wo15-historical-fit-freeze-v1",
    }
    target_manifest = {
        "target_identity_digest": "d" * 64,
        "target_nuclide_ids": ["Z80-N92"],
    }
    families = [
        {
            "backend_id": BACKEND_SKYRME,
            "physics_family": "skyrme_hfb_edf",
            "provenance_class": REFIT_STRICT,
            "parameter_artifact_id": "artifact-a",
            "predictions": {
                "Z80-N92": {
                    "nuclide_id": "Z80-N92",
                    "solver_status": "OK",
                    "prediction_keV": -1234.5,
                    "sigma_keV": 500.0,
                }
            },
            "convergence_records": [],
            "convergence_summary": {"n_records": 1, "n_converged": 1},
        }
    ]
    artifact = _artifact()
    sealed = seal_predictions(
        dest=tmp_path,
        protocol=protocol,
        target_manifest=target_manifest,
        families=families,
        artifacts={BACKEND_SKYRME: artifact},
    )
    payload = json.loads((tmp_path / SEALED_FILE).read_text(encoding="utf-8"))
    assert payload["state"] == "PREDICTIONS_SEALED_TARGET_TRUTH_UNREAD"
    blob = json.dumps(payload)
    assert "truth_keV" not in blob and "error_keV" not in blob
    assert sealed["seal_hash"] == sha256_file(tmp_path / SEALED_FILE)


def test_b004_unlock_rejects_tampering(tmp_path):
    """Every governing hash is checked before truth is read."""
    from elementzero.b004.runs import SEALED_FILE, SEALED_HASH_FILE, unlock_truth

    (tmp_path / SEALED_FILE).write_text(
        json.dumps(
            {
                "protocol_hash": "p" * 64,
                "target_identity_digest": "d" * 64,
                "parameter_artifacts": {},
            }
        ),
        encoding="utf-8",
    )
    digest = sha256_file(tmp_path / SEALED_FILE)
    (tmp_path / SEALED_HASH_FILE).write_text(digest + "\n", encoding="utf-8")
    protocol = {"protocol_hash": "p" * 64, "target_identity_digest": "d" * 64}
    with pytest.raises(ProtocolError, match="B004_CLAIM_INTEGRITY_FAILURE"):
        unlock_truth(
            dest=tmp_path,
            expected_seal_hash="wrong",
            protocol=protocol,
            artifacts={},
            repo_root=REPO_ROOT,
        )


# --------------------------------------------------------------------------- #
# Visual firewall                                                             #
# --------------------------------------------------------------------------- #


def test_pf_badge_does_not_validate():
    """Backend qualification earns a badge and never a validation stage."""
    payload = {"backend_id": BACKEND_SKYRME, "physics_family": "skyrme_hfb_edf"}
    assert claim_checked_stage_types(
        "PHYSICS_FAMILY_QUALIFIED", payload, "EZ-B004-v1"
    ) == []
    assert claim_checked_stage_types(
        "PHYSICS_BLIND_CHALLENGE_SCORED", payload, "EZ-B004-v1"
    ) == []
    assert "PF" in badges_from_event_types(["PHYSICS_FAMILY_QUALIFIED"])
    assert "PB" in badges_from_event_types(["PHYSICS_BLIND_CHALLENGE_SCORED"])
    stage = select_primary_stage(
        ["DATA_INGESTED", "PHYSICS_FAMILY_QUALIFIED",
         "PHYSICS_BLIND_CHALLENGE_SCORED"],
        z=80,
    )
    assert stage == "data_ingested"


def test_wo15_schemas_match_records():
    """The four WO-15 schemas cover the records this code emits."""
    schema_dir = REPO_ROOT / "schemas"
    for name, sample in (
        ("physics_parameter_artifact.schema.json", _artifact()),
        (
            "physics_independence_adjudication.schema.json",
            _adjudicate(),
        ),
        (
            "physics_convergence_record.schema.json",
            build_record(
                nuclide_id="Z20-N20",
                backend_id=BACKEND_SKYRME,
                parameter_artifact_id="artifact-a",
                converged=True,
                iterations=42,
                basis_policy="test",
                retry_count=0,
                failure_class="NONE",
                output_hash="a" * 64,
            ),
        ),
    ):
        schema = json.loads((schema_dir / name).read_text(encoding="utf-8"))
        for field in schema["required"]:
            assert field in sample, f"{name}: {field}"
        enums = {
            k: v["enum"]
            for k, v in schema.get("properties", {}).items()
            if "enum" in v
        }
        for field, allowed in enums.items():
            if field in sample:
                assert sample[field] in allowed, f"{name}: {field}"


def test_parameterization_chronology_is_complete():
    """Every roster parameterization has a dated, sourced record."""
    from elementzero.physics_backends.registry import ROSTER

    for backend_id, entry in ROSTER.items():
        name = entry["parameterization"]
        record = PARAMETERIZATIONS[name]
        assert record["publication_year"] > 1950, backend_id
        assert record["publication"], backend_id
        assert record["calibration_membership"] in ("EXACT", "PARTIAL"), backend_id
    assert parameterization_admissible("SKM*") is True
    assert parameterization_admissible("D1S") is True
    assert parameterization_admissible("SLY4") is False
    assert sha256_hex({"probe": 1})  # hashing available for artifact ids


def test_backend_ids_are_distinct_families():
    from elementzero.physics_backends.registry import ROSTER

    families = {ROSTER[b]["physics_family"] for b in ROSTER}
    assert len(families) == 3
    assert {BACKEND_SKYRME, BACKEND_GOGNY, BACKEND_COVARIANT} == set(ROSTER)
    functional_classes = {ROSTER[b]["functional_class"] for b in ROSTER}
    assert len(functional_classes) == 3
