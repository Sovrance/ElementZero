"""WO-12 federation protocol, registry, combination, and governance tests."""

from __future__ import annotations

import json

import pytest

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.identity import NuclideIdentity
from elementzero.data.model_tables.parser import ParsedTable, TableRow
from elementzero.data.observations import MassObservation
from elementzero.errors import LeakageError, ProtocolError
from elementzero.models.federation import GROUP_RESIDUAL_ML
from elementzero.models.federation.calibration import (
    assert_split_disjoint,
    split_fit_calibration,
)
from elementzero.models.federation.combination import (
    UniformEnsemble,
    ValidationWeightedEnsemble,
)
from elementzero.models.federation.disagreement import target_disagreement
from elementzero.models.federation.protocol import (
    OOD_POLICY_ID,
    OOD_POLICY_RULE,
    FederationPrediction,
    ood_status,
)
from elementzero.models.federation.registry import (
    MODEL_ID_GP_OPTIMIZED,
    FederationRegistry,
    OptimizedGPControl,
    WrappedBaselineModel,
)
from elementzero.models.federation.residual_wrapper import ResidualCorrectedModel
from elementzero.models.federation.runtime_lock import (
    assert_lock_complete,
    read_runtime_lock,
)
from elementzero.models.federation.table_model import TableMassModel

WO12_REPORTS = REPO_ROOT / "reports" / "model_federation" / "wo12"


def _toy_table(cells: dict[tuple[int, int], float]) -> ParsedTable:
    rows = {
        (z, n): TableRow(
            Z=z, N=n, A=z + n, mass_excess_keV=v, experimental_minus_calculated_keV=None
        )
        for (z, n), v in cells.items()
    }
    return ParsedTable(table_id="TOY", rows=rows, n_rows=len(rows), empirical_rms_keV=500.0)


def _toy_manifest(status: str = "APPROVED") -> dict:
    return {
        "source_url": "https://example.invalid/toy",
        "publication": "toy",
        "publication_doi": "https://example.invalid/doi",
        "raw_sha256": "0" * 64,
        "parser_version": "test",
        "table_version": "test",
        "model_id": "EZ-TOY-TABLE-v1",
        "observables": ["atomic_mass_excess_keV"],
        "units": "MeV -> keV",
        "license_status": status,
    }


def _observations(cells: dict[tuple[int, int], float]) -> list[MassObservation]:
    from elementzero.data.observations import RECORD_STATUS_EVALUATED_NON_ESTIMATED

    return [
        MassObservation(
            nuclide=NuclideIdentity.from_zn(z, n),
            mass_excess_keV=v,
            uncertainty_keV=10.0,
            source_edition="AME2020",
            source_release_date="2021-03-01",
            source_record_status=RECORD_STATUS_EVALUATED_NON_ESTIMATED,
            raw_source_hash="x" * 64,
        )
        for (z, n), v in sorted(cells.items())
    ]


def _grid(z0=20, z1=27, n0=20, n1=27, base=-60000.0):
    return {
        (z, n): base + 50.0 * (z - z0) + 35.0 * (n - n0)
        for z in range(z0, z1 + 1)
        for n in range(n0, n1 + 1)
    }


# --------------------------------------------------------------------------- #
# Prerequisites / governance                                                  #
# --------------------------------------------------------------------------- #


def test_wo12_prerequisites_read_from_wo11():
    baseline = json.loads((WO12_REPORTS / "input_baseline.json").read_text(encoding="utf-8"))
    readiness = json.loads(
        (REPO_ROOT / "reports" / "adjudication" / "wo11" / "model_readiness.json").read_text(
            encoding="utf-8"
        )
    )
    assert baseline["wo11_verdict"] == "FRONTIER_MODEL_RERUN_JUSTIFIED"
    verification = baseline["prerequisite_verification"]
    assert len(verification) == len(readiness["wo12_prerequisites"]) == 11
    for item, prerequisite in zip(verification, readiness["wo12_prerequisites"]):
        assert item["prerequisite"] == prerequisite
        assert item["disposition"].startswith(("SATISFIED", "ADDRESSED"))
    assert baseline["v03_tag_closeout"]["tag"] == "elementzero-validation-ladder-v0.3"


