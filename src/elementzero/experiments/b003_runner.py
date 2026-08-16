"""Run and seal one EZ-B003 hidden-shell rediscovery experiment (WO-10).

Three acts, in this order, each committed before the next begins:

    select_challenges_for_source(...)  apply the preregistered availability rule
                                       and support rule to one snapshot, and
                                       write challenges.json. Every declared
                                       closure appears, EVALUABLE or not.
    seal_b003(...)                     read the committed challenges.json, build
                                       one split and one freeze per evaluable
                                       closure, predict with the frozen
                                       three-model suite, finalize every run,
                                       and write the frozen criterion
    score_b003(...)                    score every sealed run, compare models
                                       inside each closure, and aggregate

Layout under ``<experiment_dir>``::

    challenges.json                    preregistered challenge manifest (input)
    CHALLENGES_SHA256                  hash of the challenge manifest file
    CRITERION.json / CRITERION_SHA256  frozen rediscovery thresholds
    data_audit/<edition>_parse_report.json
    environment.json
    challenges/<challenge_id>/split_manifest.json
    challenges/<challenge_id>/targets.json      identity-only
    challenges/<challenge_id>/support.json      per-chain support record
    challenges/<challenge_id>/freeze.json       KnowledgeFreeze + shell split
    challenges/<challenge_id>/runs/<model_id>/...
    challenges/<challenge_id>/challenge_comparison.json/.md
    SEALED_PREDICTIONS.json + SEALED_PREDICTIONS_SHA256
    RUN_MANIFEST.json / SCORE_MANIFEST.json
    shell_aggregate.json/.md
    SHA256SUMS.txt

``CRITERION.json`` is written by the *seal* phase, not the score phase. That
ordering is the whole point of WO-10 section 9: the thresholds are on disk, and
hashed, before any withheld closure truth has been read.

Challenge selection is a separate, earlier act because the masks must be frozen
and committed before any model is scored. This runner refuses to invent one.
"""

from __future__ import annotations

import json
import platform
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero import (
    B003_PROTOCOL_VERSION,
    BENCHMARK_EZ_B003,
    BENCHMARK_PROTOCOL_VERSION,
    __version__,
)
from elementzero.atlas_pin import REPO_ROOT, atlas_pir_ref
from elementzero.benchmark.b003_freeze import freeze_shell_split, load_shell_freeze
from elementzero.benchmark.b003_predict import (
    SUITE_MANIFEST_NAME,
    load_shell_targets,
    run_shell_suite,
)
from elementzero.benchmark.b003_prepare import (
    PROFILE_DISCOVERY,
    PROFILE_SEPARATION_RULE,
    SHELL_SPLIT_POLICY_ID,
    SPLIT_DIGEST_RULE,
    SPLIT_MANIFEST_FILE,
    SUPPORT_FILE,
    TARGETS_FILE,
    eligible_points,
    feature_policy_hash,
    feature_policy_payload,
    prepare_shell_split,
)
from elementzero.benchmark.b003_score import (
    BOUNDARY_RULE,
    CHALLENGE_COMPARISON_JSON,
    SCOPE_SYNTHETIC,
    SHELL_AGGREGATE_JSON,
    real_closure_status,
    score_shell_suite,
    write_shell_aggregate,
)
from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
from elementzero.benchmark.shell_masks import (
    CHALLENGE_POLICY_ID,
    KNOWN_NEUTRON_CLOSURES,
    KNOWN_PROTON_CLOSURES,
    MASK_POLICY_ID,
    SUPPORT_POLICY_ID,
    challenge_manifest,
    generate_challenges,
    load_challenge_manifest,
)
from elementzero.benchmark.shell_metrics import (
    CRITERION_SCOPE_RULE,
    REDISCOVERY_CRITERION_ID,
    rediscovery_criterion,
)
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.observations import GROUND_TRUTH_POLICY
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import finalization_marker_hash, read_json
from elementzero.experiments.runner import certify_source, parse_report_name, write_sha256sums
from elementzero.identity_meta import elementzero_commit, runtime_library_versions
from elementzero.physics.separation import separation_policy

