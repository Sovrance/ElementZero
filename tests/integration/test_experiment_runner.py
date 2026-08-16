"""WO-06: seal, score, and replay a full epoch on synthetic sources.

The synthetic editions keep this fast. The pipeline exercised here is exactly the
one that produced the committed official runs: same preregistration gates, same
blind-workspace preflight, same finalization, same scoring path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.helpers import synthetic_editions

from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.hashing import canonical_json
from elementzero.experiments.epochs import EpochSpec
from elementzero.experiments.preregister import (
    PREREGISTRATION_HASH_FILE,
    PROTOCOL_FILE,
    write_preregistration,
)
from elementzero.experiments.runner import (
    RUNS_DIRNAME,
    SCORE_MANIFEST_FILE,
    SEALED_PREDICTIONS_FILE,
    SEALED_PREDICTIONS_HASH_FILE,
    assert_workspace_blind,
    replay_experiment,
    score_experiment,
    seal_experiment,
    verify_sha256sums,
)

FAKE_COMMIT = "d" * 40
SYNTHETIC_EPOCH = EpochSpec(
    experiment_id="EZ-B001-A",
    training_edition="AME2003",
    truth_edition="AME2020",
    created_at="2026-08-16T00:00:00Z",
)


@pytest.fixture
def sealed(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    training, truth = synthetic_editions(tmp_path / "sources")
    experiment_dir = tmp_path / "experiments" / SYNTHETIC_EPOCH.experiment_id
    write_preregistration(
        epoch=SYNTHETIC_EPOCH,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
    )
    result = seal_experiment(
        epoch=SYNTHETIC_EPOCH,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
        subprocess_prediction=False,
    )
    return {
        "dir": experiment_dir,
        "training": training,
        "truth": truth,
        "result": result,
    }


def test_seal_writes_audit_targets_freeze_and_seal(sealed):
    experiment_dir = sealed["dir"]
    manifest = sealed["result"]["run_manifest"]

    for name in ("ame2003_parse_report.json", "ame2020_parse_report.json"):
        report = json.loads((experiment_dir / "data_audit" / name).read_text(encoding="utf-8"))
        assert report["parsed_records"] > 0
        assert report["eligible_records"] > 0
        assert report["invalid_A_equals_Z_plus_N"] == 0

    targets = json.loads((experiment_dir / "targets.json").read_text(encoding="utf-8"))["targets"]
    assert targets
    for target in targets:
        assert set(target) == {"nuclide_id", "Z", "N", "A"}

    freeze = json.loads((experiment_dir / "freeze.json").read_text(encoding="utf-8"))
    protocol = json.loads((experiment_dir / PROTOCOL_FILE).read_text(encoding="utf-8"))
    assert freeze["allowed_source_hashes"] == [protocol["training"]["raw_sha256"]]
    assert protocol["later_edition"]["raw_sha256"] in freeze["forbidden_source_hashes"]

    sealed_manifest = json.loads((experiment_dir / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    assert sealed_manifest["state"] == "PREDICTIONS_SEALED_TRUTH_LOCKED"
    assert [r["model_id"] for r in sealed_manifest["runs"]] == list(SUITE_MODEL_IDS)
    digests = {r["finalization_marker_hash"] for r in sealed_manifest["runs"]}
    assert len(digests) == len(SUITE_MODEL_IDS)
    assert (experiment_dir / SEALED_PREDICTIONS_HASH_FILE).read_text(encoding="utf-8").strip()

    # Every model shares one freeze and one target set.
    assert len({r["freeze_id"] for r in sealed_manifest["runs"]}) == 1
    assert manifest["blind_workspace"]["preflight_before_prediction"]["status"] == "BLIND"
    assert manifest["blind_workspace"]["preflight_after_prediction"]["status"] == "BLIND"
    assert verify_sha256sums(experiment_dir)["ok"]

    # No truth-bearing artifact exists before scoring.
    assert not (experiment_dir / SCORE_MANIFEST_FILE).exists()
    for model_id in SUITE_MODEL_IDS:
        assert not (experiment_dir / RUNS_DIRNAME / model_id / "scoring").exists()


def test_score_reports_every_model_and_metric(sealed):
    result = score_experiment(
        epoch=SYNTHETIC_EPOCH,
        experiment_dir=sealed["dir"],
        truth_source=sealed["truth"],
    )
    comparison = result["comparison"]
    assert [row["model_id"] for row in comparison["rows"]] == list(SUITE_MODEL_IDS)
    for row in comparison["rows"]:
        for metric in (
            "MAE_keV",
            "MedAE_keV",
            "RMSE_keV",
            "NLPD",
            "coverage_90",
            "coverage_95",
            "calibration_error_90",
            "calibration_error_95",
        ):
            assert row[metric] is not None
    assert "best" not in comparison["ranking_rule"].split(":")[0]

    scored = json.loads(
        (
            sealed["dir"] / RUNS_DIRNAME / SUITE_MODEL_IDS[0] / "scoring" / "scored_predictions.json"
        ).read_text(encoding="utf-8")
    )
    assert scored["rows"]
    assert verify_sha256sums(sealed["dir"])["ok"]


def test_replay_matches_committed_metrics_without_refit(sealed):
    score_experiment(
        epoch=SYNTHETIC_EPOCH,
        experiment_dir=sealed["dir"],
        truth_source=sealed["truth"],
    )
    before = verify_sha256sums(sealed["dir"])
    replay = replay_experiment(
        epoch=SYNTHETIC_EPOCH,
        experiment_dir=sealed["dir"],
        truth_source=sealed["truth"],
    )
    assert replay["status"] == "REPLAY_MATCHES_COMMITTED_METRICS"
    assert [m["model_id"] for m in replay["models"]] == list(SUITE_MODEL_IDS)
    assert all(m["matches"] and m["refit"] is False for m in replay["models"])
    # Replay must not touch a single committed artifact.
    assert verify_sha256sums(sealed["dir"])["ok"]
    assert before == verify_sha256sums(sealed["dir"])


def test_second_seal_into_the_same_directory_is_refused(sealed):
    with pytest.raises(ProtocolError):
        seal_experiment(
            epoch=SYNTHETIC_EPOCH,
            experiment_dir=sealed["dir"],
            training_source=sealed["training"],
            truth_source=sealed["truth"],
            subprocess_prediction=False,
        )


def test_seal_refuses_a_source_that_does_not_match_the_preregistration(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    training, truth = synthetic_editions(tmp_path / "sources")
    experiment_dir = tmp_path / "exp"
    write_preregistration(
        epoch=SYNTHETIC_EPOCH,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
    )
    tampered = tmp_path / "tampered.mas03"
    tampered.write_text(training.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ProtocolError):
        seal_experiment(
            epoch=SYNTHETIC_EPOCH,
            experiment_dir=experiment_dir,
            training_source=tampered,
            truth_source=truth,
            subprocess_prediction=False,
        )


def test_altered_preregistration_hash_blocks_the_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    training, truth = synthetic_editions(tmp_path / "sources")
    experiment_dir = tmp_path / "exp"
    write_preregistration(
        epoch=SYNTHETIC_EPOCH,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
    )
    (experiment_dir / PREREGISTRATION_HASH_FILE).write_text("0" * 64 + "\n", encoding="utf-8")
    with pytest.raises(ProtocolError):
        seal_experiment(
            epoch=SYNTHETIC_EPOCH,
            experiment_dir=experiment_dir,
            training_source=training,
            truth_source=truth,
            subprocess_prediction=False,
        )


def test_scoring_before_sealing_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    training, truth = synthetic_editions(tmp_path / "sources")
    experiment_dir = tmp_path / "exp"
    write_preregistration(
        epoch=SYNTHETIC_EPOCH,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
    )
    with pytest.raises(ProtocolError):
        score_experiment(
            epoch=SYNTHETIC_EPOCH,
            experiment_dir=experiment_dir,
            truth_source=truth,
        )


def test_score_refuses_a_tampered_sealed_manifest(sealed):
    path = sealed["dir"] / SEALED_PREDICTIONS_FILE
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["target_identity_digest"] = "0" * 64
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    with pytest.raises(ProtocolError):
        score_experiment(
            epoch=SYNTHETIC_EPOCH,
            experiment_dir=sealed["dir"],
            truth_source=sealed["truth"],
        )


def test_workspace_preflight_catches_truth_by_name_and_by_content(tmp_path):
    from elementzero.evidence.hashing import sha256_file

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "targets.json").write_text('{"targets": []}\n', encoding="utf-8")
    assert assert_workspace_blind(
        workspace,
        forbidden_source_hashes={"a" * 64},
        forbidden_filenames={"mass.mas12"},
    )["status"] == "BLIND"

    by_name = workspace / "mass.mas12"
    by_name.write_text("later edition\n", encoding="utf-8")
    with pytest.raises(LeakageError):
        assert_workspace_blind(
            workspace,
            forbidden_source_hashes={"a" * 64},
            forbidden_filenames={"mass.mas12"},
        )
    by_name.unlink()

    smuggled = workspace / "innocent_name.txt"
    smuggled.write_text("later edition\n", encoding="utf-8")
    with pytest.raises(LeakageError):
        assert_workspace_blind(
            workspace,
            forbidden_source_hashes={sha256_file(smuggled)},
            forbidden_filenames={"mass.mas12"},
        )


def test_blind_prediction_subprocess_path_matches_the_in_process_path(tmp_path, monkeypatch):
    """The real runs use a separate process; it must seal identical artifacts."""
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    training, truth = synthetic_editions(tmp_path / "sources")
    digests = {}
    for mode in ("subprocess", "in_process"):
        experiment_dir = tmp_path / mode
        write_preregistration(
            epoch=SYNTHETIC_EPOCH,
            experiment_dir=experiment_dir,
            training_source=training,
            truth_source=truth,
        )
        seal_experiment(
            epoch=SYNTHETIC_EPOCH,
            experiment_dir=experiment_dir,
            training_source=training,
            truth_source=truth,
            subprocess_prediction=mode == "subprocess",
        )
        digests[mode] = {
            model_id: json.loads(
                (experiment_dir / RUNS_DIRNAME / model_id / "run_manifest.json").read_text(
                    encoding="utf-8"
                )
            )["predictions_file_hash"]
            for model_id in SUITE_MODEL_IDS
        }
    assert digests["subprocess"] == digests["in_process"]


def test_run_manifest_records_the_layout_deviation(sealed):
    layout = sealed["result"]["run_manifest"]["artifact_layout"]
    assert layout["runs"] == RUNS_DIRNAME
    assert "results/<experiment>" in layout["layout_note"]
    assert Path(sealed["dir"] / layout["targets"]).is_file()