def test_v1_artifacts_unchanged():
    from elementzero.adjudication.artifact_audit import (
        assert_v1_evidence_unchanged,
        build_artifact_inventory,
    )

    inventory = build_artifact_inventory()
    assert inventory["all_unchanged"] is True
    assert_v1_evidence_unchanged(inventory)


def test_baseline_controls_preserved():
    from elementzero.models.gp_residual import (
        MODEL_ID_GP_DIRECT,
        MODEL_ID_SEMF_GP,
        MODEL_ID_SEMF_LS,
        build_model,
    )

    manifest = json.loads(
        (WO12_REPORTS / "federation_manifest.json").read_text(encoding="utf-8")
    )
    participants = manifest["participants"]
    for baseline_id in (MODEL_ID_SEMF_LS, MODEL_ID_GP_DIRECT, MODEL_ID_SEMF_GP):
        assert participants[baseline_id]["role"] == "CONTROL"
        # The frozen v1 registry still builds the frozen classes untouched.
        assert build_model(baseline_id).model_id == baseline_id
    assert participants[MODEL_ID_GP_OPTIMIZED]["role"] == "CONTROL"


def test_license_gate_blocks_unapproved_model():
    registry = FederationRegistry()
    for status in ("BLOCKED_AVAILABILITY", "BLOCKED_LICENSE", "APPROVED_REFERENCE_ONLY"):
        with pytest.raises(ProtocolError):
            registry.register(
                model_id=f"blocked-{status}",
                role="PHYSICS_BACKBONE",
                independence_group="skyrme_edf_bskg",
                builder=lambda: None,
                license_status=status,
            )
    registry.register(
        model_id="approved",
        role="PHYSICS_BACKBONE",
        independence_group="skyrme_edf_bskg",
        builder=lambda: None,
        license_status="APPROVED",
    )
    assert registry.model_count == 1


