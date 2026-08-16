"""The four WO-14 real validation track runners (spec sections 5-13).

Every track is two separable acts:

    seal_*   verify inputs, audit roster coverage, fit on approved
             training-era data, predict identity-only targets, and write
             SEALED_PREDICTIONS.json + its hash — no target truth read.
    score_*  verify every governing hash (truth unlock), score the sealed
             predictions against the frozen AME2020 snapshot, and write
             the required result files.

Between the two acts sits a git commit containing every seal (spec
section 12): the orchestrator in ``report.py`` enforces that ordering
through the run state machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.metrics import score_rows
from elementzero.data.amdc import load_edition
from elementzero.data.identity import NuclideIdentity, parse_nuclide_id
from elementzero.eligibility.historical_sources import (
    HISTORICAL_SOURCES,
    SourceChronology,
)
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import read_json
from elementzero.models.federation.protocol import STATUS_AVAILABLE
from elementzero.models.federation.runtime_lock import capture_runtime
from elementzero.physics.conversion import binding_energy_MeV
from elementzero.real_validation.claim_adjudication import build_adjudication
from elementzero.real_validation.derived_blindness import (
    audit_summary,
    build_records,
)
from elementzero.real_validation.input_guard import (
    WO12_PROTOCOL_HASH,
    WO12_REGISTRY_HASH,
)
from elementzero.real_validation.prediction_seal import (
    SEAL_INPUT_RULE,
    SEALED_PREDICTIONS_FILE,
    read_seal_hash,
    unlock_truth,
    write_seal,
)
from elementzero.real_validation.protocol import (
    B002_BLIND_ID,
    B002_BLIND_MODELS,
    B002_RECON_ID,
    B003_BLIND_ID,
    B003_BLIND_MODELS,
    B003_RECON_ID,
    BLIND_PHYSICS_FAMILY,
    INHERITED_CRITERION_LABEL,
    NO_POST_TRUTH_TUNING_RULE,
    RECON_EXCLUDED_MODELS,
    RECON_MODELS,
    RECON_ROSTER_RULE,
    SCOPE_CONTROL_BLIND_GEOGRAPHIC,
    SCOPE_PHYSICS_BLIND_EDGE_STRUCTURE,
    SCOPE_PHYSICS_BLIND_MASS_EDGE,
    SCOPE_RECONSTRUCTION_GEOGRAPHIC,
    SCOPE_RECONSTRUCTION_SHELL_STRUCTURE,
    TRACK_BLIND,
    TRACK_RECONSTRUCTION,
    TRUTH_EDITION,
    WO14_CREATED_AT,
)
from elementzero.real_validation.run_state import RealValidationRun

EDITION_ID = TRUTH_EDITION
SOURCE_RELPATH = "data/amdc/mass_1.mas20.txt"
RESULTS_DIRNAME = "results"
RUN_STATE_FILE = "wo14_run_state.json"
SEAL_RECORD_FILE = "wo14_seal_record.json"
DECOMPOSITION_FILE = "federation_decomposition.json"
TRUTH_UNLOCK_FILE = "truth_unlock.json"

# The 12 historically blind B003 central targets are read from the
# committed WO-13 subfederation manifest, never re-derived here.
SUBFEDERATION_RELPATH = "reports/eligibility/wo13/subfederation_summary.json"
MATRIX_RELPATH = "reports/eligibility/wo13/target_eligibility_matrix.json"
CHRONOLOGY_RELPATH = "reports/eligibility/wo13/historical_source_chronology.json"

COVERAGE_RULE = (
    "ez-wo14-real-coverage-audit-v1: before sealing, every roster model's "
    "coverage_status is audited over every split's identity corpus. A "
    "target-side gap excludes the model — the sealed pipeline never "
    "receives imputed values — and training-side gaps are recorded per "
    "split; they are lawful only because the frozen residual training "
    "policy skips-and-counts uncovered pairs and a frozen table records "
    "identities without consuming values."
)

BLIND_WORKSPACE_RULE = (
    "ez-wo14-blind-workspace-v1: blind prediction workspaces carry "
    "identity-only targets; the only mass values present are approved "
    "training-era evidence outside the sealed target set"
)

# 8071.318 keV: neutron mass excess enters binding_energy_MeV internally;
# S2n/S2p are computed from binding energies exactly as physics/separation.py
# defines them.


def _results_dir(root: Path, experiment_id: str) -> Path:
    return root / RESULTS_DIRNAME / experiment_id


def verified_source(root: Path) -> Path:
    """The pinned AME2020 snapshot; hash-verified before any use."""
    path = root / SOURCE_RELPATH
    if not path.is_file():
        raise ProtocolError(
            f"{path} is missing; fetch the pinned snapshots with "
            "tools/fetch_ame_sources.py before running WO-14"
        )
    pinned = HISTORICAL_SOURCES[EDITION_ID]["raw_sha256"]
    digest = sha256_file(path)
    if digest != pinned:
        raise ProtocolError(
            f"AME2020 snapshot hashes {digest}, pinned {pinned}; WO-14 stops"
        )
    return path


def _registry(root: Path):
    from elementzero.models.federation.registry import build_default_federation

    registry = build_default_federation(repo_root=root)
    manifest = registry.manifest()
    if manifest["registry_hash"] != WO12_REGISTRY_HASH:
        raise ProtocolError(
            "live federation registry hash "
            f"{manifest['registry_hash']} differs from the frozen "
            f"{WO12_REGISTRY_HASH}; WO-14 stops"
        )
    return registry


def audit_roster_coverage(
    registry, roster: tuple[str, ...], splits: list[dict[str, Any]]
) -> dict[str, Any]:
    """Target coverage must be total; training gaps are recorded, not fatal."""
    by_model: dict[str, Any] = {}
    excluded: list[str] = []
    for model_id in roster:
        model = registry.build(model_id)
        split_reports = []
        targets_covered = True
        for split in splits:
            uncovered_targets = []
            n_uncovered_training = 0
            for nuclide_id in split["target_nuclide_ids"]:
                z, n = parse_nuclide_id(nuclide_id)
                if model.coverage_status(NuclideIdentity.from_zn(z, n)) != STATUS_AVAILABLE:
                    uncovered_targets.append(nuclide_id)
            for nuclide_id in split["training_nuclide_ids"]:
                z, n = parse_nuclide_id(nuclide_id)
                if model.coverage_status(NuclideIdentity.from_zn(z, n)) != STATUS_AVAILABLE:
                    n_uncovered_training += 1
            targets_covered = targets_covered and not uncovered_targets
            split_reports.append(
                {
                    "split_id": split["split_id"],
                    "n_targets": len(split["target_nuclide_ids"]),
                    "uncovered_target_ids": sorted(uncovered_targets),
                    "n_training": len(split["training_nuclide_ids"]),
                    "n_uncovered_training": n_uncovered_training,
                }
            )
        by_model[model_id] = {
            "splits": split_reports,
            "all_targets_covered": targets_covered,
        }
        if not targets_covered:
            excluded.append(model_id)
    sealed = [m for m in roster if m not in excluded]
    if not sealed:
        raise ProtocolError(
            "no roster model covers every target of this track; nothing can "
            "be sealed"
        )
    return {
        "rule": COVERAGE_RULE,
        "by_model": by_model,
        "excluded_models": sorted(excluded),
        "sealed_model_ids": sealed,
    }


def _builders(registry, roster, recorder):
    from elementzero.experiments.wo12_qualification import FederationRunAdapter

    return {
        model_id: (
            lambda m=model_id: FederationRunAdapter(registry.build(m), recorder)
        )
        for model_id in roster
    }


def _eligibility_hashes(root: Path) -> dict[str, str]:
    """Per-track eligibility hashes, re-derived from the committed WO-13
    artifacts by the exact WO-13 rule: blind tracks hash the blind
    subfederation manifest; reconstruction tracks hash the blind
    experiment's eligibility matrix."""
    subfed = read_json(root / SUBFEDERATION_RELPATH)
    matrices = read_json(root / MATRIX_RELPATH)
    return {
        B002_BLIND_ID: sha256_hex(subfed["manifests"]["EZ-B002-v2-real-blind"]),
        B002_RECON_ID: sha256_hex(matrices["EZ-B002-v2-real-blind"]),
        B003_BLIND_ID: sha256_hex(subfed["manifests"]["EZ-B003-v2-real-blind"]),
        B003_RECON_ID: sha256_hex(matrices["EZ-B003-v2-real-blind"]),
    }


