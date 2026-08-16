"""WO-11.1 / WO-11.2 — freeze the v0.3 evidence baseline and replay it.

Two jobs, both read-only with respect to the committed v1 experiments:

1. ``build_artifact_inventory`` walks the frozen evidence (EZ-B001-A/B/C,
   EZ-B002-v1, EZ-B003-v1, the historical report) and records every recorded
   hash next to a freshly recomputed one. The inventory is the immutable input
   to the rest of WO-11: if any recorded hash no longer matches its recomputed
   value, WO-11 stops.

2. ``replay_b002`` / ``replay_b003`` copy a sealed experiment into a separate
   workspace and re-run only the frozen *scoring* stage on the sealed
   predictions — never ``model.fit()``. A fit tripwire is armed during replay,
   so a scoring path that tried to refit would raise instead of silently
   producing new predictions.

Replay comparison levels:

    frozen-metric level   every scoring/metrics.json byte-identical, every
                          aggregate equal after volatile evidence-bookkeeping
                          ids are stripped, every frozen criterion verdict
                          identical. This is the scientific replay claim and it
                          must hold in every environment.

    strict byte level     every regenerated file byte-identical, including raw
                          IEEE floats inside Atlas fact payloads. This holds
                          when the interpreter matches the recorded
                          environment (the v1 runs recorded CPython 3.12); a
                          different libm may move those raw floats by one ULP
                          without moving any 12-significant-digit metric.
"""

from __future__ import annotations

import contextlib
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from elementzero import __version__ as elementzero_version
from elementzero.adjudication import INPUT_RELEASE, WO11_ID
from elementzero.atlas_pin import REPO_ROOT, atlas_pir_ref
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import read_json
from elementzero.experiments.runner import verify_sha256sums
from elementzero.models import gp_residual

ARTIFACT_INVENTORY_FILE = "artifact_inventory.json"

# The v0.3 evidence baseline: the WO-10 head commit this adjudication reads.
# It is pinned as a string on purpose — the inventory describes the frozen
# baseline, not whatever HEAD the adjudication code happens to run from.
BASELINE_COMMIT = "9baee722c49296e681cf53da63f31a36bb6ab2f6"

B001_EPOCHS = ("EZ-B001-A", "EZ-B001-B", "EZ-B001-C")
B002_EXPERIMENT = "EZ-B002-v1"
B003_EXPERIMENT = "EZ-B003-v1"

# Source files whose byte hashes pin the model / metric implementations the
# v1 evidence was produced with.
MODEL_IMPLEMENTATION_FILES = (
    "src/elementzero/models/gp_residual.py",
    "src/elementzero/models/protocol.py",
    "src/elementzero/physics/semf.py",
    "src/elementzero/benchmark/metrics.py",
    "src/elementzero/benchmark/shell_metrics.py",
    "src/elementzero/benchmark/distance.py",
)

IMMUTABILITY_RULE = (
    "The v1 experiments are frozen historical evidence. WO-11 reads them and "
    "replays them into separate workspaces; it never rewrites, relaxes, or "
    "reruns them under the same protocol. A changed hash below is a stop "
    "condition for the whole work order."
)

# Volatile keys inside regenerated scoring artifacts: content-addressed Atlas
# evidence-bookkeeping ids over raw IEEE float payloads. They are compared at
# the strict byte level only; the frozen-metric comparison strips them, because
# every scientific number they bracket is fixed to 12 significant digits.
VOLATILE_REPLAY_KEYS = frozenset(
    {
        "atlas_bundle_hashes",
        "validation_fact_id",
        "finalization_fact_id",
        "truth_dataset_fact_id",
        "derived_observable_fact_ids",
        "shell_discovery_fact_id",
        "shell_hypothesis_fact_id",
        "fact_id",
        "derived_from_facts",
    }
)


# --------------------------------------------------------------------------- #
# Inventory (WO-11.1)                                                         #
# --------------------------------------------------------------------------- #


