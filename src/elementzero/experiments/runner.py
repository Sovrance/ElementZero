"""Execute and seal one preregistered EZ-B001 epoch (WO-06).

Two commands, in this order, with a git commit between them:

    seal_experiment(...)    phases 0-7: audit, targets, freeze, blind predict,
                            finalize, experiment-level sealed manifest
    score_experiment(...)   phases 9-10: truth unlock, metrics, Atlas validation,
                            model comparison

The split is the protocol, not a convenience: predictions must be committed
before any later-edition truth is read, and a sealed run may never be refit.

Artifact layout under ``experiments/<experiment_id>/`` (WO-06 writes the same
content the work order lists under ``runs/`` and ``results/``, kept together per
experiment so one directory is one auditable unit):

    data_audit/<edition>_parse_report.json
    targets.json                  identity-only target manifest
    targets_digest.json           target identity digest and manifest hash
    freeze.json                   KnowledgeFreeze
    environment.json              interpreter, libraries, commits, verification
    runs/model_suite.json         the sealed suite manifest
    runs/<model_id>/              predictions, certificates, Atlas bundle, seal
    runs/<model_id>/scoring/      metrics, score report, scored predictions
    SEALED_PREDICTIONS.json       experiment-level seal, written before scoring
    SEALED_PREDICTIONS_SHA256
    RUN_MANIFEST.json             seal-phase manifest
    SCORE_MANIFEST.json           score-phase manifest
    model_comparison.json/.md     every model, every metric, no ranking
    SHA256SUMS.txt
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_EZ_B001, BENCHMARK_PROTOCOL_VERSION, __version__
from elementzero.atlas_pin import REPO_ROOT, atlas_pir_ref
from elementzero.benchmark.b001_freeze import freeze_training, load_freeze
from elementzero.benchmark.b001_predict import load_targets
from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.b001_score import score_run
from elementzero.benchmark.model_suite import (
    COMPARISON_JSON_NAME,
    COMPARISON_MARKDOWN_NAME,
    SUITE_MANIFEST_NAME,
    build_comparison,
    comparison_markdown,
    run_suite,
)
from elementzero.data.amdc import EDITIONS
from elementzero.data.amdc.common import (
    DEFAULT_MALFORMED_FRACTION_LIMIT,
    PARSER_VERSION,
    parse_ame_mass_table_detailed,
)
from elementzero.data.observations import GROUND_TRUTH_POLICY
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import finalization_marker_hash, read_json
from elementzero.experiments.epochs import EpochSpec, truth_filenames
from elementzero.experiments.preregister import (
    EXPERIMENT_PROTOCOL_VERSION,
    PREREGISTRATION_FILES,
    PREREGISTRATION_HASH_FILE,
    PREREGISTRATION_MARKDOWN,
    PROTOCOL_FILE,
    assert_protocol_code_unchanged,
    load_preregistration,
    read_preregistration_hash,
    validate_preregistration,
)
from elementzero.identity_meta import elementzero_commit, runtime_library_versions

DATA_AUDIT_DIRNAME = "data_audit"
RUNS_DIRNAME = "runs"
SCORING_DIRNAME = "scoring"
TARGETS_FILE = "targets.json"
TARGETS_DIGEST_FILE = "targets_digest.json"
FREEZE_FILE = "freeze.json"
ENVIRONMENT_FILE = "environment.json"
RUN_MANIFEST_FILE = "RUN_MANIFEST.json"
SCORE_MANIFEST_FILE = "SCORE_MANIFEST.json"
SEALED_PREDICTIONS_FILE = "SEALED_PREDICTIONS.json"
SEALED_PREDICTIONS_HASH_FILE = "SEALED_PREDICTIONS_SHA256"
SCORED_PREDICTIONS_FILE = "scored_predictions.json"
SHA256SUMS_FILE = "SHA256SUMS.txt"

VERIFICATION_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("ruff", "check", "src", "tests"),
    (sys.executable, "-m", "pytest", "-q"),
)


# --------------------------------------------------------------------------- #
# Phase 0 - environment                                                       #
# --------------------------------------------------------------------------- #


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain_text(text: str) -> str:
    """Committed evidence stays terminal-agnostic: drop ANSI colour codes."""
    return _ANSI_RE.sub("", text).strip()


def _tail(result: subprocess.CompletedProcess[str], lines: int = 1) -> list[str]:
    stream = (result.stdout or result.stderr or "").strip().splitlines()
    return stream[-lines:] if stream else [""]


def environment_report(
    *,
    experiment_dir: str | Path,
    epoch: EpochSpec,
    preregistration_hash: str,
    root: str | Path | None = None,
    verify: bool = False,
) -> dict[str, Any]:
    """Interpreter, library, and commit identity, plus phase-0 verification."""
    versions = runtime_library_versions()
    verification: list[dict[str, Any]] = []
    for command in VERIFICATION_COMMANDS:
        if not verify:
            verification.append({"command": " ".join(command), "status": "not_executed"})
            continue
        result = subprocess.run(
            list(command), cwd=str(root or REPO_ROOT), capture_output=True, text=True, check=False
        )
        verification.append(
            {
                "command": " ".join(command),
                "status": "pass" if result.returncode == 0 else "fail",
                "returncode": result.returncode,
                "tail": [_plain_text(line) for line in _tail(result)],
            }
        )
        if result.returncode != 0:
            raise ProtocolError(
                f"phase 0 verification failed: {' '.join(command)} exited {result.returncode}"
            )
    return {
        "experiment_id": epoch.experiment_id,
        "benchmark_id": BENCHMARK_EZ_B001,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "preregistration_hash": preregistration_hash,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "library_versions": versions,
        "elementzero_version": __version__,
        "elementzero_commit": elementzero_commit(),
        "atlas_pir_ref": atlas_pir_ref(),
        "parser_version": PARSER_VERSION,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "created_at": epoch.created_at,
        "verification": verification,
    }


# --------------------------------------------------------------------------- #
# Phase 1 - parser certification                                              #
# --------------------------------------------------------------------------- #


def parse_report_name(edition_id: str) -> str:
    return f"{edition_id.lower()}_parse_report.json"


def certify_source(
    *,
    edition_id: str,
    path: str | Path,
    expected_sha256: str,
    malformed_fraction_limit: float = DEFAULT_MALFORMED_FRACTION_LIMIT,
) -> dict[str, Any]:
    """Parse one official source and prove the report is usable as evidence."""
    spec = EDITIONS[edition_id][0]
    observations, report = parse_ame_mass_table_detailed(
        path, spec, malformed_fraction_limit=malformed_fraction_limit
    )
    payload = report.to_dict()
    if payload["raw_source_hash"] != expected_sha256:
        raise ProtocolError(
            f"{edition_id} raw sha256 {payload['raw_source_hash']} does not match the "
            f"preregistered {expected_sha256}"
        )
    if payload["parsed_records"] <= 0:
        raise ProtocolError(f"{edition_id} parsed no records")
    if payload["eligible_records"] <= 0:
        raise ProtocolError(f"{edition_id} has no ground-truth eligible records")
    if payload["invalid_A_equals_Z_plus_N"] != 0:
        raise ProtocolError(
            f"{edition_id} has {payload['invalid_A_equals_Z_plus_N']} rows where A != Z + N"
        )
    if report.malformed_fraction > malformed_fraction_limit:
        raise ProtocolError(f"{edition_id} malformed fraction {report.malformed_fraction} is too high")
    bad = [o.nuclide_id for o in observations if o.A != o.Z + o.N]
    if bad:
        raise ProtocolError(f"{edition_id} normalized records violate A == Z + N: {bad[:5]}")
    payload.update(
        {
            "edition_id": edition_id,
            "raw_filename": Path(path).name,
            "release_date": spec.release_date,
            "malformed_fraction": report.malformed_fraction,
            "malformed_fraction_limit": malformed_fraction_limit,
            "ground_truth_policy": GROUND_TRUTH_POLICY,
            "eligible_fraction": payload["eligible_records"] / payload["parsed_records"],
        }
    )
    return payload


def write_data_audit(
    *,
    experiment_dir: Path,
    epoch: EpochSpec,
    training_source: Path,
    truth_source: Path,
    training_sha256: str,
    truth_sha256: str,
) -> dict[str, Any]:
    audit_dir = experiment_dir / DATA_AUDIT_DIRNAME
    audit_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    for edition_id, path, expected in (
        (epoch.training_edition, training_source, training_sha256),
        (epoch.truth_edition, truth_source, truth_sha256),
    ):
        report = certify_source(edition_id=edition_id, path=path, expected_sha256=expected)
        # The audit records counts and hashes. It records no mass value.
        (audit_dir / parse_report_name(edition_id)).write_text(
            canonical_json(report) + "\n", encoding="utf-8"
        )
        reports[edition_id] = report
    return reports


# --------------------------------------------------------------------------- #
# Phase 2/3 - identity-only targets and the freeze                            #
# --------------------------------------------------------------------------- #


def write_targets(
    *,
    experiment_dir: Path,
    epoch: EpochSpec,
    training_source: Path,
    truth_source: Path,
) -> dict[str, Any]:
    """Preparation may read both editions; the output is identities only."""
    targets_path = experiment_dir / TARGETS_FILE
    manifest = prepare_targets(
        later_source=truth_source,
        edition_id=epoch.truth_edition,
        output=targets_path,
        known_source=training_source,
        known_edition_id=epoch.training_edition,
    )
    # Re-read through the leakage-checked loader: what is on disk is what counts.
    targets = load_targets(targets_path)
    if not targets:
        raise ProtocolError(
            f"{epoch.experiment_id} has no targets; the later edition added no eligible nuclide"
        )
    for target in targets:
        if set(target) != {"nuclide_id", "Z", "N", "A"}:
            raise LeakageError(f"target record is not identity-only: {sorted(target)}")
    target_ids = [t["nuclide_id"] for t in targets]
    digest = identity_digest(target_ids)
    payload = {
        "experiment_id": epoch.experiment_id,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "n_targets": len(targets),
        "target_identity_digest": digest,
        "target_manifest_sha256": sha256_file(targets_path),
        "target_manifest_fields": ["nuclide_id", "Z", "N", "A"],
        "training_edition": epoch.training_edition,
        "later_edition": epoch.truth_edition,
    }
    (experiment_dir / TARGETS_DIGEST_FILE).write_text(
        canonical_json(payload) + "\n", encoding="utf-8"
    )
    return {"targets": targets, "digest": digest, "manifest": manifest, "summary": payload}


def write_freeze(
    *,
    experiment_dir: Path,
    epoch: EpochSpec,
    training_source: Path,
    training_sha256: str,
    truth_sha256: str,
) -> Any:
    freeze = freeze_training(
        training_source=training_source,
        training_edition_id=epoch.training_edition,
        targets_path=experiment_dir / TARGETS_FILE,
        output=experiment_dir / FREEZE_FILE,
        forbidden_source_hashes=[truth_sha256],
    )
    if list(freeze.allowed_source_hashes) != [training_sha256]:
        raise ProtocolError("freeze allows a source that is not the preregistered training source")
    if truth_sha256 not in freeze.forbidden_source_hashes:
        raise LeakageError("freeze does not forbid the preregistered later-edition hash")
    if not freeze.training_nuclide_ids:
        raise ProtocolError("freeze has no training identities")
    return freeze


# --------------------------------------------------------------------------- #
# Phase 4 - blind prediction workspace                                        #
# --------------------------------------------------------------------------- #


def assert_workspace_blind(
    workspace: str | Path,
    *,
    forbidden_source_hashes: set[str],
    forbidden_filenames: set[str],
) -> dict[str, Any]:
    """Filesystem preflight: no truth file name, no truth content, anywhere."""
    workspace = Path(workspace)
    checked = 0
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        checked += 1
        if path.name in forbidden_filenames:
            raise LeakageError(
                f"prediction workspace contains a known truth file name: {path.name}"
            )
        if sha256_file(path) in forbidden_source_hashes:
            raise LeakageError(
                f"prediction workspace contains forbidden truth content: {path.relative_to(workspace)}"
            )
    return {
        "workspace_files_checked": checked,
        "forbidden_filenames": sorted(forbidden_filenames),
        "forbidden_source_hashes": sorted(forbidden_source_hashes),
        "status": "BLIND",
    }


@contextmanager
def blind_prediction_workspace(
    *,
    experiment_dir: Path,
    epoch: EpochSpec,
    training_source: Path,
    truth_sha256: str,
) -> Iterator[dict[str, Any]]:
    """A throwaway directory holding only what a blind prediction may read."""
    tmp = Path(tempfile.mkdtemp(prefix=f"ez-blind-{epoch.experiment_id}-"))
    try:
        training_copy = tmp / epoch.training_relpath
        training_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(training_source, training_copy)
        for name in (TARGETS_FILE, FREEZE_FILE):
            shutil.copyfile(experiment_dir / name, tmp / name)
        prereg_dir = tmp / "preregistration"
        prereg_dir.mkdir(parents=True, exist_ok=True)
        for name in (*PREREGISTRATION_FILES, PREREGISTRATION_HASH_FILE, PREREGISTRATION_MARKDOWN):
            source = experiment_dir / name
            if source.is_file():
                shutil.copyfile(source, prereg_dir / name)
        forbidden_names = set(truth_filenames()) - {epoch.training_filename}
        preflight = assert_workspace_blind(
            tmp,
            forbidden_source_hashes={truth_sha256},
            forbidden_filenames=forbidden_names,
        )
        yield {
            "workspace": tmp,
            "training_source": training_copy,
            "targets": tmp / TARGETS_FILE,
            "freeze": tmp / FREEZE_FILE,
            "preflight": preflight,
            "forbidden_filenames": forbidden_names,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Phases 5-7 - predict, finalize, seal                                        #
# --------------------------------------------------------------------------- #


def _predict_in_subprocess(*, workspace: Path, epoch: EpochSpec, suite_relpath: str) -> list[str]:
    """Run the suite from inside the blind workspace as a separate process.

    The child process is started with the workspace as its working directory and
    is handed nothing but the training source, the targets, and the freeze. It
    cannot reach the later-edition file through a relative path, and the
    preflight already proved the workspace does not contain it.
    """
    argv = [
        sys.executable,
        "-m",
        "elementzero.cli",
        "benchmark",
        "suite-predict",
        "--freeze",
        FREEZE_FILE,
        "--targets",
        TARGETS_FILE,
        "--training-source",
        epoch.training_relpath,
        "--edition",
        epoch.training_edition,
        "--out",
        suite_relpath,
    ]
    result = subprocess.run(argv, cwd=str(workspace), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProtocolError(
            f"blind prediction subprocess failed ({result.returncode}): "
            f"{result.stderr.strip()[-2000:]}"
        )
    return argv[1:]


def _normalize_suite_paths(runs_dir: Path) -> dict[str, Any]:
    """Rewrite the suite manifest with experiment-relative run paths.

    Predictions are produced inside a temporary blind workspace, so the paths the
    suite recorded are machine layout, not evidence. They are rewritten to
    ``runs/<model_id>`` before the run is sealed. The suite manifest is an index;
    the sealed artifacts it points at are hashed by the finalization markers and
    are never touched here.
    """
    path = runs_dir / SUITE_MANIFEST_NAME
    suite = read_json(path)
    suite["suite_dir"] = runs_dir.name
    for run in suite["runs"]:
        run["run_dir"] = f"{runs_dir.name}/{Path(run['run_dir']).name}"
    path.write_text(canonical_json(suite) + "\n", encoding="utf-8")
    return suite


def sealed_predictions_manifest(
    *,
    experiment_dir: Path,
    epoch: EpochSpec,
    preregistration_hash: str,
    suite: dict[str, Any],
    target_digest: str,
) -> dict[str, Any]:
    runs = []
    for run in suite["runs"]:
        run_dir = experiment_dir / RUNS_DIRNAME / Path(run["run_dir"]).name
        manifest = read_json(run_dir / "run_manifest.json")
        if manifest["target_identity_digest"] != target_digest:
            raise ProtocolError(
                f"model {run['model_id']} sealed a different target set than the experiment"
            )
        runs.append(
            {
                "model_id": run["model_id"],
                "run_id": manifest["run_id"],
                "run_relpath": f"{RUNS_DIRNAME}/{run_dir.name}",
                "freeze_id": manifest["freeze_id"],
                "model_manifest_hash": manifest["model_manifest_hash"],
                "predictions_file_hash": manifest["predictions_file_hash"],
                "certificates_file_hash": manifest["certificates_file_hash"],
                "prediction_set_fact_id": manifest["prediction_set_fact_id"],
                "finalization_marker_hash": finalization_marker_hash(run_dir),
                "atlas_bundle_hashes": manifest["atlas_bundle_hashes"],
                "n_predictions": len(manifest["target_ids"]),
            }
        )
    return {
        "experiment_id": epoch.experiment_id,
        "benchmark_id": BENCHMARK_EZ_B001,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "preregistration_hash": preregistration_hash,
        "target_identity_digest": target_digest,
        "freeze_id": suite["freeze_id"],
        "model_suite_id": suite["model_suite_id"],
        "model_ids": list(suite["model_ids"]),
        "runs": runs,
        "created_at": epoch.created_at,
        "atlas_pir_ref": atlas_pir_ref(),
        "elementzero_commit": elementzero_commit(),
        "state": "PREDICTIONS_SEALED_TRUTH_LOCKED",
    }


def seal_experiment(
    *,
    epoch: EpochSpec,
    experiment_dir: str | Path | None = None,
    root: str | Path | None = None,
    training_source: str | Path | None = None,
    truth_source: str | Path | None = None,
    verify: bool = False,
    subprocess_prediction: bool = True,
) -> dict[str, Any]:
    """WO-06 phases 0-7: everything that must exist before truth is unlocked."""
    base = Path(root or REPO_ROOT)
    experiment_dir = Path(experiment_dir or base / "experiments" / epoch.experiment_id)
    training_source = Path(training_source or base / epoch.training_relpath)
    truth_source = Path(truth_source or base / epoch.truth_relpath)

    # Phase 0: the preregistration governs the run, so it is checked first.
    report = validate_preregistration(experiment_dir, root=base)
    assert_protocol_code_unchanged(experiment_dir, root=base)
    prereg = load_preregistration(experiment_dir)[PROTOCOL_FILE]
    prereg_hash = read_preregistration_hash(experiment_dir)
    if prereg["experiment_id"] != epoch.experiment_id:
        raise ProtocolError(
            f"preregistration is for {prereg['experiment_id']}, not {epoch.experiment_id}"
        )
    training_sha256 = prereg["training"]["raw_sha256"]
    truth_sha256 = prereg["later_edition"]["raw_sha256"]
    if sha256_file(training_source) != training_sha256:
        raise ProtocolError("training source hash differs from the preregistration")
    if sha256_file(truth_source) != truth_sha256:
        raise ProtocolError("later-edition source hash differs from the preregistration")

    runs_dir = experiment_dir / RUNS_DIRNAME
    if runs_dir.exists() and any(runs_dir.iterdir()):
        raise ProtocolError(
            f"{runs_dir} already holds sealed runs; a rerun must use a new experiment "
            "directory or a new protocol version, never an overwrite"
        )

    environment = environment_report(
        experiment_dir=experiment_dir,
        epoch=epoch,
        preregistration_hash=prereg_hash,
        root=base,
        verify=verify,
    )

    # Phase 1-3.
    audit = write_data_audit(
        experiment_dir=experiment_dir,
        epoch=epoch,
        training_source=training_source,
        truth_source=truth_source,
        training_sha256=training_sha256,
        truth_sha256=truth_sha256,
    )
    targets = write_targets(
        experiment_dir=experiment_dir,
        epoch=epoch,
        training_source=training_source,
        truth_source=truth_source,
    )
    freeze = write_freeze(
        experiment_dir=experiment_dir,
        epoch=epoch,
        training_source=training_source,
        training_sha256=training_sha256,
        truth_sha256=truth_sha256,
    )

    # Phase 4-6: predict and finalize from a workspace that has no truth in it.
    with blind_prediction_workspace(
        experiment_dir=experiment_dir,
        epoch=epoch,
        training_source=training_source,
        truth_sha256=truth_sha256,
    ) as blind:
        workspace = blind["workspace"]
        if subprocess_prediction:
            argv = _predict_in_subprocess(
                workspace=workspace, epoch=epoch, suite_relpath=RUNS_DIRNAME
            )
        else:
            run_suite(
                freeze=load_freeze(blind["freeze"]),
                targets=load_targets(blind["targets"]),
                training_source=blind["training_source"],
                training_edition_id=epoch.training_edition,
                suite_dir=workspace / RUNS_DIRNAME,
                created_at=epoch.created_at,
            )
            argv = ["in-process run_suite"]
        # Nothing truth-bearing may have appeared while predicting either.
        post = assert_workspace_blind(
            workspace,
            forbidden_source_hashes={truth_sha256},
            forbidden_filenames=blind["forbidden_filenames"],
        )
        shutil.copytree(workspace / RUNS_DIRNAME, runs_dir, dirs_exist_ok=True)

    _normalize_suite_paths(runs_dir)
    suite = read_json(runs_dir / SUITE_MANIFEST_NAME)
    if list(suite["model_ids"]) != list(prereg["model_ids"]):
        raise ProtocolError("sealed suite does not match the preregistered model suite")

    # Phase 7: one experiment-level seal over every model's sealed artifacts.
    sealed = sealed_predictions_manifest(
        experiment_dir=experiment_dir,
        epoch=epoch,
        preregistration_hash=prereg_hash,
        suite=suite,
        target_digest=targets["digest"],
    )
    (experiment_dir / SEALED_PREDICTIONS_FILE).write_text(
        canonical_json(sealed) + "\n", encoding="utf-8"
    )
    sealed_hash = sha256_file(experiment_dir / SEALED_PREDICTIONS_FILE)
    (experiment_dir / SEALED_PREDICTIONS_HASH_FILE).write_text(sealed_hash + "\n", encoding="utf-8")
    (experiment_dir / ENVIRONMENT_FILE).write_text(
        canonical_json(environment) + "\n", encoding="utf-8"
    )

    run_manifest = {
        "experiment_id": epoch.experiment_id,
        "benchmark_id": BENCHMARK_EZ_B001,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "stage": "sealed",
        "epoch": epoch.to_dict(),
        "preregistration_hash": prereg_hash,
        "preregistration_report": report,
        "artifact_layout": {
            "data_audit": DATA_AUDIT_DIRNAME,
            "targets": TARGETS_FILE,
            "freeze": FREEZE_FILE,
            "runs": RUNS_DIRNAME,
            "scoring": f"{RUNS_DIRNAME}/<model_id>/{SCORING_DIRNAME}",
            "model_comparison": COMPARISON_JSON_NAME,
            "layout_note": (
                "WO-06 lists runs/<experiment>/<model> and results/<experiment>/<model>; "
                "this repository keeps both under experiments/<experiment>/ so one "
                "directory is one auditable unit"
            ),
        },
        "data_audit": {
            edition: {
                "report": f"{DATA_AUDIT_DIRNAME}/{parse_report_name(edition)}",
                "raw_source_hash": payload["raw_source_hash"],
                "parsed_records": payload["parsed_records"],
                "eligible_records": payload["eligible_records"],
                "estimated_records": payload["estimated_records"],
                "malformed_fraction": payload["malformed_fraction"],
            }
            for edition, payload in audit.items()
        },
        "targets": targets["summary"],
        "freeze": {
            "freeze_id": freeze.freeze_id,
            "n_training": len(freeze.training_nuclide_ids),
            "training_identity_digest": freeze.training_identity_digest,
            "normalized_table_hash": freeze.normalized_table_hash,
            "feature_policy_id": freeze.feature_policy_id,
            "feature_policy_hash": freeze.feature_policy_hash,
            "allowed_source_hashes": list(freeze.allowed_source_hashes),
            "forbidden_source_hashes": list(freeze.forbidden_source_hashes),
            "file_sha256": sha256_file(experiment_dir / FREEZE_FILE),
        },
        "blind_workspace": {
            "preflight_before_prediction": blind["preflight"],
            "preflight_after_prediction": post,
            "prediction_process_argv": argv,
            "prediction_process_cwd": "blind workspace (temporary, discarded)",
        },
        "sealed_predictions": {
            "file": SEALED_PREDICTIONS_FILE,
            "sha256": sealed_hash,
            "state": sealed["state"],
        },
        "environment": environment,
    }
    (experiment_dir / RUN_MANIFEST_FILE).write_text(
        canonical_json(run_manifest) + "\n", encoding="utf-8"
    )
    write_sha256sums(experiment_dir)
    return {
        "experiment_dir": str(experiment_dir),
        "run_manifest": run_manifest,
        "sealed": sealed,
        "sealed_predictions_sha256": sealed_hash,
        "n_targets": targets["summary"]["n_targets"],
    }


# --------------------------------------------------------------------------- #
# Phases 9-10 - truth unlock, scoring, comparison                             #
# --------------------------------------------------------------------------- #


@contextmanager
def unlocked_truth(*, epoch: EpochSpec, truth_source: Path) -> Iterator[Path]:
    """Stage the truth file under its canonical name for the scoring process.

    Atlas records ``file:<basename>`` for a source artifact, so scoring from a
    canonically named copy keeps the sealed evidence bundle independent of local
    download paths.
    """
    tmp = Path(tempfile.mkdtemp(prefix=f"ez-truth-{epoch.experiment_id}-"))
    try:
        staged = tmp / epoch.truth_filename
        shutil.copyfile(truth_source, staged)
        yield staged
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def score_experiment(
    *,
    epoch: EpochSpec,
    experiment_dir: str | Path | None = None,
    root: str | Path | None = None,
    truth_source: str | Path | None = None,
) -> dict[str, Any]:
    """WO-06 phases 9-10: score every sealed run, then compare all of them."""
    base = Path(root or REPO_ROOT)
    experiment_dir = Path(experiment_dir or base / "experiments" / epoch.experiment_id)
    truth_source = Path(truth_source or base / epoch.truth_relpath)

    validate_preregistration(experiment_dir, root=base)
    assert_protocol_code_unchanged(experiment_dir, root=base)
    prereg = load_preregistration(experiment_dir)[PROTOCOL_FILE]
    prereg_hash = read_preregistration_hash(experiment_dir)
    truth_sha256 = sha256_file(truth_source)
    if truth_sha256 != prereg["later_edition"]["raw_sha256"]:
        raise ProtocolError("truth source hash differs from the preregistration")

    sealed_path = experiment_dir / SEALED_PREDICTIONS_FILE
    if not sealed_path.is_file():
        raise ProtocolError("predictions were never sealed; scoring is refused")
    sealed = read_json(sealed_path)
    recorded_hash = (experiment_dir / SEALED_PREDICTIONS_HASH_FILE).read_text(encoding="utf-8").strip()
    if sha256_file(sealed_path) != recorded_hash:
        raise ProtocolError("SEALED_PREDICTIONS.json does not match SEALED_PREDICTIONS_SHA256")
    if sealed["preregistration_hash"] != prereg_hash:
        raise ProtocolError("sealed manifest was created under a different preregistration")

    runs_dir = experiment_dir / RUNS_DIRNAME
    suite = read_json(runs_dir / SUITE_MANIFEST_NAME)
    reports = []
    with unlocked_truth(epoch=epoch, truth_source=truth_source) as staged_truth:
        for run in sealed["runs"]:
            run_dir = experiment_dir / run["run_relpath"]
            if finalization_marker_hash(run_dir) != run["finalization_marker_hash"]:
                raise LeakageError(
                    f"finalization marker of {run['model_id']} changed after the seal"
                )
            report = score_run(
                run_dir=run_dir,
                truth_source=staged_truth,
                truth_edition_id=epoch.truth_edition,
                out_dir=run_dir / SCORING_DIRNAME,
                created_at=epoch.created_at,
            )
            if report["truth_source_hash"] != truth_sha256:
                raise ProtocolError("scored truth hash does not match the staged truth file")
            (run_dir / SCORING_DIRNAME / SCORED_PREDICTIONS_FILE).write_text(
                canonical_json(
                    {
                        "experiment_id": epoch.experiment_id,
                        "model_id": report["model_id"],
                        "run_id": report["run_id"],
                        "truth_edition_id": epoch.truth_edition,
                        "truth_source_hash": truth_sha256,
                        "rows": report["rows"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            reports.append(report)

    # build_comparison stamps the evidence protocol version; the epoch identity and
    # the experiment protocol version are added so one comparison file is
    # self-describing for the longitudinal report.
    comparison = {
        "experiment_id": epoch.experiment_id,
        "experiment_protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "training_edition": epoch.training_edition,
        "truth_edition": epoch.truth_edition,
        "preregistration_hash": prereg_hash,
        **build_comparison(reports, suite=suite),
    }
    (experiment_dir / COMPARISON_JSON_NAME).write_text(
        canonical_json(comparison) + "\n", encoding="utf-8"
    )
    (experiment_dir / COMPARISON_MARKDOWN_NAME).write_text(
        comparison_markdown(comparison), encoding="utf-8"
    )

    score_manifest = {
        "experiment_id": epoch.experiment_id,
        "benchmark_id": BENCHMARK_EZ_B001,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "stage": "scored",
        "preregistration_hash": prereg_hash,
        "sealed_predictions_sha256": recorded_hash,
        "truth_edition_id": epoch.truth_edition,
        "truth_source_hash": truth_sha256,
        "target_identity_digest": sealed["target_identity_digest"],
        "created_at": epoch.created_at,
        "atlas_pir_ref": atlas_pir_ref(),
        "elementzero_commit": elementzero_commit(),
        "models": [
            {
                "model_id": report["model_id"],
                "run_relpath": f"{RUNS_DIRNAME}/{report['run_id']}",
                "scoring_relpath": f"{RUNS_DIRNAME}/{report['run_id']}/{SCORING_DIRNAME}",
                "metrics_sha256": sha256_file(
                    experiment_dir / RUNS_DIRNAME / report["run_id"] / SCORING_DIRNAME / "metrics.json"
                ),
                "score_report_sha256": sha256_file(
                    experiment_dir
                    / RUNS_DIRNAME
                    / report["run_id"]
                    / SCORING_DIRNAME
                    / "score_report.json"
                ),
                "metrics_content_hash": sha256_hex(report["metrics"]),
                "validation_fact_id": report["validation_fact_id"],
                "truth_dataset_fact_id": report["truth_dataset_fact_id"],
                "finalization_marker_hash": report["finalization_marker_hash"],
            }
            for report in reports
        ],
        "model_comparison": {
            "json": COMPARISON_JSON_NAME,
            "markdown": COMPARISON_MARKDOWN_NAME,
            "sha256": sha256_file(experiment_dir / COMPARISON_JSON_NAME),
        },
        "ranking_rule": comparison["ranking_rule"],
    }
    (experiment_dir / SCORE_MANIFEST_FILE).write_text(
        canonical_json(score_manifest) + "\n", encoding="utf-8"
    )
    write_sha256sums(experiment_dir)
    return {
        "experiment_dir": str(experiment_dir),
        "score_manifest": score_manifest,
        "comparison": comparison,
        "reports": reports,
    }


# --------------------------------------------------------------------------- #
# Replay (WO-07 section 7)                                                    #
# --------------------------------------------------------------------------- #


def replay_experiment(
    *,
    epoch: EpochSpec,
    experiment_dir: str | Path | None = None,
    root: str | Path | None = None,
    truth_source: str | Path | None = None,
) -> dict[str, Any]:
    """Recompute metrics from sealed predictions and truth, without refitting.

    Nothing in the experiment directory is written. The replayed metric content
    hash must equal the committed one.
    """
    base = Path(root or REPO_ROOT)
    experiment_dir = Path(experiment_dir or base / "experiments" / epoch.experiment_id)
    truth_source = Path(truth_source or base / epoch.truth_relpath)
    score_manifest = read_json(experiment_dir / SCORE_MANIFEST_FILE)
    sealed = read_json(experiment_dir / SEALED_PREDICTIONS_FILE)
    truth_sha256 = sha256_file(truth_source)
    if truth_sha256 != score_manifest["truth_source_hash"]:
        raise ProtocolError("replay truth source differs from the scored truth source")

    committed = {m["model_id"]: m for m in score_manifest["models"]}
    rows = []
    with unlocked_truth(epoch=epoch, truth_source=truth_source) as staged_truth:
        for run in sealed["runs"]:
            model_id = run["model_id"]
            run_dir = experiment_dir / run["run_relpath"]
            if finalization_marker_hash(run_dir) != run["finalization_marker_hash"]:
                raise LeakageError(f"{model_id} finalization marker changed after the seal")
            with tempfile.TemporaryDirectory(prefix="ez-replay-") as scratch:
                report = score_run(
                    run_dir=run_dir,
                    truth_source=staged_truth,
                    truth_edition_id=epoch.truth_edition,
                    out_dir=Path(scratch),
                    created_at=epoch.created_at,
                )
            replayed = sha256_hex(report["metrics"])
            expected = committed[model_id]["metrics_content_hash"]
            rows.append(
                {
                    "model_id": model_id,
                    "replayed_metrics_content_hash": replayed,
                    "committed_metrics_content_hash": expected,
                    "matches": replayed == expected,
                    "refit": False,
                }
            )
    mismatched = [r["model_id"] for r in rows if not r["matches"]]
    if mismatched:
        raise ProtocolError(f"replayed metrics do not match the committed metrics: {mismatched}")
    return {
        "experiment_id": epoch.experiment_id,
        "experiment_dir": str(experiment_dir),
        "truth_source_hash": truth_sha256,
        "models": rows,
        "refit": False,
        "status": "REPLAY_MATCHES_COMMITTED_METRICS",
    }


# --------------------------------------------------------------------------- #
# Hash manifest                                                               #
# --------------------------------------------------------------------------- #


def write_sha256sums(experiment_dir: str | Path) -> Path:
    """sha256sum-compatible manifest of every committed experiment artifact."""
    experiment_dir = Path(experiment_dir)
    lines = []
    for path in sorted(experiment_dir.rglob("*")):
        if not path.is_file() or path.name == SHA256SUMS_FILE:
            continue
        lines.append(f"{sha256_file(path)}  {path.relative_to(experiment_dir)}")
    target = experiment_dir / SHA256SUMS_FILE
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def verify_sha256sums(experiment_dir: str | Path) -> dict[str, Any]:
    experiment_dir = Path(experiment_dir)
    recorded = {}
    for line in (experiment_dir / SHA256SUMS_FILE).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relpath = line.split("  ", 1)
        recorded[relpath] = digest
    present = {
        str(path.relative_to(experiment_dir)): sha256_file(path)
        for path in sorted(experiment_dir.rglob("*"))
        if path.is_file() and path.name != SHA256SUMS_FILE
    }
    missing = sorted(set(recorded) - set(present))
    extra = sorted(set(present) - set(recorded))
    changed = sorted(k for k in set(recorded) & set(present) if recorded[k] != present[k])
    return {
        "experiment_dir": str(experiment_dir),
        "n_files": len(recorded),
        "missing": missing,
        "extra": extra,
        "changed": changed,
        "ok": not (missing or extra or changed),
    }
