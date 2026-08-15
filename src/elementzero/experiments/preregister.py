"""Immutable preregistration for one EZ-B001 historical epoch (WO-05).

A preregistration freezes the protocol before any later-edition truth is
scored. It contains identities, hashes, policies, and code identity. It contains
no truth values, and nothing in it may be rewritten after prediction.

Layout under ``experiments/<experiment_id>/``:

    PREREGISTRATION.md        prose statement of the frozen protocol
    protocol.json             protocol identity, editions, hashes, code identity
    source_manifest.json      raw file hashes, URLs, citations, parser versions
    target_policy.json        target rule and identity-only target contract
    model_suite.json          the exact three frozen models
    metrics_policy.json       the exact preregistered metrics
    PREREGISTRATION_SHA256    canonical hash over the five JSON files

Hash rule (``ez-prereg-hash-v1``):

    entries = [{"name": f, "sha256": sha256(bytes of f)} for f in FIVE_JSON_FILES]
    entries sorted by name
    PREREGISTRATION_SHA256 =
        sha256(canonical_json({"hash_rule": ..., "files": entries}))

``PREREGISTRATION.md`` is prose and is deliberately outside the hash: editing a
sentence in it must not be able to invalidate a sealed experiment, and it can
never change a number. Its own digest is recorded in the run manifests instead.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_PROTOCOL_VERSION, __version__
from elementzero.atlas_pin import atlas_pir_ref, validate_atlas_ref
from elementzero.benchmark.distance import (
    DISTANCE_BUCKET_IDS,
    DISTANCE_POLICY_ID,
    REGION_IDS,
    REGION_POLICY_ID,
)
from elementzero.benchmark.model_suite import MODEL_SUITE_ID, SUITE_MODEL_IDS
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.observations import GROUND_TRUTH_POLICY, TRUTH_BEARING_FIELDS
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.freezes import ALLOWED_TARGET_FIELDS, FEATURE_POLICY_EZ_B001
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.experiments.epochs import (
    AMDC_URLS,
    AME_CITATIONS,
    BENCHMARK_FAMILY,
    EpochSpec,
)
from elementzero.experiments.protocol_code import protocol_code_identity
from elementzero.identity_meta import elementzero_commit
from elementzero.models.gp_residual import (
    MODEL_ID_GP_DIRECT,
    MODEL_ID_SEMF_GP,
    MODEL_ID_SEMF_LS,
)
from elementzero.models.protocol import (
    PREDICTIVE_DISTRIBUTION_GAUSSIAN,
    UNCERTAINTY_METHOD_GP_RETURN_STD,
    UNCERTAINTY_METHOD_TRAINING_RESIDUAL_STD,
    Z_90,
    Z_95,
)
from elementzero.physics.constants import NORMALIZER_VERSION

# Experiment protocol version (WO-05 section 1). This is the historical
# experiment protocol, not the evidence/scoring implementation version, which is
# elementzero.BENCHMARK_PROTOCOL_VERSION and is recorded next to it.
EXPERIMENT_PROTOCOL_VERSION = "1.0.0"

PROTOCOL_FILE = "protocol.json"
SOURCE_MANIFEST_FILE = "source_manifest.json"
TARGET_POLICY_FILE = "target_policy.json"
MODEL_SUITE_FILE = "model_suite.json"
METRICS_POLICY_FILE = "metrics_policy.json"
PREREGISTRATION_MARKDOWN = "PREREGISTRATION.md"
PREREGISTRATION_HASH_FILE = "PREREGISTRATION_SHA256"

# Hashed set, sorted. PREREGISTRATION.md is prose and stays out (see module doc).
PREREGISTRATION_FILES: tuple[str, ...] = (
    METRICS_POLICY_FILE,
    MODEL_SUITE_FILE,
    PROTOCOL_FILE,
    SOURCE_MANIFEST_FILE,
    TARGET_POLICY_FILE,
)

PREREG_HASH_RULE = (
    "ez-prereg-hash-v1: sha256 of canonical JSON of the name-sorted "
    "[{name, sha256(file bytes)}] list of protocol.json, source_manifest.json, "
    "target_policy.json, model_suite.json, metrics_policy.json"
)

TARGET_POLICY_ID = "ez-b001-target-policy-v1"
METRICS_POLICY_ID = "ez-b001-metrics-policy-v1"

PRIMARY_METRICS: tuple[str, ...] = (
    "MAE_keV",
    "MedAE_keV",
    "RMSE_keV",
    "NLPD",
    "coverage_90",
    "coverage_95",
    "calibration_error_90",
    "calibration_error_95",
)

# Scoring emits cal_error_* keys; the preregistered names map onto them.
METRIC_KEY_ALIASES = {
    "calibration_error_90": "cal_error_90",
    "calibration_error_95": "cal_error_95",
}

SECONDARY_DIAGNOSTICS: tuple[str, ...] = (
    "error vs nearest_training_L1",
    "metrics per L1 distance bucket",
    "metrics per Z band",
)

FEATURES: tuple[str, ...] = ("Z", "N", "A")

FORBIDDEN_FEATURES: tuple[str, ...] = (
    "later truth values",
    "magic-number-distance features",
    "shell labels",
    "future-edition derived features",
)

NO_TUNING_RULE = (
    "Once any truth value of the later edition is scored, model definitions and "
    "hyperparameters are frozen for this experiment at protocol "
    f"{EXPERIMENT_PROTOCOL_VERSION}. A desired change requires a new protocol "
    "version (1.1.0 or 2.0.0), a complete rerun, and preservation of the old "
    "result. Nothing is overwritten."
)

POST_HOC_RULE = (
    "No metric may be added after scoring and then described as preregistered. "
    "Additional analyses are allowed only when labelled POST_HOC."
)

WORKSPACE_ISOLATION = {
    "preparation_workspace": [
        "reads the earlier and the later edition",
        "emits identity-only targets",
        "emits the later-edition raw sha256",
    ],
    "prediction_workspace": [
        "earlier-edition raw source",
        "targets.json",
        "freeze.json",
        "preregistration files",
        "must not contain the later-edition raw file",
        "checked by an automated filesystem preflight over file names and content hashes",
    ],
    "scoring_workspace": [
        "receives sealed predictions",
        "receives the later-edition raw file only after finalization",
    ],
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _model_descriptors() -> list[dict[str, Any]]:
    """Frozen description of each model: code path, hyperparameters, sigma."""
    gp_kernel = {
        "kind": "fixed_sum_kernel",
        "expression": "ConstantKernel(c) * RBF(length_scale) + WhiteKernel(noise_level)",
        "constant_value": 1.0e6,
        "constant_value_bounds": "fixed",
        "length_scale": 8.0,
        "length_scale_bounds": "fixed",
        "noise_level": 1.0e4,
        "noise_level_bounds": "fixed",
        "optimizer": None,
        "normalize_y": True,
    }
    return [
        {
            "model_id": MODEL_ID_SEMF_LS,
            "implementation_path": "src/elementzero/models/gp_residual.py",
            "implementation_symbol": "SEMFLeastSquaresModel",
            "physics_path": "src/elementzero/physics/semf.py",
            "hyperparameters": {
                "estimator": "ordinary least squares on the five SEMF terms",
                "terms": ["volume", "surface", "coulomb", "asymmetry", "pairing"],
                "regularization": None,
            },
            "random_state": 0,
            "features": list(FEATURES),
            "uncertainty_method": UNCERTAINTY_METHOD_TRAINING_RESIDUAL_STD,
            "predictive_distribution": PREDICTIVE_DISTRIBUTION_GAUSSIAN,
        },
        {
            "model_id": MODEL_ID_GP_DIRECT,
            "implementation_path": "src/elementzero/models/gp_residual.py",
            "implementation_symbol": "GPDirectModel",
            "physics_path": None,
            "hyperparameters": {
                "estimator": "sklearn.gaussian_process.GaussianProcessRegressor",
                "regression_target": "mass excess of the training edition",
                "kernel": gp_kernel,
            },
            "random_state": 0,
            "features": list(FEATURES),
            "uncertainty_method": UNCERTAINTY_METHOD_GP_RETURN_STD,
            "predictive_distribution": PREDICTIVE_DISTRIBUTION_GAUSSIAN,
        },
        {
            "model_id": MODEL_ID_SEMF_GP,
            "implementation_path": "src/elementzero/models/gp_residual.py",
            "implementation_symbol": "SEMFGPResidualModel",
            "physics_path": "src/elementzero/physics/semf.py",
            "hyperparameters": {
                "estimator": "SEMF least squares plus GaussianProcessRegressor on the residual",
                "regression_target": "observed minus SEMF residual of the training edition",
                "kernel": gp_kernel,
            },
            "random_state": 0,
            "features": list(FEATURES),
            "uncertainty_method": UNCERTAINTY_METHOD_GP_RETURN_STD,
            "predictive_distribution": PREDICTIVE_DISTRIBUTION_GAUSSIAN,
        },
    ]


def build_payloads(
    *,
    epoch: EpochSpec,
    training_source_sha256: str,
    truth_source_sha256: str,
    root: str | Path | None = None,
    ez_commit: str | None = None,
) -> dict[str, dict[str, Any]]:
    """The five preregistration JSON payloads for one epoch."""
    for label, digest in (
        ("training", training_source_sha256),
        ("truth", truth_source_sha256),
    ):
        if not _SHA256_RE.fullmatch(str(digest)):
            raise ProtocolError(f"{label} source sha256 is not 64 lowercase hex chars: {digest!r}")
    if training_source_sha256 == truth_source_sha256:
        raise ProtocolError("training and truth sources have the same sha256")

    code = protocol_code_identity(root)
    commit = ez_commit or elementzero_commit()
    atlas_ref = validate_atlas_ref(atlas_pir_ref())

    protocol = {
        "benchmark_family": BENCHMARK_FAMILY,
        "experiment_id": epoch.experiment_id,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "elementzero_version": __version__,
        "created_at": epoch.created_at,
        "training": {
            "edition": epoch.training_edition,
            "raw_relpath": epoch.training_relpath,
            "raw_filename": epoch.training_filename,
            "raw_sha256": training_source_sha256,
            "role": "only allowed training source",
        },
        "later_edition": {
            "edition": epoch.truth_edition,
            "raw_relpath": epoch.truth_relpath,
            "raw_filename": epoch.truth_filename,
            "raw_sha256": truth_source_sha256,
            "role": "later truth, forbidden until predictions are sealed",
        },
        "allowed_source_hashes": [training_source_sha256],
        "forbidden_source_hashes": [truth_source_sha256],
        "feature_policy_id": FEATURE_POLICY_EZ_B001,
        "features": list(FEATURES),
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "parser_version": PARSER_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "model_suite_id": MODEL_SUITE_ID,
        "model_ids": list(SUITE_MODEL_IDS),
        "metrics_policy_id": METRICS_POLICY_ID,
        "target_policy_id": TARGET_POLICY_ID,
        "atlas_repository": "https://github.com/Sovrance/Atlas",
        "atlas_pir_ref": atlas_ref,
        "elementzero_commit": commit,
        "protocol_code_policy_id": code["policy_id"],
        "protocol_code_digest": code["protocol_code_digest"],
        "atlas_packaging_exception": "docs/migrations/WO-04-atlas-packaging-exception.md",
        "preregistration_hash_rule": PREREG_HASH_RULE,
        "preregistration_files": list(PREREGISTRATION_FILES),
        "no_tuning_after_scoring": NO_TUNING_RULE,
        "prediction_workspace_isolation": WORKSPACE_ISOLATION,
        "stop_conditions": [
            "prediction artifacts changed after seal",
            "target manifest differs across models",
            "source hash differs from preregistration",
            "any run fit after truth was unlocked",
            "protocol code digest differs from preregistration without a protocol bump",
        ],
    }

    source_manifest = {
        "experiment_id": epoch.experiment_id,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "parser_version": PARSER_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "training_source": {
            "edition": epoch.training_edition,
            "raw_relpath": epoch.training_relpath,
            "raw_filename": epoch.training_filename,
            "raw_sha256": training_source_sha256,
            "source_uri": AMDC_URLS[epoch.training_edition],
            "citation": AME_CITATIONS[epoch.training_edition],
        },
        "later_source": {
            "edition": epoch.truth_edition,
            "raw_relpath": epoch.truth_relpath,
            "raw_filename": epoch.truth_filename,
            "raw_sha256": truth_source_sha256,
            "source_uri": AMDC_URLS[epoch.truth_edition],
            "citation": AME_CITATIONS[epoch.truth_edition],
            "forbidden_during_prediction": True,
        },
        "raw_files_committed": False,
        "raw_files_note": (
            "Raw AME tables stay gitignored. Their sha256 values, URLs, and parse "
            "reports are committed instead, which is what makes the run auditable."
        ),
    }

    target_policy = {
        "experiment_id": epoch.experiment_id,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "target_policy_id": TARGET_POLICY_ID,
        "training_edition": epoch.training_edition,
        "later_edition": epoch.truth_edition,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "rule": {
            "training_eligible_ids": (
                f"{epoch.training_edition} rows with ground_truth_eligible == True"
            ),
            "target_ids": (
                f"{epoch.truth_edition} rows with ground_truth_eligible == True "
                f"minus training_eligible_ids"
            ),
        },
        "estimated_row_rule": (
            f"An {epoch.training_edition} estimated row does not remove a target when the "
            f"corresponding {epoch.truth_edition} row becomes ground-truth eligible."
        ),
        "target_manifest_fields": sorted(ALLOWED_TARGET_FIELDS),
        "forbidden_target_fields": sorted(TRUTH_BEARING_FIELDS),
        "target_manifest_contract": (
            "The target manifest exposed to prediction contains identities only. "
            "Any other field is a leakage error."
        ),
        "distance_policy_id": DISTANCE_POLICY_ID,
        "distance_buckets": list(DISTANCE_BUCKET_IDS),
        "region_policy_id": REGION_POLICY_ID,
        "regions": list(REGION_IDS),
    }

    model_suite = {
        "experiment_id": epoch.experiment_id,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "model_suite_id": MODEL_SUITE_ID,
        "model_ids": list(SUITE_MODEL_IDS),
        "models": _model_descriptors(),
        "feature_policy_id": FEATURE_POLICY_EZ_B001,
        "features": list(FEATURES),
        "forbidden_features": list(FORBIDDEN_FEATURES),
        "no_tuning_after_scoring": NO_TUNING_RULE,
        "ranking_rule": (
            "Every metric is reported for every model. No single-metric ranking and "
            "no best-model label."
        ),
    }

    metrics_policy = {
        "experiment_id": epoch.experiment_id,
        "protocol_version": EXPERIMENT_PROTOCOL_VERSION,
        "metrics_policy_id": METRICS_POLICY_ID,
        "primary_metrics": list(PRIMARY_METRICS),
        "secondary_diagnostics": list(SECONDARY_DIAGNOSTICS),
        "definitions": {
            "error_i": "prediction_i - truth_i",
            "MAE_keV": "mean(abs(error_i))",
            "MedAE_keV": "median(abs(error_i))",
            "RMSE_keV": "sqrt(mean(error_i^2))",
            "NLPD": "mean(0.5*log(2*pi*sigma_i^2) + 0.5*((truth_i - prediction_i)/sigma_i)^2)",
            "coverage_90": "fraction of targets inside the reported 90 percent interval",
            "coverage_95": "fraction of targets inside the reported 95 percent interval",
            "calibration_error_90": "abs(coverage_90 - 0.90)",
            "calibration_error_95": "abs(coverage_95 - 0.95)",
        },
        "interval_construction": {
            "predictive_distribution": PREDICTIVE_DISTRIBUTION_GAUSSIAN,
            "z_90": Z_90,
            "z_95": Z_95,
            "sigma_source": (
                "sealed prediction file; sigma is never reconstructed from truth or "
                "from rounded intervals"
            ),
        },
        "post_hoc_rule": POST_HOC_RULE,
        "no_minimum_scientific_threshold": (
            "Engineering success is protocol integrity. A poor scientific result is "
            "reported, never dropped."
        ),
    }

    return {
        PROTOCOL_FILE: protocol,
        SOURCE_MANIFEST_FILE: source_manifest,
        TARGET_POLICY_FILE: target_policy,
        MODEL_SUITE_FILE: model_suite,
        METRICS_POLICY_FILE: metrics_policy,
    }


def hash_entries(experiment_dir: str | Path) -> list[dict[str, str]]:
    base = Path(experiment_dir)
    entries = []
    for name in sorted(PREREGISTRATION_FILES):
        path = base / name
        if not path.is_file():
            raise ProtocolError(f"preregistration file is missing: {name}")
        entries.append({"name": name, "sha256": sha256_file(path)})
    return entries


def preregistration_hash(experiment_dir: str | Path) -> str:
    """Canonical hash over the five preregistration JSON files."""
    payload = {"hash_rule": PREREG_HASH_RULE, "files": hash_entries(experiment_dir)}
    return sha256_hex(payload)


def read_preregistration_hash(experiment_dir: str | Path) -> str:
    path = Path(experiment_dir) / PREREGISTRATION_HASH_FILE
    if not path.is_file():
        raise ProtocolError(f"{PREREGISTRATION_HASH_FILE} is missing in {experiment_dir}")
    return path.read_text(encoding="utf-8").strip()


def load_preregistration(experiment_dir: str | Path) -> dict[str, Any]:
    base = Path(experiment_dir)
    payloads = {}
    for name in PREREGISTRATION_FILES:
        path = base / name
        if not path.is_file():
            raise ProtocolError(f"preregistration file is missing: {name}")
        payloads[name] = json.loads(path.read_text(encoding="utf-8"))
    return payloads


def assert_no_truth_values(payloads: dict[str, Any]) -> None:
    """No truth-bearing field may appear anywhere in the preregistration."""

    def walk(node: Any, where: str) -> None:
        if isinstance(node, dict):
            leaked = sorted(TRUTH_BEARING_FIELDS.intersection(node))
            if leaked:
                raise LeakageError(f"{where} contains truth-bearing fields: {leaked}")
            for key, value in node.items():
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{where}[{index}]")

    for name, payload in payloads.items():
        walk(payload, name)


def markdown(payloads: dict[str, Any], *, prereg_hash: str) -> str:
    protocol = payloads[PROTOCOL_FILE]
    suite = payloads[MODEL_SUITE_FILE]
    metrics = payloads[METRICS_POLICY_FILE]
    targets = payloads[TARGET_POLICY_FILE]
    sources = payloads[SOURCE_MANIFEST_FILE]
    training = protocol["training"]
    later = protocol["later_edition"]
    lines = [
        f"# Preregistration — {protocol['experiment_id']}",
        "",
        f"Protocol version: {protocol['protocol_version']}",
        f"Evidence protocol version: {protocol['evidence_protocol_version']}",
        f"Benchmark family: {protocol['benchmark_family']}",
        f"Preregistration hash: `{prereg_hash}`",
        "",
        "This document is prose. Every load-bearing value lives in the five JSON",
        "files that the preregistration hash covers. Editing this file cannot change",
        "a number, a hash, or a policy.",
        "",
        "## 1. Research question",
        "",
        f"Trained only on {training['edition']}, how accurately and how honestly do the",
        "three frozen EZ-B001 models predict the mass excess of nuclides that only",
        f"became ground-truth eligible in {later['edition']}?",
        "",
        "Engineering success is protocol integrity, not low error.",
        "",
        "## 2. Protocol identity",
        "",
        "```text",
        f"benchmark_family = {protocol['benchmark_family']}",
        f"experiment_id    = {protocol['experiment_id']}",
        f"protocol_version = {protocol['protocol_version']}",
        f"training edition = {training['edition']}",
        f"truth edition    = {later['edition']}",
        "```",
        "",
        "## 3. Sources",
        "",
        "| Role | Edition | File | sha256 |",
        "| --- | --- | --- | --- |",
        f"| training | {training['edition']} | `{training['raw_relpath']}` | `{training['raw_sha256']}` |",
        f"| later truth | {later['edition']} | `{later['raw_relpath']}` | `{later['raw_sha256']}` |",
        "",
        f"Training citation: {sources['training_source']['citation']}",
        "",
        f"Later-edition citation: {sources['later_source']['citation']}",
        "",
        f"Training URL: {sources['training_source']['source_uri']}",
        "",
        f"Later-edition URL: {sources['later_source']['source_uri']}",
        "",
        "Raw tables stay gitignored. The prediction process may know the later-edition",
        "hash; it may not read the later-edition contents.",
        "",
        "## 4. Target rule",
        "",
        "```text",
        f"training_eligible_ids = {targets['rule']['training_eligible_ids']}",
        f"target_ids            = {targets['rule']['target_ids']}",
        "```",
        "",
        targets["estimated_row_rule"],
        "",
        "The target manifest exposed to prediction contains exactly "
        f"{', '.join(targets['target_manifest_fields'])}.",
        "",
        "## 5. Ground-truth eligibility",
        "",
        f"`{protocol['ground_truth_policy']}`: only evaluated, non-estimated AME rows",
        "may act as training truth or as scored truth.",
        "",
        "## 6. Leakage controls",
        "",
        f"- allowed source hashes: `{training['raw_sha256']}`",
        f"- forbidden source hashes: `{later['raw_sha256']}`",
        "- identity-only target manifest, validated on load",
        "- KnowledgeFreeze pins training identities, normalized table hash, and feature policy",
        "- prediction ledger is finalized before any truth unlock",
        "- the prediction workspace is checked by a filesystem preflight over truth file",
        "  names and truth content hashes",
        "",
        "## 7. Model suite",
        "",
        "| model_id | implementation | random_state | uncertainty |",
        "| --- | --- | --- | --- |",
    ]
    for model in suite["models"]:
        lines.append(
            f"| {model['model_id']} | `{model['implementation_path']}::"
            f"{model['implementation_symbol']}` | {model['random_state']} | "
            f"{model['uncertainty_method']} |"
        )
    lines.extend(
        [
            "",
            f"Features: {', '.join(suite['features'])}.",
            "",
            "Forbidden in EZ-B001 v1: " + "; ".join(suite["forbidden_features"]) + ".",
            "",
            "## 8. Metrics",
            "",
            "Primary: " + ", ".join(metrics["primary_metrics"]) + ".",
            "",
            "Secondary diagnostics: " + ", ".join(metrics["secondary_diagnostics"]) + ".",
            "",
            metrics["post_hoc_rule"],
            "",
            "## 9. No model tuning after scoring",
            "",
            suite["no_tuning_after_scoring"],
            "",
            "## 10. Code identity",
            "",
            "```text",
            f"atlas_pir_ref        = {protocol['atlas_pir_ref']}",
            f"elementzero_commit   = {protocol['elementzero_commit']}",
            f"protocol_code_policy = {protocol['protocol_code_policy_id']}",
            f"protocol_code_digest = {protocol['protocol_code_digest']}",
            "```",
            "",
            "The commit SHA is lineage. The enforced gate is `protocol_code_digest`, a",
            "hash over the parser, physics, model, metric, evidence, and leakage-control",
            "source files (`src/elementzero/experiments/protocol_code.py`). Adding a",
            "report generator cannot silently invalidate a sealed experiment, and editing",
            "a model or a metric definitely does.",
            "",
            "Atlas packaging runs under the approved exception in",
            f"`{protocol['atlas_packaging_exception']}`; the pin is immutable.",
            "",
            "## 11. Preregistration hash rule",
            "",
            "```text",
            PREREG_HASH_RULE,
            "```",
            "",
            f"`{PREREGISTRATION_HASH_FILE}` holds the resulting digest and is recomputable",
            "with `elementzero benchmark validate-preregistration`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_preregistration(
    *,
    epoch: EpochSpec,
    experiment_dir: str | Path,
    training_source: str | Path,
    truth_source: str | Path,
    root: str | Path | None = None,
    ez_commit: str | None = None,
) -> dict[str, Any]:
    """Write the five JSON files, the prose statement, and the hash file."""
    base = Path(experiment_dir)
    base.mkdir(parents=True, exist_ok=True)
    payloads = build_payloads(
        epoch=epoch,
        training_source_sha256=sha256_file(training_source),
        truth_source_sha256=sha256_file(truth_source),
        root=root,
        ez_commit=ez_commit,
    )
    assert_no_truth_values(payloads)
    for name, payload in payloads.items():
        (base / name).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    digest = preregistration_hash(base)
    (base / PREREGISTRATION_HASH_FILE).write_text(digest + "\n", encoding="utf-8")
    (base / PREREGISTRATION_MARKDOWN).write_text(
        markdown(payloads, prereg_hash=digest), encoding="utf-8"
    )
    return {
        "experiment_id": epoch.experiment_id,
        "experiment_dir": str(base),
        "preregistration_hash": digest,
        "payloads": payloads,
    }


def validate_preregistration(experiment_dir: str | Path, *, root: str | Path | None = None) -> dict[str, Any]:
    """WO-05 section 10 checks. Raises on the first violation."""
    base = Path(experiment_dir)
    payloads = load_preregistration(base)
    protocol = payloads[PROTOCOL_FILE]
    sources = payloads[SOURCE_MANIFEST_FILE]
    targets = payloads[TARGET_POLICY_FILE]
    suite = payloads[MODEL_SUITE_FILE]
    metrics = payloads[METRICS_POLICY_FILE]

    if not (base / PREREGISTRATION_MARKDOWN).is_file():
        raise ProtocolError(f"{PREREGISTRATION_MARKDOWN} is missing in {base}")

    expected = preregistration_hash(base)
    recorded = read_preregistration_hash(base)
    if recorded != expected:
        raise ProtocolError(
            f"{PREREGISTRATION_HASH_FILE} is {recorded!r} but the files hash to {expected!r}"
        )

    if protocol["protocol_version"] != EXPERIMENT_PROTOCOL_VERSION:
        raise ProtocolError(
            f"protocol version {protocol['protocol_version']!r} is not the supported "
            f"{EXPERIMENT_PROTOCOL_VERSION!r}"
        )

    training_hash = protocol["training"]["raw_sha256"]
    truth_hash = protocol["later_edition"]["raw_sha256"]
    for label, digest in (("training", training_hash), ("later edition", truth_hash)):
        if not _SHA256_RE.fullmatch(str(digest)):
            raise ProtocolError(f"{label} source hash is not 64 lowercase hex chars: {digest!r}")
    if training_hash == truth_hash:
        raise ProtocolError("training and later-edition source hashes are identical")
    if sources["training_source"]["raw_sha256"] != training_hash:
        raise ProtocolError("source manifest and protocol disagree on the training hash")
    if sources["later_source"]["raw_sha256"] != truth_hash:
        raise ProtocolError("source manifest and protocol disagree on the later-edition hash")
    if truth_hash not in protocol["forbidden_source_hashes"]:
        raise LeakageError("later-edition source hash is not declared forbidden")
    if truth_hash in protocol["allowed_source_hashes"]:
        raise LeakageError("later-edition source hash is declared allowed")
    if protocol["allowed_source_hashes"] != [training_hash]:
        raise ProtocolError("allowed source hashes must be exactly the training source")
    if sources["later_source"].get("forbidden_during_prediction") is not True:
        raise LeakageError("source manifest does not forbid the later edition during prediction")

    validate_atlas_ref(protocol["atlas_pir_ref"])
    commit = str(protocol["elementzero_commit"])
    if not _COMMIT_RE.fullmatch(commit):
        raise ProtocolError(
            f"elementzero_commit {commit!r} is not a 40-character commit SHA; "
            "preregister from a committed, clean tree"
        )

    if list(suite["model_ids"]) != list(SUITE_MODEL_IDS):
        raise ProtocolError(
            f"model suite {suite['model_ids']} is not the frozen suite {list(SUITE_MODEL_IDS)}"
        )
    if len(suite["models"]) != len(SUITE_MODEL_IDS):
        raise ProtocolError("model suite must describe exactly the three frozen models")
    described = [m["model_id"] for m in suite["models"]]
    if described != list(SUITE_MODEL_IDS):
        raise ProtocolError(f"model descriptions {described} do not match the frozen suite")
    for model in suite["models"]:
        for field in ("implementation_path", "hyperparameters", "random_state", "features", "uncertainty_method"):
            if field not in model:
                raise ProtocolError(f"model {model['model_id']} does not record {field}")
        if list(model["features"]) != list(FEATURES):
            raise ProtocolError(
                f"model {model['model_id']} features {model['features']} violate the feature policy"
            )
    if protocol["model_ids"] != list(SUITE_MODEL_IDS):
        raise ProtocolError("protocol model_ids do not match the frozen suite")

    declared_metrics = list(metrics["primary_metrics"])
    unknown = sorted(set(declared_metrics) - set(PRIMARY_METRICS))
    if unknown:
        raise ProtocolError(f"unknown preregistered metrics: {unknown}")
    missing = sorted(set(PRIMARY_METRICS) - set(declared_metrics))
    if missing:
        raise ProtocolError(f"preregistration drops primary metrics: {missing}")

    if sorted(targets["target_manifest_fields"]) != sorted(ALLOWED_TARGET_FIELDS):
        raise LeakageError(
            f"target manifest fields {targets['target_manifest_fields']} are not identity-only"
        )
    if sorted(targets["forbidden_target_fields"]) != sorted(TRUTH_BEARING_FIELDS):
        raise LeakageError("target policy does not forbid the full truth-bearing field set")

    assert_no_truth_values(payloads)

    code = protocol_code_identity(root)
    return {
        "experiment_id": protocol["experiment_id"],
        "experiment_dir": str(base),
        "protocol_version": protocol["protocol_version"],
        "preregistration_hash": recorded,
        "training_edition": protocol["training"]["edition"],
        "truth_edition": protocol["later_edition"]["edition"],
        "training_source_hash": training_hash,
        "truth_source_hash": truth_hash,
        "atlas_pir_ref": protocol["atlas_pir_ref"],
        "elementzero_commit": commit,
        "model_ids": list(suite["model_ids"]),
        "primary_metrics": declared_metrics,
        "preregistered_protocol_code_digest": protocol["protocol_code_digest"],
        "current_protocol_code_digest": code["protocol_code_digest"],
        "protocol_code_matches": code["protocol_code_digest"] == protocol["protocol_code_digest"],
        "status": "VALID",
    }


def assert_protocol_code_unchanged(experiment_dir: str | Path, *, root: str | Path | None = None) -> str:
    """Refuse to run when a protocol-defining source file changed after prereg."""
    protocol = load_preregistration(experiment_dir)[PROTOCOL_FILE]
    current = protocol_code_identity(root)["protocol_code_digest"]
    if current != protocol["protocol_code_digest"]:
        raise ProtocolError(
            "protocol code digest changed after preregistration: "
            f"{protocol['protocol_code_digest']} -> {current}. Bump the protocol version "
            "and rerun every epoch instead of scoring a mixed series."
        )
    return current
