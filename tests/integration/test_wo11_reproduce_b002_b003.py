"""WO-11.2 / WO-11.7 — sealed replay without refitting, and oracle controls."""

from __future__ import annotations

import sys

import pytest

from elementzero.adjudication.artifact_audit import (
    forbid_model_fitting,
    replay_b002,
    replay_b003,
)
from elementzero.adjudication.benchmark_controls import (
    CONTROL_EXACT_ORACLE,
    CONTROL_SHELL_AWARE_ORACLE,
    CONTROL_WEAK_SMOOTH,
    run_b002_controls,
    run_b003_controls,
)
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark import b002_predict, b003_predict
from elementzero.errors import ProtocolError
from elementzero.models import gp_residual

B002 = REPO_ROOT / "experiments" / "EZ-B002-v1"
B003 = REPO_ROOT / "experiments" / "EZ-B003-v1"
B002_SNAPSHOT = REPO_ROOT / "tests" / "fixtures" / "b002" / "synthetic_chart_v1.mas20"
B003_SNAPSHOT = REPO_ROOT / "tests" / "fixtures" / "b003" / "synthetic_shell_chart_v1.mas20"

# The v1 experiments recorded CPython 3.12; on that line the replay is
# byte-identical including raw-float Atlas fact payloads.
RECORDED_PYTHON_MINOR = (3, 12)


def test_wo11_replay_does_not_refit():
    """The tripwire fires on any fit attempt, and replay survives it armed."""
    with forbid_model_fitting():
        for module in (gp_residual, b002_predict, b003_predict):
            with pytest.raises(ProtocolError):
                module.build_model("EZ-SEMF-LS-v1")
        with pytest.raises(ProtocolError):
            gp_residual.SEMFGPResidualModel().fit([])
        with pytest.raises(ProtocolError):
            gp_residual.SEMFLeastSquaresModel().fit([])
    # Outside the context the frozen registry is restored untouched.
    assert gp_residual.build_model("EZ-SEMF-LS-v1").model_id == "EZ-SEMF-LS-v1"
    assert b002_predict.build_model("EZ-GP-DIRECT-v1").model_id == "EZ-GP-DIRECT-v1"


def test_replay_b002_reproduces_frozen_metrics(tmp_path):
    result = replay_b002(
        committed_dir=B002, workspace_dir=tmp_path / "replay", snapshot=B002_SNAPSHOT
    )
    assert result["replay_status"] == "PASS"
    comparison = result["comparison"]
    assert comparison["metrics_files_identical"] == comparison["metrics_files"]
    assert comparison["frozen_metrics_identical"] is True
    # The corrected worst-region ranking (PR #11 review) legitimately differs
    # from the frozen v1 aggregate for exactly one model; the replay must
    # surface that as the documented defect, never silently pass or fail.
    assert result["aggregate_values_identical"] is False
    assert result["aggregate_values_identical_excluding_known_defects"] is True
    (defect,) = result["known_defects"]
    assert defect["defect_id"] == "b002-worst-region-string-ranking-v1"
    assert defect["models"] == ["EZ-GP-DIRECT-v1"]
    if sys.version_info[:2] == RECORDED_PYTHON_MINOR:
        assert result["unexplained_strict_byte_differences"] == []


def test_replay_b003_reproduces_frozen_verdicts(tmp_path):
    result = replay_b003(
        committed_dir=B003, workspace_dir=tmp_path / "replay", snapshot=B003_SNAPSHOT
    )
    assert result["replay_status"] == "PASS"
    assert result["verdicts_identical"] is True
    assert result["replayed_verdicts"] == {
        "EZ-GP-DIRECT-v1": "CRITERION_NOT_MET",
        "EZ-SEMF-GP-RESIDUAL-v1": "CRITERION_NOT_MET",
        "EZ-SEMF-LS-v1": "CRITERION_NOT_MET",
    }
    if sys.version_info[:2] == RECORDED_PYTHON_MINOR:
        assert result["comparison"]["strict_byte_identical"] is True


def test_replay_refuses_to_write_into_the_evidence(tmp_path):
    with pytest.raises(ProtocolError):
        replay_b002(committed_dir=B002, workspace_dir=B002, snapshot=B002_SNAPSHOT)


@pytest.fixture(scope="module")
def b002_controls(tmp_path_factory):
    return run_b002_controls(
        snapshot=B002_SNAPSHOT,
        regions_path=B002 / "regions.json",
        workspace_dir=tmp_path_factory.mktemp("b002-controls") / "run",
    )


@pytest.fixture(scope="module")
def b003_controls(tmp_path_factory):
    return run_b003_controls(
        snapshot=B003_SNAPSHOT,
        challenges_path=B003 / "challenges.json",
        workspace_dir=tmp_path_factory.mktemp("b003-controls") / "run",
    )


def test_oracle_control_passes_synthetic_b002(b002_controls):
    assert b002_controls["status"] == "PASS"
    exact = b002_controls["by_model"][CONTROL_EXACT_ORACLE]
    assert exact["MAE_keV"] == 0.0
    assert exact["coverage_90"] == 1.0


def test_shell_oracle_passes_synthetic_b003(b003_controls):
    oracle = b003_controls["by_model"][CONTROL_SHELL_AWARE_ORACLE]
    assert oracle["verdict"] == "CRITERION_MET"
    assert oracle["rank_1_fraction"] == 1.0
    assert b003_controls["status"] == "PASS"


def test_weak_control_fails_expected_criterion(b002_controls, b003_controls):
    weak_shell = b003_controls["by_model"][CONTROL_WEAK_SMOOTH]
    assert weak_shell["verdict"] == "CRITERION_NOT_MET"
    weak_mass = b002_controls["by_model"][CONTROL_WEAK_SMOOTH]
    exact = b002_controls["by_model"][CONTROL_EXACT_ORACLE]
    assert weak_mass["MAE_keV"] > 100.0 * max(exact["MAE_keV"], 1.0)