def _recorded_hash(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _hash_pair(recorded_file: Path, subject_file: Path) -> dict[str, Any]:
    recorded = _recorded_hash(recorded_file)
    recomputed = sha256_file(subject_file)
    return {
        "file": subject_file.name,
        "recorded_sha256": recorded,
        "recomputed_sha256": recomputed,
        "unchanged": recorded == recomputed,
    }


def _b001_epoch_entry(root: Path) -> dict[str, Any]:
    from elementzero.experiments.preregister import (
        preregistration_hash,
        read_preregistration_hash,
    )

    recorded_prereg = read_preregistration_hash(root)
    recomputed_prereg = preregistration_hash(root)
    entry = {
        # ez-prereg-hash-v1: the recorded hash covers the five frozen protocol
        # JSON files, not the prose PREREGISTRATION.md (which is hashed via
        # SHA256SUMS.txt instead).
        "preregistration": {
            "file": "PREREGISTRATION_SHA256",
            "recorded_sha256": recorded_prereg,
            "recomputed_sha256": recomputed_prereg,
            "unchanged": recorded_prereg == recomputed_prereg,
        },
        "sealed_predictions": _hash_pair(
            root / "SEALED_PREDICTIONS_SHA256", root / "SEALED_PREDICTIONS.json"
        ),
        "model_comparison_sha256": sha256_file(root / "model_comparison.json"),
        "score_manifest_sha256": sha256_file(root / "SCORE_MANIFEST.json"),
        "run_manifest_sha256": sha256_file(root / "RUN_MANIFEST.json"),
        "sha256sums_ok": bool(verify_sha256sums(root)["ok"]),
    }
    return entry


def _b002_entry(root: Path) -> dict[str, Any]:
    run_manifest = read_json(root / "RUN_MANIFEST.json")
    aggregate = read_json(root / "region_aggregate.json")
    return {
        "protocol_version": run_manifest["protocol_version"],
        "regions": _hash_pair(root / "REGIONS_SHA256", root / "regions.json"),
        "sealed_predictions": _hash_pair(
            root / "SEALED_PREDICTIONS_SHA256", root / "SEALED_PREDICTIONS.json"
        ),
        # EZ-B002 v1 froze the *absence* of an accuracy criterion: the
        # characterization rule is the frozen protocol object, and its hash is
        # what a later protocol version would have to move.
        "frozen_criterion": {
            "criterion_id": "ez-b002-v1-no-accuracy-threshold",
            "no_threshold_rule": run_manifest["no_threshold_rule"],
            "no_threshold_rule_sha256": sha256_hex(run_manifest["no_threshold_rule"]),
        },
        "score_manifest_sha256": sha256_file(root / "SCORE_MANIFEST.json"),
        "region_aggregate_sha256": sha256_file(root / "region_aggregate.json"),
        "sha256sums_ok": bool(verify_sha256sums(root)["ok"]),
        "status": "ENGINEERING_PASS_CHARACTERIZATION",
        "status_note": (
            "EZ-B002 v1 preregistered no accuracy pass/fail threshold; its "
            "committed result is characterization evidence, and the observed "
            "weaknesses (SEMF-LS undercoverage, GP overcoverage, GP MAE) are "
            "adjudicated in the WO-11 failure records without inventing a "
            "criterion after the fact."
        ),
        "seal_commit": aggregate["elementzero_commit"],
        "n_scored_targets": aggregate["n_scored_targets"],
        "model_ids": list(aggregate["model_ids"]),
        "region_ids": list(aggregate["region_ids"]),
    }


def _b003_entry(root: Path) -> dict[str, Any]:
    criterion = read_json(root / "CRITERION.json")
    aggregate = read_json(root / "shell_aggregate.json")
    verdicts = {
        model_id: payload["criterion"]["verdict"]
        for model_id, payload in sorted(aggregate["by_model"].items())
    }
    return {
        "protocol_version": criterion["protocol_version"],
        "challenges": _hash_pair(root / "CHALLENGES_SHA256", root / "challenges.json"),
        "sealed_predictions": _hash_pair(
            root / "SEALED_PREDICTIONS_SHA256", root / "SEALED_PREDICTIONS.json"
        ),
        "frozen_criterion": {
            **_hash_pair(root / "CRITERION_SHA256", root / "CRITERION.json"),
            "criterion_id": criterion["criterion_id"],
            "criterion_digest": criterion["criterion_digest"],
            "thresholds": {
                "min_sign_fraction": criterion["criterion"]["min_sign_fraction"],
                "min_top_k_fraction": criterion["criterion"]["min_top_k_fraction"],
                "min_rank_1_fraction": criterion["criterion"]["min_rank_1_fraction"],
                "max_calibration_error_90": criterion["criterion"]["max_calibration_error_90"],
            },
        },
        "score_manifest_sha256": sha256_file(root / "SCORE_MANIFEST.json"),
        "shell_aggregate_sha256": sha256_file(root / "shell_aggregate.json"),
        "sha256sums_ok": bool(verify_sha256sums(root)["ok"]),
        "status": "CRITERION_NOT_MET_ALL_BASELINES",
        "verdicts": verdicts,
        "scope": aggregate["scope"],
        "evaluated_mass_table_verdict": criterion["evaluated_mass_table_verdict"],
        "seal_commit": aggregate["elementzero_commit"],
        "n_scored_targets": aggregate["n_scored_targets"],
        "model_ids": list(aggregate["model_ids"]),
        "challenge_ids": list(aggregate["challenge_ids"]),
        "not_evaluable_closures": [
            {"challenge_id": c["challenge_id"], "reasons": list(c["reasons"])}
            for c in aggregate["not_evaluable_closures"]
        ],
    }


def build_artifact_inventory(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    """The frozen v0.3 evidence inventory. Deterministic: no timestamps."""
    root = Path(repo_root or REPO_ROOT)
    experiments_root = root / "experiments"
    inventory: dict[str, Any] = {
        "work_order": WO11_ID,
        "input_release": INPUT_RELEASE,
        "baseline_commit": BASELINE_COMMIT,
        "immutability_rule": IMMUTABILITY_RULE,
        "elementzero_version": elementzero_version,
        "atlas_pir_ref": atlas_pir_ref(),
        "parser_version": PARSER_VERSION,
        "model_implementation_hashes": {
            relpath: sha256_file(root / relpath) for relpath in MODEL_IMPLEMENTATION_FILES
        },
        "experiments": {},
    }
    for epoch in B001_EPOCHS:
        inventory["experiments"][epoch] = _b001_epoch_entry(experiments_root / epoch)
    inventory["experiments"][B002_EXPERIMENT] = _b002_entry(experiments_root / B002_EXPERIMENT)
    inventory["experiments"][B003_EXPERIMENT] = _b003_entry(experiments_root / B003_EXPERIMENT)
    historical = root / "reports" / "historical" / "v1"
    inventory["historical_report"] = {
        "report_sha256": sha256_file(historical / "ElementZero_Historical_Benchmark_Report_v1.md"),
        "benchmark_status_sha256": sha256_file(historical / "benchmark_status.json"),
        "aggregate_metrics_sha256": sha256_file(historical / "aggregate_metrics.json"),
    }
    inventory["all_unchanged"] = _all_unchanged(inventory)
    return inventory


def _all_unchanged(inventory: dict[str, Any]) -> bool:
    for entry in inventory["experiments"].values():
        if not entry["sha256sums_ok"]:
            return False
        for key in ("preregistration", "sealed_predictions", "regions", "challenges"):
            pair = entry.get(key)
            if pair is not None and not pair["unchanged"]:
                return False
        frozen = entry.get("frozen_criterion")
        if frozen is not None and frozen.get("unchanged") is False:
            return False
    return True


def assert_v1_evidence_unchanged(inventory: dict[str, Any]) -> None:
    """Stop condition: any moved v1 hash halts the whole adjudication."""
    if not inventory["all_unchanged"]:
        raise ProtocolError(
            "a frozen v1 artifact hash no longer matches its recorded value; "
            "WO-11 stops here (integrity defect, not a scientific diagnosis)"
        )


def write_artifact_inventory(
    *, out_dir: str | Path, repo_root: str | Path | None = None
) -> dict[str, Any]:
    inventory = build_artifact_inventory(repo_root=repo_root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / ARTIFACT_INVENTORY_FILE).write_text(
        canonical_json(inventory) + "\n", encoding="utf-8"
    )
    return inventory


# --------------------------------------------------------------------------- #
# Fit tripwire (WO-11.2: replay must not refit)                               #
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def forbid_model_fitting():
    """Arm a tripwire: any model construction or fit during replay raises."""

    def _refuse_build(model_id: str):
        raise ProtocolError(
            f"WO-11 replay tried to build model {model_id!r}; replay scores "
            "sealed predictions and must never refit"
        )

    def _refuse_fit(self, observations):  # noqa: ARG001 - signature parity
        raise ProtocolError(
            "WO-11 replay tried to call model.fit(); replay scores sealed "
            "predictions and must never refit"
        )

    from elementzero.benchmark import b001_predict, b002_predict, b003_predict

    # The class-level fit tripwire covers every construction path; the
    # build_model bindings are patched in every consumer module as well,
    # because ``from ... import build_model`` copies the reference.
    modules = (gp_residual, b001_predict, b002_predict, b003_predict)
    saved_builds = {module: module.build_model for module in modules}
    saved_fits = {
        cls: cls.fit
        for cls in (
            gp_residual.SEMFLeastSquaresModel,
            gp_residual.GPDirectModel,
            gp_residual.SEMFGPResidualModel,
        )
    }
    for module in modules:
        module.build_model = _refuse_build
    for cls in saved_fits:
        cls.fit = _refuse_fit
    try:
        yield
    finally:
        for module, build in saved_builds.items():
            module.build_model = build
        for cls, fit in saved_fits.items():
            cls.fit = fit


@contextlib.contextmanager
def _pinned_commit(commit: str):
    """Replay under the commit id the sealed run recorded, then restore."""
    saved = os.environ.get("ELEMENTZERO_COMMIT")
    os.environ["ELEMENTZERO_COMMIT"] = commit
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("ELEMENTZERO_COMMIT", None)
        else:
            os.environ["ELEMENTZERO_COMMIT"] = saved


# --------------------------------------------------------------------------- #
# Replay (WO-11.2)                                                            #
# --------------------------------------------------------------------------- #


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            key: _strip_volatile(value)
            for key, value in obj.items()
            if key not in VOLATILE_REPLAY_KEYS
        }
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# Derived checksum indexes: their bytes change whenever any file they index
# changes, so they carry no scientific content of their own. They participate
# in the strict byte comparison only.
BOOKKEEPING_BASENAMES = frozenset({"SHA256SUMS.txt", "SCORE_MANIFEST.json"})


def _compare_trees(committed: Path, replayed: Path) -> dict[str, Any]:
    a, b = _tree_hashes(committed), _tree_hashes(replayed)
    differing = sorted(k for k in a if k in b and a[k] != b[k])
    missing = sorted(k for k in a if k not in b)
    metrics_files = sorted(k for k in a if k.endswith("metrics.json"))
    metrics_identical = [k for k in metrics_files if a.get(k) == b.get(k)]
    frozen_metric_differences = []
    for rel in differing:
        # Atlas fact bundles serialize raw IEEE floats and content-address
        # them; every scientific number they carry is compared through the
        # canonically formatted scoring artifacts instead.
        if Path(rel).name in BOOKKEEPING_BASENAMES or "atlas/" in rel:
            continue
        if not rel.endswith(".json"):
            frozen_metric_differences.append(rel)
            continue
        committed_payload = read_json(committed / rel)
        replayed_payload = read_json(replayed / rel)
        if canonical_json(_strip_volatile(committed_payload)) != canonical_json(
            _strip_volatile(replayed_payload)
        ):
            frozen_metric_differences.append(rel)
    return {
        "n_files": len(a),
        "n_identical": sum(1 for k in a if b.get(k) == a[k]),
        "differing_files": differing,
        "missing_files": missing,
        "metrics_files": len(metrics_files),
        "metrics_files_identical": len(metrics_identical),
        "strict_byte_identical": not differing and not missing,
        "frozen_metrics_identical": (
            not missing
            and len(metrics_identical) == len(metrics_files)
            and not frozen_metric_differences
        ),
        "frozen_metric_differences": frozen_metric_differences,
    }


def _replay_environment() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
    }


