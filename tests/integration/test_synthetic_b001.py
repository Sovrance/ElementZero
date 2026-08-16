import json

from elementzero import BENCHMARK_PROTOCOL_VERSION
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.benchmark.model_suite import (
    COMPARISON_JSON_NAME,
    COMPARISON_MARKDOWN_NAME,
    SUITE_MODEL_IDS,
    run_suite,
    score_suite,
)
from elementzero.cli import main
from elementzero.evidence.atlas_adapter import AtlasEvidenceAdapter, read_atlas_facts
from elementzero.evidence.ledger import is_finalized


def _prepared(tmp_path, synthetic_sources):
    old, later = synthetic_sources
    targets = tmp_path / "targets.json"
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=targets,
        known_source=old,
        known_edition_id="AME2003",
    )
    freeze = freeze_training(
        training_source=old,
        training_edition_id="AME2003",
        targets_path=targets,
        output=tmp_path / "freeze.json",
    )
    return old, later, targets, freeze


def test_cli_four_process_flow(tmp_path, synthetic_sources):
    old, later = synthetic_sources
    targets = tmp_path / "targets.json"
    freeze = tmp_path / "freeze.json"
    run = tmp_path / "prediction"
    score = tmp_path / "scoring"
    assert main([
        "benchmark", "prepare-targets",
        "--benchmark", "EZ-B001",
        "--later-source", str(later),
        "--edition", "AME2020",
        "--known-source", str(old),
        "--known-edition", "AME2003",
        "--output", str(targets),
    ]) == 0
    payload = load_targets(targets)
    assert payload
    assert set(payload[0]) == {"nuclide_id", "Z", "N", "A"}
    assert main([
        "benchmark", "freeze",
        "--benchmark", "EZ-B001",
        "--training-source", str(old),
        "--edition", "AME2003",
        "--targets", str(targets),
        "--output", str(freeze),
    ]) == 0
    assert main([
        "benchmark", "predict",
        "--benchmark", "EZ-B001",
        "--freeze", str(freeze),
        "--targets", str(targets),
        "--training-source", str(old),
        "--edition", "AME2003",
        "--out", str(run),
    ]) == 0
    assert not is_finalized(run)
    assert main(["benchmark", "finalize", "--run", str(run)]) == 0
    assert is_finalized(run)
    assert main([
        "benchmark", "score",
        "--run", str(run),
        "--truth-source", str(later),
        "--edition", "AME2020",
        "--out", str(score),
    ]) == 0
    assert (score / "metrics.json").is_file()


def test_predict_does_not_read_later_source(tmp_path, synthetic_sources, monkeypatch):
    old, later = synthetic_sources
    targets = tmp_path / "targets.json"
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=targets,
        known_source=old,
        known_edition_id="AME2003",
    )
    freeze = freeze_training(
        training_source=old,
        training_edition_id="AME2003",
        targets_path=targets,
    )
    later.unlink()
    predict_run(
        freeze=freeze,
        targets=load_targets(targets),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=tmp_path / "run",
    )
    finalize(tmp_path / "run")
    # Recreate later truth only for scoring.
    from tests.helpers import synthetic_editions

    _old2, later2 = synthetic_editions(tmp_path / "truth")
    report = score_run(
        run_dir=tmp_path / "run",
        truth_source=later2,
        truth_edition_id="AME2020",
        out_dir=tmp_path / "score",
    )
    assert report["metrics"]["n"] >= 1