def _claim_manifest(root: Path, experiment_id: str) -> dict[str, Any]:
    return read_json(root / "experiments" / experiment_id / "claim_manifest.json")


def _threshold_hash(root: Path, experiment_id: str) -> str:
    return sha256_hex(
        read_json(root / "experiments" / experiment_id / "threshold_manifest.json")
    )


def _preregistered_target_ids(root: Path, experiment_id: str) -> list[str]:
    """The union of the committed identity-only target groups, sorted."""
    prereg = root / "experiments" / experiment_id
    for name in ("region_targets.json", "challenge_targets.json"):
        path = prereg / name
        if path.is_file():
            groups = read_json(path)["targets"]
            return sorted({t for group in groups.values() for t in group})
    raise ProtocolError(f"no preregistered target list for {experiment_id}")


def blind_target_ids(root: Path) -> list[str]:
    """The 12 physics-blind B003 targets from the committed manifest."""
    subfed = read_json(root / SUBFEDERATION_RELPATH)
    manifest = subfed["manifests"]["EZ-B003-v2-real-blind"]
    ids = sorted(
        t["target_id"]
        for t in manifest["targets"]
        if t["tier"] == "PHYSICS_BLIND_EVALUABLE"
    )
    if len(ids) != 12:
        raise ProtocolError(
            f"committed manifest yields {len(ids)} physics-blind targets, "
            "expected 12; WO-14 stops rather than guess"
        )
    return ids


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return sha256_file(path)


def _run_id(experiment_id: str) -> str:
    return f"wo14-{experiment_id}-run-v1"


def _new_run(root: Path, experiment_id: str, claim_track: str) -> RealValidationRun:
    run = RealValidationRun(
        experiment_id=experiment_id,
        run_id=_run_id(experiment_id),
        claim_track=claim_track,
        protocol_hash=WO12_PROTOCOL_HASH,
        eligibility_manifest_hash=_eligibility_hashes(root)[experiment_id],
    )
    run.advance("INPUTS_VERIFIED")
    return run


def _persist_run(dest: Path, run: RealValidationRun) -> None:
    _write_json(dest / RUN_STATE_FILE, run.to_dict())


def _load_run(dest: Path) -> RealValidationRun:
    payload = read_json(dest / RUN_STATE_FILE)
    run = RealValidationRun(
        experiment_id=payload["experiment_id"],
        run_id=payload["run_id"],
        claim_track=payload["claim_track"],
        protocol_hash=payload["protocol_hash"],
        eligibility_manifest_hash=payload["eligibility_manifest_hash"],
    )
    run.state = payload["state"]
    run.history = [payload["state"]]
    if payload["prediction_seal_hash"]:
        run.prediction_seal_hash = payload["prediction_seal_hash"]
    return run


def _seal_record(
    *,
    dest: Path,
    run: RealValidationRun,
    roster: tuple[str, ...],
    coverage: dict[str, Any],
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "experiment_id": run.experiment_id,
        "run_id": run.run_id,
        "claim_track": run.claim_track,
        "created_at": WO14_CREATED_AT,
        "roster": list(roster),
        "coverage_audit": coverage,
        "seal_input_rule": SEAL_INPUT_RULE,
        "blind_workspace_rule": BLIND_WORKSPACE_RULE,
        "no_post_truth_tuning_rule": NO_POST_TRUTH_TUNING_RULE,
        "runtime": capture_runtime(),
        "prediction_seal_hash": run.prediction_seal_hash,
        "seal_commit": None,
        **(extras or {}),
    }
    _write_json(dest / SEAL_RECORD_FILE, record)
    return record


# --------------------------------------------------------------------------- #
# B002 tracks (frozen seal_b002 / score_b002 mechanics)                       #
# --------------------------------------------------------------------------- #


def seal_b002_track(
    *, root: str | Path | None = None, experiment_id: str
) -> dict[str, Any]:
    from elementzero.adjudication.benchmark_controls import control_model_registry
    from elementzero.experiments.b002_runner import seal_b002
    from elementzero.experiments.wo12_qualification import _b002_split_manifests

    root = Path(root or REPO_ROOT)
    source = verified_source(root)
    if experiment_id == B002_BLIND_ID:
        roster, claim_track = B002_BLIND_MODELS, TRACK_BLIND
    elif experiment_id == B002_RECON_ID:
        roster, claim_track = RECON_MODELS, TRACK_RECONSTRUCTION
    else:
        raise ProtocolError(f"{experiment_id} is not a WO-14 B002 track")
    regions_path = root / "experiments" / experiment_id / "regions.json"
    dest = _results_dir(root, experiment_id)

    registry = _registry(root)
    splits = _b002_split_manifests(chart=source, regions_path=regions_path)
    coverage = audit_roster_coverage(registry, roster, splits)
    recorder: dict[str, dict[str, dict[str, Any]]] = {}
    builders = _builders(registry, coverage["sealed_model_ids"], recorder)
    run = _new_run(root, experiment_id, claim_track)
    with control_model_registry(builders):
        sealed = seal_b002(
            source=source,
            edition_id=EDITION_ID,
            regions_path=regions_path,
            experiment_dir=dest,
            created_at=WO14_CREATED_AT,
            model_ids=tuple(coverage["sealed_model_ids"]),
        )
    run.advance("PREDICTIONS_GENERATED")
    run.advance("PREDICTIONS_FINALIZED")
    run.record_seal(sealed["sealed_predictions_sha256"])
    _write_json(dest / DECOMPOSITION_FILE, {"by_model": recorder})
    extras = {}
    if experiment_id == B002_RECON_ID:
        extras = {
            "roster_rule": RECON_ROSTER_RULE,
            "excluded_models": RECON_EXCLUDED_MODELS,
        }
    _seal_record(dest=dest, run=run, roster=roster, coverage=coverage, extras=extras)
    _persist_run(dest, run)
    _rewrite_sha256sums(dest)
    return {"experiment_id": experiment_id, "seal_hash": run.prediction_seal_hash}


