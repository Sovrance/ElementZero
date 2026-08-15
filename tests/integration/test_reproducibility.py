from pathlib import Path

from tests.helpers import synthetic_editions

from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.evidence.hashing import sha256_file

CREATED_AT = "2026-08-15T00:00:00Z"


def _run_once(root: Path) -> dict[str, str]:
    old, later = synthetic_editions(root / "data")
    targets = root / "targets.json"
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=targets,
        known_source=old,
        known_edition_id="AME2003",
    )
    freeze_path = root / "freeze.json"
    freeze = freeze_training(
        training_source=old,
        training_edition_id="AME2003",
        targets_path=targets,
        output=freeze_path,
    )
    run_dir = root / "prediction"
    predict_run(
        freeze=freeze,
        targets=load_targets(targets),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    finalize(run_dir, created_at=CREATED_AT)
    score_run(
        run_dir=run_dir,
        truth_source=later,
        truth_edition_id="AME2020",
        out_dir=root / "scoring",
        created_at=CREATED_AT,
    )
    return {
        "freeze": sha256_file(freeze_path),
        "model_manifest": sha256_file(run_dir / "model_manifest.json"),
        "predictions": sha256_file(run_dir / "predictions.json"),
        "certificates": sha256_file(run_dir / "certificates.json"),
        "ledger": sha256_file(run_dir / "LEDGER_FINALIZED"),
        "metrics": sha256_file(root / "scoring" / "metrics.json"),
        "run_manifest": sha256_file(run_dir / "run_manifest.json"),
        "atlas_artifacts": sha256_file(run_dir / "atlas" / "artifacts.json"),
        "atlas_events": sha256_file(run_dir / "atlas" / "events.json"),
        "atlas_facts": sha256_file(run_dir / "atlas" / "facts.json"),
        "atlas_provenance": sha256_file(run_dir / "atlas" / "provenance.json"),
        "atlas_finalization_facts": sha256_file(
            run_dir / "atlas" / "finalization_facts.json"
        ),
        "atlas_finalization_provenance": sha256_file(
            run_dir / "atlas" / "finalization_provenance.json"
        ),
        "atlas_scoring_facts": sha256_file(root / "scoring" / "atlas" / "scoring_facts.json"),
        "atlas_scoring_provenance": sha256_file(
            root / "scoring" / "atlas" / "scoring_provenance.json"
        ),
    }


def test_synthetic_b001_is_reproducible_across_two_clean_runs(tmp_path):
    first = _run_once(tmp_path / "a")
    second = _run_once(tmp_path / "b")
    assert first == second


def test_reproducible_atlas_fact_hashes(tmp_path):
    first = _run_once(tmp_path / "a")
    second = _run_once(tmp_path / "b")
    atlas_keys = [k for k in first if k.startswith("atlas_")]
    assert len(atlas_keys) == 8
    for key in atlas_keys:
        assert first[key] == second[key], key


def test_metric_json_reproducible(tmp_path):
    first = _run_once(tmp_path / "a")
    second = _run_once(tmp_path / "b")
    assert first["metrics"] == second["metrics"]
    # Re-scoring the same sealed run must not change the metric file either.
    run_dir = tmp_path / "a" / "prediction"
    before = sha256_file(tmp_path / "a" / "scoring" / "metrics.json")
    score_run(
        run_dir=run_dir,
        truth_source=tmp_path / "a" / "data" / "later.mas20",
        truth_edition_id="AME2020",
        out_dir=tmp_path / "a" / "rescore",
        created_at=CREATED_AT,
    )
    assert sha256_file(tmp_path / "a" / "rescore" / "metrics.json") == before