CHALLENGES_FILE = "challenges.json"
CHALLENGES_HASH_FILE = "CHALLENGES_SHA256"
CRITERION_FILE = "CRITERION.json"
CRITERION_HASH_FILE = "CRITERION_SHA256"
CHALLENGES_DIRNAME = "challenges"
RUNS_DIRNAME = "runs"
SCORING_DIRNAME = "scoring"
DATA_AUDIT_DIRNAME = "data_audit"
ENVIRONMENT_FILE = "environment.json"
RUN_MANIFEST_FILE = "RUN_MANIFEST.json"
SCORE_MANIFEST_FILE = "SCORE_MANIFEST.json"
SEALED_PREDICTIONS_FILE = "SEALED_PREDICTIONS.json"
SEALED_PREDICTIONS_HASH_FILE = "SEALED_PREDICTIONS_SHA256"

STOP_CONDITIONS = (
    "a known closure label reaching a discovery-model feature",
    "target truth used to tune hyperparameters",
    "a threshold selected after real scoring",
    "successful mass interpolation described as proof of a new island of stability",
    "masks changed after seeing performance",
    "a NOT_EVALUABLE closure silently omitted",
    "a sealed run refit",
)


# --------------------------------------------------------------------------- #
# Challenge selection (must happen before any scoring)                        #
# --------------------------------------------------------------------------- #


def select_challenges_for_source(
    *,
    source: str | Path,
    edition_id: str,
    output: str | Path | None = None,
    source_relpath: str | None = None,
    neutron_closures: Sequence[int] = KNOWN_NEUTRON_CLOSURES,
    proton_closures: Sequence[int] = KNOWN_PROTON_CLOSURES,
    notes: str | None = None,
) -> dict[str, Any]:
    """Apply the availability and support rules to one snapshot; write challenges.json.

    The availability set is declared, not chosen: it is the textbook closure list
    of ``shell_masks``. Which of its members is produced is decided by the support
    rule alone, never by how well a model does on them.
    """
    source = Path(source)
    points = eligible_points(source, edition_id)
    generated = generate_challenges(
        points, neutron_closures=neutron_closures, proton_closures=proton_closures
    )
    manifest = challenge_manifest(
        generated["challenges"],
        benchmark_id=BENCHMARK_EZ_B003,
        protocol_version=B003_PROTOCOL_VERSION,
        settings=generated["settings"],
        source={
            "edition_id": edition_id,
            "raw_relpath": source_relpath or source.name,
            "raw_filename": source.name,
            "raw_sha256": sha256_file(source),
            "ground_truth_policy": GROUND_TRUTH_POLICY,
            "parser_version": PARSER_VERSION,
            "n_eligible": generated["n_eligible_points"],
        },
        notes=notes,
    )
    if output is not None:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return {"manifest": manifest, "generated": generated}