def _b002_track_unlock(
    root: Path, experiment_id: str, dest: Path, *, expected_seal_hash: str
) -> dict[str, Any]:
    claim = _claim_manifest(root, experiment_id)
    sealed = read_json(dest / SEALED_PREDICTIONS_FILE)
    sealed_target_ids: list[str] = []
    for entry in sealed["regions"]:
        targets = read_json(dest / entry["region_relpath"] / "targets.json")
        sealed_target_ids.extend(t["nuclide_id"] for t in targets["targets"])
    unlock = unlock_truth(
        seal_dir=dest,
        # The expected hash is the one finalization persisted in the run
        # state — never re-read from the seal directory, or a post-
        # finalization rewrite of both seal files would compare a tampered
        # digest against itself.
        expected_seal_hash=expected_seal_hash,
        eligibility_manifest_hash=_eligibility_hashes(root)[experiment_id],
        expected_eligibility_hash=claim["eligibility_manifest_hash"],
        threshold_hash=_threshold_hash(root, experiment_id),
        expected_threshold_hash=claim["threshold_manifest_hash"],
        registry_hash=_registry(root).manifest()["registry_hash"],
        expected_registry_hash=WO12_REGISTRY_HASH,
        protocol_hash=read_json(root / "experiments/EZ-B002-v2/PROTOCOL.json")[
            "protocol_hash"
        ],
        expected_protocol_hash=WO12_PROTOCOL_HASH,
        target_identity_digest=identity_digest(sorted(sealed_target_ids)),
        expected_target_identity_digest=identity_digest(
            _preregistered_target_ids(root, experiment_id)
        ),
    )
    _write_json(dest / TRUTH_UNLOCK_FILE, unlock)
    return unlock