def test_prediction_run_persists_the_atlas_bundle(tmp_path, synthetic_sources):
    old, _later, targets, freeze = _prepared(tmp_path, synthetic_sources)
    run_dir = tmp_path / "run"
    result = predict_run(
        freeze=freeze,
        targets=load_targets(targets),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=run_dir,
        created_at="2026-08-15T00:00:00Z",
    )
    for name in ("artifacts.json", "events.json", "facts.json", "provenance.json"):
        assert (run_dir / "atlas" / name).is_file()
    facts = read_atlas_facts(run_dir, stage="predict")
    kinds = [f["content"]["kind"] for f in facts]
    assert kinds.count("nuclear_training_dataset") == 1
    assert kinds.count("nuclear_knowledge_freeze") == 1
    assert kinds.count("nuclear_mass_model_fit") == 1
    assert kinds.count("nuclear_mass_prediction_set") == 1
    assert kinds.count("nuclear_mass_prediction") == len(result["predictions"])
    # No per-observation fact is emitted; the corpus is one aggregate fact.
    assert "nuclear_mass_observation" not in kinds

    manifest = result["run_manifest"]
    assert manifest["protocol_version"] == BENCHMARK_PROTOCOL_VERSION
    assert manifest["prediction_set_fact_id"]
    fit_id = manifest["model_fit_fact_id"]
    for fact in facts:
        if fact["content"]["kind"] == "nuclear_mass_prediction":
            assert fact["depends_on_facts"] == [fit_id]

    schema = json.loads(
        (REPO_ROOT / "schemas" / "run_manifest.schema.json").read_text(encoding="utf-8")
    )
    for field in schema["required"]:
        assert field in manifest, field
    cert_schema = json.loads(
        (REPO_ROOT / "schemas" / "prediction_certificate.schema.json").read_text(encoding="utf-8")
    )
    for field in cert_schema["required"]:
        assert field in result["certificates"][0], field


def test_scoring_validation_depends_on_truth_and_finalization(tmp_path, synthetic_sources):
    old, later, targets, freeze = _prepared(tmp_path, synthetic_sources)
    run_dir = tmp_path / "run"
    predict_run(
        freeze=freeze,
        targets=load_targets(targets),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=run_dir,
        created_at="2026-08-15T00:00:00Z",
    )
    marker = finalize(run_dir, created_at="2026-08-15T00:00:00Z")
    report = score_run(
        run_dir=run_dir,
        truth_source=later,
        truth_edition_id="AME2020",
        out_dir=tmp_path / "score",
        created_at="2026-08-15T00:00:00Z",
    )
    scoring_facts = read_atlas_facts(tmp_path / "score", stage="score")
    validation = next(
        f for f in scoring_facts if f["content"]["kind"] == "nuclear_benchmark_validation"
    )
    truth = next(f for f in scoring_facts if f["content"]["kind"] == "nuclear_truth_dataset")
    assert set(validation["depends_on_facts"]) == {
        report["prediction_set_fact_id"],
        marker["finalization_fact_id"],
        truth["fact_id"],
    }
    assert validation["content"]["protocol_version"] == BENCHMARK_PROTOCOL_VERSION
    assert validation["content"]["truth_source_hash"] == report["truth_source_hash"]
    assert (
        validation["content"]["finalization_marker_hash"] == marker["finalization_marker_hash"]
    )
    assert report["metrics"]["n"] == len(report["rows"])
    row = report["rows"][0]
    assert row["nearest_training_L1"] >= 1
    assert row["distance_bucket"]
    assert row["region"]
    assert "isospin_asymmetry" in row


def test_full_synthetic_graph_is_acyclic(tmp_path, synthetic_sources):
    old, later, targets, freeze = _prepared(tmp_path, synthetic_sources)
    run_dir = tmp_path / "run"
    predict_run(
        freeze=freeze,
        targets=load_targets(targets),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=run_dir,
        created_at="2026-08-15T00:00:00Z",
    )
    finalize(run_dir, created_at="2026-08-15T00:00:00Z")
    score_run(
        run_dir=run_dir,
        truth_source=later,
        truth_edition_id="AME2020",
        out_dir=tmp_path / "score",
        created_at="2026-08-15T00:00:00Z",
    )
    # Rebuilding every stage into one append-only store proves the whole graph
    # is a DAG: FactStore refuses a fact that closes a cycle.
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    adapter.rehydrate(read_atlas_facts(run_dir, stage="predict"))
    adapter.rehydrate(read_atlas_facts(run_dir, stage="finalize"))
    adapter.rehydrate(read_atlas_facts(tmp_path / "score", stage="score"))

    facts = {f.fact_id: f for f in adapter.store.facts()}
    for fact in facts.values():
        assert fact.fact_id not in adapter.store.dependents_of_fact(fact.fact_id)
    validation = next(
        f for f in facts.values() if f.content["kind"] == "nuclear_benchmark_validation"
    )
    training = next(
        f for f in facts.values() if f.content["kind"] == "nuclear_training_dataset"
    )
    assert validation.fact_id in adapter.store.dependents_of_fact(training.fact_id)