def replay_b002(
    *,
    committed_dir: str | Path,
    workspace_dir: str | Path,
    snapshot: str | Path,
    edition_id: str = "AME2020",
) -> dict[str, Any]:
    """Re-score the sealed EZ-B002-v1 runs in a workspace copy, no refitting."""
    from elementzero.experiments.b002_runner import score_b002

    committed = Path(committed_dir)
    workspace = Path(workspace_dir)
    if workspace.resolve() == committed.resolve():
        raise ProtocolError("replay must write into a separate workspace, never the v1 evidence")
    if workspace.exists():
        raise ProtocolError(f"replay workspace {workspace} already exists; refusing to overwrite")
    shutil.copytree(committed, workspace)
    score_manifest = read_json(committed / "SCORE_MANIFEST.json")
    with _pinned_commit(score_manifest["elementzero_commit"]), forbid_model_fitting():
        score_b002(
            source=snapshot,
            edition_id=edition_id,
            experiment_dir=workspace,
            created_at=score_manifest["created_at"],
        )
    comparison = _compare_trees(committed, workspace)
    replayed_aggregate = read_json(workspace / "region_aggregate.json")
    committed_aggregate = read_json(committed / "region_aggregate.json")
    return {
        "benchmark_id": "EZ-B002",
        "experiment": committed.name,
        "environment": _replay_environment(),
        "comparison": comparison,
        "aggregate_values_identical": canonical_json(_strip_volatile(committed_aggregate))
        == canonical_json(_strip_volatile(replayed_aggregate)),
        "replay_status": "PASS" if comparison["frozen_metrics_identical"] else "FAIL",
    }


