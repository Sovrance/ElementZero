"""EZ-B002 end to end on a synthetic chart with a hidden rectangular block.

WO-09 section 10 asks for exactly this rehearsal before the real tables:

* target values are unavailable during the fit,
* region identities remain available,
* the distance metric is correct,
* deeper points have larger L1 distance,
* sealing and scoring mirror EZ-B001.
"""

from __future__ import annotations

import json

import pytest

from elementzero import B002_PROTOCOL_VERSION, BENCHMARK_EZ_B002, BENCHMARK_PROTOCOL_VERSION
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.b002_finalize import finalize_region_run
from elementzero.benchmark.b002_freeze import freeze_geographic_split, load_geographic_freeze
from elementzero.benchmark.b002_predict import (
    MODEL_SUITE_ID_B002,
    SUITE_MANIFEST_NAME,
    load_region_targets,
    predict_region_run,
    run_region_suite,
)
from elementzero.benchmark.b002_prepare import (
    SPLIT_MANIFEST_FILE,
    TARGETS_FILE,
    eligible_observations,
    prepare_geographic_split,
)
from elementzero.benchmark.b002_score import (
    REGION_AGGREGATE_JSON,
    REGION_AGGREGATE_MARKDOWN,
    REGION_COMPARISON_JSON,
    REGION_COMPARISON_MARKDOWN,
    aggregate_regions,
    score_region_suite,
)
from elementzero.benchmark.distance import l1_distance
from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
from elementzero.benchmark.regions import rectangle_region, region_manifest_hash
from elementzero.cli import main
from elementzero.errors import ProtocolError
from elementzero.evidence.atlas_adapter import read_atlas_facts
from elementzero.evidence.ledger import is_finalized
from elementzero.experiments.b002_runner import (
    REGIONS_FILE,
    SEALED_PREDICTIONS_FILE,
    score_b002,
    seal_b002,
    select_regions_for_source,
)
from elementzero.experiments.runner import verify_sha256sums

EDITION = "AME2020"
CREATED_AT = "2026-01-01T00:00:00Z"
# A rectangle in the middle of the small chart's single Z band: it is wide
# enough in both directions to hold points at more than one depth.
REGION = rectangle_region(12, 15, 13, 17)
SCHEMAS = REPO_ROOT / "schemas"


def _split_and_freeze(tmp_path, source, region=REGION):
    region_dir = tmp_path / "region"
    split = prepare_geographic_split(
        source=source,
        edition_id=EDITION,
        region=region,
        region_manifest_hash=region_manifest_hash([region]),
        out_dir=region_dir,
    )
    freeze = freeze_geographic_split(
        source=source,
        edition_id=EDITION,
        split_manifest=region_dir / SPLIT_MANIFEST_FILE,
        output=region_dir / "freeze.json",
    )
    return split, freeze, load_region_targets(region_dir / TARGETS_FILE)


# --------------------------------------------------------------------------- #
# WO-09 section 10                                                            #
# --------------------------------------------------------------------------- #


def test_target_values_are_unavailable_during_the_fit(tmp_path, small_synthetic_chart, monkeypatch):
    """Spy on the fit: it may see identities outside the block and nothing else."""
    _split, freeze, targets = _split_and_freeze(tmp_path, small_synthetic_chart)
    seen: list[list] = []
    real_build = __import__(
        "elementzero.models.gp_residual", fromlist=["build_model"]
    ).build_model

    def spying_build(model_id):
        model = real_build(model_id)
        real_fit = model.fit

        def fit(observations):
            seen.append(list(observations))
            return real_fit(observations)

        model.fit = fit
        return model

    monkeypatch.setattr("elementzero.benchmark.b002_predict.build_model", spying_build)
    predict_region_run(
        geographic_freeze=freeze,
        targets=targets,
        source=small_synthetic_chart,
        edition_id=EDITION,
        run_dir=tmp_path / "run",
        created_at=CREATED_AT,
    )
    assert len(seen) == 1
    fitted = seen[0]
    assert fitted
    withheld = set(freeze.target_nuclide_ids)
    # Not one row of the hidden block reached the fit, by identity...
    assert not {obs.nuclide_id for obs in fitted} & withheld
    assert not [obs for obs in fitted if freeze.region.contains(obs.Z, obs.N)]
    # ...nor by value: no withheld mass excess appears among the fitted masses.
    hidden_masses = {
        obs.mass_excess_keV
        for obs in eligible_observations(small_synthetic_chart, EDITION)
        if obs.nuclide_id in withheld
    }
    assert not {obs.mass_excess_keV for obs in fitted} & hidden_masses
    # The fitted corpus is exactly the frozen training corpus.
    assert {obs.nuclide_id for obs in fitted} == set(freeze.freeze.training_nuclide_ids)


