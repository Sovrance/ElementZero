"""EZ-B003 must reproduce: same snapshot and same closures, same bytes (WO-10).

Reproducibility carries more weight here than in EZ-B002. A rediscovery claim is
a claim that a *specific* coordinate ranked first, so the whole result rests on a
ranking over floating-point indicator values derived from floating-point mass
predictions. If that ranking is not bit-stable, "the closure ranked first" is not
a finding, and neither is "it did not". The committed EZ-B003-v1 verdict is
CRITERION_NOT_MET, and a negative result has to be exactly as reproducible as a
positive one or it cannot be argued with.

Three things are checked: two clean runs of the whole protocol agree byte for
byte, the committed seal is re-derivable from the committed synthetic snapshot,
and the committed metrics are re-derivable from the committed seal.
"""

from __future__ import annotations

import json

import pytest
from tests.helpers import write_synthetic_shell_chart

from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
from elementzero.benchmark.shell_masks import load_challenge_manifest
from elementzero.evidence.hashing import sha256_file, sha256_hex
from elementzero.experiments.b003_runner import (
    CHALLENGES_FILE,
    CRITERION_FILE,
    CRITERION_HASH_FILE,
    RUNS_DIRNAME,
    SCORING_DIRNAME,
    SEALED_PREDICTIONS_FILE,
    SEALED_PREDICTIONS_HASH_FILE,
    run_b003,
    seal_b003,
    select_challenges_for_source,
)
from elementzero.experiments.runner import verify_sha256sums

EDITION = "AME2020"
CREATED_AT = "2026-01-01T00:00:00Z"
SCOPE = "synthetic"
COMMITTED = REPO_ROOT / "experiments" / "EZ-B003-v1"
COMMITTED_SNAPSHOT = REPO_ROOT / "tests" / "fixtures" / "b003" / "synthetic_shell_chart_v1.mas20"
AGGREGATE_FILE = "shell_aggregate.json"


def _run_once(root) -> dict[str, str]:
    """Select, seal, and score one whole EZ-B003 experiment under ``root``."""
    source = write_synthetic_shell_chart(root / "data" / "chart.mas20")
    challenges_path = root / CHALLENGES_FILE
    select_challenges_for_source(
        source=source,
        edition_id=EDITION,
        output=challenges_path,
        source_relpath="chart.mas20",
    )
    experiment_dir = root / "experiment"
    result = run_b003(
        source=source,
        edition_id=EDITION,
        challenges_path=challenges_path,
        experiment_dir=experiment_dir,
        scope=SCOPE,
        created_at=CREATED_AT,
    )
    hashes = {
        "snapshot": sha256_file(source),
        "challenges": sha256_file(challenges_path),
        "criterion": sha256_file(experiment_dir / CRITERION_FILE),
        "sealed": sha256_file(experiment_dir / SEALED_PREDICTIONS_FILE),
        "aggregate": sha256_file(experiment_dir / AGGREGATE_FILE),
    }
    for entry in result["sealed"]["sealed"]["challenges"]:
        challenge_id = entry["challenge_id"]
        challenge_dir = experiment_dir / entry["challenge_relpath"]
        for name in ("split_manifest", "targets", "freeze", "support"):
            hashes[f"{challenge_id}/{name}"] = sha256_file(challenge_dir / f"{name}.json")
        hashes[f"{challenge_id}/comparison"] = sha256_file(
            challenge_dir / "challenge_comparison.json"
        )
        for model_id in SUITE_MODEL_IDS:
            run_dir = challenge_dir / RUNS_DIRNAME / model_id
            for name in ("predictions", "certificates", "model_manifest", "freeze"):
                hashes[f"{challenge_id}/{model_id}/{name}"] = sha256_file(run_dir / f"{name}.json")
            hashes[f"{challenge_id}/{model_id}/ledger"] = sha256_file(run_dir / "LEDGER_FINALIZED")
            for name in ("facts", "provenance", "artifacts", "events"):
                hashes[f"{challenge_id}/{model_id}/atlas_{name}"] = sha256_file(
                    run_dir / "atlas" / f"{name}.json"
                )
            hashes[f"{challenge_id}/{model_id}/metrics"] = sha256_file(
                run_dir / SCORING_DIRNAME / "metrics.json"
            )
    return hashes