def read_challenges(path: str | Path) -> dict[str, Any]:
    """Load and verify a preregistered challenge manifest file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    parsed = load_challenge_manifest(payload)
    if payload.get("benchmark_id") != BENCHMARK_EZ_B003:
        raise ProtocolError(
            f"challenge manifest declares benchmark {payload.get('benchmark_id')!r}, "
            f"not {BENCHMARK_EZ_B003}"
        )
    return {**parsed, "payload": payload, "path": str(path)}


def criterion_payload(*, scope: str) -> dict[str, Any]:
    """The frozen rediscovery criterion, written before any truth is read."""
    return {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": B003_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "criterion_id": REDISCOVERY_CRITERION_ID,
        "state": "THRESHOLDS_FROZEN_BEFORE_ANY_CLOSURE_TRUTH_READ",
        # Digest rather than a dict comparison: canonical JSON renders floats as
        # fixed-precision strings, so a round-tripped payload never compares equal
        # to the live one. The digest is what the score phase re-derives.
        "criterion_digest": sha256_hex(rediscovery_criterion()),
        **real_closure_status(scope=scope),
    }


# --------------------------------------------------------------------------- #
# Seal phase                                                                  #
# --------------------------------------------------------------------------- #


def environment_report(
    *, challenge_manifest_sha256: str, created_at: str, profile: str
) -> dict[str, Any]:
    policy = feature_policy_payload(profile=profile)
    return {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": B003_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "challenge_manifest_sha256": challenge_manifest_sha256,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "library_versions": runtime_library_versions(),
        "elementzero_version": __version__,
        "elementzero_commit": elementzero_commit(),
        "atlas_pir_ref": atlas_pir_ref(),
        "parser_version": PARSER_VERSION,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "profile": profile,
        "feature_policy_id": policy["feature_policy_id"],
        "feature_policy_hash": feature_policy_hash(profile=profile),
        "features": list(policy["features"]),
        "firewall": policy["firewall"],
        "separation_policy": separation_policy(),
        "created_at": created_at,
    }


def seal_b003(
    *,
    source: str | Path,
    edition_id: str,
    challenges_path: str | Path,
    experiment_dir: str | Path,
    scope: str = SCOPE_SYNTHETIC,
    profile: str = PROFILE_DISCOVERY,
    created_at: str | None = None,
    model_ids: Sequence[str] = SUITE_MODEL_IDS,
    min_targets: int = 1,
) -> dict[str, Any]:
    """Split, freeze, predict, and seal every evaluable closure."""
    source = Path(source)
    experiment_dir = Path(experiment_dir)
    challenges_path = Path(challenges_path)
    challenges = read_challenges(challenges_path)
    manifest_hash = challenges["challenge_manifest_hash"]
    declared_source = (challenges["source"] or {}).get("raw_sha256")
    source_hash = sha256_file(source)
    if declared_source is not None and declared_source != source_hash:
        raise ProtocolError(
            "snapshot hash differs from the one the challenges were selected on: "
            f"{source_hash} is not {declared_source}"
        )
    if not challenges["evaluable_challenge_ids"]:
        raise ProtocolError(
            f"{challenges_path} declares no EVALUABLE closure; there is nothing to seal"
        )

    root = experiment_dir / CHALLENGES_DIRNAME
    if root.exists() and any(root.iterdir()):
        raise ProtocolError(
            f"{root} already holds sealed runs; a rerun must use a new experiment "
            "directory or a new protocol version, never an overwrite"
        )
    experiment_dir.mkdir(parents=True, exist_ok=True)

    audit_dir = experiment_dir / DATA_AUDIT_DIRNAME
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit = certify_source(edition_id=edition_id, path=source, expected_sha256=source_hash)
    (audit_dir / parse_report_name(edition_id)).write_text(
        canonical_json(audit) + "\n", encoding="utf-8"
    )

    if challenges_path.resolve() != (experiment_dir / CHALLENGES_FILE).resolve():
        (experiment_dir / CHALLENGES_FILE).write_text(
            canonical_json(challenges["payload"]) + "\n", encoding="utf-8"
        )
    challenges_file_hash = sha256_file(experiment_dir / CHALLENGES_FILE)
    (experiment_dir / CHALLENGES_HASH_FILE).write_text(
        challenges_file_hash + "\n", encoding="utf-8"
    )

    # WO-10 section 9: the thresholds land on disk, hashed, before the first
    # withheld closure truth is read.
    criterion = criterion_payload(scope=scope)
    (experiment_dir / CRITERION_FILE).write_text(
        canonical_json(criterion) + "\n", encoding="utf-8"
    )
    criterion_file_hash = sha256_file(experiment_dir / CRITERION_FILE)
    (experiment_dir / CRITERION_HASH_FILE).write_text(
        criterion_file_hash + "\n", encoding="utf-8"
    )

    sealed_challenges = []
    for challenge in challenges["challenges"]:
        if challenge["status"] != "EVALUABLE":
            continue
        challenge_id = challenge["challenge_id"]
        mask = challenges["masks"][challenge_id]
        cdir = root / challenge_id
        split = prepare_shell_split(
            source=source,
            edition_id=edition_id,
            mask=mask,
            challenge_manifest_hash=manifest_hash,
            out_dir=cdir,
            min_targets=min_targets,
            profile=profile,
        )
        freeze_shell_split(
            source=source,
            edition_id=edition_id,
            split_manifest=cdir / SPLIT_MANIFEST_FILE,
            output=cdir / "freeze.json",
        )
        # Re-read both artifacts through their validating loaders: what is on
        # disk is what the prediction stage will consume.
        targets = load_shell_targets(cdir / TARGETS_FILE)
        shell = load_shell_freeze(cdir / "freeze.json")
        suite = run_shell_suite(
            shell_freeze=shell,
            targets=targets,
            source=source,
            edition_id=edition_id,
            suite_dir=cdir / RUNS_DIRNAME,
            model_ids=model_ids,
            created_at=created_at,
        )
        _normalize_suite_paths(cdir / RUNS_DIRNAME)
        sealed_challenges.append(
            {
                "challenge_id": challenge_id,
                "axis": mask.axis,
                "closure": mask.closure,
                "indicator": mask.indicator,
                "mask": mask.to_dict(),
                "mask_id": mask.mask_id,
                "mask_hash": shell.mask_hash,
                "challenge_relpath": f"{CHALLENGES_DIRNAME}/{challenge_id}",
                "profile": shell.profile,
                "split_id": split["split_manifest"]["split_id"],
                "split_digest": split["split_manifest"]["split_digest"],
                "freeze_id": shell.freeze_id,
                "n_targets": split["split_manifest"]["n_targets"],
                "n_training": split["split_manifest"]["n_training"],
                "supported_chains": list(shell.supported_chains),
                "unsupported_chains": list(shell.unsupported_chains),
                "targets_sha256": sha256_file(cdir / TARGETS_FILE),
                "split_manifest_sha256": sha256_file(cdir / SPLIT_MANIFEST_FILE),
                "support_sha256": sha256_file(cdir / SUPPORT_FILE),
                "freeze_sha256": sha256_file(cdir / "freeze.json"),
                "runs": [
                    {
                        "model_id": run["model_id"],
                        "run_relpath": (
                            f"{CHALLENGES_DIRNAME}/{challenge_id}/{RUNS_DIRNAME}/{run['model_id']}"
                        ),
                        "model_manifest_hash": run["model_manifest_hash"],
                        "prediction_set_fact_id": run["prediction_set_fact_id"],
                        "shell_hypothesis_fact_id": run["shell_hypothesis_fact_id"],
                        "finalization_marker_hash": run["finalization_marker_hash"],
                    }
                    for run in suite["runs"]
                ],
            }
        )

    sealed = {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": B003_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "scope": scope,
        "profile": profile,
        "edition_id": edition_id,
        "raw_source_hash": source_hash,
        "challenge_manifest_hash": manifest_hash,
        "challenge_manifest_sha256": challenges_file_hash,
        "criterion_id": REDISCOVERY_CRITERION_ID,
        "criterion_sha256": criterion_file_hash,
        "challenge_ids": list(challenges["evaluable_challenge_ids"]),
        "not_evaluable_challenge_ids": list(challenges["not_evaluable_challenge_ids"]),
        "not_evaluable": [
            {
                "challenge_id": c["challenge_id"],
                "axis": c["axis"],
                "closure": c["closure"],
                "status": c["status"],
                "reasons": list(c.get("reasons", [])),
            }
            for c in challenges["challenges"]
            if c["status"] != "EVALUABLE"
        ],
        "model_ids": list(model_ids),
        "split_policy_id": SHELL_SPLIT_POLICY_ID,
        "split_digest_rule": SPLIT_DIGEST_RULE,
        "challenge_policy_id": CHALLENGE_POLICY_ID,
        "mask_policy_id": MASK_POLICY_ID,
        "support_policy_id": SUPPORT_POLICY_ID,
        "feature_policy_id": feature_policy_payload(profile=profile)["feature_policy_id"],
        "feature_policy_hash": feature_policy_hash(profile=profile),
        "challenges": sealed_challenges,
        "created_at": created_at,
        "atlas_pir_ref": atlas_pir_ref(),
        "elementzero_commit": elementzero_commit(),
        "state": "PREDICTIONS_SEALED_CLOSURE_TRUTH_UNREAD",
        "boundary_rule": BOUNDARY_RULE,
        "profile_separation_rule": PROFILE_SEPARATION_RULE,
    }
    (experiment_dir / SEALED_PREDICTIONS_FILE).write_text(
        canonical_json(sealed) + "\n", encoding="utf-8"
    )
    sealed_hash = sha256_file(experiment_dir / SEALED_PREDICTIONS_FILE)
    (experiment_dir / SEALED_PREDICTIONS_HASH_FILE).write_text(
        sealed_hash + "\n", encoding="utf-8"
    )
    environment = environment_report(
        challenge_manifest_sha256=challenges_file_hash,
        created_at=created_at or "unpinned",
        profile=profile,
    )
    (experiment_dir / ENVIRONMENT_FILE).write_text(
        canonical_json(environment) + "\n", encoding="utf-8"
    )
    run_manifest = {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": B003_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "stage": "sealed",
        "scope": scope,
        "profile": profile,
        "edition_id": edition_id,
        "raw_source_hash": source_hash,
        "data_audit": {
            "report": f"{DATA_AUDIT_DIRNAME}/{parse_report_name(edition_id)}",
            "parsed_records": audit["parsed_records"],
            "eligible_records": audit["eligible_records"],
            "estimated_records": audit["estimated_records"],
            "malformed_fraction": audit["malformed_fraction"],
        },
        "challenge_manifest_hash": manifest_hash,
        "challenge_manifest_sha256": challenges_file_hash,
        "criterion": {
            "file": CRITERION_FILE,
            "sha256": criterion_file_hash,
            "criterion_id": REDISCOVERY_CRITERION_ID,
            "state": criterion["state"],
        },
        "challenges": [
            {
                "challenge_id": entry["challenge_id"],
                "axis": entry["axis"],
                "closure": entry["closure"],
                "indicator": entry["indicator"],
                "mask_id": entry["mask_id"],
                "n_targets": entry["n_targets"],
                "n_training": entry["n_training"],
                "n_supported_chains": len(entry["supported_chains"]),
                "freeze_id": entry["freeze_id"],
                "split_digest": entry["split_digest"],
            }
            for entry in sealed_challenges
        ],
        "not_evaluable": sealed["not_evaluable"],
        "model_ids": list(model_ids),
        "sealed_predictions": {
            "file": SEALED_PREDICTIONS_FILE,
            "sha256": sealed_hash,
            "state": sealed["state"],
        },
        "boundary_rule": BOUNDARY_RULE,
        "scope_rule": CRITERION_SCOPE_RULE,
        "stop_conditions": list(STOP_CONDITIONS),
        "environment": environment,
    }
    (experiment_dir / RUN_MANIFEST_FILE).write_text(
        canonical_json(run_manifest) + "\n", encoding="utf-8"
    )
    write_sha256sums(experiment_dir)
    return {
        "experiment_dir": str(experiment_dir),
        "sealed": sealed,
        "run_manifest": run_manifest,
        "criterion": criterion,
        "sealed_predictions_sha256": sealed_hash,
        "challenge_ids": sealed["challenge_ids"],
    }


def _normalize_suite_paths(runs_dir: Path) -> dict[str, Any]:
    """Store experiment-relative run paths; absolute paths are machine layout."""
    path = runs_dir / SUITE_MANIFEST_NAME
    suite = read_json(path)
    suite["suite_dir"] = runs_dir.name
    for run in suite["runs"]:
        run["run_dir"] = f"{runs_dir.name}/{Path(run['run_dir']).name}"
    path.write_text(canonical_json(suite) + "\n", encoding="utf-8")
    return suite


# --------------------------------------------------------------------------- #
# Score phase                                                                 #
# --------------------------------------------------------------------------- #


def score_b003(
    *,
    source: str | Path,
    edition_id: str,
    experiment_dir: str | Path,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Score every sealed closure, compare models, and aggregate all closures."""
    source = Path(source)
    experiment_dir = Path(experiment_dir)
    sealed_path = experiment_dir / SEALED_PREDICTIONS_FILE
    if not sealed_path.is_file():
        raise ProtocolError("predictions were never sealed; scoring is refused")
    sealed = read_json(sealed_path)
    recorded = (experiment_dir / SEALED_PREDICTIONS_HASH_FILE).read_text(encoding="utf-8").strip()
    if sha256_file(sealed_path) != recorded:
        raise ProtocolError(
            f"{SEALED_PREDICTIONS_FILE} does not match {SEALED_PREDICTIONS_HASH_FILE}"
        )
    criterion_path = experiment_dir / CRITERION_FILE
    if not criterion_path.is_file():
        raise ProtocolError(
            "the frozen criterion is absent; thresholds must be committed before scoring"
        )
    criterion_recorded = (experiment_dir / CRITERION_HASH_FILE).read_text(encoding="utf-8").strip()
    if sha256_file(criterion_path) != criterion_recorded:
        raise ProtocolError(f"{CRITERION_FILE} does not match {CRITERION_HASH_FILE}")
    if criterion_recorded != sealed["criterion_sha256"]:
        raise ProtocolError(
            "the committed criterion is not the one that was frozen at seal time; "
            "a threshold change requires a new protocol version and a full rerun"
        )
    frozen_criterion = read_json(criterion_path)
    if frozen_criterion["criterion_digest"] != sha256_hex(rediscovery_criterion()):
        raise ProtocolError(
            "the frozen criterion on disk differs from the criterion in code; a "
            "threshold selected after scoring is a stop condition, not a result"
        )
    if frozen_criterion["criterion_id"] != REDISCOVERY_CRITERION_ID:
        raise ProtocolError(
            f"the frozen criterion is {frozen_criterion['criterion_id']!r}, "
            f"not {REDISCOVERY_CRITERION_ID!r}"
        )
    source_hash = sha256_file(source)
    if source_hash != sealed["raw_source_hash"]:
        raise ProtocolError("scoring snapshot differs from the sealed snapshot")
    if edition_id != sealed["edition_id"]:
        raise ProtocolError(
            f"scoring edition {edition_id!r} differs from the sealed {sealed['edition_id']!r}"
        )
    challenges = read_challenges(experiment_dir / CHALLENGES_FILE)
    if challenges["challenge_manifest_hash"] != sealed["challenge_manifest_hash"]:
        raise ProtocolError(
            "committed challenges.json is not the challenge set that was sealed"
        )

    scope = sealed["scope"]
    reports = []
    for entry in sealed["challenges"]:
        cdir = experiment_dir / entry["challenge_relpath"]
        for run in entry["runs"]:
            run_dir = experiment_dir / run["run_relpath"]
            if finalization_marker_hash(run_dir) != run["finalization_marker_hash"]:
                raise LeakageError(
                    f"finalization marker of {entry['challenge_id']}/{run['model_id']} "
                    "changed after the seal"
                )
        comparison = score_shell_suite(
            suite_dir=cdir / RUNS_DIRNAME,
            truth_source=source,
            truth_edition_id=edition_id,
            scope=scope,
            out_dir=cdir,
            created_at=created_at,
        )
        if comparison["challenge_id"] != entry["challenge_id"]:
            raise ProtocolError("scored comparison does not match the sealed closure")
        for run in entry["runs"]:
            reports.append(
                read_json(
                    experiment_dir / run["run_relpath"] / SCORING_DIRNAME / "score_report.json"
                )
            )

    aggregate = write_shell_aggregate(
        out_dir=experiment_dir,
        reports=reports,
        challenge_ids=sealed["challenge_ids"],
        model_ids=sealed["model_ids"],
        challenge_manifest_hash=sealed["challenge_manifest_hash"],
        scope=scope,
        not_evaluable=sealed["not_evaluable"],
    )
    score_manifest = {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": B003_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "stage": "scored",
        "scope": scope,
        "profile": sealed["profile"],
        "edition_id": edition_id,
        "raw_source_hash": source_hash,
        "truth_source_hash": source_hash,
        "truth_source_note": (
            "EZ-B003 has one frozen snapshot: the training corpus is the eligible "
            "nuclei outside each closure neighborhood and the truth is the eligible "
            "nuclei inside it. The holdout is geometric, so the truth hash equals the "
            "training hash by construction."
        ),
        "challenge_manifest_hash": sealed["challenge_manifest_hash"],
        "sealed_predictions_sha256": recorded,
        "criterion_sha256": criterion_recorded,
        "criterion_id": REDISCOVERY_CRITERION_ID,
        "challenge_ids": list(sealed["challenge_ids"]),
        "not_evaluable_challenge_ids": list(sealed["not_evaluable_challenge_ids"]),
        "model_ids": list(sealed["model_ids"]),
        "created_at": created_at,
        "atlas_pir_ref": atlas_pir_ref(),
        "elementzero_commit": elementzero_commit(),
        "challenges": [
            {
                "challenge_id": entry["challenge_id"],
                "comparison_relpath": f"{entry['challenge_relpath']}/{CHALLENGE_COMPARISON_JSON}",
                "comparison_sha256": sha256_file(
                    experiment_dir / entry["challenge_relpath"] / CHALLENGE_COMPARISON_JSON
                ),
                "models": [
                    {
                        "model_id": run["model_id"],
                        "scoring_relpath": f"{run['run_relpath']}/{SCORING_DIRNAME}",
                        "metrics_sha256": sha256_file(
                            experiment_dir / run["run_relpath"] / SCORING_DIRNAME / "metrics.json"
                        ),
                        "metrics_content_hash": sha256_hex(
                            read_json(
                                experiment_dir
                                / run["run_relpath"]
                                / SCORING_DIRNAME
                                / "metrics.json"
                            )
                        ),
                    }
                    for run in entry["runs"]
                ],
            }
            for entry in sealed["challenges"]
        ],
        "aggregate": {
            "file": SHELL_AGGREGATE_JSON,
            "sha256": sha256_file(experiment_dir / SHELL_AGGREGATE_JSON),
            "n_scored_targets": aggregate["n_scored_targets"],
            "verdicts": {
                model_id: aggregate["by_model"][model_id]["criterion"]["verdict"]
                for model_id in aggregate["model_ids"]
            },
        },
        "real_closure_status": aggregate["real_closure_status"],
        "boundary_rule": BOUNDARY_RULE,
        "scope_rule": CRITERION_SCOPE_RULE,
    }
    (experiment_dir / SCORE_MANIFEST_FILE).write_text(
        canonical_json(score_manifest) + "\n", encoding="utf-8"
    )
    write_sha256sums(experiment_dir)
    return {
        "experiment_dir": str(experiment_dir),
        "score_manifest": score_manifest,
        "aggregate": aggregate,
        "reports": reports,
    }


def run_b003(
    *,
    source: str | Path,
    edition_id: str,
    challenges_path: str | Path,
    experiment_dir: str | Path,
    scope: str = SCOPE_SYNTHETIC,
    profile: str = PROFILE_DISCOVERY,
    created_at: str | None = None,
    model_ids: Sequence[str] = SUITE_MODEL_IDS,
    min_targets: int = 1,
) -> dict[str, Any]:
    """Seal, then score. Convenience wrapper; the two phases stay separable."""
    sealed = seal_b003(
        source=source,
        edition_id=edition_id,
        challenges_path=challenges_path,
        experiment_dir=experiment_dir,
        scope=scope,
        profile=profile,
        created_at=created_at,
        model_ids=model_ids,
        min_targets=min_targets,
    )
    scored = score_b003(
        source=source,
        edition_id=edition_id,
        experiment_dir=experiment_dir,
        created_at=created_at,
    )
    return {"sealed": sealed, "scored": scored}


def default_experiment_dir(experiment_id: str, *, root: str | Path | None = None) -> Path:
    return Path(root or REPO_ROOT) / "experiments" / experiment_id