def _inherited_criterion(pooled: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    met = (
        float(pooled["MAE_keV"]) <= float(thresholds["best_model_max_MAE_keV"])
        and float(pooled["cal_error_90"])
        <= float(thresholds["best_model_max_calibration_error_90"])
    )
    return {
        "label": INHERITED_CRITERION_LABEL,
        "rule": (
            "the frozen EZ-B002-v2 qualification gate applied verbatim; "
            "meeting it on real data is NOT a universal real-world "
            "performance standard"
        ),
        "max_MAE_keV": float(thresholds["best_model_max_MAE_keV"]),
        "max_calibration_error_90": float(
            thresholds["best_model_max_calibration_error_90"]
        ),
        "observed_MAE_keV": float(pooled["MAE_keV"]),
        "observed_calibration_error_90": float(pooled["cal_error_90"]),
        "met": met,
    }


def score_b002_track(
    *, root: str | Path | None = None, experiment_id: str
) -> dict[str, Any]:
    from elementzero.experiments.b002_runner import score_b002

    root = Path(root or REPO_ROOT)
    source = verified_source(root)
    dest = _results_dir(root, experiment_id)
    run = _load_run(dest)
    if run.state != "SEALED_COMMIT_RECORDED":
        raise ProtocolError(
            f"{experiment_id} is {run.state}; scoring requires "
            "SEALED_COMMIT_RECORDED — commit the seal first"
        )
    _b002_track_unlock(
        root, experiment_id, dest, expected_seal_hash=run.prediction_seal_hash
    )
    run.advance("TRUTH_UNLOCKED")
    scored = score_b002(
        source=source,
        edition_id=EDITION_ID,
        experiment_dir=dest,
        created_at=WO14_CREATED_AT,
    )
    run.advance("SCORED")

    aggregate = scored["aggregate"]
    thresholds = read_json(
        root / "experiments" / experiment_id / "threshold_manifest.json"
    )["frozen_thresholds"]
    by_model = {}
    for model_id, payload in aggregate["by_model"].items():
        pooled = payload["pooled"]
        by_model[model_id] = {
            "pooled": {k: pooled[k] for k in (
                "n",
                "MAE_keV",
                "MedAE_keV",
                "RMSE_keV",
                "NLPD",
                "coverage_90",
                "coverage_95",
                "cal_error_90",
                "cal_error_95",
            )},
            "per_region": payload.get("per_region"),
            "distance_buckets": pooled.get("distance_buckets"),
            "worst_region": payload.get("worst_region"),
            "inherited_criterion": _inherited_criterion(pooled, thresholds),
        }

    if experiment_id == B002_BLIND_ID:
        result = _finish_b002_blind(root, dest, run, by_model)
    else:
        result = _finish_b002_recon(root, dest, run, by_model)
    run.advance("CLAIM_ADJUDICATED")
    _persist_run(dest, run)
    _rewrite_sha256sums(dest)
    return result


def _best_by_mae(by_model: dict[str, Any], candidates=None) -> tuple[str, dict[str, Any]]:
    pool = {
        model_id: payload
        for model_id, payload in by_model.items()
        if candidates is None or model_id in candidates
    }
    best = min(pool, key=lambda m: float(pool[m]["pooled"]["MAE_keV"]))
    return best, pool[best]


def _finish_b002_blind(
    root: Path, dest: Path, run: RealValidationRun, by_model: dict[str, Any]
) -> dict[str, Any]:
    best_model, best = _best_by_mae(by_model)
    criterion = best["inherited_criterion"]
    status = (
        "CONTROL_BLIND_CRITERION_MET"
        if criterion["met"]
        else "CONTROL_BLIND_CRITERION_NOT_MET"
    )
    aggregate = {
        "experiment_id": run.experiment_id,
        "run_id": run.run_id,
        "claim_track": run.claim_track,
        "scientific_scope": SCOPE_CONTROL_BLIND_GEOGRAPHIC,
        "truth_edition": EDITION_ID,
        "by_model": dict(sorted(by_model.items())),
        "best_baseline": best_model,
        "inherited_gate_met": criterion["met"],
        "inherited_criterion": criterion,
        "control_blind_status": status,
        "federation_improved_over_baseline": "NOT_EVALUABLE_FOR_BLIND_B002",
        "note": (
            "zero blind physics groups on these targets: this run measures "
            "freeze-controlled statistical baselines only and can never "
            "become physics validation"
        ),
    }
    _write_json(dest / "aggregate.json", aggregate)
    _write_json(
        dest / "model_comparison.json",
        {
            "experiment_id": run.experiment_id,
            "columns": [
                "model_id",
                "n",
                "MAE_keV",
                "MedAE_keV",
                "RMSE_keV",
                "NLPD",
                "coverage_90",
                "coverage_95",
                "cal_error_90",
                "cal_error_95",
            ],
            "rows": [
                {"model_id": model_id, **payload["pooled"]}
                for model_id, payload in sorted(by_model.items())
            ],
            "ranking_rule": (
                "best_baseline is ranked by pooled MAE alone and reported "
                "next to every other metric; no metric is suppressed"
            ),
        },
    )
    adjudication = build_adjudication(
        experiment_id=run.experiment_id,
        run_id=run.run_id,
        benchmark_id="EZ-B002",
        claim_track=TRACK_BLIND,
        prediction_seal_hash=run.prediction_seal_hash,
        eligible_model_ids=list(by_model),
        excluded_model_ids=sorted(
            (set(RECON_MODELS) | set(RECON_EXCLUDED_MODELS)) - set(B002_BLIND_MODELS)
        ),
        physics_independence_groups=[],
        claim_type="STRICT_BLIND",
        scientific_scope=SCOPE_CONTROL_BLIND_GEOGRAPHIC,
        inherited_criterion_status=aggregate["control_blind_status"],
        blind_gate_status="CONTROL_BLIND_EVALUABLE",
        visual_stage_permission="BADGE_CB_ONLY_NO_STAGE_PROMOTION",
        next_gate=(
            "blind global-physics geographic validation still missing; "
            "see WO-15"
        ),
    )
    _write_json(dest / "claim_adjudication.json", {"records": [adjudication]})
    return {
        "experiment_id": run.experiment_id,
        "status": aggregate["control_blind_status"],
        "best_baseline": best_model,
        "inherited_gate_met": criterion["met"],
    }


def _finish_b002_recon(
    root: Path, dest: Path, run: RealValidationRun, by_model: dict[str, Any]
) -> dict[str, Any]:
    # Cross-reference the blind-track baselines instead of re-running them
    # under a weaker label (RECON_ROSTER_RULE).
    blind_aggregate = read_json(_results_dir(root, B002_BLIND_ID) / "aggregate.json")
    blind_by_model = blind_aggregate["by_model"]
    best_baseline, baseline = _best_by_mae(blind_by_model)
    best_table, table = _best_by_mae(by_model, candidates=("EZ-BSKG3-TABLE-v1",))
    best_residual, residual = _best_by_mae(
        by_model, candidates=("EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",)
    )
    best_recon, recon = _best_by_mae(by_model)
    improved = float(recon["pooled"]["MAE_keV"]) < float(
        baseline["pooled"]["MAE_keV"]
    )
    aggregate = {
        "experiment_id": run.experiment_id,
        "run_id": run.run_id,
        "claim_track": run.claim_track,
        "scientific_scope": SCOPE_RECONSTRUCTION_GEOGRAPHIC,
        "truth_edition": EDITION_ID,
        "by_model": dict(sorted(by_model.items())),
        "roster_rule": RECON_ROSTER_RULE,
        "excluded_models": RECON_EXCLUDED_MODELS,
        "best_baseline_model": {
            "model_id": best_baseline,
            "MAE_keV": baseline["pooled"]["MAE_keV"],
            "source": f"cross-referenced from {B002_BLIND_ID} (identical targets)",
        },
        "best_physics_table_model": {
            "model_id": best_table,
            "MAE_keV": table["pooled"]["MAE_keV"],
        },
        "best_residual_physics_model": {
            "model_id": best_residual,
            "MAE_keV": residual["pooled"]["MAE_keV"],
        },
        "best_combined_model": {
            "status": "NOT_RUN_NO_ELIGIBLE_COMBINER",
            "reason": (
                "the committed WO-13 eligibility admits no combiner on this "
                "track: every combiner contains the unknown-provenance "
                "FRDM95 lineage, and a combiner cannot hide an ineligible "
                "contributor"
            ),
        },
        "reconstruction_federation_improved_over_best_baseline": improved,
        "improvement_comparison": {
            "best_reconstruction_model": best_recon,
            "reconstruction_MAE_keV": recon["pooled"]["MAE_keV"],
            "baseline_MAE_keV": baseline["pooled"]["MAE_keV"],
            "same_targets": True,
        },
        "status": "B002_RECON_COMPLETE",
        "note": (
            "descriptive reconstruction evidence, not blind extrapolation; "
            "reference status only"
        ),
    }
    _write_json(dest / "aggregate.json", aggregate)
    _write_json(
        dest / "model_comparison.json",
        {
            "experiment_id": run.experiment_id,
            "columns": [
                "model_id",
                "n",
                "MAE_keV",
                "MedAE_keV",
                "RMSE_keV",
                "NLPD",
                "coverage_90",
                "coverage_95",
                "cal_error_90",
                "cal_error_95",
            ],
            "rows": [
                {"model_id": model_id, **payload["pooled"]}
                for model_id, payload in sorted(by_model.items())
            ]
            + [
                {
                    "model_id": f"{model_id} [blind-track cross-reference]",
                    **payload["pooled"],
                }
                for model_id, payload in sorted(blind_by_model.items())
            ],
            "ranking_rule": (
                "reconstruction rows and blind-track cross-references are "
                "labeled and never mixed into one claim"
            ),
        },
    )
    adjudication = build_adjudication(
        experiment_id=run.experiment_id,
        run_id=run.run_id,
        benchmark_id="EZ-B002",
        claim_track=TRACK_RECONSTRUCTION,
        prediction_seal_hash=run.prediction_seal_hash,
        eligible_model_ids=list(by_model),
        excluded_model_ids=sorted(RECON_EXCLUDED_MODELS),
        physics_independence_groups=["skyrme_edf_bskg"],
        claim_type="RECONSTRUCTION_REFERENCE",
        scientific_scope=SCOPE_RECONSTRUCTION_GEOGRAPHIC,
        inherited_criterion_status="NOT_A_BLIND_CRITERION_REFERENCE_ONLY",
        blind_gate_status="NOT_APPLICABLE_RECONSTRUCTION_TRACK",
        visual_stage_permission="BADGE_R_ONLY_NO_STAGE_PROMOTION",
        next_gate=(
            "reconstruction evidence never upgrades; blind credit requires "
            "the BLIND track"
        ),
    )
    _write_json(dest / "claim_adjudication.json", {"records": [adjudication]})
    return {
        "experiment_id": run.experiment_id,
        "status": "B002_RECON_COMPLETE",
        "improved_over_baseline": improved,
    }


def _rewrite_sha256sums(dest: Path) -> None:
    from elementzero.experiments.runner import write_sha256sums

    write_sha256sums(dest)


def finalize_run_state(
    *, root: str | Path | None = None, experiment_id: str
) -> dict[str, Any]:
    """Advance an adjudicated run to REPORTED before the report is built,
    so the committed report bundle embeds the terminal state and the CI
    rebuild (which never mutates result trees) reproduces it byte-for-byte."""
    root = Path(root or REPO_ROOT)
    dest = _results_dir(root, experiment_id)
    run = _load_run(dest)
    if run.state == "REPORTED":
        return run.to_dict()
    run.advance("REPORTED")
    _persist_run(dest, run)
    _rewrite_sha256sums(dest)
    return run.to_dict()


def _assert_seal_commit_valid(
    root: Path, *, experiment_id: str, commit: str, seal_hash: str
) -> None:
    """The recorded commit must exist, be an ancestor of HEAD, and carry
    the finalized seal bytes — a name alone proves nothing."""
    import hashlib
    import subprocess

    def _git(*args: str, capture: bool = False):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
        )

    if _git("cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        raise ProtocolError(
            f"{experiment_id}: {commit} is not a commit in this repository; "
            "a seal commit must be a real, reachable commit"
        )
    if _git("merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        raise ProtocolError(
            f"{experiment_id}: {commit} is not an ancestor of HEAD; the "
            "seal commit must be part of the published history"
        )
    relpath = (
        f"{RESULTS_DIRNAME}/{experiment_id}/{SEALED_PREDICTIONS_FILE}"
    )
    shown = _git("show", f"{commit}:{relpath}")
    if shown.returncode != 0:
        raise ProtocolError(
            f"{experiment_id}: {commit} does not contain {relpath}; the "
            "seal commit must carry the sealed predictions"
        )
    digest = hashlib.sha256(shown.stdout).hexdigest()
    if digest != seal_hash:
        raise ProtocolError(
            f"{experiment_id}: the seal committed in {commit} hashes "
            f"{digest}, not the finalized {seal_hash}"
        )


