from __future__ import annotations

import json

import pytest

from elementzero.atlas_pin import validate_atlas_ref
from elementzero.benchmark.b001_finalize import finalize
from elementzero.benchmark.b001_freeze import freeze_training
from elementzero.benchmark.b001_predict import load_targets, predict_run
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.errors import AtlasContractError, LeakageError, ProtocolError
from elementzero.evidence.freezes import (
    KnowledgeFreeze,
    assert_holdout_disjoint,
    assert_training_digest,
)
from elementzero.evidence.ledger import write_run_artifact


def test_truth_field_in_target_manifest_is_rejected(tmp_path, synthetic_sources):
    old, later = synthetic_sources
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=tmp_path / "targets.json",
        known_source=old,
        known_edition_id="AME2003",
    )
    payload = json.loads((tmp_path / "targets.json").read_text())
    payload["targets"][0]["mass_excess_keV"] = 1.0
    bad = tmp_path / "bad_targets.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LeakageError):
        load_targets(bad)


def test_held_out_nuclide_in_training_ids_is_rejected(synthetic_sources, tmp_path):
    old, later = synthetic_sources
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=tmp_path / "targets.json",
        known_source=old,
        known_edition_id="AME2003",
    )
    freeze = freeze_training(
        training_source=old,
        training_edition_id="AME2003",
        targets_path=tmp_path / "targets.json",
        output=tmp_path / "freeze.json",
    )
    mutated = freeze.to_dict()
    mutated["training_nuclide_ids"] = list(freeze.training_nuclide_ids) + ["Z18-N19"]
    bad = KnowledgeFreeze.from_dict(mutated)
    with pytest.raises(LeakageError):
        assert_holdout_disjoint(bad, ["Z18-N19"])


def test_truth_source_hash_allowed_by_freeze_is_rejected(tmp_path, synthetic_sources):
    old, later = synthetic_sources
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=tmp_path / "targets.json",
        known_source=old,
        known_edition_id="AME2003",
    )
    freeze = freeze_training(
        training_source=old,
        training_edition_id="AME2003",
        targets_path=tmp_path / "targets.json",
        output=tmp_path / "freeze.json",
    )
    predict_run(
        freeze=freeze,
        targets=load_targets(tmp_path / "targets.json"),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=tmp_path / "run",
    )
    finalize(tmp_path / "run")
    with pytest.raises(LeakageError):
        score_run(
            run_dir=tmp_path / "run",
            truth_source=old,
            truth_edition_id="AME2003",
            out_dir=tmp_path / "score",
        )


def test_training_digest_change_is_rejected(tmp_path, synthetic_sources):
    old, later = synthetic_sources
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=tmp_path / "targets.json",
        known_source=old,
        known_edition_id="AME2003",
    )
    freeze = freeze_training(
        training_source=old,
        training_edition_id="AME2003",
        targets_path=tmp_path / "targets.json",
    )
    with pytest.raises(LeakageError):
        assert_training_digest(freeze, ["Z1-N1"])


def test_prediction_modified_after_finalization_is_rejected(tmp_path, synthetic_sources):
    old, later = synthetic_sources
    prepare_targets(
        later_source=later,
        edition_id="AME2020",
        output=tmp_path / "targets.json",
        known_source=old,
        known_edition_id="AME2003",
    )
    freeze = freeze_training(
        training_source=old,
        training_edition_id="AME2003",
        targets_path=tmp_path / "targets.json",
    )
    run_dir = tmp_path / "run"
    predict_run(
        freeze=freeze,
        targets=load_targets(tmp_path / "targets.json"),
        training_source=old,
        training_edition_id="AME2003",
        run_dir=run_dir,
    )
    finalize(run_dir)
    with pytest.raises(ProtocolError):
        write_run_artifact(run_dir, "predictions", [{"tampered": True}])
    (run_dir / "predictions.json").write_text('[{"tampered": true}]\n', encoding="utf-8")
    with pytest.raises(LeakageError):
        score_run(run_dir=run_dir, truth_source=later, truth_edition_id="AME2020", out_dir=tmp_path / "s")


def test_mutable_and_unresolved_atlas_refs_are_rejected():
    with pytest.raises(AtlasContractError):
        validate_atlas_ref("main")
    with pytest.raises(AtlasContractError):
        validate_atlas_ref(None)
