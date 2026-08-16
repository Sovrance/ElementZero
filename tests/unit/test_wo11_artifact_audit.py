"""WO-11.1 — the frozen v1 evidence must be byte-for-byte intact."""

from __future__ import annotations

import json

from elementzero.adjudication.artifact_audit import (
    assert_v1_evidence_unchanged,
    build_artifact_inventory,
)
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.shell_metrics import rediscovery_criterion
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex

B002 = REPO_ROOT / "experiments" / "EZ-B002-v1"
B003 = REPO_ROOT / "experiments" / "EZ-B003-v1"
COMMITTED_INVENTORY = REPO_ROOT / "reports" / "adjudication" / "wo11" / "artifact_inventory.json"


def test_v1_threshold_files_unchanged():
    """The frozen B003 criterion and B002 region manifest never move."""
    recorded = (B003 / "CRITERION_SHA256").read_text(encoding="utf-8").strip()
    assert sha256_file(B003 / "CRITERION.json") == recorded
    criterion = json.loads((B003 / "CRITERION.json").read_text(encoding="utf-8"))
    # The thresholds on disk are the thresholds in code; a moved threshold
    # would change this digest and is a stop condition, not a fix.
    assert criterion["criterion_digest"] == sha256_hex(rediscovery_criterion())
    recorded_regions = (B002 / "REGIONS_SHA256").read_text(encoding="utf-8").strip()
    assert sha256_file(B002 / "regions.json") == recorded_regions


def test_v1_prediction_hashes_unchanged():
    for experiment in (B002, B003, *(REPO_ROOT / "experiments" / e for e in ("EZ-B001-A", "EZ-B001-B", "EZ-B001-C"))):
        recorded = (experiment / "SEALED_PREDICTIONS_SHA256").read_text(encoding="utf-8").strip()
        assert sha256_file(experiment / "SEALED_PREDICTIONS.json") == recorded, experiment.name


def test_inventory_reports_everything_unchanged():
    inventory = build_artifact_inventory()
    assert inventory["all_unchanged"] is True
    assert_v1_evidence_unchanged(inventory)
    assert inventory["experiments"]["EZ-B003-v1"]["verdicts"] == {
        "EZ-GP-DIRECT-v1": "CRITERION_NOT_MET",
        "EZ-SEMF-GP-RESIDUAL-v1": "CRITERION_NOT_MET",
        "EZ-SEMF-LS-v1": "CRITERION_NOT_MET",
    }
    # EZ-B002-v1 froze no accuracy criterion; the inventory must say so
    # rather than inventing a CRITERION_NOT_MET status for it.
    assert inventory["experiments"]["EZ-B002-v1"]["status"] == "ENGINEERING_PASS_CHARACTERIZATION"


def test_committed_inventory_matches_a_fresh_build():
    committed = json.loads(COMMITTED_INVENTORY.read_text(encoding="utf-8"))
    fresh = json.loads(canonical_json(build_artifact_inventory()))
    assert fresh == committed


def test_tampering_is_detected(tmp_path):
    original = (B003 / "CRITERION.json").read_bytes()
    tampered = tmp_path / "CRITERION.json"
    tampered.write_bytes(original.replace(b"7.500000000000e-01", b"7.400000000000e-01", 1))
    recorded = (B003 / "CRITERION_SHA256").read_text(encoding="utf-8").strip()
    assert sha256_file(tampered) != recorded
