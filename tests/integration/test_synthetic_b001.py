
from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.cli import main
from elementzero.evidence.ledger import is_finalized


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