def record_seal_commit(
    *, root: str | Path | None = None, experiment_id: str, commit: str
) -> dict[str, Any]:
    """Advance a sealed run to SEALED_COMMIT_RECORDED with the commit id."""
    root = Path(root or REPO_ROOT)
    dest = _results_dir(root, experiment_id)
    run = _load_run(dest)
    # Re-verify the seal is byte-identical to what was finalized.
    actual = read_seal_hash(dest)
    if actual != run.prediction_seal_hash:
        raise ProtocolError(
            f"{experiment_id}: sealed predictions hash {actual} no longer "
            f"matches the finalized {run.prediction_seal_hash}"
        )
    if run.state != "PREDICTIONS_FINALIZED":
        raise ProtocolError(
            f"{experiment_id} is {run.state}; recording a seal commit "
            "requires PREDICTIONS_FINALIZED"
        )
    _assert_seal_commit_valid(
        root,
        experiment_id=experiment_id,
        commit=commit,
        seal_hash=run.prediction_seal_hash,
    )
    run.advance("SEALED_COMMIT_RECORDED")
    record = read_json(dest / SEAL_RECORD_FILE)
    record["seal_commit"] = commit
    _write_json(dest / SEAL_RECORD_FILE, record)
    _persist_run(dest, run)
    _rewrite_sha256sums(dest)
    return {"experiment_id": experiment_id, "seal_commit": commit}


# --------------------------------------------------------------------------- #
# B003 REAL-BLIND (custom 12-target sealed run)                               #
# --------------------------------------------------------------------------- #


def seal_b003_blind(*, root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or REPO_ROOT)
    source = verified_source(root)
    dest = _results_dir(root, B003_BLIND_ID)
    if (dest / SEALED_PREDICTIONS_FILE).exists():
        raise ProtocolError(
            f"{dest} already holds a sealed run; a rerun requires a new "
            "experiment directory or run id, never an overwrite"
        )
    targets = blind_target_ids(root)
    target_set = frozenset(targets)
    corpus = [
        o
        for o in load_edition(EDITION_ID, str(source))
        if o.ground_truth_eligible
    ]
    training = [o for o in corpus if o.nuclide_id not in target_set]
    if len(training) + len(targets) != len(corpus):
        raise ProtocolError("blind targets are not a subset of the eligible corpus")

    registry = _registry(root)
    splits = [
        {
            "split_id": "historical-blind-12",
            "training_nuclide_ids": sorted(o.nuclide_id for o in training),
            "target_nuclide_ids": targets,
        }
    ]
    coverage = audit_roster_coverage(registry, B003_BLIND_MODELS, splits)

    # Derived blindness audit — decided entirely pre-truth from committed
    # eligibility records and the committed chronology.
    chronology = SourceChronology.from_committed(root / CHRONOLOGY_RELPATH)
    corpus_ids = frozenset(o.nuclide_id for o in corpus)
    records = build_records(
        blind_target_ids=targets,
        model_ids=list(coverage["sealed_model_ids"]),
        chronology=chronology,
        truth_available=corpus_ids,
    )
    summary = audit_summary(records)
    derived_hash = _write_json(
        dest / "derived_blindness.json",
        {"records": records, "summary": summary},
    )

    predictions: dict[str, Any] = {}
    manifests: dict[str, Any] = {}
    for model_id in coverage["sealed_model_ids"]:
        model = registry.build(model_id)
        model.fit(training)
        rows = {}
        for nuclide_id in targets:
            z, n = parse_nuclide_id(nuclide_id)
            prediction = model.predict(NuclideIdentity.from_zn(z, n))
            if prediction.status != STATUS_AVAILABLE:
                raise ProtocolError(
                    f"{model_id} cannot cover {nuclide_id} despite the "
                    "pre-seal coverage audit; sealing stops"
                )
            rows[nuclide_id] = prediction.to_dict()
        predictions[model_id] = rows
        manifests[model_id] = model.manifest()

    seal_payload = {
        "experiment_id": B003_BLIND_ID,
        "run_id": _run_id(B003_BLIND_ID),
        "claim_track": TRACK_BLIND,
        "benchmark_id": "EZ-B003",
        "edition_id": EDITION_ID,
        "raw_source_hash": sha256_file(source),
        "created_at": WO14_CREATED_AT,
        "target_nuclide_ids": targets,
        "target_identity_digest": identity_digest(targets),
        "n_training": len(training),
        "training_identity_digest": identity_digest(
            sorted(o.nuclide_id for o in training)
        ),
        "model_ids": list(coverage["sealed_model_ids"]),
        "model_manifest_hashes": {
            model_id: sha256_hex(manifest)
            for model_id, manifest in manifests.items()
        },
        "blind_physics_family": BLIND_PHYSICS_FAMILY,
        "derived_blindness_hash": derived_hash,
        "predictions": predictions,
        "state": "PREDICTIONS_SEALED_TARGET_TRUTH_UNREAD",
    }
    run = _new_run(root, B003_BLIND_ID, TRACK_BLIND)
    seal_hash = write_seal(dest, seal_payload)
    run.advance("PREDICTIONS_GENERATED")
    run.advance("PREDICTIONS_FINALIZED")
    run.record_seal(seal_hash)
    _write_json(
        dest / "model_manifests.json",
        {"manifests": manifests},
    )
    _seal_record(
        dest=dest,
        run=run,
        roster=B003_BLIND_MODELS,
        coverage=coverage,
        extras={
            "derived_blindness_hash": derived_hash,
            # Frozen before any truth unlock: the blind mass result is
            # judged by the inherited synthetic qualification criterion
            # applied to the best blind-physics-family model, and by
            # nothing invented later.
            "blind_mass_criterion": {
                "label": INHERITED_CRITERION_LABEL,
                "applies_to": "best model of the blind physics family",
                "family_model_ids": [
                    "EZ-FRDM95-TABLE-v1",
                    "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
                ],
                "max_MAE_keV": 150.0,
                "max_calibration_error_90": 0.15,
                "rule": (
                    "the frozen EZ-B002-v2 qualification gate values applied "
                    "verbatim as the preregistered mass criterion for the 12 "
                    "historical-blind targets; frozen in the seal commit "
                    "before truth unlock, and never a universal real-world "
                    "performance standard"
                ),
            },
        },
    )
    _persist_run(dest, run)
    _rewrite_sha256sums(dest)
    return {"experiment_id": B003_BLIND_ID, "seal_hash": seal_hash}