def test_shell_results_reproducible(tmp_path):
    first = _run_once(tmp_path / "a")
    second = _run_once(tmp_path / "b")
    # Same generator on the same snapshot admits the same closures...
    assert first["snapshot"] == second["snapshot"]
    assert first["challenges"] == second["challenges"]
    # ...the thresholds are the frozen ones either way...
    assert first["criterion"] == second["criterion"]
    # ...and the whole sealed, scored experiment is byte-identical.
    assert set(first) == set(second)
    for key in sorted(first):
        assert first[key] == second[key], key
    # Two closures survive the support rule on this chart, three models each.
    metric_keys = [k for k in first if k.endswith("/metrics")]
    assert len(metric_keys) == 2 * len(SUITE_MODEL_IDS)


def test_rescoring_a_sealed_closure_does_not_change_its_metrics(tmp_path):
    """Scoring is a read. Running it twice may not move a rank or a metric."""
    from elementzero.benchmark.b003_score import score_shell_run

    source = write_synthetic_shell_chart(tmp_path / "data" / "chart.mas20")
    challenges_path = tmp_path / CHALLENGES_FILE
    selected = select_challenges_for_source(
        source=source,
        edition_id=EDITION,
        output=challenges_path,
        source_relpath="chart.mas20",
    )
    experiment_dir = tmp_path / "experiment"
    seal_b003(
        source=source,
        edition_id=EDITION,
        challenges_path=challenges_path,
        experiment_dir=experiment_dir,
        scope=SCOPE,
        created_at=CREATED_AT,
    )
    challenge_id = selected["manifest"]["evaluable_challenge_ids"][0]
    run_dir = experiment_dir / "challenges" / challenge_id / RUNS_DIRNAME / SUITE_MODEL_IDS[0]
    reports = [
        score_shell_run(
            run_dir=run_dir,
            truth_source=source,
            truth_edition_id=EDITION,
            scope=SCOPE,
            out_dir=tmp_path / f"score_{tag}",
            created_at=CREATED_AT,
        )
        for tag in ("a", "b")
    ]
    first, second = reports
    assert sha256_file(tmp_path / "score_a" / "metrics.json") == sha256_file(
        tmp_path / "score_b" / "metrics.json"
    )
    assert first["validation_fact_id"] == second["validation_fact_id"]
    assert first["finalization_marker_hash"] == second["finalization_marker_hash"]
    # The rank of the withheld closure is the claim; it may not wobble.
    assert first["metrics"]["discovery"] == second["metrics"]["discovery"]
    assert first["discovery_rows"] == second["discovery_rows"]


# --------------------------------------------------------------------------- #
# The committed experiment                                                    #
# --------------------------------------------------------------------------- #


def test_committed_snapshot_regenerates_byte_for_byte(tmp_path):
    """The committed synthetic shell chart is reproducible from tests/helpers.py."""
    regenerated = write_synthetic_shell_chart(tmp_path / "chart.mas20")
    assert sha256_file(regenerated) == sha256_file(COMMITTED_SNAPSHOT)
    manifest = json.loads((COMMITTED / CHALLENGES_FILE).read_text(encoding="utf-8"))
    assert manifest["source"]["raw_sha256"] == sha256_file(COMMITTED_SNAPSHOT)
    assert manifest["source"]["raw_relpath"].endswith("synthetic_shell_chart_v1.mas20")


