"""WO-12 qualification mechanics and report reproducibility."""

from __future__ import annotations

import json

import pytest

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.model_tables.manifests import table_available
from elementzero.data.model_tables.parser import ParsedTable, TableRow
from elementzero.evidence.hashing import sha256_file

TABLES_PRESENT = table_available("BSKG3") and table_available("FRDM95")
WO12_REPORTS = REPO_ROOT / "reports" / "model_federation" / "wo12"

# Artifacts whose bytes are runtime-independent within one runtime and fully
# deterministic across rebuilds on the reference runtime.
COMMITTED_REPORT_FILES = (
    "input_baseline.json",
    "candidate_review.json",
    "license_availability_review.json",
    "federation_manifest.json",
    "synthetic_qualification.json",
    "calibration_report.json",
    "WO12_Model_Federation_Report.md",
)


def _mini_registry(chart_cells):
    """A small CI-safe federation: no raw tables, same machinery."""
    from elementzero.models.federation.capabilities import (
        ROLE_COMBINER,
        ROLE_CONTROL,
        ROLE_PHYSICS_BACKBONE,
        ROLE_RESIDUAL_CHALLENGER,
    )
    from elementzero.models.federation.combination import UniformEnsemble
    from elementzero.models.federation.registry import (
        FederationRegistry,
        WrappedBaselineModel,
    )
    from elementzero.models.federation.residual_wrapper import ResidualCorrectedModel
    from elementzero.models.federation.table_model import TableMassModel

    rows = {
        (z, n): TableRow(
            Z=z,
            N=n,
            A=z + n,
            mass_excess_keV=v - 1500.0,  # a constant physics offset
            experimental_minus_calculated_keV=None,
        )
        for (z, n), v in chart_cells.items()
    }
    table = ParsedTable(table_id="TOY", rows=rows, n_rows=len(rows), empirical_rms_keV=800.0)
    manifest = {
        "source_url": "https://example.invalid/toy",
        "publication": "toy fixture",
        "publication_doi": "https://example.invalid/doi",
        "raw_sha256": "0" * 64,
        "parser_version": "test",
        "table_version": "test",
        "model_id": "EZ-TOY-TABLE-v1",
        "observables": ["atomic_mass_excess_keV"],
        "units": "MeV -> keV",
        "license_status": "APPROVED",
    }

    def _table():
        return TableMassModel(
            model_id="EZ-TOY-TABLE-v1",
            family_id="toy",
            independence_group="skyrme_edf_bskg",
            table=table,
            source_manifest=manifest,
        )

    registry = FederationRegistry()
    registry.register(
        model_id="EZ-SEMF-LS-v1",
        role=ROLE_CONTROL,
        independence_group="liquid_drop_baseline",
        builder=lambda: WrappedBaselineModel("EZ-SEMF-LS-v1"),
        full_chart_coverage=True,
    )
    registry.register(
        model_id="EZ-TOY-TABLE-v1",
        role=ROLE_PHYSICS_BACKBONE,
        independence_group="skyrme_edf_bskg",
        builder=_table,
        license_status="APPROVED",
    )
    registry.register(
        model_id="EZ-TOY-TABLE-v1+GP-RESIDUAL-v1",
        role=ROLE_RESIDUAL_CHALLENGER,
        independence_group="residual_ml",
        builder=lambda: ResidualCorrectedModel(_table()),
    )
    registry.register(
        model_id="EZ-TOY-UNIFORM-v1",
        role=ROLE_COMBINER,
        independence_group="model_combination",
        builder=lambda: UniformEnsemble(
            [_table(), ResidualCorrectedModel(_table())], model_id="EZ-TOY-UNIFORM-v1"
        ),
    )
    return registry


def _chart_cells(path):
    from elementzero.data.amdc import load_edition

    return {
        (o.Z, o.N): o.mass_excess_keV
        for o in load_edition("AME2020", str(path))
        if o.ground_truth_eligible
    }


