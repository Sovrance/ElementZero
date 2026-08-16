"""WO-11 report bundle — deterministic, and the committed bundle regenerates."""

from __future__ import annotations

import json

from elementzero.adjudication.report import run_wo11
from elementzero.atlas_pin import REPO_ROOT
from elementzero.evidence.hashing import sha256_file

COMMITTED = REPO_ROOT / "reports" / "adjudication" / "wo11"

# Artifacts whose bytes are independent of the interpreter that produced them.
# replay_verification.json records the replay environment, the markdown report
# quotes it, and SHA256SUMS.txt indexes both.
ENVIRONMENT_INDEPENDENT_FILES = (
    "README.md",
    "ablation_matrix.json",
    "artifact_inventory.json",
    "benchmark_controls.json",
    "failure_records.json",
    "frontier_model_candidates.json",
    "model_readiness.json",
    "uncertainty_diagnostics.json",
    "wo11_adjudication_report.json",
)


def test_wo11_report_reproducible(tmp_path):
    """Two clean builds agree byte for byte, SHA256SUMS included."""
    first = run_wo11(out_dir=tmp_path / "a", workspace_dir=tmp_path / "wsa")
    second = run_wo11(out_dir=tmp_path / "b", workspace_dir=tmp_path / "wsb")
    assert first["adjudication"] == second["adjudication"]
    files_a = sorted(p.name for p in (tmp_path / "a").iterdir())
    files_b = sorted(p.name for p in (tmp_path / "b").iterdir())
    assert files_a == files_b
    for name in files_a:
        assert sha256_file(tmp_path / "a" / name) == sha256_file(tmp_path / "b" / name), name


def test_committed_bundle_regenerates(tmp_path):
    """A fresh build reproduces every committed environment-independent file."""
    result = run_wo11(out_dir=tmp_path / "out", workspace_dir=tmp_path / "ws")
    assert result["adjudication"]["replay_status"] == "PASS"
    assert result["adjudication"]["benchmark_control_status"] == "PASS"
    assert (
        result["adjudication"]["model_readiness_verdict"] == "FRONTIER_MODEL_RERUN_JUSTIFIED"
    )
    for name in ENVIRONMENT_INDEPENDENT_FILES:
        assert sha256_file(tmp_path / "out" / name) == sha256_file(COMMITTED / name), name
    regenerated = json.loads((tmp_path / "out" / "replay_verification.json").read_text("utf-8"))
    assert regenerated["replay_status"] == "PASS"


def test_committed_bundle_checksums_verify():
    from elementzero.experiments.runner import verify_sha256sums

    assert verify_sha256sums(COMMITTED)["ok"]