def score_b003_blind(*, root: str | Path | None = None) -> dict[str, Any]:
    root = Path(root or REPO_ROOT)
    source = verified_source(root)
    dest = _results_dir(root, B003_BLIND_ID)
    run = _load_run(dest)
    if run.state != "SEALED_COMMIT_RECORDED":
        raise ProtocolError(
            f"{B003_BLIND_ID} is {run.state}; scoring requires "
            "SEALED_COMMIT_RECORDED — commit the seal first"
        )
    sealed = read_json(dest / SEALED_PREDICTIONS_FILE)
    claim = _claim_manifest(root, B003_BLIND_ID)
    unlock = unlock_truth(
        seal_dir=dest,
        # Expected = the hash finalization persisted, never re-read from
        # the seal directory (a rewrite of both seal files would otherwise
        # compare a tampered digest against itself).
        expected_seal_hash=run.prediction_seal_hash,
        eligibility_manifest_hash=_eligibility_hashes(root)[B003_BLIND_ID],
        expected_eligibility_hash=claim["eligibility_manifest_hash"],
        threshold_hash=_threshold_hash(root, B003_BLIND_ID),
        expected_threshold_hash=claim["threshold_manifest_hash"],
        registry_hash=_registry(root).manifest()["registry_hash"],
        expected_registry_hash=WO12_REGISTRY_HASH,
        protocol_hash=read_json(root / "experiments/EZ-B003-v2/PROTOCOL.json")[
            "protocol_hash"
        ],
        expected_protocol_hash=WO12_PROTOCOL_HASH,
        target_identity_digest=sealed["target_identity_digest"],
        expected_target_identity_digest=identity_digest(blind_target_ids(root)),
    )
    _write_json(dest / TRUTH_UNLOCK_FILE, unlock)
    run.advance("TRUTH_UNLOCKED")

    truth = {
        o.nuclide_id: o.mass_excess_keV
        for o in load_edition(EDITION_ID, str(source))
        if o.ground_truth_eligible
    }

    # ---- individual mass metrics per model ---------------------------------
    by_model: dict[str, Any] = {}
    for model_id, rows in sealed["predictions"].items():
        scored_rows = []
        per_target = {}
        for nuclide_id, prediction in rows.items():
            mu = float(prediction["point_keV"])
            sigma = float(prediction["predictive_std_keV"])
            truth_keV = truth[nuclide_id]
            scored_rows.append(
                {
                    "prediction_keV": mu,
                    "truth_keV": truth_keV,
                    "std_keV": sigma,
                    # The sealed intervals, exactly as finalized pre-truth.
                    "interval_p90": prediction["predictive_interval_90"],
                    "interval_p95": prediction["predictive_interval_95"],
                }
            )
            per_target[nuclide_id] = {
                "prediction_keV": mu,
                "std_keV": sigma,
                "truth_keV": truth_keV,
                "abs_error_keV": abs(mu - truth_keV),
            }
        metrics = score_rows(scored_rows)
        by_model[model_id] = {"metrics": metrics, "per_target": per_target}

    # The mass criterion frozen in the seal commit, never re-decided here.
    frozen_mass_criterion = read_json(dest / SEAL_RECORD_FILE)["blind_mass_criterion"]
    family_models = list(frozen_mass_criterion["family_model_ids"])
    best_family, family = _best_by_mae(
        {m: {"pooled": by_model[m]["metrics"]} for m in family_models}
    )
    family_criterion = _inherited_criterion(
        family["pooled"],
        {
            "best_model_max_MAE_keV": frozen_mass_criterion["max_MAE_keV"],
            "best_model_max_calibration_error_90": frozen_mass_criterion[
                "max_calibration_error_90"
            ],
        },
    )
    mass_status = (
        "PHYSICS_BLIND_MASS_CRITERION_MET"
        if family_criterion["met"]
        else "PHYSICS_BLIND_MASS_CRITERION_NOT_MET"
    )
    mass_results = {
        "experiment_id": B003_BLIND_ID,
        "run_id": run.run_id,
        "scientific_scope": SCOPE_PHYSICS_BLIND_MASS_EDGE,
        "truth_edition": EDITION_ID,
        "n_targets": len(sealed["target_nuclide_ids"]),
        "blind_physics_family": BLIND_PHYSICS_FAMILY,
        "by_model": {
            model_id: payload["metrics"]
            for model_id, payload in sorted(by_model.items())
        },
        "per_target": {
            model_id: payload["per_target"]
            for model_id, payload in sorted(by_model.items())
        },
        "best_blind_family_model": best_family,
        "inherited_criterion": family_criterion,
        "individual_mass_blind_result": mass_status,
        "note": (
            "12 historically blind targets, one blind physics family; the "
            "baselines are freeze-controlled statistical comparators, not "
            "independent physics"
        ),
    }
    _write_json(dest / "mass_results.json", mass_results)

    # ---- derived edge-structure metrics where eligible ----------------------
    audit = read_json(dest / "derived_blindness.json")
    eligible_records = [
        r for r in audit["records"] if r["all_model_inputs_blind_eligible"]
    ]
    edge_rows = []
    for record in eligible_records:
        if record["observable"] not in ("S2n", "S2p"):
            continue
        central = record["central_nuclide_id"]
        components = record["component_nuclide_ids"]
        z, n = parse_nuclide_id(central)
        for model_id, rows in sealed["predictions"].items():
            def _binding(nuclide_id: str, mass_keV: float) -> float:
                cz, cn = parse_nuclide_id(nuclide_id)
                return binding_energy_MeV(z=cz, n=cn, mass_excess_keV=mass_keV)

            model_values = {
                c: _binding(c, float(rows[c]["point_keV"])) for c in components
            }
            truth_values = {c: _binding(c, truth[c]) for c in components}
            if record["observable"] == "S2n":
                other = f"Z{z}-N{n - 2}"
            else:
                other = f"Z{z - 2}-N{n}"
            predicted = model_values[central] - model_values[other]
            observed = truth_values[central] - truth_values[other]
            edge_rows.append(
                {
                    "derived_observable_id": record["derived_observable_id"],
                    "observable": record["observable"],
                    "central_nuclide_id": central,
                    "model_id": model_id,
                    "predicted_MeV": predicted,
                    "truth_MeV": observed,
                    "error_MeV": predicted - observed,
                    "sign_recovered": (predicted > 0) == (observed > 0),
                    "all_components_predicted_blind": True,
                }
            )
    edge_evaluable = bool(edge_rows)
    full_shell = audit["summary"]["full_shell_blind_evaluable"]
    full_shell_status = (
        "FULL_SHELL_BLIND_CRITERION_NOT_MET"
        if full_shell
        else "FULL_SHELL_BLIND_NOT_EVALUABLE"
    )
    derived_results = {
        "experiment_id": B003_BLIND_ID,
        "run_id": run.run_id,
        "audit_summary": audit["summary"],
        "edge_rows": edge_rows,
        "edge_structure_blind_result": (
            "PHYSICS_BLIND_EDGE_VALIDATION"
            if edge_evaluable
            else "EDGE_STRUCTURE_NOT_EVALUABLE"
        ),
        "full_shell_blind_result": full_shell_status,
        "rule": (
            "edge validation is not full shell rediscovery: the audited "
            "blind-eligible observables cover drip-side S2n edges only, and "
            "delta2n/delta2p/local_peak_rank dependencies are nonblind"
        ),
    }
    _write_json(dest / "derived_results.json", derived_results)
    run.advance("SCORED")

    adjudications = [
        build_adjudication(
            experiment_id=B003_BLIND_ID,
            run_id=run.run_id,
            benchmark_id="EZ-B003",
            claim_track=TRACK_BLIND,
            prediction_seal_hash=run.prediction_seal_hash,
            eligible_model_ids=sealed["model_ids"],
            excluded_model_ids=sorted(
                set(RECON_MODELS)
                | {"EZ-FED-UNIFORM-ENSEMBLE-v1", "EZ-FED-VALIDATION-WEIGHTED-v1"}
            ),
            physics_independence_groups=[BLIND_PHYSICS_FAMILY],
            claim_type="HISTORICAL_BLIND",
            scientific_scope=SCOPE_PHYSICS_BLIND_MASS_EDGE,
            inherited_criterion_status=mass_status,
            blind_gate_status="PHYSICS_BLIND_EVALUABLE",
            visual_stage_permission="BADGE_HB_ONLY_NO_STAGE_PROMOTION",
            next_gate=(
                "second independent blind physics family still missing; "
                "see WO-15"
            ),
        )
    ]
    if edge_evaluable:
        adjudications.append(
            build_adjudication(
                experiment_id=B003_BLIND_ID,
                run_id=run.run_id,
                benchmark_id="EZ-B003",
                claim_track=TRACK_BLIND,
                prediction_seal_hash=run.prediction_seal_hash,
                eligible_model_ids=sealed["model_ids"],
                excluded_model_ids=sorted(
                    set(RECON_MODELS)
                    | {"EZ-FED-UNIFORM-ENSEMBLE-v1", "EZ-FED-VALIDATION-WEIGHTED-v1"}
                ),
                physics_independence_groups=[BLIND_PHYSICS_FAMILY],
                claim_type="HISTORICAL_BLIND",
                scientific_scope=SCOPE_PHYSICS_BLIND_EDGE_STRUCTURE,
                inherited_criterion_status="PHYSICS_BLIND_EDGE_VALIDATION",
                blind_gate_status=full_shell_status,
                visual_stage_permission="BADGE_HB_ONLY_NO_STAGE_PROMOTION",
                next_gate=(
                    "full shell blind rediscovery requires blind "
                    "delta2n/delta2p/local_peak_rank dependencies; not "
                    "evaluable with this target set"
                ),
            )
        )
    _write_json(dest / "claim_adjudication.json", {"records": adjudications})
    run.advance("CLAIM_ADJUDICATED")
    _persist_run(dest, run)
    _rewrite_sha256sums(dest)
    return {
        "experiment_id": B003_BLIND_ID,
        "mass_status": mass_status,
        "edge_status": derived_results["edge_structure_blind_result"],
        "full_shell_status": full_shell_status,
        "best_blind_family_model": best_family,
    }