def test_mini_federation_through_frozen_b002_mechanics(tmp_path):
    """The sealed pipeline accepts federation participants end to end."""
    from tests.helpers import write_small_synthetic_chart

    from elementzero.adjudication.benchmark_controls import control_model_registry
    from elementzero.evidence.ledger import read_json
    from elementzero.experiments.b002_runner import (
        score_b002,
        seal_b002,
        select_regions_for_source,
    )
    from elementzero.experiments.wo12_qualification import FederationRunAdapter

    chart = write_small_synthetic_chart(tmp_path / "chart.mas20")
    registry = _mini_registry(_chart_cells(chart))
    recorder: dict[str, dict] = {}
    builders = {
        model_id: (lambda m=model_id: FederationRunAdapter(registry.build(m), recorder))
        for model_id in registry.model_ids
    }
    regions_path = tmp_path / "regions.json"
    select_regions_for_source(
        source=chart,
        edition_id="AME2020",
        output=regions_path,
        source_relpath="chart.mas20",
        bands=("light",),
        allow_missing_bands=True,
    )
    experiment_dir = tmp_path / "exp"
    with control_model_registry(builders):
        seal_b002(
            source=chart,
            edition_id="AME2020",
            regions_path=regions_path,
            experiment_dir=experiment_dir,
            created_at="2026-08-16T12:00:00Z",
            model_ids=tuple(registry.model_ids),
        )
        score_b002(
            source=chart,
            edition_id="AME2020",
            experiment_dir=experiment_dir,
            created_at="2026-08-16T12:00:00Z",
        )
    aggregate = read_json(experiment_dir / "region_aggregate.json")
    assert set(aggregate["model_ids"]) == set(registry.model_ids)
    # The recorder captured a decomposed prediction for every sealed target
    # instance, keyed by the fit identity of the split that produced it.
    n_targets = aggregate["n_scored_targets"] // len(registry.model_ids)
    for model_id in registry.model_ids:
        recorded = sum(len(per_fit) for per_fit in recorder[model_id].values())
        assert recorded >= n_targets
    # The constant table offset is fully recovered by the residual challenger.
    residual_mae = float(
        aggregate["by_model"]["EZ-TOY-TABLE-v1+GP-RESIDUAL-v1"]["pooled"]["MAE_keV"]
    )
    table_mae = float(aggregate["by_model"]["EZ-TOY-TABLE-v1"]["pooled"]["MAE_keV"])
    assert residual_mae < table_mae


@pytest.mark.skipif(not TABLES_PRESENT, reason="raw model tables not fetched")
def test_committed_qualification_artifacts_are_coherent():
    qualification = json.loads(
        (WO12_REPORTS / "synthetic_qualification.json").read_text(encoding="utf-8")
    )
    assert qualification["qualification_status"] == "PASS"
    b003 = qualification["EZ-B003-v2-qual"]
    assert "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1" in b003["models_meeting_criterion"]
    # Committed chart fixtures match the hashes the qualification recorded.
    for name, digest in qualification["fixture_hashes"].items():
        assert sha256_file(REPO_ROOT / "tests" / "fixtures" / "wo12" / name) == digest
    # The sealed summaries under experiments/ agree with the report.
    aggregate = json.loads(
        (
            REPO_ROOT / "experiments" / "EZ-B003-v2" / "qualification" / "shell_aggregate.json"
        ).read_text(encoding="utf-8")
    )
    for model_id, payload in aggregate["by_model"].items():
        assert payload["criterion"]["verdict"] == b003["by_model"][model_id]["verdict"]
    # The two B003 challenges share nine target nuclides; every prediction
    # instance is kept per split fit (63 + 75 = 138), never overwritten.
    for model_id, statuses in b003["coverage"].items():
        assert sum(statuses.values()) == 138, model_id
    for model_id, payload in b003["calibration_by_model"].items():
        assert payload["n"] == 138, model_id
    # Residual lineage carries one fit identity per split, not the first
    # split's identity standing in for all of them.
    for model_id, entry in b003["lineage_inputs"].items():
        digests = [s["prediction_set_digest"] for s in entry["splits"]]
        assert len(digests) == 2 and len(set(digests)) == 2, model_id
    # The committed B002-v2 worst-region table ranks numerically.
    region_aggregate = json.loads(
        (
            REPO_ROOT / "experiments" / "EZ-B002-v2" / "qualification" / "region_aggregate.json"
        ).read_text(encoding="utf-8")
    )
    for model_id, payload in region_aggregate["by_model"].items():
        worst = max(payload["per_region"], key=lambda r: float(r["MAE_keV"]))
        assert payload["worst_region"]["region_id"] == worst["region_id"], model_id


@pytest.mark.skipif(not TABLES_PRESENT, reason="raw model tables not fetched")
def test_wo12_report_reproducible(tmp_path):
    """A fresh full rebuild reproduces the committed bundle byte for byte on
    the reference runtime; elsewhere the statuses and verdicts must match."""
    from elementzero.models.federation.runtime_lock import compare_runtime, read_runtime_lock
    from elementzero.reporting.wo12_federation import run_wo12

    result = run_wo12(
        out_dir=tmp_path / "out", workspace_dir=tmp_path / "ws", commit_artifacts=False
    )
    assert result["qualification_status"] == "PASS"
    lock = read_runtime_lock(REPO_ROOT / "runtime.lock.json")
    if compare_runtime(lock)["mode"] == "REFERENCE_MATCH":
        for name in COMMITTED_REPORT_FILES:
            assert sha256_file(tmp_path / "out" / name) == sha256_file(
                WO12_REPORTS / name
            ), name
        for name in ("facts.json", "provenance.json", "artifacts.json"):
            assert sha256_file(tmp_path / "out" / "atlas" / name) == sha256_file(
                WO12_REPORTS / "atlas" / name
            ), name
    else:
        fresh = json.loads(
            (tmp_path / "out" / "synthetic_qualification.json").read_text(encoding="utf-8")
        )
        committed = json.loads(
            (WO12_REPORTS / "synthetic_qualification.json").read_text(encoding="utf-8")
        )
        assert fresh["qualification_status"] == committed["qualification_status"]
        for benchmark in ("EZ-B002-v2-qual", "EZ-B003-v2-qual"):
            fresh_verdicts = {
                m: p.get("verdict", p.get("MAE_keV"))
                for m, p in fresh[benchmark]["by_model"].items()
            }
            committed_verdicts = {
                m: p.get("verdict", p.get("MAE_keV"))
                for m, p in committed[benchmark]["by_model"].items()
            }
            assert set(fresh_verdicts) == set(committed_verdicts)