def test_independence_groups():
    manifest = json.loads(
        (WO12_REPORTS / "federation_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["model_count"] == 10
    assert manifest["independence_group_count"] == 6
    assert set(manifest["physics_backbone_groups"]) == {
        "skyrme_edf_bskg",
        "macroscopic_microscopic_frdm",
    }
    # A residual variant of one base model is never an independent model.
    table = TableMassModel(
        model_id="EZ-TOY-TABLE-v1",
        family_id="toy",
        independence_group="skyrme_edf_bskg",
        table=_toy_table(_grid()),
        source_manifest=_toy_manifest(),
    )
    residual = ResidualCorrectedModel(table)
    assert residual.independence_group == GROUP_RESIDUAL_ML
    assert residual.manifest()["base_independence_group"] == "skyrme_edf_bskg"


def test_runtime_lock_complete():
    lock = read_runtime_lock(REPO_ROOT / "runtime.lock.json")
    assert_lock_complete(lock)
    assert lock["python_minor"] in ("3.11", "3.12", "3.13")
    assert lock["blas_lapack"]["blas"]["name"]


# --------------------------------------------------------------------------- #
# Coverage / uncertainty / disagreement mechanics                             #
# --------------------------------------------------------------------------- #


def test_missing_table_prediction_explicit():
    table = TableMassModel(
        model_id="EZ-TOY-TABLE-v1",
        family_id="toy",
        independence_group="skyrme_edf_bskg",
        table=_toy_table({(20, 20): -1000.0}),
        source_manifest=_toy_manifest(),
    )
    table.fit(_observations({(20, 20): -1000.0}))
    missing = table.predict(NuclideIdentity.from_zn(21, 21))
    assert missing.status == "OUT_OF_TABLE"
    assert missing.point_keV is None
    with pytest.raises(ProtocolError):
        missing.to_benchmark_prediction(uncertainty_method="test")
    with pytest.raises(ProtocolError):
        FederationPrediction(
            nuclide=NuclideIdentity.from_zn(21, 21),
            status="OUT_OF_TABLE",
            model_id="x",
            point_keV=0.0,  # a missing prediction is never a number
        )


def test_uncertainty_components_preserved():
    prediction = FederationPrediction(
        nuclide=NuclideIdentity.from_zn(20, 20),
        status="AVAILABLE",
        model_id="x",
        point_keV=-1000.0,
        within_model_std_keV=300.0,
        residual_std_keV=400.0,
        model_disagreement_std_keV=0.0,
        nearest_training_L1=2,
    )
    assert prediction.predictive_std_keV == pytest.approx(500.0)
    payload = prediction.to_dict()
    for field in (
        "point_keV",
        "within_model_std_keV",
        "residual_std_keV",
        "model_disagreement_std_keV",
        "predictive_std_keV",
        "predictive_interval_90",
        "predictive_interval_95",
        "nearest_training_L1",
        "ood_status",
    ):
        assert field in payload
    assert payload["ood_status"] == "LOCAL_EXTRAPOLATION"


def test_disagreement_metrics():
    summary = target_disagreement({"a": 1.0, "b": 2.0, "c": 3.0})
    assert summary["ensemble_mean_keV"] == pytest.approx(2.0)
    assert summary["disagreement_std_keV"] == pytest.approx(0.816496580927726)
    assert summary["disagreement_mad_keV"] == pytest.approx(1.0)
    lonely = target_disagreement({"a": 5.0})
    assert lonely["disagreement_std_keV"] is None


def test_ood_policy_versioned():
    assert OOD_POLICY_ID.endswith("-v1")
    assert OOD_POLICY_ID in OOD_POLICY_RULE
    assert ood_status(0) == "IN_DOMAIN"
    assert ood_status(2) == "LOCAL_EXTRAPOLATION"
    assert ood_status(4) == "REGIONAL_EXTRAPOLATION"
    assert ood_status(9) == "EXTREME_EXTRAPOLATION"
    assert ood_status(None) is None


# --------------------------------------------------------------------------- #
# Leakage discipline                                                          #
# --------------------------------------------------------------------------- #


def test_residual_wrapper_no_truth_leakage():
    cells = _grid()
    targets = {(23, 23), (23, 24), (24, 23)}
    training = {k: v for k, v in cells.items() if k not in targets}
    table = TableMassModel(
        model_id="EZ-TOY-TABLE-v1",
        family_id="toy",
        independence_group="skyrme_edf_bskg",
        table=_toy_table({k: v - 750.0 for k, v in cells.items()}),
        source_manifest=_toy_manifest(),
    )
    residual = ResidualCorrectedModel(table)
    residual.fit(_observations(training))
    manifest = residual.manifest()
    target_ids = {f"Z{z}-N{n}" for z, n in targets}
    assert not target_ids & set(manifest["fitted_nuclide_ids"])
    assert not any(tid in json.dumps(manifest) for tid in target_ids)
    prediction = residual.predict(NuclideIdentity.from_zn(23, 23))
    assert prediction.status == "AVAILABLE"
    # The table offset is constant, so the correction must recover truth well.
    assert abs(prediction.point_keV - cells[(23, 23)]) < 100.0


def test_combiner_uses_training_only():
    cells = _grid()
    observations = _observations(cells)
    components = [
        TableMassModel(
            model_id=f"EZ-TOY-{offset}-v1",
            family_id="toy",
            independence_group="skyrme_edf_bskg",
            table=_toy_table({k: v + offset for k, v in cells.items()}),
            source_manifest=_toy_manifest(),
        )
        for offset in (-200.0, 300.0)
    ]
    ensemble = ValidationWeightedEnsemble(components, model_id="EZ-TOY-ENSEMBLE")
    ensemble.fit(observations)
    manifest = ensemble.manifest()
    from elementzero.evidence.freezes import identity_digest

    _, calibration_set = split_fit_calibration(observations)
    expected_digest = identity_digest(sorted(o.nuclide_id for o in calibration_set))
    assert manifest["calibration"]["calibration_identity_digest"] == expected_digest
    assert "hidden benchmark truth never enters" in manifest["calibration"]["truth_rule"]
    # The closer component earns the larger weight, from training data alone.
    weights = manifest["weights"]
    assert weights["EZ-TOY--200.0-v1"] > weights["EZ-TOY-300.0-v1"]


def test_fit_calibration_target_ids_disjoint():
    record = assert_split_disjoint(
        fit_ids=["Z1-N1", "Z1-N2"],
        calibration_ids=["Z1-N3"],
        benchmark_target_ids=["Z9-N9"],
    )
    assert record["n_fit"] == 2 and record["n_calibration"] == 1
    with pytest.raises(LeakageError):
        assert_split_disjoint(
            fit_ids=["Z1-N1"],
            calibration_ids=["Z1-N3"],
            benchmark_target_ids=["Z1-N1"],
        )
    with pytest.raises(LeakageError):
        assert_split_disjoint(
            fit_ids=["Z1-N1"],
            calibration_ids=["Z1-N1"],
            benchmark_target_ids=["Z9-N9"],
        )


def test_shell_feature_firewall_still_blocks_magic_features():
    from elementzero.adjudication.ablations import assert_dev_shell_features
    from elementzero.benchmark.b003_prepare import assert_discovery_features

    for forbidden in ("magic_label", "distance_to_126", "shellDistance", "known_closure"):
        with pytest.raises(LeakageError):
            assert_discovery_features(["Z", "N", "A", forbidden])
        with pytest.raises(LeakageError):
            assert_dev_shell_features(("Z", "N", "A", forbidden))
    # Every federation participant declares identity features only.
    table = TableMassModel(
        model_id="EZ-TOY-TABLE-v1",
        family_id="toy",
        independence_group="skyrme_edf_bskg",
        table=_toy_table(_grid()),
        source_manifest=_toy_manifest(),
    )
    assert table.manifest()["features"] == ["Z", "N", "A"]
    assert OptimizedGPControl().manifest()["features"] == ["Z", "N", "A"]
    assert WrappedBaselineModel("EZ-SEMF-LS-v1").manifest()["features"] == ["Z", "N", "A"]
    uniform = UniformEnsemble([table], model_id="EZ-TOY-U")
    assert uniform.manifest()["features"] == ["Z", "N", "A"]


# --------------------------------------------------------------------------- #
# v2 qualification governance artifacts                                       #
# --------------------------------------------------------------------------- #


def test_v2_qualification_fixture_differs_from_v1(tmp_path):
    from elementzero.adjudication.ablations import (
        write_b002_dev_chart,
        write_b003_dev_chart,
    )
    from elementzero.evidence.hashing import sha256_file
    from elementzero.experiments.wo12_qualification import (
        B003_QUAL_NEUTRON_CLOSURE,
        B003_QUAL_PROTON_CLOSURE,
        write_b002_qual_chart,
        write_b003_qual_chart,
    )

    committed_b002 = REPO_ROOT / "tests" / "fixtures" / "wo12" / "ez-b002-v2-qual-chart.mas20"
    committed_b003 = REPO_ROOT / "tests" / "fixtures" / "wo12" / "ez-b003-v2-qual-chart.mas20"
    # Byte-reproducible from code.
    assert sha256_file(write_b002_qual_chart(tmp_path / "b002.mas20")) == sha256_file(
        committed_b002
    )
    assert sha256_file(write_b003_qual_chart(tmp_path / "b003.mas20")) == sha256_file(
        committed_b003
    )
    others = {
        sha256_file(REPO_ROOT / "tests" / "fixtures" / "b002" / "synthetic_chart_v1.mas20"),
        sha256_file(
            REPO_ROOT / "tests" / "fixtures" / "b003" / "synthetic_shell_chart_v1.mas20"
        ),
        sha256_file(write_b002_dev_chart(tmp_path / "dev-b002.mas20")),
        sha256_file(write_b003_dev_chart(tmp_path / "dev-b003.mas20")),
    }
    assert sha256_file(committed_b002) not in others
    assert sha256_file(committed_b003) not in others
    # Closures moved off both the v1 pair and the WO-11 dev pair.
    assert (B003_QUAL_NEUTRON_CLOSURE, B003_QUAL_PROTON_CLOSURE) not in {(50, 28), (82, 50)}


def test_thresholds_frozen_before_real_truth():
    for experiment_id in ("EZ-B002-v2", "EZ-B003-v2"):
        directory = REPO_ROOT / "experiments" / experiment_id
        protocol = json.loads((directory / "PROTOCOL.json").read_text(encoding="utf-8"))
        assert protocol["state"] == "QUALIFICATION_ONLY"
        assert protocol["frozen_thresholds"]
        markdown = (directory / "PREREGISTRATION.md").read_text(encoding="utf-8")
        assert "QUALIFICATION_ONLY" in markdown
    qualification = json.loads(
        (WO12_REPORTS / "synthetic_qualification.json").read_text(encoding="utf-8")
    )
    assert float(qualification["protocol"]["b003_v2_criterion"]["min_rank_1_fraction"]) == 0.5
    assert "evaluated-table" in qualification["evaluated_table_rule"]


def test_atlas_lineage_preserves_model_sources():
    facts = json.loads((WO12_REPORTS / "atlas" / "facts.json").read_text(encoding="utf-8"))
    by_kind: dict[str, list[dict]] = {}
    for fact in facts:
        by_kind.setdefault(fact["content"]["kind"], []).append(fact)
    adapters = by_kind["federation_model_adapter"]
    assert {f["content"]["model_id"] for f in adapters} == {
        "EZ-BSKG3-TABLE-v1",
        "EZ-FRDM95-TABLE-v1",
    }
    for fact in adapters:
        assert fact["content"]["table_raw_sha256"]
    combinations = by_kind["federation_combination"]
    for fact in combinations:
        content = fact["content"]
        assert content["contributing_fact_ids"], "contributors must never be anonymous"
        assert content["weights"]
        assert set(content["contributing_model_ids"]) == set(content["contributing_fact_ids"])
    assert by_kind["federation_residual_model_fit"]
    assert by_kind["federation_residual_corrected_prediction_set"]


def test_visual_does_not_upgrade_on_qualification_failure():
    from elementzero.visuals.aggregate import aggregate_events, health_from_events
    from elementzero.visuals.event_types import ProgressEvent, make_event_id
    from elementzero.visuals.status import EVENT_TO_STAGE

    for event_type in (
        "FEDERATION_MODEL_AVAILABLE",
        "FEDERATION_QUALIFICATION_TARGETED",
        "FEDERATION_QUALIFICATION_SCORED",
    ):
        assert event_type not in EVENT_TO_STAGE

    def _event(event_type: str, status: str) -> ProgressEvent:
        return ProgressEvent(
            event_id=make_event_id(
                event_type=event_type, source_hash="f" * 64, element_Z=82
            ),
            event_type=event_type,
            event_time="2026-08-16T12:00:00Z",
            project_version="test",
            source_kind="test",
            source_path="test",
            source_hash="f" * 64,
            element_Z=82,
            status=status,
        )

    events = [
        _event("FEDERATION_QUALIFICATION_TARGETED", "info"),
        _event("FEDERATION_QUALIFICATION_SCORED", "fail"),
    ]
    health = health_from_events(events)
    assert health["benchmark"] == "unknown"  # qualification never flips health
    state = aggregate_events(events)
    element = next(e for e in state["elements"] if e["Z"] == 82)
    assert element["project_primary_stage"] == "not_touched"
