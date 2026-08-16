"""EZ-B002 must reproduce: same snapshot and same regions, same bytes (WO-09).

Reproducibility is one of the four engineering PASS conditions of EZ-B002 v1, so
it is tested twice over: two clean runs of the same protocol must agree byte for
byte, and the committed ``experiments/EZ-B002-v1`` seal must be re-derivable from
the committed synthetic snapshot.
"""

from __future__ import annotations

import json

import pytest
from tests.helpers import write_synthetic_chart

from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
from elementzero.benchmark.regions import load_region_manifest
from elementzero.evidence.hashing import sha256_file, sha256_hex
from elementzero.experiments.b002_runner import (
    REGIONS_DIRNAME,
    REGIONS_FILE,
    RUNS_DIRNAME,
    SCORING_DIRNAME,
    SEALED_PREDICTIONS_FILE,
    SEALED_PREDICTIONS_HASH_FILE,
    read_regions,
    run_b002,
    seal_b002,
)
from elementzero.experiments.runner import verify_sha256sums

EDITION = "AME2020"
CREATED_AT = "2026-01-01T00:00:00Z"
COMMITTED = REPO_ROOT / "experiments" / "EZ-B002-v1"
COMMITTED_SNAPSHOT = REPO_ROOT / "tests" / "fixtures" / "b002" / "synthetic_chart_v1.mas20"


def _run_once(root) -> dict[str, str]:
    """Select, seal, and score one whole EZ-B002 experiment under ``root``."""
    from elementzero.experiments.b002_runner import select_regions_for_source

    source = write_synthetic_chart(root / "data" / "chart.mas20")
    regions_path = root / "regions.json"
    select_regions_for_source(
        source=source,
        edition_id=EDITION,
        output=regions_path,
        candidates_output=root / "candidates.json",
        source_relpath="chart.mas20",
    )
    experiment_dir = root / "experiment"
    run_b002(
        source=source,
        edition_id=EDITION,
        regions_path=regions_path,
        experiment_dir=experiment_dir,
        created_at=CREATED_AT,
    )
    hashes = {
        "snapshot": sha256_file(source),
        "regions": sha256_file(regions_path),
        "candidates": sha256_file(root / "candidates.json"),
        "sealed": sha256_file(experiment_dir / SEALED_PREDICTIONS_FILE),
        "aggregate": sha256_file(experiment_dir / "region_aggregate.json"),
    }
    regions = read_regions(experiment_dir / REGIONS_FILE)
    for region in regions["regions"]:
        region_dir = experiment_dir / REGIONS_DIRNAME / region.region_id
        hashes[f"{region.region_id}/split"] = sha256_file(region_dir / "split_manifest.json")
        hashes[f"{region.region_id}/targets"] = sha256_file(region_dir / "targets.json")
        hashes[f"{region.region_id}/freeze"] = sha256_file(region_dir / "freeze.json")
        hashes[f"{region.region_id}/comparison"] = sha256_file(
            region_dir / "region_comparison.json"
        )
        for model_id in SUITE_MODEL_IDS:
            run_dir = region_dir / RUNS_DIRNAME / model_id
            for name in ("predictions", "certificates", "model_manifest", "freeze"):
                hashes[f"{region.region_id}/{model_id}/{name}"] = sha256_file(
                    run_dir / f"{name}.json"
                )
            hashes[f"{region.region_id}/{model_id}/ledger"] = sha256_file(
                run_dir / "LEDGER_FINALIZED"
            )
            for name in ("facts", "provenance", "artifacts", "events"):
                hashes[f"{region.region_id}/{model_id}/atlas_{name}"] = sha256_file(
                    run_dir / "atlas" / f"{name}.json"
                )
            hashes[f"{region.region_id}/{model_id}/metrics"] = sha256_file(
                run_dir / SCORING_DIRNAME / "metrics.json"
            )
    return hashes


def test_region_results_reproducible(tmp_path):
    first = _run_once(tmp_path / "a")
    second = _run_once(tmp_path / "b")
    # Same generator on the same snapshot selects the same regions...
    assert first["snapshot"] == second["snapshot"]
    assert first["regions"] == second["regions"]
    assert first["candidates"] == second["candidates"]
    # ...and the whole sealed, scored experiment is byte-identical.
    assert set(first) == set(second)
    for key in sorted(first):
        assert first[key] == second[key], key
    metric_keys = [k for k in first if k.endswith("/metrics")]
    assert len(metric_keys) == 3 * len(SUITE_MODEL_IDS)


def test_rescoring_a_sealed_region_does_not_change_its_metrics(tmp_path):
    from elementzero.benchmark.b002_score import score_region_run
    from elementzero.experiments.b002_runner import select_regions_for_source

    source = write_synthetic_chart(tmp_path / "data" / "chart.mas20")
    regions_path = tmp_path / "regions.json"
    selected = select_regions_for_source(
        source=source,
        edition_id=EDITION,
        output=regions_path,
        source_relpath="chart.mas20",
    )
    experiment_dir = tmp_path / "experiment"
    seal_b002(
        source=source,
        edition_id=EDITION,
        regions_path=regions_path,
        experiment_dir=experiment_dir,
        created_at=CREATED_AT,
    )
    region_id = selected["manifest"]["region_ids"][0]
    run_dir = experiment_dir / REGIONS_DIRNAME / region_id / RUNS_DIRNAME / SUITE_MODEL_IDS[0]
    first = score_region_run(
        run_dir=run_dir,
        truth_source=source,
        truth_edition_id=EDITION,
        out_dir=tmp_path / "score_a",
        created_at=CREATED_AT,
    )
    second = score_region_run(
        run_dir=run_dir,
        truth_source=source,
        truth_edition_id=EDITION,
        out_dir=tmp_path / "score_b",
        created_at=CREATED_AT,
    )
    assert sha256_file(tmp_path / "score_a" / "metrics.json") == sha256_file(
        tmp_path / "score_b" / "metrics.json"
    )
    assert first["validation_fact_id"] == second["validation_fact_id"]
    assert first["finalization_marker_hash"] == second["finalization_marker_hash"]