def test_region_identities_remain_available(tmp_path, small_synthetic_chart):
    split, freeze, targets = _split_and_freeze(tmp_path, small_synthetic_chart)
    eligible = eligible_observations(small_synthetic_chart, EDITION)
    expected = {o.nuclide_id for o in eligible if REGION.contains(o.Z, o.N)}
    assert expected
    assert {t["nuclide_id"] for t in targets} == expected
    for target in targets:
        # Z, N, A are allowed. Nothing else is.
        assert set(target) == {"nuclide_id", "Z", "N", "A"}
        assert target["A"] == target["Z"] + target["N"]
        assert REGION.contains(target["Z"], target["N"])
    assert split["split_manifest"]["n_targets"] == len(expected)
    assert freeze.region == REGION


def test_distance_to_training_is_correct_and_grows_with_depth(tmp_path, small_synthetic_chart):
    _split, freeze, targets = _split_and_freeze(tmp_path, small_synthetic_chart)
    run_dir = tmp_path / "run"
    predict_region_run(
        geographic_freeze=freeze,
        targets=targets,
        source=small_synthetic_chart,
        edition_id=EDITION,
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    finalize_region_run(run_dir, created_at=CREATED_AT)
    from elementzero.benchmark.b002_score import score_region_run

    report = score_region_run(
        run_dir=run_dir,
        truth_source=small_synthetic_chart,
        truth_edition_id=EDITION,
        out_dir=tmp_path / "score",
        created_at=CREATED_AT,
    )
    training = []
    for nid in freeze.freeze.training_nuclide_ids:
        z, n = nid[1:].split("-N")
        training.append((int(z), int(n)))

    depths = {}
    for row in report["rows"]:
        # Brute-force the same quantity independently of the implementation.
        expected = min(l1_distance(row["Z"], row["N"], z, n) for z, n in training)
        assert row["nearest_training_L1"] == expected
        assert row["nearest_training_L1"] >= 1
        depths[(row["Z"], row["N"])] = row["nearest_training_L1"]

    # Depth is a distance to the boundary: a point one step further inside the
    # block on both axes is never closer to training.
    for (z, n), depth in depths.items():
        for neighbour in ((z + 1, n), (z, n + 1)):
            if neighbour in depths:
                assert abs(depths[neighbour] - depth) <= 1
    # The block is deep enough that at least two depths are present, otherwise
    # "metrics by depth" would be a table with one row.
    assert len(set(depths.values())) >= 2
    assert max(depths.values()) > min(depths.values())
    assert report["metrics"]["max_nearest_training_L1"] == max(depths.values())
    assert report["metrics"]["min_nearest_training_L1"] == min(depths.values())
    by_depth = report["metrics"]["depths"]
    assert sum(summary["n"] for summary in by_depth.values()) == len(report["rows"])
    for key, summary in by_depth.items():
        assert key == f"L1={summary['nearest_training_L1']}"
        assert "calibration_error_90" in summary
        assert "calibration_error_95" in summary


def test_sealing_and_scoring_mirror_ez_b001(tmp_path, small_synthetic_chart):
    _split, freeze, targets = _split_and_freeze(tmp_path, small_synthetic_chart)
    run_dir = tmp_path / "run"
    result = predict_region_run(
        geographic_freeze=freeze,
        targets=targets,
        source=small_synthetic_chart,
        edition_id=EDITION,
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    assert not is_finalized(run_dir)
    marker = finalize_region_run(run_dir, created_at=CREATED_AT)
    assert is_finalized(run_dir)
    assert marker["benchmark_id"] == BENCHMARK_EZ_B002
    assert marker["region_id"] == freeze.region_id

    # Same manifest and certificate contracts as EZ-B001.
    run_schema = json.loads((SCHEMAS / "run_manifest.schema.json").read_text("utf-8"))
    for field in run_schema["required"]:
        assert field in result["run_manifest"], field
    cert_schema = json.loads((SCHEMAS / "prediction_certificate.schema.json").read_text("utf-8"))
    for field in cert_schema["required"]:
        assert field in result["certificates"][0], field
    assert result["run_manifest"]["benchmark_id"] == BENCHMARK_EZ_B002
    assert result["run_manifest"]["protocol_version"] == BENCHMARK_PROTOCOL_VERSION
    assert result["run_manifest"]["b002_protocol_version"] == B002_PROTOCOL_VERSION

    # Same Atlas lineage as EZ-B001, with the geographic split inside the freeze
    # node and the region inside the model-fit node (WO-09 section 11).
    facts = read_atlas_facts(run_dir, stage="predict")
    kinds = [f["content"]["kind"] for f in facts]
    assert kinds.count("nuclear_training_dataset") == 1
    assert kinds.count("nuclear_knowledge_freeze") == 1
    assert kinds.count("nuclear_mass_model_fit") == 1
    assert kinds.count("nuclear_mass_prediction_set") == 1
    assert kinds.count("nuclear_mass_prediction") == len(targets)
    freeze_fact = next(f for f in facts if f["content"]["kind"] == "nuclear_knowledge_freeze")
    split_payload = freeze_fact["content"]["geographic_split"]
    assert split_payload["region_id"] == freeze.region_id
    assert split_payload["region_manifest_hash"] == freeze.region_manifest_hash
    assert split_payload["split_digest"] == freeze.split_digest
    fit_fact = next(f for f in facts if f["content"]["kind"] == "nuclear_mass_model_fit")
    assert fit_fact["content"]["region_id"] == freeze.region_id
    assert fit_fact["content"]["region_manifest_hash"] == freeze.region_manifest_hash

    from elementzero.benchmark.b002_score import score_region_run

    report = score_region_run(
        run_dir=run_dir,
        truth_source=small_synthetic_chart,
        truth_edition_id=EDITION,
        out_dir=tmp_path / "score",
        created_at=CREATED_AT,
    )
    for metric in (
        "MAE_keV",
        "MedAE_keV",
        "RMSE_keV",
        "NLPD",
        "coverage_90",
        "coverage_95",
        "cal_error_90",
        "cal_error_95",
    ):
        assert metric in report["metrics"], metric
    assert "no accuracy pass/fail threshold" in report["metrics"]["no_threshold_rule"].lower()
    scoring_facts = read_atlas_facts(tmp_path / "score", stage="score")
    validation = next(
        f for f in scoring_facts if f["content"]["kind"] == "nuclear_benchmark_validation"
    )
    truth = next(f for f in scoring_facts if f["content"]["kind"] == "nuclear_truth_dataset")
    assert set(validation["depends_on_facts"]) == {
        report["prediction_set_fact_id"],
        report["finalization_fact_id"],
        truth["fact_id"],
    }
    assert validation["content"]["benchmark_id"] == BENCHMARK_EZ_B002


# --------------------------------------------------------------------------- #
# One split per suite, all regions reported                                    #
# --------------------------------------------------------------------------- #


def test_all_models_same_region(tmp_path, small_synthetic_chart):
    _split, freeze, targets = _split_and_freeze(tmp_path, small_synthetic_chart)
    suite_dir = tmp_path / "runs"
    suite = run_region_suite(
        geographic_freeze=freeze,
        targets=targets,
        source=small_synthetic_chart,
        edition_id=EDITION,
        suite_dir=suite_dir,
        created_at=CREATED_AT,
    )
    assert suite["model_suite_id"] == MODEL_SUITE_ID_B002
    assert suite["model_ids"] == list(SUITE_MODEL_IDS)
    assert "No baseline is removed" in suite["weak_baseline_rule"]

    regions, freezes, splits, target_digests, manifest_hashes = set(), set(), set(), set(), set()
    for model_id in SUITE_MODEL_IDS:
        run_dir = suite_dir / model_id
        assert is_finalized(run_dir)
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["model_id"] == model_id
        regions.add(manifest["region_id"])
        freezes.add(manifest["freeze_id"])
        splits.add(manifest["split_digest"])
        target_digests.add(manifest["target_identity_digest"])
        manifest_hashes.add(manifest["model_manifest_hash"])
        assert manifest["target_ids"] == [t["nuclide_id"] for t in targets]
        sealed = load_geographic_freeze(run_dir / "freeze.json")
        assert sealed.region == freeze.region
        assert sealed.split_digest == freeze.split_digest
    # One region, one freeze, one split, one target set...
    assert regions == {freeze.region_id}
    assert len(freezes) == len(splits) == len(target_digests) == 1
    # ...and three genuinely different models.
    assert len(manifest_hashes) == len(SUITE_MODEL_IDS)

    comparison = score_region_suite(
        suite_dir=suite_dir,
        truth_source=small_synthetic_chart,
        truth_edition_id=EDITION,
        created_at=CREATED_AT,
    )
    assert [row["model_id"] for row in comparison["rows"]] == list(SUITE_MODEL_IDS)
    assert comparison["region_id"] == freeze.region_id
    assert comparison["split_digest"] == freeze.split_digest
    assert (suite_dir / REGION_COMPARISON_JSON).is_file()
    markdown = (suite_dir / REGION_COMPARISON_MARKDOWN).read_text(encoding="utf-8")
    for model_id in SUITE_MODEL_IDS:
        assert model_id in markdown

    # A comparison assembled from two different splits is refused.
    from elementzero.benchmark.b002_score import build_region_comparison

    reports = [
        json.loads(
            (suite_dir / model_id / "scoring" / "score_report.json").read_text(encoding="utf-8")
        )
        for model_id in SUITE_MODEL_IDS
    ]
    mixed = [*reports[:-1], {**reports[-1], "split_digest": "0" * 64}]
    with pytest.raises(ProtocolError):
        build_region_comparison(mixed, suite=json.loads(
            (suite_dir / SUITE_MANIFEST_NAME).read_text(encoding="utf-8")
        ))
    with pytest.raises(ProtocolError):
        build_region_comparison(reports[:-1], suite=json.loads(
            (suite_dir / SUITE_MANIFEST_NAME).read_text(encoding="utf-8")
        ))


def test_aggregate_reports_all_regions(tmp_path, synthetic_chart):
    experiment_dir = tmp_path / "EZ-B002-TEST"
    selected = select_regions_for_source(
        source=synthetic_chart,
        edition_id=EDITION,
        output=tmp_path / "regions.json",
        source_relpath="chart.mas20",
    )
    region_ids = selected["manifest"]["region_ids"]
    assert len(region_ids) == 3

    sealed = seal_b002(
        source=synthetic_chart,
        edition_id=EDITION,
        regions_path=tmp_path / "regions.json",
        experiment_dir=experiment_dir,
        created_at=CREATED_AT,
    )
    assert sealed["region_ids"] == region_ids
    assert sealed["sealed"]["state"] == "PREDICTIONS_SEALED_REGION_TRUTH_UNREAD"
    assert (experiment_dir / SEALED_PREDICTIONS_FILE).is_file()
    assert (experiment_dir / REGIONS_FILE).is_file()

    scored = score_b002(
        source=synthetic_chart,
        edition_id=EDITION,
        experiment_dir=experiment_dir,
        created_at=CREATED_AT,
    )
    aggregate = scored["aggregate"]
    assert aggregate["region_ids"] == region_ids
    assert aggregate["model_ids"] == list(SUITE_MODEL_IDS)
    # Every region x model pair is reported, with nothing dropped.
    assert {(row["region_id"], row["model_id"]) for row in aggregate["rows"]} == {
        (region_id, model_id) for region_id in region_ids for model_id in SUITE_MODEL_IDS
    }
    assert len(aggregate["rows"]) == len(region_ids) * len(SUITE_MODEL_IDS)
    for model_id in SUITE_MODEL_IDS:
        by_model = aggregate["by_model"][model_id]
        assert by_model["n_regions"] == len(region_ids)
        assert [r["region_id"] for r in by_model["per_region"]] == sorted(region_ids)
        # The worst region is named, not hidden behind a pooled average.
        assert by_model["worst_region"]["region_id"] in region_ids
        assert float(by_model["worst_region"]["MAE_keV"]) == max(
            float(r["MAE_keV"]) for r in by_model["per_region"]
        )
    assert aggregate["n_scored_targets"] == sum(row["n"] for row in aggregate["rows"])
    for region_id in region_ids:
        assert region_id in (experiment_dir / REGION_AGGREGATE_MARKDOWN).read_text("utf-8")
    assert (experiment_dir / REGION_AGGREGATE_JSON).is_file()
    assert verify_sha256sums(experiment_dir)["ok"]

    # Dropping a region from the aggregate is a protocol error, which is what
    # stops a run from reporting only the regions that reconstructed well.
    reports = scored["reports"]
    kept = [r for r in reports if r["region_id"] != region_ids[0]]
    with pytest.raises(ProtocolError):
        aggregate_regions(
            kept,
            region_ids=region_ids,
            model_ids=list(SUITE_MODEL_IDS),
            region_manifest_hash=selected["manifest"]["region_manifest_hash"],
        )
    # So is quoting a region manifest hash the runs never saw.
    with pytest.raises(ProtocolError):
        aggregate_regions(
            reports,
            region_ids=region_ids,
            model_ids=list(SUITE_MODEL_IDS),
            region_manifest_hash="0" * 64,
        )
    # A rerun may not overwrite a sealed experiment directory.
    with pytest.raises(ProtocolError):
        seal_b002(
            source=synthetic_chart,
            edition_id=EDITION,
            regions_path=tmp_path / "regions.json",
            experiment_dir=experiment_dir,
            created_at=CREATED_AT,
        )


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def test_cli_b002_stage_flow(tmp_path, small_synthetic_chart, capsys):
    regions_path = tmp_path / "regions.json"
    region_dir = tmp_path / "region"
    suite_dir = region_dir / "runs"
    assert main([
        "benchmark", "b002-select-regions",
        "--source", str(small_synthetic_chart),
        "--edition", EDITION,
        "--output", str(regions_path),
        "--candidates-output", str(tmp_path / "candidates.json"),
        "--per-band", "1",
        "--allow-missing-bands",
    ]) == 0
    manifest = json.loads(regions_path.read_text(encoding="utf-8"))
    region_id = manifest["region_ids"][0]
    assert manifest["benchmark_id"] == BENCHMARK_EZ_B002

    assert main([
        "benchmark", "b002-prepare",
        "--source", str(small_synthetic_chart),
        "--edition", EDITION,
        "--regions", str(regions_path),
        "--region-id", region_id,
        "--out", str(region_dir),
    ]) == 0
    assert main([
        "benchmark", "b002-freeze",
        "--source", str(small_synthetic_chart),
        "--edition", EDITION,
        "--split-manifest", str(region_dir / SPLIT_MANIFEST_FILE),
        "--output", str(region_dir / "freeze.json"),
    ]) == 0
    assert main([
        "benchmark", "b002-predict",
        "--source", str(small_synthetic_chart),
        "--edition", EDITION,
        "--freeze", str(region_dir / "freeze.json"),
        "--targets", str(region_dir / TARGETS_FILE),
        "--out", str(suite_dir),
    ]) == 0
    for model_id in SUITE_MODEL_IDS:
        # b002-predict seals each run as it goes, exactly like suite-predict.
        assert is_finalized(suite_dir / model_id)
    assert main([
        "benchmark", "b002-score",
        "--suite", str(suite_dir),
        "--source", str(small_synthetic_chart),
        "--edition", EDITION,
    ]) == 0
    comparison = json.loads((suite_dir / REGION_COMPARISON_JSON).read_text(encoding="utf-8"))
    assert comparison["region_id"] == region_id
    assert [row["model_id"] for row in comparison["rows"]] == list(SUITE_MODEL_IDS)

    # An unsealed run can be finalized through the CLI as its own stage.
    lone = tmp_path / "lone"
    freeze = load_geographic_freeze(region_dir / "freeze.json")
    predict_region_run(
        geographic_freeze=freeze,
        targets=load_region_targets(region_dir / TARGETS_FILE),
        source=small_synthetic_chart,
        edition_id=EDITION,
        run_dir=lone,
        created_at=CREATED_AT,
    )
    capsys.readouterr()
    assert main(["benchmark", "b002-finalize", "--run", str(lone)]) == 0
    assert is_finalized(lone)

    with pytest.raises(SystemExit):
        main([
            "benchmark", "b002-prepare",
            "--source", str(small_synthetic_chart),
            "--edition", EDITION,
            "--regions", str(regions_path),
            "--region-id", "rect-Z1-2-N1-2",
            "--out", str(tmp_path / "nope"),
        ])


def test_cli_b002_experiment_flow(tmp_path, synthetic_chart):
    regions_path = tmp_path / "regions.json"
    experiment_dir = tmp_path / "EZ-B002-CLI"
    assert main([
        "benchmark", "b002-select-regions",
        "--source", str(synthetic_chart),
        "--edition", EDITION,
        "--output", str(regions_path),
    ]) == 0
    assert main([
        "benchmark", "b002-seal-experiment",
        "--source", str(synthetic_chart),
        "--edition", EDITION,
        "--regions", str(regions_path),
        "--dir", str(experiment_dir),
        "--created-at", CREATED_AT,
    ]) == 0
    sealed = json.loads((experiment_dir / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    assert sealed["state"] == "PREDICTIONS_SEALED_REGION_TRUTH_UNREAD"
    assert not (experiment_dir / REGION_AGGREGATE_JSON).exists()
    assert main([
        "benchmark", "b002-score-experiment",
        "--source", str(synthetic_chart),
        "--edition", EDITION,
        "--dir", str(experiment_dir),
        "--created-at", CREATED_AT,
    ]) == 0
    aggregate = json.loads((experiment_dir / REGION_AGGREGATE_JSON).read_text(encoding="utf-8"))
    assert aggregate["region_ids"] == sealed["region_ids"]
    assert verify_sha256sums(experiment_dir)["ok"]