# --------------------------------------------------------------------------- #
# B003 REAL-RECON (frozen seal_b003 / score_b003 mechanics)                   #
# --------------------------------------------------------------------------- #

SCOPE_REAL_WO14 = "real-evaluated-data-wo14"


def seal_b003_recon(*, root: str | Path | None = None) -> dict[str, Any]:
    from elementzero.adjudication.benchmark_controls import control_model_registry
    from elementzero.experiments.b003_runner import seal_b003
    from elementzero.experiments.wo12_qualification import _b003_split_manifests

    root = Path(root or REPO_ROOT)
    source = verified_source(root)
    experiment_id = B003_RECON_ID
    challenges_path = root / "experiments" / experiment_id / "challenges.json"
    dest = _results_dir(root, experiment_id)

    registry = _registry(root)
    splits = _b003_split_manifests(chart=source, challenges_path=challenges_path)
    coverage = audit_roster_coverage(registry, RECON_MODELS, splits)
    recorder: dict[str, dict[str, dict[str, Any]]] = {}
    builders = _builders(registry, coverage["sealed_model_ids"], recorder)
    run = _new_run(root, experiment_id, TRACK_RECONSTRUCTION)
    with control_model_registry(builders):
        sealed = seal_b003(
            source=source,
            edition_id=EDITION_ID,
            challenges_path=challenges_path,
            experiment_dir=dest,
            scope=SCOPE_REAL_WO14,
            created_at=WO14_CREATED_AT,
            model_ids=tuple(coverage["sealed_model_ids"]),
        )
    run.advance("PREDICTIONS_GENERATED")
    run.advance("PREDICTIONS_FINALIZED")
    run.record_seal(sealed["sealed_predictions_sha256"])
    _write_json(dest / DECOMPOSITION_FILE, {"by_model": recorder})
    _seal_record(
        dest=dest,
        run=run,
        roster=RECON_MODELS,
        coverage=coverage,
        extras={
            "roster_rule": RECON_ROSTER_RULE,
            "excluded_models": RECON_EXCLUDED_MODELS,
        },
    )
    _persist_run(dest, run)
    _rewrite_sha256sums(dest)
    return {"experiment_id": experiment_id, "seal_hash": run.prediction_seal_hash}


