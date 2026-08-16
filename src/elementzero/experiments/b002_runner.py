"""Run and seal one EZ-B002 geographic-holdout experiment (WO-09).

Two commands, in this order, with the seal committed in between:

    seal_b002(...)     select nothing, read the preregistered regions.json, build
                       one split and one freeze per region, predict with the
                       frozen three-model suite, finalize every run
    score_b002(...)    score every sealed run against the frozen snapshot,
                       compare the models inside each region, and aggregate over
                       every region

Layout under ``<experiment_dir>``::

    regions.json                       preregistered region manifest (input)
    REGIONS_SHA256                     hash of the region manifest file
    data_audit/<edition>_parse_report.json
    environment.json
    regions/<region_id>/split_manifest.json
    regions/<region_id>/targets.json   identity-only
    regions/<region_id>/freeze.json    KnowledgeFreeze + geographic split
    regions/<region_id>/runs/<model_id>/...
    regions/<region_id>/region_comparison.json/.md
    SEALED_PREDICTIONS.json + SEALED_PREDICTIONS_SHA256
    RUN_MANIFEST.json / SCORE_MANIFEST.json
    region_aggregate.json/.md
    SHA256SUMS.txt

Region selection is a separate, earlier act (``select_regions_for_source``): the
manifest must be frozen and committed before any model is scored, and this
runner refuses to invent one.
"""

from __future__ import annotations

import json
import platform
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero import (
    B002_PROTOCOL_VERSION,
    BENCHMARK_EZ_B002,
    BENCHMARK_PROTOCOL_VERSION,
    __version__,
)
from elementzero.atlas_pin import REPO_ROOT, atlas_pir_ref
from elementzero.benchmark.b002_freeze import freeze_geographic_split, load_geographic_freeze
from elementzero.benchmark.b002_predict import (
    SUITE_MANIFEST_NAME,
    load_region_targets,
    run_region_suite,
)
from elementzero.benchmark.b002_prepare import (
    FEATURE_POLICY_EZ_B002,
    GEOGRAPHIC_SPLIT_POLICY_ID,
    SPLIT_DIGEST_RULE,
    SPLIT_MANIFEST_FILE,
    TARGETS_FILE,
    eligible_points,
    feature_policy_hash,
    prepare_geographic_split,
)
from elementzero.benchmark.b002_score import (
    NO_THRESHOLD_RULE,
    REGION_AGGREGATE_JSON,
    REGION_COMPARISON_JSON,
    score_region_suite,
    write_region_aggregate,
)
from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
from elementzero.benchmark.regions import (
    DEFAULT_MIN_SUPPORTED_SIDES,
    DEFAULT_MIN_TARGETS,
    DEFAULT_N_SPAN,
    DEFAULT_REGIONS_PER_BAND,
    DEFAULT_Z_SPAN,
    SELECTION_Z_BANDS,
    generate_regions,
    load_region_manifest,
    region_manifest,
)
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.observations import GROUND_TRUTH_POLICY
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import finalization_marker_hash, read_json
from elementzero.experiments.runner import certify_source, parse_report_name, write_sha256sums
from elementzero.identity_meta import elementzero_commit, runtime_library_versions

REGIONS_FILE = "regions.json"
REGIONS_HASH_FILE = "REGIONS_SHA256"
CANDIDATES_FILE = "region_candidates.json"
REGIONS_DIRNAME = "regions"
RUNS_DIRNAME = "runs"
SCORING_DIRNAME = "scoring"
DATA_AUDIT_DIRNAME = "data_audit"
ENVIRONMENT_FILE = "environment.json"
RUN_MANIFEST_FILE = "RUN_MANIFEST.json"
SCORE_MANIFEST_FILE = "SCORE_MANIFEST.json"
SEALED_PREDICTIONS_FILE = "SEALED_PREDICTIONS.json"
SEALED_PREDICTIONS_HASH_FILE = "SEALED_PREDICTIONS_SHA256"