def test_persisted_graph_invalidation_reaches_predictions(tmp_path, synthetic_sources):
    old, _later, targets, freeze = _prepared(tmp_path, synthetic_sources)
    run_dir = tmp_path / "run"
    predict_run(
        freeze=freeze,
        targets=load_targets(targets),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=run_dir,
        created_at="2026-08-15T00:00:00Z",
    )
    adapter = AtlasEvidenceAdapter(created_at="2026-08-15T00:00:00Z")
    adapter.rehydrate(read_atlas_facts(run_dir, stage="predict"))
    affected = adapter.invalidate_assumption(
        f"src:{freeze.raw_source_hash}", "training source edition recalled"
    )
    assert set(affected) == {f.fact_id for f in adapter.store.facts()}
    downgraded_kinds = {adapter.store.get(fid).content["kind"] for fid in affected}
    assert downgraded_kinds == {
        "nuclear_training_dataset",
        "nuclear_knowledge_freeze",
        "nuclear_mass_model_fit",
        "nuclear_mass_prediction",
        "nuclear_mass_prediction_set",
    }
    for fact in adapter.store.facts():
        assert fact.status.value == "DOWNGRADED"


def test_three_model_suite_same_freeze(tmp_path, synthetic_sources):
    old, later, targets, freeze = _prepared(tmp_path, synthetic_sources)
    suite_dir = tmp_path / "suite"
    suite = run_suite(
        freeze=freeze,
        targets=load_targets(targets),
        training_source=old,
        training_edition_id="AME2003",
        suite_dir=suite_dir,
        created_at="2026-08-15T00:00:00Z",
    )
    assert suite["model_ids"] == list(SUITE_MODEL_IDS)
    digests = set()
    manifest_hashes = set()
    for model_id in SUITE_MODEL_IDS:
        run_dir = suite_dir / model_id
        assert is_finalized(run_dir)
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["model_id"] == model_id
        assert manifest["freeze_id"] == freeze.freeze_id
        assert manifest["source_hashes"] == list(freeze.allowed_source_hashes)
        assert manifest["feature_policy_id"] == freeze.feature_policy_id
        digests.add(manifest["target_identity_digest"])
        manifest_hashes.add(manifest["model_manifest_hash"])
    # One freeze, one target set, three genuinely different models.
    assert len(digests) == 1
    assert len(manifest_hashes) == len(SUITE_MODEL_IDS)

    comparison = score_suite(
        suite_dir=suite_dir,
        truth_source=later,
        truth_edition_id="AME2020",
        created_at="2026-08-15T00:00:00Z",
    )
    assert [row["model_id"] for row in comparison["rows"]] == list(SUITE_MODEL_IDS)
    assert (suite_dir / COMPARISON_JSON_NAME).is_file()
    markdown = (suite_dir / COMPARISON_MARKDOWN_NAME).read_text(encoding="utf-8")
    for model_id in SUITE_MODEL_IDS:
        assert model_id in markdown
    for model_id in SUITE_MODEL_IDS:
        assert (suite_dir / model_id / "scoring" / "metrics.json").is_file()


def test_cli_suite_predict_and_suite_score(tmp_path, synthetic_sources):
    old, later = synthetic_sources
    targets = tmp_path / "targets.json"
    freeze = tmp_path / "freeze.json"
    suite_dir = tmp_path / "suite"
    assert main([
        "benchmark", "prepare-targets",
        "--later-source", str(later),
        "--edition", "AME2020",
        "--known-source", str(old),
        "--known-edition", "AME2003",
        "--output", str(targets),
    ]) == 0
    assert main([
        "benchmark", "freeze",
        "--training-source", str(old),
        "--edition", "AME2003",
        "--targets", str(targets),
        "--output", str(freeze),
    ]) == 0
    assert main([
        "benchmark", "suite-predict",
        "--freeze", str(freeze),
        "--targets", str(targets),
        "--training-source", str(old),
        "--edition", "AME2003",
        "--out", str(suite_dir),
    ]) == 0
    assert main([
        "benchmark", "suite-score",
        "--suite", str(suite_dir),
        "--truth-source", str(later),
        "--edition", "AME2020",
    ]) == 0
    comparison = json.loads((suite_dir / COMPARISON_JSON_NAME).read_text(encoding="utf-8"))
    assert [row["model_id"] for row in comparison["rows"]] == list(SUITE_MODEL_IDS)
