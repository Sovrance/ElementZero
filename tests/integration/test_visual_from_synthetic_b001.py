import json
from pathlib import Path

from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training, load_freeze
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.cli import main
from elementzero.visuals.build import build_visual_table


def test_visual_build_from_synthetic_b001(tmp_path, synthetic_sources):
    old, later = synthetic_sources
    work = tmp_path / "run"
    targets = work / "experiments" / "EZ-B001-synth" / "targets.json"
    freeze = work / "freeze.json"
    run = work / "prediction"
    score = work / "results" / "EZ-B001-synth" / "semf_gp"
    targets.parent.mkdir(parents=True)
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=targets,
        known_source=old,
        known_edition_id="AME2003",
    )
    freeze_training(
        training_source=old,
        training_edition_id="AME2003",
        targets_path=targets,
        output=freeze,
    )
    predict_run(
        freeze=load_freeze(freeze),
        targets=load_targets(targets),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=run,
    )
    finalize(run)
    score_run(run_dir=run, truth_source=later, truth_edition_id="AME2020", out_dir=score)
    # Keep the AME tables inside the visual input root.
    (work / "data").mkdir()
    (work / "data" / "old.mas03").write_bytes(Path(old).read_bytes())
    (work / "data" / "later.mas20").write_bytes(Path(later).read_bytes())
    out = tmp_path / "visuals"
    result = build_visual_table(input_root=work, output_root=out)
    state = json.loads(Path(result["state"]).read_text())
    assert len(state["elements"]) == 200
    by_z = {item["Z"]: item for item in state["elements"]}
    validated = [item for item in state["elements"] if item["project_primary_stage"] == "historically_validated"]
    assert validated
    assert any(item["counts"]["eligible_observation_count"] > 0 for item in by_z.values())
    html = Path(result["html"]).read_text()
    svg = Path(result["svg"]).read_text()
    assert "Historically validated" in html
    assert "stage-historically_validated" in svg
    bundle = json.loads(Path(result["bundle"]).read_text())
    assert bundle["state_hash"]
    assert bundle["events_hash"]
    assert bundle["atlas_commit"]
    assert main(["visual", "build", "--input-root", str(work), "--output-root", str(tmp_path / "cli")]) == 0