def score_b003_recon(*, root: str | Path | None = None) -> dict[str, Any]:
    from elementzero.experiments.b003_runner import score_b003

    root = Path(root or REPO_ROOT)
    source = verified_source(root)
    experiment_id = B003_RECON_ID
    dest = _results_dir(root, experiment_id)
    run = _load_run(dest)
    if run.state != "SEALED_COMMIT_RECORDED":
        raise ProtocolError(
            f"{experiment_id} is {run.state}; scoring requires "
            "SEALED_COMMIT_RECORDED — commit the seal first"
        )
    claim = _claim_manifest(root, experiment_id)
    sealed = read_json(dest / SEALED_PREDICTIONS_FILE)
    sealed_target_ids: list[str] = []
    for entry in sealed["challenges"]:
        targets = read_json(dest / entry["challenge_relpath"] / "targets.json")
        sealed_target_ids.extend(t["nuclide_id"] for t in targets["targets"])
    unlock = unlock_truth(
        seal_dir=dest,
        # Expected = the hash finalization persisted, never re-read from
        # the seal directory.
        expected_seal_hash=run.prediction_seal_hash,
        eligibility_manifest_hash=_eligibility_hashes(root)[experiment_id],
        expected_eligibility_hash=claim["eligibility_manifest_hash"],
        threshold_hash=_threshold_hash(root, experiment_id),
        expected_threshold_hash=claim["threshold_manifest_hash"],
        registry_hash=_registry(root).manifest()["registry_hash"],
        expected_registry_hash=WO12_REGISTRY_HASH,
        protocol_hash=read_json(root / "experiments/EZ-B003-v2/PROTOCOL.json")[
            "protocol_hash"
        ],
        expected_protocol_hash=WO12_PROTOCOL_HASH,
        target_identity_digest=identity_digest(sorted(set(sealed_target_ids))),
        expected_target_identity_digest=identity_digest(
            _preregistered_target_ids(root, experiment_id)
        ),
    )
    _write_json(dest / TRUTH_UNLOCK_FILE, unlock)
    run.advance("TRUTH_UNLOCKED")
    score_b003(
        source=source,
        edition_id=EDITION_ID,
        experiment_dir=dest,
        created_at=WO14_CREATED_AT,
    )
    run.advance("SCORED")

    aggregate = read_json(dest / "shell_aggregate.json")
    by_model: dict[str, Any] = {}
    for model_id, payload in aggregate["by_model"].items():
        checks = payload["criterion"]["checks"]
        verdict = payload["criterion"]["verdict"]
        by_model[model_id] = {
            "verdict": verdict,
            "recon_status": (
                "RECONSTRUCTION_CRITERION_MET"
                if verdict == "CRITERION_MET"
                else "RECONSTRUCTION_CRITERION_NOT_MET"
            ),
            "checks": {
                name: {
                    "observed": check["observed"],
                    "threshold": check.get("threshold"),
                    "met": check.get("met"),
                }
                for name, check in checks.items()
            },
            "pooled_mass": payload.get("pooled_mass"),
            "per_closure": payload.get("per_closure"),
        }
    met_models = sorted(
        m for m, p in by_model.items() if p["verdict"] == "CRITERION_MET"
    )
    recon_status = (
        "B003_RECON_CRITERION_MET" if met_models else "B003_RECON_CRITERION_NOT_MET"
    )
    # Model-family disagreement from the sealed (pre-truth) predictions:
    # per challenge, |table - table+residual| over the shared targets.
    decomposition = read_json(dest / DECOMPOSITION_FILE)["by_model"]
    disagreement: dict[str, Any] = {}
    model_ids = sorted(decomposition)
    if len(model_ids) == 2:
        first, second = model_ids
        for fit_digest, first_rows in decomposition[first].items():
            second_rows = decomposition[second].get(fit_digest, {})
            deltas = [
                abs(
                    float(first_rows[nuclide]["point_keV"])
                    - float(second_rows[nuclide]["point_keV"])
                )
                for nuclide in first_rows
                if nuclide in second_rows
            ]
            if deltas:
                disagreement[fit_digest] = {
                    "n": len(deltas),
                    "mean_abs_keV": sum(deltas) / len(deltas),
                    "max_abs_keV": max(deltas),
                }
    closure_results = {
        "experiment_id": experiment_id,
        "run_id": run.run_id,
        "claim_track": run.claim_track,
        "scientific_scope": SCOPE_RECONSTRUCTION_SHELL_STRUCTURE,
        "truth_edition": EDITION_ID,
        "by_model": dict(sorted(by_model.items())),
        "models_meeting_criterion": met_models,
        "status": recon_status,
        "model_family_disagreement": {
            "rule": (
                "per fitted split, mean/max absolute difference between the "
                "two reconstruction lineage members over shared targets, "
                "computed from the sealed predictions"
            ),
            "by_fit_digest": disagreement,
        },
        "roster_rule": RECON_ROSTER_RULE,
        "excluded_models": RECON_EXCLUDED_MODELS,
        "rule": (
            "RECONSTRUCTION_CRITERION_MET is reference evidence about known "
            "structure; BLIND_REDISCOVERY_CRITERION_MET can only be earned "
            "by the BLIND track, which this run is not"
        ),
    }
    _write_json(dest / "closure_results.json", closure_results)
    _write_json(
        dest / "model_comparison.json",
        {
            "experiment_id": experiment_id,
            "columns": [
                "model_id",
                "verdict",
                "sign_fraction",
                "top_k_fraction",
                "rank_1_fraction",
                "calibration_error_90",
            ],
            "rows": [
                {
                    "model_id": model_id,
                    "verdict": payload["verdict"],
                    "sign_fraction": payload["checks"]["sign_fraction"]["observed"],
                    "top_k_fraction": payload["checks"]["top_k_fraction"]["observed"],
                    "rank_1_fraction": payload["checks"]["rank_1_fraction"][
                        "observed"
                    ],
                    "calibration_error_90": payload["checks"][
                        "calibration_error_90"
                    ]["observed"],
                }
                for model_id, payload in sorted(by_model.items())
            ],
            "ranking_rule": (
                "every frozen check is reported for every model; the verdict "
                "is the frozen criterion's, not a ranking"
            ),
        },
    )
    adjudication = build_adjudication(
        experiment_id=experiment_id,
        run_id=run.run_id,
        benchmark_id="EZ-B003",
        claim_track=TRACK_RECONSTRUCTION,
        prediction_seal_hash=run.prediction_seal_hash,
        eligible_model_ids=list(by_model),
        excluded_model_ids=sorted(RECON_EXCLUDED_MODELS),
        physics_independence_groups=["skyrme_edf_bskg"],
        claim_type="RECONSTRUCTION_REFERENCE",
        scientific_scope=SCOPE_RECONSTRUCTION_SHELL_STRUCTURE,
        inherited_criterion_status=recon_status,
        blind_gate_status="NOT_APPLICABLE_RECONSTRUCTION_TRACK",
        visual_stage_permission="BADGE_R_ONLY_NO_STAGE_PROMOTION",
        next_gate=(
            "reconstruction of known structure never becomes rediscovery; "
            "blind shell credit requires the BLIND track"
        ),
    )
    _write_json(dest / "claim_adjudication.json", {"records": [adjudication]})
    run.advance("CLAIM_ADJUDICATED")
    _persist_run(dest, run)
    _rewrite_sha256sums(dest)
    return {
        "experiment_id": experiment_id,
        "status": recon_status,
        "models_meeting_criterion": met_models,
    }