# --------------------------------------------------------------------------- #
# The committed experiment                                                    #
# --------------------------------------------------------------------------- #


def test_committed_snapshot_regenerates_byte_for_byte(tmp_path):
    """The committed synthetic snapshot is reproducible from tests/helpers.py."""
    regenerated = write_synthetic_chart(tmp_path / "chart.mas20")
    assert sha256_file(regenerated) == sha256_file(COMMITTED_SNAPSHOT)
    manifest = json.loads((COMMITTED / REGIONS_FILE).read_text(encoding="utf-8"))
    assert manifest["source"]["raw_sha256"] == sha256_file(COMMITTED_SNAPSHOT)
    assert manifest["source"]["raw_relpath"].endswith("synthetic_chart_v1.mas20")


def test_committed_experiment_artifact_hashes_verify():
    if not (COMMITTED / SEALED_PREDICTIONS_FILE).is_file():
        pytest.skip("EZ-B002-v1 is preregistered but not sealed in this checkout")
    assert verify_sha256sums(COMMITTED)["ok"]
    recorded = (COMMITTED / SEALED_PREDICTIONS_HASH_FILE).read_text(encoding="utf-8").strip()
    assert sha256_file(COMMITTED / SEALED_PREDICTIONS_FILE) == recorded
    sealed = json.loads((COMMITTED / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    regions = load_region_manifest(json.loads((COMMITTED / REGIONS_FILE).read_text("utf-8")))
    assert sealed["region_manifest_hash"] == regions["region_manifest_hash"]
    assert sealed["region_ids"] == [r.region_id for r in regions["regions"]]
    assert sealed["model_ids"] == list(SUITE_MODEL_IDS)


def test_committed_seal_is_reproducible_from_the_committed_snapshot(tmp_path, monkeypatch):
    """Re-seal the committed regions and reproduce the committed digests.

    ``elementzero_commit`` is part of the freeze payload, so it is an input to
    ``freeze_id``. Pinning it to the value the committed run recorded is what
    makes this a reproducibility check rather than a "did the repo move" check.
    """
    if not (COMMITTED / SEALED_PREDICTIONS_FILE).is_file():
        pytest.skip("EZ-B002-v1 is preregistered but not sealed in this checkout")
    sealed = json.loads((COMMITTED / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    monkeypatch.setenv("ELEMENTZERO_COMMIT", sealed["elementzero_commit"])

    replay = seal_b002(
        source=COMMITTED_SNAPSHOT,
        edition_id=sealed["edition_id"],
        regions_path=COMMITTED / REGIONS_FILE,
        experiment_dir=tmp_path / "replay",
        created_at=sealed["created_at"],
    )
    assert replay["sealed"]["region_manifest_hash"] == sealed["region_manifest_hash"]
    assert replay["sealed"]["raw_source_hash"] == sealed["raw_source_hash"]
    for committed_region, replayed_region in zip(
        sealed["regions"], replay["sealed"]["regions"], strict=True
    ):
        assert replayed_region["region_id"] == committed_region["region_id"]
        assert replayed_region["split_digest"] == committed_region["split_digest"]
        assert replayed_region["freeze_id"] == committed_region["freeze_id"]
        assert replayed_region["targets_sha256"] == committed_region["targets_sha256"]
        assert replayed_region["freeze_sha256"] == committed_region["freeze_sha256"]
        for committed_run, replayed_run in zip(
            committed_region["runs"], replayed_region["runs"], strict=True
        ):
            assert replayed_run["model_id"] == committed_run["model_id"]
            assert replayed_run["model_manifest_hash"] == committed_run["model_manifest_hash"]
            assert (
                replayed_run["prediction_set_fact_id"] == committed_run["prediction_set_fact_id"]
            )
            assert (
                replayed_run["finalization_marker_hash"]
                == committed_run["finalization_marker_hash"]
            )
    assert replay["sealed_predictions_sha256"] == (
        COMMITTED / SEALED_PREDICTIONS_HASH_FILE
    ).read_text(encoding="utf-8").strip()


def test_committed_metrics_are_reproducible_from_the_committed_seal(tmp_path, monkeypatch):
    if not (COMMITTED / "region_aggregate.json").is_file():
        pytest.skip("EZ-B002-v1 is sealed but not scored in this checkout")
    from elementzero.benchmark.b002_score import score_region_run

    sealed = json.loads((COMMITTED / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    monkeypatch.setenv("ELEMENTZERO_COMMIT", sealed["elementzero_commit"])
    score_manifest = json.loads((COMMITTED / "SCORE_MANIFEST.json").read_text("utf-8"))
    recorded = {
        (region["region_id"], model["model_id"]): model["metrics_content_hash"]
        for region in score_manifest["regions"]
        for model in region["models"]
    }
    assert recorded
    for region in sealed["regions"]:
        for run in region["runs"]:
            report = score_region_run(
                run_dir=COMMITTED / run["run_relpath"],
                truth_source=COMMITTED_SNAPSHOT,
                truth_edition_id=sealed["edition_id"],
                out_dir=tmp_path / region["region_id"] / run["model_id"],
                created_at=score_manifest["created_at"],
            )
            key = (region["region_id"], run["model_id"])
            assert sha256_hex(report["metrics"]) == recorded[key], key
