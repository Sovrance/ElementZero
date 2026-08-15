from pathlib import Path

from tests.helpers import synthetic_editions

from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.evidence.hashing import sha256_file


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
        created_at="2026-08-15T00:00:00Z",
    )
    finalize(run_dir)
    score_run(
        run_dir=run_dir,
        truth_source=later,
        truth_edition_id="AME2020",
        out_dir=root / "scoring",
    )
    return {
        "freeze": sha256_file(freeze_path),
        "model_manifest": sha256_file(run_dir / "model_manifest.json"),
        "predictions": sha256_file(run_dir / "predictions.json"),
        "certificates": sha256_file(run_dir / "certificates.json"),
        "ledger": sha256_file(run_dir / "LEDGER_FINALIZED"),
        "metrics": sha256_file(root / "scoring" / "metrics.json"),
        "run_manifest": sha256_file(run_dir / "run_manifest.json"),
    }


def test_synthetic_b001_is_reproducible_across_two_clean_runs(tmp_path):
    first = _run_once(tmp_path / "a")
    second = _run_once(tmp_path / "b")
    assert first == second