STOP_CONDITIONS = (
    "regions changed after seeing performance",
    "only easy regions retained",
    "target values entering normalization statistics",
    "hyperparameters tuned against hidden-region truth",
    "a sealed run refit",
)


# --------------------------------------------------------------------------- #
# Region selection (must happen before any scoring)                           #
# --------------------------------------------------------------------------- #


def select_regions_for_source(
    *,
    source: str | Path,
    edition_id: str,
    output: str | Path | None = None,
    candidates_output: str | Path | None = None,
    source_relpath: str | None = None,
    z_span: int = DEFAULT_Z_SPAN,
    n_span: int = DEFAULT_N_SPAN,
    min_targets: int = DEFAULT_MIN_TARGETS,
    min_supported_sides: int = DEFAULT_MIN_SUPPORTED_SIDES,
    per_band: int = DEFAULT_REGIONS_PER_BAND,
    bands: Sequence[str] = SELECTION_Z_BANDS,
    allow_missing_bands: bool = False,
    notes: str | None = None,
) -> dict[str, Any]:
    """Deterministically select regions from one snapshot and write regions.json."""
    source = Path(source)
    points = eligible_points(source, edition_id)
    generated = generate_regions(
        points,
        z_span=z_span,
        n_span=n_span,
        min_targets=min_targets,
        min_supported_sides=min_supported_sides,
        per_band=per_band,
        bands=bands,
        allow_missing_bands=allow_missing_bands,
    )
    manifest = region_manifest(
        generated["selected"],
        benchmark_id=BENCHMARK_EZ_B002,
        protocol_version=B002_PROTOCOL_VERSION,
        source={
            "edition_id": edition_id,
            "raw_relpath": source_relpath or source.name,
            "raw_filename": source.name,
            "raw_sha256": sha256_file(source),
            "ground_truth_policy": GROUND_TRUTH_POLICY,
            "parser_version": PARSER_VERSION,
            "n_eligible": generated["n_eligible_points"],
        },
        generator={**generated["settings"], "n_candidates": generated["n_candidates"]},
        notes=notes,
    )
    if output is not None:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    if candidates_output is not None:
        Path(candidates_output).parent.mkdir(parents=True, exist_ok=True)
        # The full candidate list is committed next to the selection so a reader
        # can check that the retained regions are the deterministic top of the
        # order, not a hand-picked subset.
        Path(candidates_output).write_text(
            canonical_json(
                {
                    "benchmark_id": BENCHMARK_EZ_B002,
                    "protocol_version": B002_PROTOCOL_VERSION,
                    "settings": generated["settings"],
                    "n_eligible_points": generated["n_eligible_points"],
                    "n_candidates": generated["n_candidates"],
                    "candidates": generated["candidates"],
                    "selected_region_ids": manifest["region_ids"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
    return {"manifest": manifest, "generated": generated}


def read_regions(path: str | Path) -> dict[str, Any]:
    """Load and verify a preregistered region manifest file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    parsed = load_region_manifest(payload)
    if payload.get("benchmark_id") != BENCHMARK_EZ_B002:
        raise ProtocolError(
            f"region manifest declares benchmark {payload.get('benchmark_id')!r}, "
            f"not {BENCHMARK_EZ_B002}"
        )
    return {**parsed, "payload": payload, "path": str(path)}


# --------------------------------------------------------------------------- #
# Seal phase                                                                  #
# --------------------------------------------------------------------------- #


def environment_report(*, region_manifest_sha256: str, created_at: str) -> dict[str, Any]:
    return {
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": B002_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "region_manifest_sha256": region_manifest_sha256,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "library_versions": runtime_library_versions(),
        "elementzero_version": __version__,
        "elementzero_commit": elementzero_commit(),
        "atlas_pir_ref": atlas_pir_ref(),
        "parser_version": PARSER_VERSION,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "feature_policy_id": FEATURE_POLICY_EZ_B002,
        "feature_policy_hash": feature_policy_hash(),
        "created_at": created_at,
    }


def seal_b002(
    *,
    source: str | Path,
    edition_id: str,
    regions_path: str | Path,
    experiment_dir: str | Path,
    created_at: str | None = None,
    model_ids: Sequence[str] = SUITE_MODEL_IDS,
    min_targets: int = 1,
) -> dict[str, Any]:
    """Split, freeze, predict, and seal every preregistered region."""
    source = Path(source)
    experiment_dir = Path(experiment_dir)
    regions_path = Path(regions_path)
    regions = read_regions(regions_path)
    manifest_hash = regions["region_manifest_hash"]
    declared_source = (regions["source"] or {}).get("raw_sha256")
    source_hash = sha256_file(source)
    if declared_source is not None and declared_source != source_hash:
        raise ProtocolError(
            "snapshot hash differs from the one the regions were selected on: "
            f"{source_hash} is not {declared_source}"
        )

    regions_root = experiment_dir / REGIONS_DIRNAME
    if regions_root.exists() and any(regions_root.iterdir()):
        raise ProtocolError(
            f"{regions_root} already holds sealed runs; a rerun must use a new experiment "
            "directory or a new protocol version, never an overwrite"
        )
    experiment_dir.mkdir(parents=True, exist_ok=True)

    audit_dir = experiment_dir / DATA_AUDIT_DIRNAME
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit = certify_source(edition_id=edition_id, path=source, expected_sha256=source_hash)
    (audit_dir / parse_report_name(edition_id)).write_text(
        canonical_json(audit) + "\n", encoding="utf-8"
    )

    if regions_path.resolve() != (experiment_dir / REGIONS_FILE).resolve():
        (experiment_dir / REGIONS_FILE).write_text(
            canonical_json(regions["payload"]) + "\n", encoding="utf-8"
        )
    regions_file_hash = sha256_file(experiment_dir / REGIONS_FILE)
    (experiment_dir / REGIONS_HASH_FILE).write_text(regions_file_hash + "\n", encoding="utf-8")

    sealed_regions = []
    for region in regions["regions"]:
        region_dir = regions_root / region.region_id
        split = prepare_geographic_split(
            source=source,
            edition_id=edition_id,
            region=region,
            region_manifest_hash=manifest_hash,
            out_dir=region_dir,
            min_targets=min_targets,
        )
        freeze_geographic_split(
            source=source,
            edition_id=edition_id,
            split_manifest=region_dir / SPLIT_MANIFEST_FILE,
            output=region_dir / "freeze.json",
        )
        # Re-read both artifacts through their validating loaders: what is on
        # disk is what the prediction stage will consume.
        targets = load_region_targets(region_dir / TARGETS_FILE)
        geographic = load_geographic_freeze(region_dir / "freeze.json")
        suite = run_region_suite(
            geographic_freeze=geographic,
            targets=targets,
            source=source,
            edition_id=edition_id,
            suite_dir=region_dir / RUNS_DIRNAME,
            model_ids=model_ids,
            created_at=created_at,
        )
        _normalize_suite_paths(region_dir / RUNS_DIRNAME)
        sealed_regions.append(
            {
                "region_id": region.region_id,
                "region": region.to_dict(),
                "z_band": region.z_band,
                "region_relpath": f"{REGIONS_DIRNAME}/{region.region_id}",
                "split_id": split["split_manifest"]["split_id"],
                "split_digest": split["split_manifest"]["split_digest"],
                "freeze_id": geographic.freeze_id,
                "n_targets": split["split_manifest"]["n_targets"],
                "n_training": split["split_manifest"]["n_training"],
                "supported_sides": split["split_manifest"]["supported_sides"],
                "targets_sha256": sha256_file(region_dir / TARGETS_FILE),
                "split_manifest_sha256": sha256_file(region_dir / SPLIT_MANIFEST_FILE),
                "freeze_sha256": sha256_file(region_dir / "freeze.json"),
                "runs": [
                    {
                        "model_id": run["model_id"],
                        "run_relpath": (
                            f"{REGIONS_DIRNAME}/{region.region_id}/{RUNS_DIRNAME}/{run['model_id']}"
                        ),
                        "model_manifest_hash": run["model_manifest_hash"],
                        "prediction_set_fact_id": run["prediction_set_fact_id"],
                        "finalization_marker_hash": run["finalization_marker_hash"],
                    }
                    for run in suite["runs"]
                ],
            }
        )

    sealed = {
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": B002_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "edition_id": edition_id,
        "raw_source_hash": source_hash,
        "region_manifest_hash": manifest_hash,
        "region_manifest_sha256": regions_file_hash,
        "region_ids": [r.region_id for r in regions["regions"]],
        "model_ids": list(model_ids),
        "split_policy_id": GEOGRAPHIC_SPLIT_POLICY_ID,
        "split_digest_rule": SPLIT_DIGEST_RULE,
        "feature_policy_id": FEATURE_POLICY_EZ_B002,
        "feature_policy_hash": feature_policy_hash(),
        "regions": sealed_regions,
        "created_at": created_at,
        "atlas_pir_ref": atlas_pir_ref(),
        "elementzero_commit": elementzero_commit(),
        "state": "PREDICTIONS_SEALED_REGION_TRUTH_UNREAD",
    }
    (experiment_dir / SEALED_PREDICTIONS_FILE).write_text(
        canonical_json(sealed) + "\n", encoding="utf-8"
    )
    sealed_hash = sha256_file(experiment_dir / SEALED_PREDICTIONS_FILE)
    (experiment_dir / SEALED_PREDICTIONS_HASH_FILE).write_text(sealed_hash + "\n", encoding="utf-8")
    environment = environment_report(
        region_manifest_sha256=regions_file_hash, created_at=created_at or "unpinned"
    )
    (experiment_dir / ENVIRONMENT_FILE).write_text(
        canonical_json(environment) + "\n", encoding="utf-8"
    )
    run_manifest = {
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": B002_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "stage": "sealed",
        "edition_id": edition_id,
        "raw_source_hash": source_hash,
        "data_audit": {
            "report": f"{DATA_AUDIT_DIRNAME}/{parse_report_name(edition_id)}",
            "parsed_records": audit["parsed_records"],
            "eligible_records": audit["eligible_records"],
            "estimated_records": audit["estimated_records"],
            "malformed_fraction": audit["malformed_fraction"],
        },
        "region_manifest_hash": manifest_hash,
        "region_manifest_sha256": regions_file_hash,
        "regions": [
            {
                "region_id": entry["region_id"],
                "z_band": entry["z_band"],
                "n_targets": entry["n_targets"],
                "n_training": entry["n_training"],
                "supported_sides": entry["supported_sides"],
                "freeze_id": entry["freeze_id"],
                "split_digest": entry["split_digest"],
            }
            for entry in sealed_regions
        ],
        "model_ids": list(model_ids),
        "sealed_predictions": {
            "file": SEALED_PREDICTIONS_FILE,
            "sha256": sealed_hash,
            "state": sealed["state"],
        },
        "no_threshold_rule": NO_THRESHOLD_RULE,
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
        "sealed_predictions_sha256": sealed_hash,
        "region_ids": sealed["region_ids"],
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


def score_b002(
    *,
    source: str | Path,
    edition_id: str,
    experiment_dir: str | Path,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Score every sealed region, compare models, and aggregate all regions."""
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
    source_hash = sha256_file(source)
    if source_hash != sealed["raw_source_hash"]:
        raise ProtocolError("scoring snapshot differs from the sealed snapshot")
    if edition_id != sealed["edition_id"]:
        raise ProtocolError(
            f"scoring edition {edition_id!r} differs from the sealed {sealed['edition_id']!r}"
        )
    regions = read_regions(experiment_dir / REGIONS_FILE)
    if regions["region_manifest_hash"] != sealed["region_manifest_hash"]:
        raise ProtocolError("committed regions.json is not the region set that was sealed")

    reports = []
    for entry in sealed["regions"]:
        region_dir = experiment_dir / entry["region_relpath"]
        for run in entry["runs"]:
            run_dir = experiment_dir / run["run_relpath"]
            if finalization_marker_hash(run_dir) != run["finalization_marker_hash"]:
                raise LeakageError(
                    f"finalization marker of {entry['region_id']}/{run['model_id']} "
                    "changed after the seal"
                )
        comparison = score_region_suite(
            suite_dir=region_dir / RUNS_DIRNAME,
            truth_source=source,
            truth_edition_id=edition_id,
            out_dir=region_dir,
            created_at=created_at,
        )
        for run in entry["runs"]:
            report_path = (
                experiment_dir / run["run_relpath"] / SCORING_DIRNAME / "score_report.json"
            )
            reports.append(read_json(report_path))
        if comparison["region_id"] != entry["region_id"]:
            raise ProtocolError("scored region comparison does not match the sealed region")

    aggregate = write_region_aggregate(
        out_dir=experiment_dir,
        reports=reports,
        region_ids=sealed["region_ids"],
        model_ids=sealed["model_ids"],
        region_manifest_hash=sealed["region_manifest_hash"],
    )
    score_manifest = {
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": B002_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "stage": "scored",
        "edition_id": edition_id,
        "raw_source_hash": source_hash,
        "truth_source_hash": source_hash,
        "truth_source_note": (
            "EZ-B002 has one frozen snapshot: the training corpus is the eligible "
            "nuclei outside each region and the truth is the eligible nuclei inside "
            "it. The holdout is geometric, so the truth hash equals the training hash "
            "by construction."
        ),
        "region_manifest_hash": sealed["region_manifest_hash"],
        "sealed_predictions_sha256": recorded,
        "region_ids": list(sealed["region_ids"]),
        "model_ids": list(sealed["model_ids"]),
        "created_at": created_at,
        "atlas_pir_ref": atlas_pir_ref(),
        "elementzero_commit": elementzero_commit(),
        "regions": [
            {
                "region_id": entry["region_id"],
                "comparison_relpath": f"{entry['region_relpath']}/{REGION_COMPARISON_JSON}",
                "comparison_sha256": sha256_file(
                    experiment_dir / entry["region_relpath"] / REGION_COMPARISON_JSON
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
            for entry in sealed["regions"]
        ],
        "aggregate": {
            "file": REGION_AGGREGATE_JSON,
            "sha256": sha256_file(experiment_dir / REGION_AGGREGATE_JSON),
            "n_scored_targets": aggregate["n_scored_targets"],
        },
        "no_threshold_rule": NO_THRESHOLD_RULE,
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


def run_b002(
    *,
    source: str | Path,
    edition_id: str,
    regions_path: str | Path,
    experiment_dir: str | Path,
    created_at: str | None = None,
    model_ids: Sequence[str] = SUITE_MODEL_IDS,
    min_targets: int = 1,
) -> dict[str, Any]:
    """Seal, then score. Convenience wrapper; the two phases stay separable."""
    sealed = seal_b002(
        source=source,
        edition_id=edition_id,
        regions_path=regions_path,
        experiment_dir=experiment_dir,
        created_at=created_at,
        model_ids=model_ids,
        min_targets=min_targets,
    )
    scored = score_b002(
        source=source,
        edition_id=edition_id,
        experiment_dir=experiment_dir,
        created_at=created_at,
    )
    return {"sealed": sealed, "scored": scored}


def default_experiment_dir(experiment_id: str, *, root: str | Path | None = None) -> Path:
    return Path(root or REPO_ROOT) / "experiments" / experiment_id
