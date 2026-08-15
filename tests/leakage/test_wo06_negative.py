"""WO-06 required negative tests: seven ways to break the protocol, all refused.

Each test maps to one numbered item of the WO-06 'Required negative tests'
section. They run against the same code path as the committed official runs.
"""

from __future__ import annotations

import json

import pytest
from tests.helpers import synthetic_editions

from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_score import score_run
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.freezes import KnowledgeFreeze
from elementzero.evidence.hashing import canonical_json
from elementzero.experiments.epochs import EpochSpec
from elementzero.experiments.preregister import (
    PREREGISTRATION_HASH_FILE,
    write_preregistration,
)
from elementzero.experiments.runner import (
    RUNS_DIRNAME,
    score_experiment,
    seal_experiment,
    sealed_predictions_manifest,
)

FAKE_COMMIT = "e" * 40
EPOCH = EpochSpec(
    experiment_id="EZ-B001-A",
    training_edition="AME2003",
    truth_edition="AME2020",
    created_at="2026-08-16T00:00:00Z",
)


def _prereg(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    training, truth = synthetic_editions(tmp_path / "sources")
    experiment_dir = tmp_path / "exp"
    write_preregistration(
        epoch=EPOCH,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
    )
    return experiment_dir, training, truth


def _sealed(tmp_path, monkeypatch):
    experiment_dir, training, truth = _prereg(tmp_path, monkeypatch)
    seal_experiment(
        epoch=EPOCH,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
        subprocess_prediction=False,
    )
    return experiment_dir, training, truth


def test_1_truth_field_in_targets_json_is_refused(tmp_path, monkeypatch):
    experiment_dir, training, truth = _sealed(tmp_path, monkeypatch)
    targets_path = experiment_dir / "targets.json"
    payload = json.loads(targets_path.read_text(encoding="utf-8"))
    payload["targets"][0]["mass_excess_keV"] = -8000.0
    tampered = tmp_path / "tampered_targets.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(LeakageError):
        load_targets(tampered)
    with pytest.raises(LeakageError):
        freeze_training(
            training_source=training,
            training_edition_id="AME2003",
            targets_path=tampered,
            forbidden_source_hashes=[],
        )


def test_2_using_the_later_edition_as_a_training_source_is_refused(tmp_path, monkeypatch):
    experiment_dir, training, truth = _prereg(tmp_path, monkeypatch)
    with pytest.raises(ProtocolError):
        seal_experiment(
            epoch=EPOCH,
            experiment_dir=experiment_dir,
            training_source=truth,
            truth_source=truth,
            subprocess_prediction=False,
        )

    # The freeze itself also refuses a fit against the forbidden source.
    freeze = freeze_training(
        training_source=training,
        training_edition_id="AME2003",
        targets_path=_write_targets(tmp_path, training, truth),
    )
    with pytest.raises(LeakageError):
        predict_run(
            freeze=freeze,
            targets=load_targets(tmp_path / "targets.json"),
            training_source=truth,
            training_edition_id="AME2020",
            run_dir=tmp_path / "run_truth_fit",
        )


def test_3_a_target_identity_inside_the_training_set_is_refused(tmp_path, monkeypatch):
    experiment_dir, training, truth = _prereg(tmp_path, monkeypatch)
    targets_path = _write_targets(tmp_path, training, truth)
    freeze = freeze_training(
        training_source=training,
        training_edition_id="AME2003",
        targets_path=targets_path,
    )
    targets = load_targets(targets_path)
    mutated = freeze.to_dict()
    mutated["training_nuclide_ids"] = [
        *freeze.training_nuclide_ids,
        targets[0]["nuclide_id"],
    ]
    with pytest.raises(LeakageError):
        predict_run(
            freeze=KnowledgeFreeze.from_dict(mutated),
            targets=targets,
            training_source=training,
            training_edition_id="AME2003",
            run_dir=tmp_path / "run_overlap",
        )


def test_4_altering_predictions_after_finalization_is_refused(tmp_path, monkeypatch):
    experiment_dir, training, truth = _sealed(tmp_path, monkeypatch)
    run_dir = experiment_dir / RUNS_DIRNAME / "EZ-SEMF-LS-v1"
    predictions = json.loads((run_dir / "predictions.json").read_text(encoding="utf-8"))
    predictions[0]["mass_excess_keV"] = 0.0
    (run_dir / "predictions.json").write_text(
        canonical_json(predictions) + "\n", encoding="utf-8"
    )
    with pytest.raises(LeakageError):
        score_experiment(epoch=EPOCH, experiment_dir=experiment_dir, truth_source=truth)


def test_5_scoring_before_finalization_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    training, truth = synthetic_editions(tmp_path / "sources")
    targets_path = _write_targets(tmp_path, training, truth)
    freeze = freeze_training(
        training_source=training,
        training_edition_id="AME2003",
        targets_path=targets_path,
    )
    run_dir = tmp_path / "unsealed_run"
    predict_run(
        freeze=freeze,
        targets=load_targets(targets_path),
        training_source=training,
        training_edition_id="AME2003",
        run_dir=run_dir,
    )
    with pytest.raises(LeakageError):
        score_run(
            run_dir=run_dir,
            truth_source=truth,
            truth_edition_id="AME2020",
            out_dir=tmp_path / "scoring",
        )
    # Sealing first makes the same scoring call legal.
    finalize(run_dir)
    report = score_run(
        run_dir=run_dir,
        truth_source=truth,
        truth_edition_id="AME2020",
        out_dir=tmp_path / "scoring",
    )
    assert report["metrics"]["n"] > 0


def test_6_altering_the_preregistration_hash_is_refused(tmp_path, monkeypatch):
    experiment_dir, training, truth = _sealed(tmp_path, monkeypatch)
    (experiment_dir / PREREGISTRATION_HASH_FILE).write_text("f" * 64 + "\n", encoding="utf-8")
    with pytest.raises(ProtocolError):
        score_experiment(epoch=EPOCH, experiment_dir=experiment_dir, truth_source=truth)


def test_7_a_model_with_a_different_target_set_is_refused(tmp_path, monkeypatch):
    experiment_dir, training, truth = _sealed(tmp_path, monkeypatch)
    suite = json.loads(
        (experiment_dir / RUNS_DIRNAME / "model_suite.json").read_text(encoding="utf-8")
    )
    run_dir = experiment_dir / RUNS_DIRNAME / "EZ-GP-DIRECT-v1"
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["target_identity_digest"] = "1" * 64
    (run_dir / "run_manifest.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")

    with pytest.raises(ProtocolError):
        sealed_predictions_manifest(
            experiment_dir=experiment_dir,
            epoch=EPOCH,
            preregistration_hash="0" * 64,
            suite=suite,
            target_digest=json.loads(
                (experiment_dir / "targets_digest.json").read_text(encoding="utf-8")
            )["target_identity_digest"],
        )


def _write_targets(tmp_path, training, truth):
    from elementzero.benchmark.b001_prepare import prepare_targets

    output = tmp_path / "targets.json"
    prepare_targets(
        later_source=truth,
        edition_id="AME2020",
        output=output,
        known_source=training,
        known_edition_id="AME2003",
    )
    return output
