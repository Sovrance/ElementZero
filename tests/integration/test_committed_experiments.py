"""The committed experiment artifacts must keep validating in a clean checkout.

These tests read what is in the repository, not a fixture. If a protocol source
file is edited after an experiment was preregistered and sealed, the protocol
code digest stops matching and this suite fails loudly instead of letting a
mixed-protocol series be reported as one benchmark.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from elementzero.benchmark.model_suite import COMPARISON_JSON_NAME, SUITE_MODEL_IDS
from elementzero.experiments.epochs import EPOCH_ORDER, epoch_for
from elementzero.experiments.preregister import (
    EXPERIMENT_PROTOCOL_VERSION,
    PREREGISTRATION_FILES,
    PREREGISTRATION_HASH_FILE,
    PROTOCOL_FILE,
    preregistration_hash,
    validate_preregistration,
)
from elementzero.experiments.runner import replay_experiment, verify_sha256sums

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = REPO_ROOT / "experiments"


def committed_experiments() -> list[Path]:
    if not EXPERIMENTS.is_dir():
        return []
    return [
        EXPERIMENTS / experiment_id
        for experiment_id in EPOCH_ORDER
        if (EXPERIMENTS / experiment_id / PROTOCOL_FILE).is_file()
    ]


def pytest_generate_tests(metafunc):  # pragma: no cover - collection helper
    if "experiment_dir" in metafunc.fixturenames:
        dirs = committed_experiments()
        metafunc.parametrize("experiment_dir", dirs, ids=[d.name for d in dirs])


def test_at_least_one_experiment_is_preregistered():
    assert committed_experiments(), "no committed experiment preregistration found"


def test_committed_preregistration_validates(experiment_dir):
    report = validate_preregistration(experiment_dir, root=REPO_ROOT)
    assert report["status"] == "VALID"
    assert report["protocol_version"] == EXPERIMENT_PROTOCOL_VERSION
    assert report["protocol_code_matches"], (
        "a protocol source file changed after this experiment was preregistered; "
        "bump the protocol version and rerun every epoch"
    )


def test_committed_preregistration_hash_is_reproducible(experiment_dir):
    recorded = (experiment_dir / PREREGISTRATION_HASH_FILE).read_text(encoding="utf-8").strip()
    assert recorded == preregistration_hash(experiment_dir)
    for name in PREREGISTRATION_FILES:
        assert (experiment_dir / name).is_file()


def test_committed_artifact_hashes_verify(experiment_dir):
    report = verify_sha256sums(experiment_dir)
    assert report["ok"], report


def test_every_scored_epoch_reports_every_model(experiment_dir):
    comparison_path = experiment_dir / COMPARISON_JSON_NAME
    if not comparison_path.is_file():
        pytest.skip(f"{experiment_dir.name} is preregistered but not scored yet")
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert [row["model_id"] for row in comparison["rows"]] == list(SUITE_MODEL_IDS)


def test_committed_replay_matches_committed_metrics(experiment_dir):
    """Replay the committed seal against the raw truth table, without refitting.

    The raw AME tables are not committed (they are licensed upstream files kept
    out of git), so a checkout without ``data/raw`` skips instead of failing.
    """
    epoch = epoch_for(experiment_dir.name)
    truth_source = REPO_ROOT / epoch.truth_relpath
    if not truth_source.is_file() or not (experiment_dir / COMPARISON_JSON_NAME).is_file():
        pytest.skip(f"{epoch.truth_edition} raw table or scoring is absent in this checkout")
    report = replay_experiment(epoch=epoch, experiment_dir=experiment_dir, root=REPO_ROOT)
    assert report["status"] == "REPLAY_MATCHES_COMMITTED_METRICS"
    assert report["refit"] is False
    assert [m["model_id"] for m in report["models"]] == list(SUITE_MODEL_IDS)
    assert all(m["matches"] for m in report["models"])


def test_committed_preregistrations_share_one_protocol(request):
    dirs = committed_experiments()
    if len(dirs) < 2:
        pytest.skip("fewer than two experiments are preregistered")
    protocols = [json.loads((d / PROTOCOL_FILE).read_text(encoding="utf-8")) for d in dirs]
    assert {p["protocol_version"] for p in protocols} == {EXPERIMENT_PROTOCOL_VERSION}
    assert len({p["protocol_code_digest"] for p in protocols}) == 1
    assert len({tuple(p["model_ids"]) for p in protocols}) == 1
    assert len({p["atlas_pir_ref"] for p in protocols}) == 1