def test_mini_federation_through_frozen_b003_mechanics(tmp_path):
    """A physics-carrying table beats smooth priors on the shell mechanics.

    The toy table is the truth surface shifted by a constant mass-excess
    offset; a constant offset cancels exactly in delta2n, so the table (and
    its residual correction) must localize the injected closure at rank 1
    through the frozen B003 mechanics — the WO-12 core claim in miniature.
    """
    from tests.helpers import write_small_synthetic_shell_chart

    from elementzero.adjudication.benchmark_controls import control_model_registry
    from elementzero.evidence.ledger import read_json
    from elementzero.experiments.b003_runner import (
        score_b003,
        seal_b003,
        select_challenges_for_source,
    )
    from elementzero.experiments.wo12_qualification import FederationRunAdapter

    chart = write_small_synthetic_shell_chart(tmp_path / "chart.mas20")
    registry = _mini_registry(_chart_cells(chart))
    recorder: dict[str, dict] = {}
    builders = {
        model_id: (lambda m=model_id: FederationRunAdapter(registry.build(m), recorder))
        for model_id in registry.model_ids
    }
    challenges_path = tmp_path / "challenges.json"
    select_challenges_for_source(
        source=chart,
        edition_id="AME2020",
        output=challenges_path,
        source_relpath="chart.mas20",
    )
    experiment_dir = tmp_path / "exp"
    with control_model_registry(builders):
        seal_b003(
            source=chart,
            edition_id="AME2020",
            challenges_path=challenges_path,
            experiment_dir=experiment_dir,
            created_at="2026-08-16T12:00:00Z",
            model_ids=tuple(registry.model_ids),
        )
        score_b003(
            source=chart,
            edition_id="AME2020",
            experiment_dir=experiment_dir,
            created_at="2026-08-16T12:00:00Z",
        )
    aggregate = read_json(experiment_dir / "shell_aggregate.json")
    assert "neutron-N50" in aggregate["challenge_ids"]
    table_checks = aggregate["by_model"]["EZ-TOY-TABLE-v1"]["criterion"]["checks"]
    assert float(table_checks["rank_1_fraction"]["observed"]) == 1.0
    assert float(table_checks["sign_fraction"]["observed"]) == 1.0
    semf_checks = aggregate["by_model"]["EZ-SEMF-LS-v1"]["criterion"]["checks"]
    assert float(semf_checks["rank_1_fraction"]["observed"]) < 1.0


def test_mini_federation_deterministic(tmp_path):
    """Two clean mini-federation runs agree byte for byte."""
    from tests.helpers import write_small_synthetic_chart

    from elementzero.adjudication.benchmark_controls import control_model_registry
    from elementzero.experiments.b002_runner import (
        score_b002,
        seal_b002,
        select_regions_for_source,
    )
    from elementzero.experiments.wo12_qualification import FederationRunAdapter

    digests = []
    for run in ("a", "b"):
        base = tmp_path / run
        chart = write_small_synthetic_chart(base / "chart.mas20")
        registry = _mini_registry(_chart_cells(chart))
        recorder: dict[str, dict] = {}
        builders = {
            model_id: (lambda m=model_id: FederationRunAdapter(registry.build(m), recorder))
            for model_id in registry.model_ids
        }
        regions_path = base / "regions.json"
        select_regions_for_source(
            source=chart,
            edition_id="AME2020",
            output=regions_path,
            source_relpath="chart.mas20",
            bands=("light",),
            allow_missing_bands=True,
        )
        experiment_dir = base / "exp"
        with control_model_registry(builders):
            seal_b002(
                source=chart,
                edition_id="AME2020",
                regions_path=regions_path,
                experiment_dir=experiment_dir,
                created_at="2026-08-16T12:00:00Z",
                model_ids=tuple(registry.model_ids),
            )
            score_b002(
                source=chart,
                edition_id="AME2020",
                experiment_dir=experiment_dir,
                created_at="2026-08-16T12:00:00Z",
            )
        digests.append(sha256_file(experiment_dir / "region_aggregate.json"))
    assert digests[0] == digests[1]