def replay_b003(
    *,
    committed_dir: str | Path,
    workspace_dir: str | Path,
    snapshot: str | Path,
    edition_id: str = "AME2020",
) -> dict[str, Any]:
    """Re-score the sealed EZ-B003-v1 runs in a workspace copy, no refitting."""
    from elementzero.experiments.b003_runner import score_b003

    committed = Path(committed_dir)
    workspace = Path(workspace_dir)
    if workspace.resolve() == committed.resolve():
        raise ProtocolError("replay must write into a separate workspace, never the v1 evidence")
    if workspace.exists():
        raise ProtocolError(f"replay workspace {workspace} already exists; refusing to overwrite")
    shutil.copytree(committed, workspace)
    score_manifest = read_json(committed / "SCORE_MANIFEST.json")
    with _pinned_commit(score_manifest["elementzero_commit"]), forbid_model_fitting():
        score_b003(
            source=snapshot,
            edition_id=edition_id,
            experiment_dir=workspace,
            created_at=score_manifest["created_at"],
        )
    comparison = _compare_trees(committed, workspace)
    committed_aggregate = read_json(committed / "shell_aggregate.json")
    replayed_aggregate = read_json(workspace / "shell_aggregate.json")
    committed_verdicts = {
        m: p["criterion"]["verdict"] for m, p in committed_aggregate["by_model"].items()
    }
    replayed_verdicts = {
        m: p["criterion"]["verdict"] for m, p in replayed_aggregate["by_model"].items()
    }
    return {
        "benchmark_id": "EZ-B003",
        "experiment": committed.name,
        "environment": _replay_environment(),
        "comparison": comparison,
        "aggregate_values_identical": canonical_json(_strip_volatile(committed_aggregate))
        == canonical_json(_strip_volatile(replayed_aggregate)),
        "committed_verdicts": committed_verdicts,
        "replayed_verdicts": replayed_verdicts,
        "verdicts_identical": committed_verdicts == replayed_verdicts,
        "replay_status": (
            "PASS"
            if comparison["frozen_metrics_identical"] and committed_verdicts == replayed_verdicts
            else "FAIL"
        ),
    }


def replay_all(
    *,
    workspace_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Replay both frozen benchmarks; the combined status gates the verdict."""
    root = Path(repo_root or REPO_ROOT)
    workspace = Path(workspace_root)
    b002 = replay_b002(
        committed_dir=root / "experiments" / B002_EXPERIMENT,
        workspace_dir=workspace / B002_EXPERIMENT,
        snapshot=root / "tests" / "fixtures" / "b002" / "synthetic_chart_v1.mas20",
    )
    b003 = replay_b003(
        committed_dir=root / "experiments" / B003_EXPERIMENT,
        workspace_dir=workspace / B003_EXPERIMENT,
        snapshot=root / "tests" / "fixtures" / "b003" / "synthetic_shell_chart_v1.mas20",
    )
    status = "PASS" if b002["replay_status"] == b003["replay_status"] == "PASS" else "FAIL"
    return {
        "replay_status": status,
        "no_refit_rule": (
            "Replay re-runs only the frozen scoring stage on the sealed "
            "predictions with a fit tripwire armed; a replay that needed "
            "model.fit() would raise ProtocolError instead of reproducing."
        ),
        "EZ-B002-v1": b002,
        "EZ-B003-v1": b003,
    }
