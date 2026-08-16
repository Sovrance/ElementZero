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


def test_worst_region_defect_classifier_accepts_only_the_ranking_defect():
    from elementzero.adjudication.artifact_audit import (
        _markdown_defect_only,
        _worst_region_defect_models,
    )

    def _aggregate(worst_id: str, worst_mae: str) -> dict:
        per_region = [
            {"region_id": "rect-A", "MAE_keV": "2.242414147464e+03"},
            {"region_id": "rect-B", "MAE_keV": "8.968206217060e+02"},
        ]
        return {
            "by_model": {
                "EZ-GP-DIRECT-v1": {
                    "worst_region": {"region_id": worst_id, "MAE_keV": worst_mae},
                    "per_region": per_region,
                }
            }
        }

    committed = _aggregate("rect-B", "8.968206217060e+02")  # string max, wrong
    replayed = _aggregate("rect-A", "2.242414147464e+03")  # numeric max, right
    assert _worst_region_defect_models(committed, replayed) == ["EZ-GP-DIRECT-v1"]
    # Identical aggregates report no affected models.
    assert _worst_region_defect_models(replayed, replayed) == []
    # A replayed choice that is NOT the numeric argmax is a real failure.
    bogus = _aggregate("rect-B", "8.968206217060e+02")
    bogus["by_model"]["EZ-GP-DIRECT-v1"]["worst_region"]["region_id"] = "rect-C"
    assert _worst_region_defect_models(committed, bogus) is None
    # Any difference outside worst_region is a real failure too.
    drifted = _aggregate("rect-A", "2.242414147464e+03")
    drifted["by_model"]["EZ-GP-DIRECT-v1"]["per_region"][0]["MAE_keV"] = (
        "2.242414147465e+03"
    )
    assert _worst_region_defect_models(committed, drifted) is None

    models = ["EZ-GP-DIRECT-v1"]
    assert _markdown_defect_only(
        "| EZ-GP-DIRECT-v1 | rect-B | 896.821 |",
        "| EZ-GP-DIRECT-v1 | rect-A | 2242.41 |",
        models,
    )
    assert not _markdown_defect_only(
        "| EZ-SEMF-LS-v1 | rect-B | 1.0 |",
        "| EZ-SEMF-LS-v1 | rect-A | 2.0 |",
        models,
    )
    assert not _markdown_defect_only("a\nb", "a", models)