def test_committed_experiment_artifact_hashes_verify():
    if not (COMMITTED / SEALED_PREDICTIONS_FILE).is_file():
        pytest.skip("EZ-B003-v1 is preregistered but not sealed in this checkout")
    assert verify_sha256sums(COMMITTED)["ok"]
    recorded = (COMMITTED / SEALED_PREDICTIONS_HASH_FILE).read_text(encoding="utf-8").strip()
    assert sha256_file(COMMITTED / SEALED_PREDICTIONS_FILE) == recorded
    sealed = json.loads((COMMITTED / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    challenges = load_challenge_manifest(
        json.loads((COMMITTED / CHALLENGES_FILE).read_text(encoding="utf-8"))
    )
    assert sealed["challenge_manifest_hash"] == challenges["challenge_manifest_hash"]
    assert sealed["challenge_ids"] == list(challenges["evaluable_challenge_ids"])
    assert sealed["model_ids"] == list(SUITE_MODEL_IDS)
    # The criterion is a separate committed file with its own digest, and the
    # seal names the exact bytes it froze.
    criterion_recorded = (COMMITTED / CRITERION_HASH_FILE).read_text(encoding="utf-8").strip()
    assert sha256_file(COMMITTED / CRITERION_FILE) == criterion_recorded
    assert sealed["criterion_sha256"] == criterion_recorded


def test_the_committed_criterion_was_frozen_before_the_committed_score():
    """Thresholds are frozen, and the real-closure verdict stays NOT_YET_SCORED."""
    if not (COMMITTED / CRITERION_FILE).is_file():
        pytest.skip("EZ-B003-v1 is preregistered but not sealed in this checkout")
    from elementzero.benchmark.shell_metrics import rediscovery_criterion

    criterion = json.loads((COMMITTED / CRITERION_FILE).read_text(encoding="utf-8"))
    assert criterion["thresholds_frozen"] is True
    assert criterion["scored_scope"] == SCOPE
    assert criterion["evaluated_mass_table_verdict"] == "NOT_YET_SCORED"
    assert criterion["state"] == "THRESHOLDS_FROZEN_BEFORE_ANY_CLOSURE_TRUTH_READ"
    # The digest of the *live* criterion is what the score phase compares against,
    # because canonical JSON renders floats as fixed-precision strings and a
    # round-tripped payload never compares equal to the dict in code.
    assert criterion["criterion_digest"] == sha256_hex(rediscovery_criterion())
    if not (COMMITTED / AGGREGATE_FILE).is_file():
        pytest.skip("EZ-B003-v1 is sealed but not scored in this checkout")
    aggregate = json.loads((COMMITTED / AGGREGATE_FILE).read_text(encoding="utf-8"))
    # The thresholds published beside the numbers are the frozen ones.
    assert aggregate["criterion"] == criterion["criterion"]
    assert aggregate["real_closure_status"]["evaluated_mass_table_verdict"] == "NOT_YET_SCORED"
    # Every declared closure is still accounted for after scoring.
    assert aggregate["n_not_evaluable_closures"] == len(aggregate["not_evaluable_closures"])
    assert len(aggregate["challenge_ids"]) + aggregate["n_not_evaluable_closures"] == 9


def test_committed_seal_is_reproducible_from_the_committed_snapshot(tmp_path, monkeypatch):
    """Re-seal the committed closures and reproduce the committed digests.

    ``elementzero_commit`` is part of the freeze payload, so it is an input to
    ``freeze_id``. Pinning it to the value the committed run recorded is what
    makes this a reproducibility check rather than a "did the repo move" check.
    """
    if not (COMMITTED / SEALED_PREDICTIONS_FILE).is_file():
        pytest.skip("EZ-B003-v1 is preregistered but not sealed in this checkout")
    sealed = json.loads((COMMITTED / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    monkeypatch.setenv("ELEMENTZERO_COMMIT", sealed["elementzero_commit"])

    replay = seal_b003(
        source=COMMITTED_SNAPSHOT,
        edition_id=sealed["edition_id"],
        challenges_path=COMMITTED / CHALLENGES_FILE,
        experiment_dir=tmp_path / "replay",
        scope=sealed["scope"],
        profile=sealed["profile"],
        created_at=sealed["created_at"],
    )
    assert replay["sealed"]["challenge_manifest_hash"] == sealed["challenge_manifest_hash"]
    assert replay["sealed"]["raw_source_hash"] == sealed["raw_source_hash"]
    # The frozen thresholds are re-derived identically, so the criterion the
    # score phase verifies against is not an artifact of one machine.
    assert replay["sealed"]["criterion_sha256"] == sealed["criterion_sha256"]
    for committed_challenge, replayed_challenge in zip(
        sealed["challenges"], replay["sealed"]["challenges"], strict=True
    ):
        assert replayed_challenge["challenge_id"] == committed_challenge["challenge_id"]
        assert replayed_challenge["mask_hash"] == committed_challenge["mask_hash"]
        assert replayed_challenge["split_digest"] == committed_challenge["split_digest"]
        assert replayed_challenge["freeze_id"] == committed_challenge["freeze_id"]
        assert replayed_challenge["targets_sha256"] == committed_challenge["targets_sha256"]
        assert replayed_challenge["freeze_sha256"] == committed_challenge["freeze_sha256"]
        for committed_run, replayed_run in zip(
            committed_challenge["runs"], replayed_challenge["runs"], strict=True
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
    """Re-score the committed seal and reproduce every committed metric hash.

    This is the check that makes the committed CRITERION_NOT_MET verdict
    arguable: the discovery metrics behind it, including the rank of each
    withheld closure, come back identical from the sealed predictions.
    """
    if not (COMMITTED / AGGREGATE_FILE).is_file():
        pytest.skip("EZ-B003-v1 is sealed but not scored in this checkout")
    from elementzero.benchmark.b003_score import score_shell_run

    sealed = json.loads((COMMITTED / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    monkeypatch.setenv("ELEMENTZERO_COMMIT", sealed["elementzero_commit"])
    score_manifest = json.loads((COMMITTED / "SCORE_MANIFEST.json").read_text(encoding="utf-8"))
    recorded = {
        (challenge["challenge_id"], model["model_id"]): model["metrics_content_hash"]
        for challenge in score_manifest["challenges"]
        for model in challenge["models"]
    }
    assert recorded
    for challenge in sealed["challenges"]:
        for run in challenge["runs"]:
            report = score_shell_run(
                run_dir=COMMITTED / run["run_relpath"],
                truth_source=COMMITTED_SNAPSHOT,
                truth_edition_id=sealed["edition_id"],
                scope=score_manifest["scope"],
                out_dir=tmp_path / challenge["challenge_id"] / run["model_id"],
                created_at=score_manifest["created_at"],
            )
            key = (challenge["challenge_id"], run["model_id"])
            assert sha256_hex(report["metrics"]) == recorded[key], key


def test_the_committed_verdicts_are_the_ones_the_frozen_criterion_gives():
    """The published verdict is re-derived from the published numbers.

    Every EZ-B003-v1 baseline fails, and the aggregate has to say *which*
    threshold each one missed rather than only that it missed. Recomputing the
    verdict from the recorded fractions is what keeps the negative result from
    being an unfalsifiable label.
    """
    if not (COMMITTED / AGGREGATE_FILE).is_file():
        pytest.skip("EZ-B003-v1 is sealed but not scored in this checkout")
    aggregate = json.loads((COMMITTED / AGGREGATE_FILE).read_text(encoding="utf-8"))
    comparisons = {">=": float.__ge__, "<=": float.__le__}
    for model_id, entry in aggregate["by_model"].items():
        criterion = entry["criterion"]
        checks = criterion["checks"]
        # Every threshold is named, with the observed value beside it, so a
        # reader can see which one failed instead of taking the verdict on faith.
        assert set(checks) == {
            "sign_fraction",
            "top_k_fraction",
            "rank_1_fraction",
            "calibration_error_90",
        }
        for name, check in checks.items():
            compare = comparisons[check["comparison"]]
            assert check["met"] is compare(
                float(check["observed"]), float(check["threshold"])
            ), f"{model_id}/{name}"
        expected = "CRITERION_MET" if all(c["met"] for c in checks.values()) else "CRITERION_NOT_MET"
        assert criterion["verdict"] == expected, model_id
