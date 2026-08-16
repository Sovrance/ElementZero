"""ElementZero Historical Benchmark Report v1 (WO-08).

The report turns the three sealed EZ-B001 epochs into a repository record that
another researcher can audit without chat history. Three rules shape the whole
module:

1. Every number is read from a committed artifact. Nothing is refit here, no
   metric is recomputed from raw tables, and no value is typed in by hand.
2. Nothing is dropped. All three epochs, all three models, and all eight
   preregistered metrics appear, including the badly behaved combinations.
3. Anything the preregistration did not declare is emitted with the literal
   ``POST_HOC`` label, in the machine-readable payload and in the prose.

Output tree (``reports/historical/v1/``)::

    README.md
    ElementZero_Historical_Benchmark_Report_v1.md
    aggregate_metrics.json
    model_table.csv
    distance_table.csv
    artifact_manifest.json
    benchmark_status.json
    figures/*.svg
    SHA256SUMS.txt

The generator is deterministic: given the same committed artifacts it writes
byte-identical files, which is what lets ``SHA256SUMS.txt`` be verified in a
clean checkout by ``scripts/reproduce_historical_report.py``. That rules out
wall-clock timestamps and live git state in the payload, so epoch identity comes
from the pinned ``created_at`` of each epoch and the commit SHAs come from the
sealed manifests rather than from ``HEAD``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_EZ_B001, BENCHMARK_PROTOCOL_VERSION
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.distance import (
    DISTANCE_BUCKET_IDS,
    DISTANCE_POLICY_ID,
    REGION_IDS,
    REGION_POLICY_ID,
)
from elementzero.benchmark.model_suite import (
    COMPARISON_JSON_NAME,
    MODEL_SUITE_ID,
    SUITE_MODEL_IDS,
)
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file
from elementzero.evidence.ledger import read_json
from elementzero.experiments.aggregate import (
    AGGREGATE_DIRNAME,
    AGGREGATE_JSON,
    DISTANCE_COLUMNS,
    MODEL_COLUMNS,
    build_aggregate,
    experiment_dirs,
    number,
)
from elementzero.experiments.epochs import (
    AMDC_URLS,
    AME_CITATIONS,
    EPOCH_ORDER,
    epoch_for,
)
from elementzero.experiments.preregister import (
    EXPERIMENT_PROTOCOL_VERSION,
    METRIC_KEY_ALIASES,
    METRICS_POLICY_FILE,
    MODEL_SUITE_FILE,
    PREREGISTRATION_FILES,
    PREREGISTRATION_HASH_FILE,
    PRIMARY_METRICS,
    PROTOCOL_FILE,
    SECONDARY_DIAGNOSTICS,
    SOURCE_MANIFEST_FILE,
    TARGET_POLICY_FILE,
    read_preregistration_hash,
)
from elementzero.experiments.runner import (
    DATA_AUDIT_DIRNAME,
    ENVIRONMENT_FILE,
    FREEZE_FILE,
    RUN_MANIFEST_FILE,
    RUNS_DIRNAME,
    SCORE_MANIFEST_FILE,
    SCORED_PREDICTIONS_FILE,
    SCORING_DIRNAME,
    SEALED_PREDICTIONS_FILE,
    SEALED_PREDICTIONS_HASH_FILE,
    TARGETS_DIGEST_FILE,
    parse_report_name,
)
from elementzero.reporting import figures as fig

REPORT_VERSION = "v1"
REPORT_DIRNAME = "reports/historical/v1"
REPORT_MARKDOWN = "ElementZero_Historical_Benchmark_Report_v1.md"
README_FILE = "README.md"
AGGREGATE_METRICS_JSON = "aggregate_metrics.json"
MODEL_TABLE_CSV = "model_table.csv"
DISTANCE_TABLE_CSV = "distance_table.csv"
ARTIFACT_MANIFEST_JSON = "artifact_manifest.json"
BENCHMARK_STATUS_JSON = "benchmark_status.json"
FIGURES_DIRNAME = "figures"
SHA256SUMS_FILE = "SHA256SUMS.txt"

REPORT_TITLE = "ElementZero Historical Benchmark Report v1"
REPRODUCE_SCRIPT = "scripts/reproduce_historical_report.py"
RELEASE_TAG = "elementzero-historical-benchmark-v1"

# The 20 sections WO-08 section 1 requires, in order. The report is generated
# from this tuple so a section cannot silently disappear.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Research question",
    "Protocol and preregistration",
    "Data editions",
    "Ground-truth eligibility policy",
    "Leakage controls",
    "Model definitions",
    "Uncertainty definitions",
    "Metrics",
    "EZ-B001-A results",
    "EZ-B001-B results",
    "EZ-B001-C results",
    "Longitudinal comparison",
    "Error vs extrapolation distance",
    "Calibration",
    "Model failures",
    "Limitations",
    "Deviations from preregistration",
    "Reproducibility instructions",
    "Artifact hashes",
    "Next benchmark decision",
)

POST_HOC_LABEL = "POST_HOC"

# Quantities this report adds on top of the preregistered metric set. They are
# diagnostics, not preregistered metrics, so they carry the POST_HOC label
# everywhere they appear (WO-08 section 2, metrics policy post_hoc_rule).
POST_HOC_FIELDS: tuple[str, ...] = (
    "metric_delta_first_to_last_epoch",
    "calibration_delta_first_to_last_epoch",
    "mae_non_decreasing_with_distance",
    "mean_predictive_sigma_keV",
    "rmse_over_mean_predictive_sigma",
    "coverage_gap_below_nominal",
    "known_failure_screen",
)

# POST_HOC screening thresholds for the failure list in section 15. They select
# which rows are called out; they never remove a row from any table.
CALIBRATION_TOLERANCE = 0.05
SIGMA_UNDERSTATEMENT_RATIO = 2.0

ALLOWED_CONCLUSIONS: tuple[str, ...] = (
    "interpolation and extrapolation behaviour on later-edition nuclides",
    "historical predictive accuracy of the three frozen models",
    "calibration of the reported predictive intervals",
    "degradation of error with nearest-training L1 distance",
    "relative behaviour of the three model families under one protocol",
)

FORBIDDEN_CONCLUSIONS: tuple[str, ...] = (
    "no claim that a model learned nuclear physics",
    "no significance test, p-value, or confidence statement that was not preregistered",
    "no best-model label and no single-metric ranking",
    "no extrapolation of these results to nuclides outside the scored target sets",
)

EVIDENCE_CHAIN: tuple[str, ...] = (
    "source",
    "normalized dataset",
    "freeze",
    "model fit",
    "prediction set",
    "finalization",
    "truth",
    "validation",
)

PRIMARY_TABLE_COLUMNS: tuple[str, ...] = (
    "Experiment",
    "Model",
    "N",
    "MAE",
    "MedAE",
    "RMSE",
    "NLPD",
    "Cov90",
    "Cov95",
)
PRIMARY_TABLE_KEYS: tuple[str, ...] = (
    "experiment_id",
    "model_id",
    "n",
    "MAE_keV",
    "MedAE_keV",
    "RMSE_keV",
    "NLPD",
    "coverage_90",
    "coverage_95",
)

CALIBRATION_TABLE_COLUMNS: tuple[str, ...] = ("Experiment", "Model", "CalErr90", "CalErr95")
CALIBRATION_TABLE_KEYS: tuple[str, ...] = (
    "experiment_id",
    "model_id",
    "cal_error_90",
    "cal_error_95",
)

DISTANCE_TABLE_COLUMNS: tuple[str, ...] = (
    "Experiment",
    "Model",
    "DistanceBucket",
    "N",
    "MAE",
    "RMSE",
    "NLPD",
)
DISTANCE_TABLE_KEYS: tuple[str, ...] = (
    "experiment_id",
    "model_id",
    "distance_bucket",
    "n",
    "MAE_keV",
    "RMSE_keV",
    "NLPD",
)

REGION_TABLE_COLUMNS: tuple[str, ...] = (
    "Experiment",
    "Model",
    "Region",
    "N",
    "MAE",
    "RMSE",
    "NLPD",
    "MeanIsospinAsymmetry",
)
REGION_TABLE_KEYS: tuple[str, ...] = (
    "experiment_id",
    "model_id",
    "region",
    "n",
    "MAE_keV",
    "RMSE_keV",
    "NLPD",
    "mean_isospin_asymmetry",
)

CALIBRATION_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "model_id",
    "coverage_90",
    "coverage_95",
    "cal_error_90",
    "cal_error_95",
)

REGION_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "model_id",
    "region",
    "n",
    "MAE_keV",
    "RMSE_keV",
    "NLPD",
    "mean_isospin_asymmetry",
)

NOMINAL_COVERAGE = {"coverage_90": 0.90, "coverage_95": 0.95}


# --------------------------------------------------------------------------- #
# Formatting                                                                  #
# --------------------------------------------------------------------------- #


def display(value: Any) -> str:
    """Human-readable cell for the markdown tables.

    Markdown is the display layer: it rounds. The machine-readable values live
    in ``aggregate_metrics.json`` and in the two CSV files, and the tests check
    the prose against them through this exact function.
    """
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def csv_cell(value: Any) -> str:
    """Lossless cell for the CSV files (ADR-0002 numeric serialization)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".12e")
    text = str(value)
    return f'"{text}"' if "," in text or '"' in text else text


def csv_table(columns: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(csv_cell(row.get(column)) for column in columns))
    return "\n".join(lines) + "\n"


def markdown_table(
    columns: tuple[str, ...],
    keys: tuple[str, ...],
    rows: list[dict[str, Any]],
) -> list[str]:
    out = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(display(row.get(key)) for key in keys) + " |")
    return out


def _heading(index: int) -> str:
    return f"## {index}. {REQUIRED_SECTIONS[index - 1]}"


# --------------------------------------------------------------------------- #
# Committed inputs                                                            #
# --------------------------------------------------------------------------- #


def _hashed(root: Path, relpath: str, role: str) -> dict[str, str]:
    path = root / relpath
    if not path.is_file():
        raise ProtocolError(f"the report needs committed artifact {relpath}, which is missing")
    return {"path": relpath, "sha256": sha256_file(path), "role": role}


def load_epoch(root: Path, experiment_id: str) -> dict[str, Any]:
    """Every committed artifact of one scored epoch that the report reads."""
    relative = f"experiments/{experiment_id}"
    base = root / relative
    epoch = epoch_for(experiment_id)
    protocol = read_json(base / PROTOCOL_FILE)
    score_manifest = read_json(base / SCORE_MANIFEST_FILE)
    sealed = read_json(base / SEALED_PREDICTIONS_FILE)
    comparison = read_json(base / COMPARISON_JSON_NAME)
    targets = read_json(base / TARGETS_DIGEST_FILE)

    sealed_hash = (base / SEALED_PREDICTIONS_HASH_FILE).read_text(encoding="utf-8").strip()
    if sha256_file(base / SEALED_PREDICTIONS_FILE) != sealed_hash:
        raise ProtocolError(f"{experiment_id}: {SEALED_PREDICTIONS_FILE} does not match its hash file")
    if score_manifest["sealed_predictions_sha256"] != sealed_hash:
        raise ProtocolError(f"{experiment_id}: the score manifest points at a different seal")
    if score_manifest["model_comparison"]["sha256"] != sha256_file(base / COMPARISON_JSON_NAME):
        raise ProtocolError(f"{experiment_id}: {COMPARISON_JSON_NAME} does not match the score manifest")

    inputs = [
        _hashed(root, f"{relative}/{name}", "preregistration")
        for name in (*PREREGISTRATION_FILES, PREREGISTRATION_HASH_FILE)
    ]
    inputs.append(_hashed(root, f"{relative}/{TARGETS_DIGEST_FILE}", "identity-only target digest"))
    inputs.append(_hashed(root, f"{relative}/{FREEZE_FILE}", "knowledge freeze"))
    inputs.append(_hashed(root, f"{relative}/{SEALED_PREDICTIONS_FILE}", "experiment-level seal"))
    inputs.append(_hashed(root, f"{relative}/{RUN_MANIFEST_FILE}", "seal-phase manifest"))
    inputs.append(_hashed(root, f"{relative}/{SCORE_MANIFEST_FILE}", "score-phase manifest"))
    inputs.append(_hashed(root, f"{relative}/{COMPARISON_JSON_NAME}", "model comparison"))
    inputs.append(_hashed(root, f"{relative}/{ENVIRONMENT_FILE}", "run environment"))

    audits = {}
    for edition in (epoch.training_edition, epoch.truth_edition):
        relpath = f"{relative}/{DATA_AUDIT_DIRNAME}/{parse_report_name(edition)}"
        audits[edition] = read_json(root / relpath)
        inputs.append(_hashed(root, relpath, f"{edition} parse report"))

    scored: dict[str, list[dict[str, Any]]] = {}
    scored_relpaths: dict[str, str] = {}
    for model_id in SUITE_MODEL_IDS:
        run = f"{relative}/{RUNS_DIRNAME}/{model_id}"
        scored_relpath = f"{run}/{SCORING_DIRNAME}/{SCORED_PREDICTIONS_FILE}"
        payload = read_json(root / scored_relpath)
        if payload["model_id"] != model_id or payload["experiment_id"] != experiment_id:
            raise ProtocolError(f"{scored_relpath} does not belong to {experiment_id}/{model_id}")
        scored[model_id] = payload["rows"]
        scored_relpaths[model_id] = scored_relpath
        inputs.append(_hashed(root, scored_relpath, "scored predictions"))
        inputs.append(_hashed(root, f"{run}/{SCORING_DIRNAME}/metrics.json", "metrics"))
        inputs.append(_hashed(root, f"{run}/{SCORING_DIRNAME}/score_report.json", "score report"))
        inputs.append(_hashed(root, f"{run}/predictions.json", "sealed predictions"))
        inputs.append(_hashed(root, f"{run}/LEDGER_FINALIZED", "finalization marker"))

    return {
        "experiment_id": experiment_id,
        "experiment_relpath": relative,
        "epoch": epoch,
        "protocol": protocol,
        "preregistration": {
            name: read_json(base / name)
            for name in (SOURCE_MANIFEST_FILE, TARGET_POLICY_FILE, MODEL_SUITE_FILE, METRICS_POLICY_FILE)
        },
        "preregistration_hash": read_preregistration_hash(base),
        "score_manifest": score_manifest,
        "sealed": sealed,
        "sealed_predictions_sha256": sealed_hash,
        "comparison": comparison,
        "targets": targets,
        "data_audit": audits,
        "scored_rows": scored,
        "scored_relpaths": scored_relpaths,
        "comparison_relpath": f"{relative}/{COMPARISON_JSON_NAME}",
        "inputs": inputs,
    }


def load_series(root: str | Path | None = None) -> dict[str, Any]:
    """The scored epoch series plus the committed longitudinal aggregate.

    The aggregate is rebuilt from the committed per-epoch comparisons and checked
    against ``results/EZ-B001/aggregate_v1.json`` byte for byte. A report that
    disagrees with the published aggregate is a defect, not a rounding detail.
    """
    base = Path(root or REPO_ROOT)
    dirs = experiment_dirs(base)
    if not dirs:
        raise ProtocolError("no scored experiment was found; the historical report needs EZ-B001-A/B/C")
    missing = [e for e in EPOCH_ORDER if e not in {d.name for d in dirs}]
    if missing:
        raise ProtocolError(
            f"the historical report covers the declared series {list(EPOCH_ORDER)}; "
            f"unscored epochs {missing} may not be omitted"
        )
    epochs = [load_epoch(base, d.name) for d in dirs]
    aggregate = build_aggregate(dirs)
    rebuilt = canonical_json(aggregate) + "\n"
    aggregate_relpath = f"{AGGREGATE_DIRNAME}/{AGGREGATE_JSON}"
    committed_path = base / aggregate_relpath
    if not committed_path.is_file():
        raise ProtocolError(f"the published aggregate {aggregate_relpath} is missing")
    matches_published = committed_path.read_text(encoding="utf-8") == rebuilt
    if not matches_published:
        raise ProtocolError(
            f"the aggregate rebuilt from the committed comparisons differs from {aggregate_relpath}; "
            "publish the aggregate again instead of reporting two different numbers"
        )
    return {
        "root": base,
        "epochs": epochs,
        "aggregate": aggregate,
        "aggregate_matches_published": matches_published,
        "aggregate_source": _hashed(base, aggregate_relpath, "longitudinal aggregate"),
    }


# --------------------------------------------------------------------------- #
# Derived tables                                                              #
# --------------------------------------------------------------------------- #


def edition_rows(epochs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per AME edition, with its role in each epoch it appears in.

    AME2012 is truth for epoch A and training for epoch B. The same file must
    therefore hash to the same value in both epochs; disagreement means the
    series is not one data lineage.
    """
    rows: dict[str, dict[str, Any]] = {}
    for entry in epochs:
        epoch = entry["epoch"]
        sources = entry["preregistration"][SOURCE_MANIFEST_FILE]
        for role, edition, source in (
            ("training", epoch.training_edition, sources["training_source"]),
            ("truth", epoch.truth_edition, sources["later_source"]),
        ):
            audit = entry["data_audit"][edition]
            row = rows.setdefault(
                edition,
                {
                    "edition_id": edition,
                    "raw_filename": audit["raw_filename"],
                    "raw_relpath": source["raw_relpath"],
                    "raw_sha256": audit["raw_source_hash"],
                    "release_date": audit["release_date"],
                    "parser_version": audit["parser_version"],
                    "parsed_records": int(audit["parsed_records"]),
                    "eligible_records": int(audit["eligible_records"]),
                    "estimated_records": int(audit["estimated_records"]),
                    "duplicate_ids": int(audit["duplicate_ids"]),
                    "malformed_fraction": number(audit["malformed_fraction"]),
                    "invalid_A_equals_Z_plus_N": int(audit["invalid_A_equals_Z_plus_N"]),
                    "source_uri": AMDC_URLS[edition],
                    "citation": AME_CITATIONS[edition],
                    "roles": [],
                },
            )
            if row["raw_sha256"] != audit["raw_source_hash"]:
                raise ProtocolError(
                    f"{edition} has two different raw hashes across the series: "
                    f"{row['raw_sha256']} and {audit['raw_source_hash']}"
                )
            if source["raw_sha256"] != audit["raw_source_hash"]:
                raise ProtocolError(f"{edition}: the source manifest and the parse report disagree on the hash")
            row["roles"].append(f"{role} in {entry['experiment_id']}")
    return [rows[edition] for edition in sorted(rows, key=lambda e: rows[e]["release_date"])]


def calibration_rows(aggregate: dict[str, Any]) -> list[dict[str, Any]]:
    return [{column: row[column] for column in CALIBRATION_COLUMNS} for row in aggregate["rows"]]


def sigma_diagnostics(epochs: list[dict[str, Any]], aggregate: dict[str, Any]) -> list[dict[str, Any]]:
    """POST_HOC: mean reported sigma against RMSE, per epoch and model.

    NLPD already penalises an interval that is too narrow, but it mixes width and
    error into one number. The ratio makes the direction explicit: a value above
    one means the reported sigma is smaller than the realised error.
    """
    rmse = {(r["experiment_id"], r["model_id"]): r["RMSE_keV"] for r in aggregate["rows"]}
    out = []
    for entry in epochs:
        for model_id in SUITE_MODEL_IDS:
            rows = entry["scored_rows"][model_id]
            sigmas = [float(number(row["std_keV"])) for row in rows]
            mean_sigma = sum(sigmas) / len(sigmas) if sigmas else None
            error = rmse[(entry["experiment_id"], model_id)]
            ratio = None
            if mean_sigma not in (None, 0.0) and error is not None:
                ratio = float(error) / float(mean_sigma)
            out.append(
                {
                    "experiment_id": entry["experiment_id"],
                    "model_id": model_id,
                    "n": len(rows),
                    "mean_predictive_sigma_keV": mean_sigma,
                    "rmse_over_mean_predictive_sigma": ratio,
                    "label": POST_HOC_LABEL,
                }
            )
    return out


def coverage_gaps(aggregate: dict[str, Any]) -> list[dict[str, Any]]:
    """POST_HOC: signed shortfall of each coverage against its nominal level."""
    out = []
    for row in aggregate["rows"]:
        for key, nominal in NOMINAL_COVERAGE.items():
            coverage = row[key]
            if coverage is None:
                continue
            out.append(
                {
                    "experiment_id": row["experiment_id"],
                    "model_id": row["model_id"],
                    "coverage": key,
                    "nominal": nominal,
                    "observed": coverage,
                    "coverage_gap_below_nominal": max(nominal - float(coverage), 0.0),
                    "label": POST_HOC_LABEL,
                }
            )
    return out


def known_failures(
    *,
    aggregate: dict[str, Any],
    sigma_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """POST_HOC screen over the committed metrics; nothing here is removed elsewhere.

    Screening rules, all applied to every epoch and model:

        undercoverage_90 / undercoverage_95
            observed coverage is below the nominal level; severity records
            whether the calibration error exceeds CALIBRATION_TOLERANCE
        overcoverage_90 / overcoverage_95
            observed coverage exceeds the nominal level by more than
            CALIBRATION_TOLERANCE, which means the interval is too wide
        predictive_sigma_understates_error
            RMSE exceeds SIGMA_UNDERSTATEMENT_RATIO times the mean reported sigma
        predictive_sigma_overstates_error
            RMSE is below the reciprocal of that ratio times the mean sigma
        error_not_non_decreasing_with_distance
            MAE does not grow monotonically across the populated distance buckets
        metric_worsens_across_epochs
            MAE, RMSE, or NLPD is worse in the last epoch than in the first
    """
    failures: list[dict[str, Any]] = []
    for row in aggregate["rows"]:
        for key, nominal in NOMINAL_COVERAGE.items():
            observed = row[key]
            if observed is None:
                continue
            level = key.rsplit("_", 1)[-1]
            cal_key = f"cal_error_{level}"
            cal_error = float(row[cal_key])
            severity = (
                "outside_calibration_tolerance"
                if cal_error > CALIBRATION_TOLERANCE
                else "within_calibration_tolerance"
            )
            if float(observed) < nominal:
                failures.append(
                    {
                        "kind": f"undercoverage_{level}",
                        "experiment_id": row["experiment_id"],
                        "model_id": row["model_id"],
                        "detail": (
                            f"{key} = {display(observed)} is below the nominal {nominal}; "
                            f"{cal_key} = {display(cal_error)}"
                        ),
                        "severity": severity,
                        "retained": True,
                        "label": POST_HOC_LABEL,
                    }
                )
            elif float(observed) - nominal > CALIBRATION_TOLERANCE:
                failures.append(
                    {
                        "kind": f"overcoverage_{level}",
                        "experiment_id": row["experiment_id"],
                        "model_id": row["model_id"],
                        "detail": (
                            f"{key} = {display(observed)} exceeds the nominal {nominal} by more than "
                            f"{display(CALIBRATION_TOLERANCE)}; the reported interval is too wide, and "
                            f"{cal_key} = {display(cal_error)}"
                        ),
                        "severity": severity,
                        "retained": True,
                        "label": POST_HOC_LABEL,
                    }
                )
    for row in sigma_rows:
        ratio = row["rmse_over_mean_predictive_sigma"]
        if ratio is None:
            continue
        kind = None
        if ratio > SIGMA_UNDERSTATEMENT_RATIO:
            kind = "predictive_sigma_understates_error"
        elif ratio < 1.0 / SIGMA_UNDERSTATEMENT_RATIO:
            kind = "predictive_sigma_overstates_error"
        if kind is None:
            continue
        failures.append(
            {
                "kind": kind,
                "experiment_id": row["experiment_id"],
                "model_id": row["model_id"],
                "detail": (
                    f"RMSE is {display(ratio)} times the mean reported sigma "
                    f"({display(row['mean_predictive_sigma_keV'])} keV)"
                ),
                "severity": "outside_calibration_tolerance",
                "retained": True,
                "label": POST_HOC_LABEL,
            }
        )
    for model_id, diagnostics in aggregate["stability"].items():
        for experiment_id, trend in diagnostics["error_vs_distance_trend"].items():
            if trend["mae_non_decreasing_with_distance"] is False:
                populated = [
                    f"{bucket} = {display(value)}"
                    for bucket, value in zip(trend["buckets"], trend["MAE_keV"])
                    if bucket in trend["populated_buckets"]
                ]
                failures.append(
                    {
                        "kind": "error_not_non_decreasing_with_distance",
                        "experiment_id": experiment_id,
                        "model_id": model_id,
                        "detail": (
                            "MAE over the populated buckets ("
                            + ", ".join(populated)
                            + ") is not monotonic in distance"
                        ),
                        "severity": "diagnostic",
                        "retained": True,
                        "label": POST_HOC_LABEL,
                    }
                )
        for metric in ("MAE_keV", "RMSE_keV", "NLPD"):
            drift = diagnostics["metric_drift"][metric]
            if drift["delta"] is not None and float(drift["delta"]) > 0:
                failures.append(
                    {
                        "kind": "metric_worsens_across_epochs",
                        "experiment_id": f"{aggregate['experiment_ids'][0]} -> {aggregate['experiment_ids'][-1]}",
                        "model_id": model_id,
                        "detail": (
                            f"{metric} moved from {display(drift['first'])} to {display(drift['last'])} "
                            f"(delta {display(drift['delta'])})"
                        ),
                        "severity": "diagnostic",
                        "retained": True,
                        "label": POST_HOC_LABEL,
                    }
                )
    return failures


def deviations(epochs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Disclosed differences between the preregistration and what was published."""
    protocol = epochs[0]["protocol"]
    out = [
        {
            "id": "artifact-layout",
            "status": "disclosed",
            "preregistered": "WO-06 lists runs/<experiment>/<model> and results/<experiment>/<model>",
            "actual": "experiments/<experiment>/runs/<model> keeps seal, scoring, and Atlas bundle together",
            "affects_numbers": False,
            "reference": "experiments/<experiment>/RUN_MANIFEST.json -> artifact_layout.layout_note",
        },
        {
            "id": "atlas-packaging-overlay",
            "status": "approved exception",
            "preregistered": "Atlas PIR is consumed as a commit-pinned upstream dependency",
            "actual": (
                "the pinned Atlas commit is installed through the ensure overlay in "
                "tools/ensure_atlas_pir.py; the pin itself is unchanged"
            ),
            "affects_numbers": False,
            "reference": protocol["atlas_packaging_exception"],
        },
        {
            "id": "post-hoc-diagnostics",
            "status": f"{POST_HOC_LABEL} additions, labelled",
            "preregistered": (
                "primary metrics " + ", ".join(PRIMARY_METRICS) + "; secondary diagnostics "
                + ", ".join(SECONDARY_DIAGNOSTICS)
            ),
            "actual": (
                f"this report adds the {POST_HOC_LABEL} fields " + ", ".join(POST_HOC_FIELDS)
            ),
            "affects_numbers": False,
            "reference": f"{REPORT_DIRNAME}/{AGGREGATE_METRICS_JSON} -> post_hoc",
        },
        {
            "id": "raw-tables-not-committed",
            "status": "disclosed",
            "preregistered": "raw AME tables stay gitignored; hashes, URLs, and parse reports are committed",
            "actual": "unchanged; a rebuild without data/raw verifies hashes and skips the truth replay",
            "affects_numbers": False,
            "reference": f"experiments/<experiment>/{SOURCE_MANIFEST_FILE} -> raw_files_note",
        },
    ]
    for entry in epochs:
        protocol = entry["protocol"]
        if protocol["protocol_version"] != EXPERIMENT_PROTOCOL_VERSION:
            out.append(
                {
                    "id": f"protocol-version-{entry['experiment_id']}",
                    "status": "violation",
                    "preregistered": EXPERIMENT_PROTOCOL_VERSION,
                    "actual": protocol["protocol_version"],
                    "affects_numbers": True,
                    "reference": f"{entry['experiment_relpath']}/{PROTOCOL_FILE}",
                }
            )
    return out


def assert_no_missing_primary_metric(aggregate: dict[str, Any]) -> None:
    """Every preregistered primary metric exists for every epoch and model."""
    expected = {(e, m) for e in aggregate["experiment_ids"] for m in SUITE_MODEL_IDS}
    present = {(r["experiment_id"], r["model_id"]) for r in aggregate["rows"]}
    if present != expected:
        raise ProtocolError(f"the report needs one row per epoch and model; missing {sorted(expected - present)}")
    for row in aggregate["rows"]:
        for metric in PRIMARY_METRICS:
            key = METRIC_KEY_ALIASES.get(metric, metric)
            if row.get(key) is None:
                raise ProtocolError(
                    f"{row['experiment_id']}/{row['model_id']} has no {metric}; a primary metric "
                    "is never omitted, not even when it is poor"
                )


def build_metrics(series: dict[str, Any]) -> dict[str, Any]:
    """The machine-readable payload every table and figure is rendered from."""
    aggregate = series["aggregate"]
    epochs = series["epochs"]
    assert_no_missing_primary_metric(aggregate)
    metrics_policy = epochs[0]["preregistration"][METRICS_POLICY_FILE]
    suite = epochs[0]["preregistration"][MODEL_SUITE_FILE]
    policies = {e["protocol"]["ground_truth_policy"] for e in epochs}
    if len(policies) != 1:
        raise ProtocolError(f"the epochs do not share one ground-truth policy: {sorted(policies)}")
    sigma_rows = sigma_diagnostics(epochs, aggregate)
    metric_status = {metric: "preregistered" for metric in PRIMARY_METRICS}
    metric_status.update({field: POST_HOC_LABEL for field in POST_HOC_FIELDS})
    return {
        "report_version": REPORT_VERSION,
        "report_title": REPORT_TITLE,
        "benchmark_id": BENCHMARK_EZ_B001,
        "protocol_version": aggregate["protocol_version"],
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "protocol_code_digest": aggregate["protocol_code_digest"],
        "atlas_repository": epochs[0]["protocol"]["atlas_repository"],
        "atlas_pir_ref": aggregate["atlas_pir_ref"],
        "model_suite_id": MODEL_SUITE_ID,
        "model_ids": list(SUITE_MODEL_IDS),
        "experiment_ids": list(aggregate["experiment_ids"]),
        "features": list(aggregate["features"]),
        "ground_truth_policy": policies.pop(),
        "ranking_rule": aggregate["ranking_rule"],
        "aggregate_source": series["aggregate_source"],
        "aggregate_matches_published": bool(series["aggregate_matches_published"]),
        "epochs": [
            {
                "experiment_id": entry["experiment_id"],
                "training_edition": entry["epoch"].training_edition,
                "truth_edition": entry["epoch"].truth_edition,
                "created_at": entry["epoch"].created_at,
                "n_targets": int(entry["targets"]["n_targets"]),
                "target_identity_digest": entry["targets"]["target_identity_digest"],
                "preregistration_hash": entry["preregistration_hash"],
                "sealed_predictions_sha256": entry["sealed_predictions_sha256"],
                "model_comparison_sha256": entry["score_manifest"]["model_comparison"]["sha256"],
                "training_source_hash": entry["protocol"]["training"]["raw_sha256"],
                "truth_source_hash": entry["protocol"]["later_edition"]["raw_sha256"],
                "freeze_id": entry["sealed"]["freeze_id"],
                "elementzero_commit": entry["score_manifest"]["elementzero_commit"],
                "atlas_pir_ref": entry["score_manifest"]["atlas_pir_ref"],
                "protocol_version": entry["protocol"]["protocol_version"],
                "protocol_code_digest": entry["protocol"]["protocol_code_digest"],
                "target_rule": entry["preregistration"][TARGET_POLICY_FILE]["rule"],
                "estimated_row_rule": entry["preregistration"][TARGET_POLICY_FILE]["estimated_row_rule"],
                "experiment_relpath": entry["experiment_relpath"],
                "validation_fact_ids": {
                    model["model_id"]: model["validation_fact_id"]
                    for model in entry["score_manifest"]["models"]
                },
                "truth_dataset_fact_ids": sorted(
                    {model["truth_dataset_fact_id"] for model in entry["score_manifest"]["models"]}
                ),
                "prediction_set_fact_ids": {
                    run["model_id"]: run["prediction_set_fact_id"] for run in entry["sealed"]["runs"]
                },
                "finalization_marker_hashes": {
                    run["model_id"]: run["finalization_marker_hash"] for run in entry["sealed"]["runs"]
                },
                "state": entry["sealed"]["state"],
            }
            for entry in epochs
        ],
        "editions": edition_rows(epochs),
        "models": suite["models"],
        "feature_policy_id": suite["feature_policy_id"],
        "forbidden_features": list(suite["forbidden_features"]),
        "metrics_policy_id": metrics_policy["metrics_policy_id"],
        "metric_definitions": metrics_policy["definitions"],
        "interval_construction": metrics_policy["interval_construction"],
        "preregistered_primary_metrics": list(PRIMARY_METRICS),
        "preregistered_secondary_diagnostics": list(SECONDARY_DIAGNOSTICS),
        "metric_status": metric_status,
        "post_hoc": {
            "label": POST_HOC_LABEL,
            "rule": metrics_policy["post_hoc_rule"],
            "fields": list(POST_HOC_FIELDS),
            "calibration_tolerance": CALIBRATION_TOLERANCE,
            "sigma_understatement_ratio": SIGMA_UNDERSTATEMENT_RATIO,
        },
        "model_columns": list(MODEL_COLUMNS),
        "rows": aggregate["rows"],
        "calibration_columns": list(CALIBRATION_COLUMNS),
        "calibration_rows": calibration_rows(aggregate),
        "distance_policy_id": DISTANCE_POLICY_ID,
        "distance_buckets": list(DISTANCE_BUCKET_IDS),
        "distance_columns": list(DISTANCE_COLUMNS),
        "distance_rows": aggregate["distance_rows"],
        "region_policy_id": REGION_POLICY_ID,
        "regions": list(REGION_IDS),
        "region_columns": list(REGION_COLUMNS),
        "region_rows": aggregate["region_rows"],
        "stability": aggregate["stability"],
        "post_hoc_sigma_rows": sigma_rows,
        "post_hoc_coverage_gaps": coverage_gaps(aggregate),
        "known_failures": known_failures(aggregate=aggregate, sigma_rows=sigma_rows),
        "deviations": deviations(epochs),
        "allowed_conclusions": list(ALLOWED_CONCLUSIONS),
        "forbidden_conclusions": list(FORBIDDEN_CONCLUSIONS),
        "evidence_chain": list(EVIDENCE_CHAIN),
    }


# --------------------------------------------------------------------------- #
# Figures                                                                     #
# --------------------------------------------------------------------------- #


def _bar_groups(
    metrics: dict[str, Any], column: str
) -> tuple[list[fig.BarGroup], list[str], list[str]]:
    by_key = {(r["experiment_id"], r["model_id"]): r[column] for r in metrics["rows"]}
    labels = list(SUITE_MODEL_IDS)
    colours = [fig.colour_for(label, index) for index, label in enumerate(labels)]
    groups = [
        fig.BarGroup(
            label=experiment_id,
            values=tuple(
                None if by_key.get((experiment_id, model)) is None else float(by_key[(experiment_id, model)])
                for model in labels
            ),
        )
        for experiment_id in metrics["experiment_ids"]
    ]
    return groups, labels, colours


def build_figures(series: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministic SVGs, each declaring the committed artifacts it came from."""
    out: list[dict[str, Any]] = []
    comparison_sources = [
        {"path": entry["comparison_relpath"], "sha256": sha256_file(series["root"] / entry["comparison_relpath"])}
        for entry in series["epochs"]
    ]

    for entry in series["epochs"]:
        experiment_id = entry["experiment_id"]
        sources = [
            {"path": relpath, "sha256": sha256_file(series["root"] / relpath)}
            for relpath in (entry["scored_relpaths"][m] for m in SUITE_MODEL_IDS)
        ]
        truth_series = []
        error_series = []
        for index, model_id in enumerate(SUITE_MODEL_IDS):
            rows = entry["scored_rows"][model_id]
            colour = fig.colour_for(model_id, index)
            truth_series.append(
                fig.Series(
                    label=model_id,
                    colour=colour,
                    points=tuple(
                        (float(number(r["truth_keV"])), float(number(r["prediction_keV"]))) for r in rows
                    ),
                )
            )
            error_series.append(
                fig.Series(
                    label=model_id,
                    colour=colour,
                    points=tuple(
                        (
                            float(r["nearest_training_L1"]),
                            abs(float(number(r["prediction_keV"])) - float(number(r["truth_keV"]))),
                        )
                        for r in rows
                    ),
                )
            )
        out.append(
            {
                "file": f"predicted_vs_truth_{experiment_id}.svg",
                "title": f"{experiment_id}: predicted versus truth mass excess",
                "kind": "scatter",
                "sources": sources,
                "svg": fig.scatter_svg(
                    title=f"{experiment_id} predicted vs truth mass excess (keV)",
                    x_label=f"{entry['epoch'].truth_edition} truth mass excess (keV)",
                    y_label="predicted mass excess (keV)",
                    series=tuple(truth_series),
                    identity_line=True,
                ),
            }
        )
        distances = [p[0] for s in error_series for p in s.points]
        out.append(
            {
                "file": f"abs_error_vs_distance_{experiment_id}.svg",
                "title": f"{experiment_id}: absolute error versus nearest-training L1 distance",
                "kind": "scatter",
                "sources": sources,
                "svg": fig.scatter_svg(
                    title=f"{experiment_id} absolute error vs nearest-training L1 distance",
                    x_label="nearest_training_L1",
                    y_label="absolute error (keV)",
                    series=tuple(error_series),
                    x_range=(min(distances) - 0.5, max(distances) + 0.5),
                ),
            }
        )

    for column, title, y_label, reference in (
        ("MAE_keV", "MAE by epoch and model", "MAE (keV)", ()),
        ("RMSE_keV", "RMSE by epoch and model", "RMSE (keV)", ()),
        ("NLPD", "NLPD by epoch and model", "NLPD (nats)", ()),
        (
            "coverage_90",
            "90 percent interval coverage by epoch and model",
            "coverage_90",
            ((0.90, "nominal 0.90"),),
        ),
        (
            "coverage_95",
            "95 percent interval coverage by epoch and model",
            "coverage_95",
            ((0.95, "nominal 0.95"),),
        ),
    ):
        groups, labels, colours = _bar_groups(metrics, column)
        out.append(
            {
                "file": f"{column.lower()}_by_epoch.svg",
                "title": title,
                "kind": "grouped_bar",
                "sources": comparison_sources,
                "svg": fig.grouped_bar_svg(
                    title=title,
                    x_label="experiment",
                    y_label=y_label,
                    series_labels=labels,
                    colours=colours,
                    groups=tuple(groups),
                    reference_lines=reference,
                ),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Machine-readable status                                                     #
# --------------------------------------------------------------------------- #


def build_status(metrics: dict[str, Any]) -> dict[str, Any]:
    """WO-08 section 8 status file.

    ``engineering_status`` is a protocol-integrity statement over gates that can
    be checked mechanically. It contains no accuracy threshold, and the
    scientific verdict is deliberately null: this benchmark measures behaviour,
    it does not certify a model.
    """
    epochs = metrics["epochs"]
    gates = {
        "all_declared_epochs_scored": list(metrics["experiment_ids"]) == list(EPOCH_ORDER),
        "all_models_reported_in_every_epoch": all(
            any(r["experiment_id"] == e and r["model_id"] == m for r in metrics["rows"])
            for e in metrics["experiment_ids"]
            for m in metrics["model_ids"]
        ),
        "one_protocol_version_across_epochs": {e["protocol_version"] for e in epochs}
        == {EXPERIMENT_PROTOCOL_VERSION},
        "one_protocol_code_digest_across_epochs": len({e["protocol_code_digest"] for e in epochs}) == 1,
        "one_atlas_pin_across_epochs": len({e["atlas_pir_ref"] for e in epochs}) == 1,
        "every_primary_metric_present": all(
            row[METRIC_KEY_ALIASES.get(metric, metric)] is not None
            for row in metrics["rows"]
            for metric in PRIMARY_METRICS
        ),
        "report_matches_published_aggregate": metrics["aggregate_matches_published"],
        "predictions_sealed_before_truth": all(
            e["state"] == "PREDICTIONS_SEALED_TRUTH_LOCKED" for e in epochs
        ),
        "post_hoc_fields_labelled": all(
            metrics["metric_status"][field] == POST_HOC_LABEL for field in metrics["post_hoc"]["fields"]
        ),
        "deviations_disclosed": all(d["status"] != "violation" for d in metrics["deviations"]),
    }
    return {
        "protocol_version": metrics["protocol_version"],
        "report_version": REPORT_VERSION,
        "benchmark_id": metrics["benchmark_id"],
        "status_rule": (
            "There is no single PASS field for this benchmark. engineering_status covers "
            "protocol integrity only and contains no accuracy threshold; the scientific "
            "verdict stays null because the benchmark measures behaviour rather than "
            "certifying a model."
        ),
        "experiments_completed": [
            {
                "experiment_id": epoch["experiment_id"],
                "training_edition": epoch["training_edition"],
                "truth_edition": epoch["truth_edition"],
                "n_targets": epoch["n_targets"],
                "models_scored": list(metrics["model_ids"]),
                "preregistration_hash": epoch["preregistration_hash"],
                "sealed_predictions_sha256": epoch["sealed_predictions_sha256"],
                "state": "SCORED",
            }
            for epoch in epochs
        ],
        "models": [
            {
                "model_id": model["model_id"],
                "implementation": f"{model['implementation_path']}::{model['implementation_symbol']}",
                "uncertainty_method": model["uncertainty_method"],
                "predictive_distribution": model["predictive_distribution"],
                "epochs_reported": [
                    row["experiment_id"] for row in metrics["rows"] if row["model_id"] == model["model_id"]
                ],
            }
            for model in metrics["models"]
        ],
        "engineering_status": {
            "scope": "protocol integrity of the committed EZ-B001 series",
            "gates": gates,
            "gates_pass": all(gates.values()),
            "note": (
                "gates_pass is an engineering statement about preregistration, sealing, "
                "hashing, and completeness. It is not a scientific verdict and it does "
                "not depend on how accurate any model is."
            ),
        },
        "scientific_summary": {
            "verdict": None,
            "measured": list(metrics["allowed_conclusions"]),
            "not_claimed": list(metrics["forbidden_conclusions"]),
            "primary_metrics_reference": f"{REPORT_DIRNAME}/{AGGREGATE_METRICS_JSON} -> rows",
            "calibration_reference": f"{REPORT_DIRNAME}/{AGGREGATE_METRICS_JSON} -> calibration_rows",
            "distance_reference": f"{REPORT_DIRNAME}/{AGGREGATE_METRICS_JSON} -> distance_rows",
            "observed": {
                "epochs": len(epochs),
                "models": len(metrics["model_ids"]),
                "scored_targets": sum(epoch["n_targets"] for epoch in epochs),
                "undercovered_model_epochs": sorted(
                    {
                        f"{f['experiment_id']}/{f['model_id']}"
                        for f in metrics["known_failures"]
                        if f["kind"].startswith("undercoverage")
                    }
                ),
                "overcovered_model_epochs": sorted(
                    {
                        f"{f['experiment_id']}/{f['model_id']}"
                        for f in metrics["known_failures"]
                        if f["kind"].startswith("overcoverage")
                    }
                ),
                "failure_kinds": sorted({f["kind"] for f in metrics["known_failures"]}),
            },
        },
        "known_failures": list(metrics["known_failures"]),
        "next_gate": {
            "work_order": "WO-09",
            "benchmark_id": "EZ-B002",
            "title": "Geographic Nuclear-Chart Holdout",
            "blocked_until": [
                "this report exists in the repository",
                f"{REPRODUCE_SCRIPT} passes without --refit",
                "unresolved data or parser issues are documented",
                "any benchmark protocol change is versioned rather than edited in place",
            ],
            "recommended_release_tag": RELEASE_TAG,
        },
    }


# --------------------------------------------------------------------------- #
# Prose                                                                       #
# --------------------------------------------------------------------------- #


def _epoch_metrics(metrics: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    for epoch in metrics["epochs"]:
        if epoch["experiment_id"] == experiment_id:
            return epoch
    raise ProtocolError(f"{experiment_id} is not in the report payload")


def _epoch_section(metrics: dict[str, Any], index: int, experiment_id: str) -> list[str]:
    epoch = _epoch_metrics(metrics, experiment_id)
    rows = [r for r in metrics["rows"] if r["experiment_id"] == experiment_id]
    lines = [
        _heading(index),
        "",
        f"{epoch['training_edition']} is the only training source; {epoch['truth_edition']} is the "
        f"scored truth. {epoch['n_targets']} nuclides became ground-truth eligible in "
        f"{epoch['truth_edition']} and are scored for all three models.",
        "",
        "```text",
        f"experiment_id              = {epoch['experiment_id']}",
        f"n_targets                  = {epoch['n_targets']}",
        f"freeze_id                  = {epoch['freeze_id']}",
        f"preregistration_hash       = {epoch['preregistration_hash']}",
        f"sealed_predictions_sha256  = {epoch['sealed_predictions_sha256']}",
        f"target_identity_digest     = {epoch['target_identity_digest']}",
        f"training_source_sha256     = {epoch['training_source_hash']}",
        f"truth_source_sha256        = {epoch['truth_source_hash']}",
        f"seal_state                 = {epoch['state']}",
        "```",
        "",
        f"### {index}.1 Primary metrics",
        "",
    ]
    lines.extend(markdown_table(PRIMARY_TABLE_COLUMNS, PRIMARY_TABLE_KEYS, rows))
    lines.extend(["", f"### {index}.2 Calibration", ""])
    lines.extend(markdown_table(CALIBRATION_TABLE_COLUMNS, CALIBRATION_TABLE_KEYS, rows))
    lines.extend(
        [
            "",
            f"### {index}.3 Error versus nearest-training L1 distance",
            "",
            f"Distance policy `{metrics['distance_policy_id']}`. An empty bucket is reported with "
            "N = 0 rather than dropped.",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            DISTANCE_TABLE_COLUMNS,
            DISTANCE_TABLE_KEYS,
            [r for r in metrics["distance_rows"] if r["experiment_id"] == experiment_id],
        )
    )
    lines.extend(
        [
            "",
            f"### {index}.4 Metrics per Z band (preregistered secondary diagnostic)",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            REGION_TABLE_COLUMNS,
            REGION_TABLE_KEYS,
            [r for r in metrics["region_rows"] if r["experiment_id"] == experiment_id],
        )
    )
    lines.extend(
        [
            "",
            f"Figures: `{FIGURES_DIRNAME}/predicted_vs_truth_{experiment_id}.svg`, "
            f"`{FIGURES_DIRNAME}/abs_error_vs_distance_{experiment_id}.svg`.",
            "",
            "Validation fact ids: "
            + ", ".join(f"{m} = `{i}`" for m, i in sorted(epoch["validation_fact_ids"].items()))
            + ".",
            "",
        ]
    )
    return lines


def report_markdown(metrics: dict[str, Any]) -> str:
    epochs = metrics["epochs"]
    lines = [
        f"# {REPORT_TITLE}",
        "",
        "This is a repository record, not a summary for readers who want a headline. Every",
        "number below is read from a committed artifact under `experiments/` and",
        f"`{AGGREGATE_DIRNAME}/`, and the machine-readable form of every table in this file is",
        f"`{AGGREGATE_METRICS_JSON}` next to it.",
        "",
        "```text",
        f"benchmark_id               = {metrics['benchmark_id']}",
        f"report_version             = {metrics['report_version']}",
        f"experiment_protocol        = {metrics['protocol_version']}",
        f"evidence_protocol          = {metrics['evidence_protocol_version']}",
        f"protocol_code_digest       = {metrics['protocol_code_digest']}",
        f"model_suite_id             = {metrics['model_suite_id']}",
        f"epochs                     = {', '.join(metrics['experiment_ids'])}",
        f"models                     = {', '.join(metrics['model_ids'])}",
        "```",
        "",
        f"Ranking rule: {metrics['ranking_rule']}",
        "",
        _heading(1),
        "",
        "Trained only on an earlier AME edition, how accurately and how honestly do the three",
        "frozen EZ-B001 models predict the mass excess of nuclides that only became",
        "ground-truth eligible in the following edition?",
        "",
        "The question is deliberately narrow. What this benchmark measures:",
        "",
    ]
    lines.extend(f"- {item}" for item in metrics["allowed_conclusions"])
    lines.extend(["", "What it does not measure, and what is therefore not claimed anywhere below:", ""])
    lines.extend(f"- {item}" for item in metrics["forbidden_conclusions"])
    lines.extend(
        [
            "",
            "Engineering success for this series is protocol integrity. A poor scientific result",
            "is reported, never dropped.",
            "",
            _heading(2),
            "",
            "Each epoch was preregistered before any later-edition truth was read, sealed, and",
            "only then scored. The preregistration hash covers five JSON files; the prose",
            "statement in `PREREGISTRATION.md` is outside the hash and cannot change a number.",
            "",
            "| Experiment | Training | Truth | N | Preregistration hash | Sealed predictions sha256 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for epoch in epochs:
        lines.append(
            f"| {epoch['experiment_id']} | {epoch['training_edition']} | {epoch['truth_edition']} | "
            f"{epoch['n_targets']} | `{epoch['preregistration_hash']}` | "
            f"`{epoch['sealed_predictions_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "One protocol governs the whole series: same parser and normalizer versions, same",
            "target rule, same model suite, same hyperparameters, same uncertainty method, same",
            "metric definitions. The longitudinal aggregate refuses to mix protocol versions,",
            "model suites, Atlas pins, or protocol code digests, so a mixed series cannot be",
            "published as one benchmark.",
            "",
            "Model definitions and hyperparameters were frozen at the moment the first truth",
            "value was scored. A change requires a new protocol version and a complete rerun;",
            "nothing is overwritten.",
            "",
            _heading(3),
            "",
            "Raw AME tables are licensed upstream files and stay out of git. Their sha256",
            "values, download URLs, citations, and parse reports are committed instead, which is",
            "what makes the run auditable without the files.",
            "",
            "| Edition | Release | File | sha256 | Parsed | Eligible | Estimated | Malformed fraction | Roles |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for edition in metrics["editions"]:
        lines.append(
            f"| {edition['edition_id']} | {edition['release_date']} | `{edition['raw_filename']}` | "
            f"`{edition['raw_sha256']}` | {edition['parsed_records']} | {edition['eligible_records']} | "
            f"{edition['estimated_records']} | {display(edition['malformed_fraction'])} | "
            f"{'; '.join(edition['roles'])} |"
        )
    lines.extend(["", "Citations and download locations:", ""])
    for edition in metrics["editions"]:
        lines.append(f"- {edition['edition_id']}: {edition['citation']}")
        lines.append(f"  - `{edition['source_uri']}` -> `{edition['raw_relpath']}`")
    lines.extend(
        [
            "",
            f"Parser version `{metrics['editions'][0]['parser_version']}`. Every parse report records "
            "zero rows with `A != Z + N` and zero duplicate identities.",
            "",
            _heading(4),
            "",
            f"Policy `{metrics['ground_truth_policy']}`: only evaluated, non-estimated AME rows may",
            "act as training truth or as scored truth. An estimated row in the training edition",
            "does not remove a target when the later edition promotes that nuclide to",
            "ground-truth eligible, because that promotion is exactly the historical event the",
            "benchmark measures.",
            "",
            "| Experiment | training_eligible_ids | target_ids |",
            "| --- | --- | --- |",
        ]
    )
    for epoch in epochs:
        lines.append(
            f"| {epoch['experiment_id']} | {epoch['target_rule']['training_eligible_ids']} | "
            f"{epoch['target_rule']['target_ids']} |"
        )
    lines.extend(
        [
            "",
            "Preregistered wording of the estimated-row rule, per epoch:",
            "",
        ]
    )
    lines.extend(f"- {epoch['experiment_id']}: {epoch['estimated_row_rule']}" for epoch in epochs)
    lines.extend(
        [
            "",
            _heading(5),
            "",
            "Controls, in the order they take effect:",
            "",
            "- the preregistration declares the later-edition sha256 forbidden and the training",
            "  sha256 as the only allowed source",
            "- the target manifest handed to prediction carries identities only "
            f"({', '.join(metrics['features'])} and `nuclide_id`); any other field is a leakage error",
            "- the KnowledgeFreeze pins the training identities, the normalized table hash, and",
            "  the feature policy, and carries the forbidden hash with it",
            "- prediction runs in a throwaway workspace that is checked by a filesystem preflight",
            "  over truth file names and truth content hashes, before and after prediction",
            "- the prediction ledger is finalized, and the experiment-level seal is committed,",
            "  before any truth file is opened",
            "- scoring refuses to run when a finalization marker changed after the seal",
            "",
            "### 5.1 Atlas evidence summary",
            "",
            "```text",
            "\n  ->\n".join(metrics["evidence_chain"]),
            "```",
            "",
            "Each stage above is a recorded Atlas PIR fact, not a prose claim. The chain per",
            "epoch:",
            "",
            "| Experiment | Prediction set fact ids | Truth dataset fact ids | Validation fact ids |",
            "| --- | --- | --- | --- |",
        ]
    )
    for epoch in epochs:
        prediction = ", ".join(f"`{v}`" for _, v in sorted(epoch["prediction_set_fact_ids"].items()))
        truth = ", ".join(f"`{v}`" for v in epoch["truth_dataset_fact_ids"])
        validation = ", ".join(f"`{v}`" for _, v in sorted(epoch["validation_fact_ids"].items()))
        lines.append(f"| {epoch['experiment_id']} | {prediction} | {truth} | {validation} |")
    lines.extend(
        [
            "",
            "Code identity of the sealed series:",
            "",
            "```text",
            f"atlas_repository     = {metrics['atlas_repository']}",
            f"atlas_pir_ref        = {metrics['atlas_pir_ref']}",
            f"protocol_code_digest = {metrics['protocol_code_digest']}",
            "```",
            "",
            "| Experiment | elementzero_commit | atlas_pir_ref |",
            "| --- | --- | --- |",
        ]
    )
    for epoch in epochs:
        lines.append(
            f"| {epoch['experiment_id']} | `{epoch['elementzero_commit']}` | `{epoch['atlas_pir_ref']}` |"
        )
    lines.extend(
        [
            "",
            "The commit SHA is lineage. The enforced gate is `protocol_code_digest`, a hash over",
            "the parser, physics, model, metric, evidence, and leakage-control sources: adding a",
            "report generator cannot invalidate a sealed experiment, and editing a model or a",
            "metric does.",
            "",
            _heading(6),
            "",
            f"Model suite `{metrics['model_suite_id']}`, frozen and ordered. Features: "
            f"{', '.join(metrics['features'])}.",
            "",
            "| Model | Implementation | Estimator | random_state |",
            "| --- | --- | --- | --- |",
        ]
    )
    for model in metrics["models"]:
        lines.append(
            f"| {model['model_id']} | `{model['implementation_path']}::{model['implementation_symbol']}` | "
            f"{model['hyperparameters']['estimator']} | {model['random_state']} |"
        )
    lines.extend(
        [
            "",
            "Hyperparameters exactly as preregistered. Numbers appear in the 12-digit canonical",
            "form the committed preregistration stores (ADR-0002).",
            "",
        ]
    )
    for model in metrics["models"]:
        lines.append(f"- {model['model_id']}:")
        for key, value in sorted(model["hyperparameters"].items()):
            if isinstance(value, dict):
                lines.append(f"  - {key}:")
                for inner_key, inner_value in sorted(value.items()):
                    lines.append(f"    - {inner_key} = {inner_value}")
            else:
                lines.append(f"  - {key} = {value}")
    lines.extend(
        [
            "",
            f"Forbidden features in EZ-B001 v1: {'; '.join(metrics['forbidden_features'])}.",
            "",
            _heading(7),
            "",
            "Every model reports a Gaussian predictive distribution, and sigma is taken from the",
            "sealed prediction file. It is never reconstructed from truth or from rounded",
            "intervals.",
            "",
            "| Model | Uncertainty method | Predictive distribution |",
            "| --- | --- | --- |",
        ]
    )
    for model in metrics["models"]:
        lines.append(
            f"| {model['model_id']} | {model['uncertainty_method']} | {model['predictive_distribution']} |"
        )
    interval = metrics["interval_construction"]
    lines.extend(
        [
            "",
            "```text",
            f"predictive_distribution = {interval['predictive_distribution']}",
            f"z_90                    = {display(number(interval['z_90']))}",
            f"z_95                    = {display(number(interval['z_95']))}",
            f"sigma_source            = {interval['sigma_source']}",
            "```",
            "",
            _heading(8),
            "",
            f"Metrics policy `{metrics['metrics_policy_id']}`. The `status` column is the whole",
            "point of this table: a quantity is either preregistered or it is labelled",
            f"`{POST_HOC_LABEL}`. Nothing is described as preregistered after the fact.",
            "",
            "| Quantity | Definition | status |",
            "| --- | --- | --- |",
        ]
    )
    definitions = metrics["metric_definitions"]
    for metric in metrics["preregistered_primary_metrics"]:
        lines.append(f"| {metric} | {definitions.get(metric, 'see metrics policy')} | preregistered |")
    post_hoc_definitions = {
        "metric_delta_first_to_last_epoch": "last-epoch metric minus first-epoch metric, per model",
        "calibration_delta_first_to_last_epoch": "last-epoch coverage or calibration error minus the first-epoch value",
        "mae_non_decreasing_with_distance": "whether MAE is monotonic across the populated distance buckets",
        "mean_predictive_sigma_keV": "mean of the sealed per-target sigma",
        "rmse_over_mean_predictive_sigma": "RMSE divided by the mean sealed sigma",
        "coverage_gap_below_nominal": "max(nominal coverage - observed coverage, 0)",
        "known_failure_screen": (
            "screening rules that select rows for section 15; thresholds "
            f"calibration_tolerance = {display(CALIBRATION_TOLERANCE)}, "
            f"sigma_understatement_ratio = {display(SIGMA_UNDERSTATEMENT_RATIO)}"
        ),
    }
    for field in metrics["post_hoc"]["fields"]:
        lines.append(f"| {field} | {post_hoc_definitions[field]} | {POST_HOC_LABEL} |")
    lines.extend(
        [
            "",
            "Preregistered secondary diagnostics: "
            + ", ".join(metrics["preregistered_secondary_diagnostics"])
            + ".",
            "",
            metrics["post_hoc"]["rule"],
            "",
            "Definitions in ASCII, exactly as preregistered:",
            "",
            "```text",
        ]
    )
    for name in sorted(definitions):
        lines.append(f"{name:<22}= {definitions[name]}")
    lines.append("```")
    lines.append("")

    lines.extend(_epoch_section(metrics, 9, "EZ-B001-A"))
    lines.extend(_epoch_section(metrics, 10, "EZ-B001-B"))
    lines.extend(_epoch_section(metrics, 11, "EZ-B001-C"))

    lines.extend(
        [
            _heading(12),
            "",
            "All three epochs and all three models, in one table. No epoch is dropped for",
            "behaving badly and no metric is hidden because another one looks better.",
            "",
        ]
    )
    lines.extend(markdown_table(PRIMARY_TABLE_COLUMNS, PRIMARY_TABLE_KEYS, metrics["rows"]))
    lines.extend(
        [
            "",
            f"Figures: `{FIGURES_DIRNAME}/mae_kev_by_epoch.svg`, `{FIGURES_DIRNAME}/rmse_kev_by_epoch.svg`,",
            f"`{FIGURES_DIRNAME}/nlpd_by_epoch.svg`.",
            "",
            f"### 12.1 {POST_HOC_LABEL} drift across epochs",
            "",
            f"Labelled {POST_HOC_LABEL}: cross-epoch deltas were not preregistered as metrics. A",
            "later epoch is not assumed to be better, and a worsening delta is reported as it is.",
            "The three epochs also score different target sets of different sizes, so a delta is",
            "a description of the series, not a controlled comparison.",
            "",
            "| Model | Quantity | First epoch | Last epoch | Delta | Direction | status |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for model_id in metrics["model_ids"]:
        diagnostics = metrics["stability"][model_id]
        for group, field in (
            ("metric_drift", "metric_delta_first_to_last_epoch"),
            ("calibration_drift", "calibration_delta_first_to_last_epoch"),
        ):
            for name, drift in diagnostics[group].items():
                lines.append(
                    f"| {model_id} | {name} ({field}) | {display(drift['first'])} | "
                    f"{display(drift['last'])} | {display(drift['delta'])} | {drift['direction']} | "
                    f"{POST_HOC_LABEL} |"
                )
        count = diagnostics["target_count_drift"]
        lines.append(
            f"| {model_id} | n_targets (metric_delta_first_to_last_epoch) | {display(count['first'])} | "
            f"{display(count['last'])} | {display(count['delta'])} | {count['direction']} | "
            f"{POST_HOC_LABEL} |"
        )
    lines.extend(
        [
            "",
            _heading(13),
            "",
            f"Distance policy `{metrics['distance_policy_id']}`; buckets "
            f"{', '.join(metrics['distance_buckets'])} over `nearest_training_L1`, the L1 lattice",
            "distance from a scored target to the closest training nucleus.",
            "",
        ]
    )
    lines.extend(markdown_table(DISTANCE_TABLE_COLUMNS, DISTANCE_TABLE_KEYS, metrics["distance_rows"]))
    lines.extend(
        [
            "",
            f"### 13.1 {POST_HOC_LABEL} monotonicity screen",
            "",
            f"Labelled {POST_HOC_LABEL}: the preregistration asks for metrics per bucket, not for a",
            "monotonicity claim. `mae_non_decreasing_with_distance` is `null` when fewer than two",
            "buckets are populated.",
            "",
            "| Experiment | Model | Populated buckets | mae_non_decreasing_with_distance | status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for model_id in metrics["model_ids"]:
        trends = metrics["stability"][model_id]["error_vs_distance_trend"]
        for experiment_id in metrics["experiment_ids"]:
            trend = trends[experiment_id]
            lines.append(
                f"| {experiment_id} | {model_id} | {', '.join(trend['populated_buckets'])} | "
                f"{display(trend['mae_non_decreasing_with_distance'])} | {POST_HOC_LABEL} |"
            )
    lines.extend(
        [
            "",
            f"Figures: `{FIGURES_DIRNAME}/abs_error_vs_distance_EZ-B001-A.svg` and the equivalent",
            "figure for each epoch.",
            "",
            _heading(14),
            "",
            "Coverage is the fraction of scored targets inside the reported interval;",
            "`CalErr` is the absolute distance from the nominal level. Both nominal levels are",
            "reported for every model in every epoch.",
            "",
        ]
    )
    lines.extend(markdown_table(CALIBRATION_TABLE_COLUMNS, CALIBRATION_TABLE_KEYS, metrics["rows"]))
    lines.extend(
        [
            "",
            f"Figures: `{FIGURES_DIRNAME}/coverage_90_by_epoch.svg`, "
            f"`{FIGURES_DIRNAME}/coverage_95_by_epoch.svg` (nominal levels drawn as reference lines).",
            "",
            f"### 14.1 {POST_HOC_LABEL} interval width against realised error",
            "",
            f"Labelled {POST_HOC_LABEL}. NLPD already penalises a badly sized interval, but it mixes",
            "width and error into one number. The ratio below separates them: above one means the",
            "reported sigma is smaller than the realised error, and well below one means the",
            "interval is far wider than the error it has to cover, which is how a model reaches",
            "coverage 1 and a poor NLPD at the same time.",
            "",
            "| Experiment | Model | N | mean_predictive_sigma_keV | rmse_over_mean_predictive_sigma | status |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in metrics["post_hoc_sigma_rows"]:
        lines.append(
            f"| {row['experiment_id']} | {row['model_id']} | {row['n']} | "
            f"{display(row['mean_predictive_sigma_keV'])} | "
            f"{display(row['rmse_over_mean_predictive_sigma'])} | {POST_HOC_LABEL} |"
        )
    lines.extend(
        [
            "",
            _heading(15),
            "",
            "Failures stay in the record. Every row below is also present, unchanged, in the",
            "tables above and in `aggregate_metrics.json`; this section only points at them.",
            "",
            f"The screen itself is {POST_HOC_LABEL} (`known_failure_screen`), with a calibration",
            f"tolerance of {display(CALIBRATION_TOLERANCE)} and a sigma ratio bound of",
            f"{display(SIGMA_UNDERSTATEMENT_RATIO)} in both directions. Changing a threshold changes",
            "which rows are listed here; it cannot change a metric.",
            "",
            "| Kind | Experiment | Model | Detail | Severity | Retained | status |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for failure in metrics["known_failures"]:
        lines.append(
            f"| {failure['kind']} | {failure['experiment_id']} | {failure['model_id']} | "
            f"{failure['detail']} | {failure['severity']} | {failure['retained']} | {POST_HOC_LABEL} |"
        )
    if not metrics["known_failures"]:
        lines.append("| none | n/a | n/a | no screening rule fired | n/a | True | POST_HOC |")
    lines.extend(
        [
            "",
            _heading(16),
            "",
            "- The three epochs score different target sets of different sizes. A metric that",
            "  moves between epochs may reflect which nuclides became eligible, not model skill.",
            "- Targets are the nuclides a later edition added, which are systematically further",
            "  from stability and closer to the measurement frontier than an average nucleus.",
            "  Nothing here generalises to interpolation inside well-measured regions.",
            "- Later-edition truth values carry their own experimental uncertainty; the metrics",
            "  above treat them as exact.",
            "- Distance buckets far from the training corpus contain very few targets, so their",
            "  metrics are noisy. They are reported with their N and not smoothed.",
            "- The uncertainty families differ by construction: one model reports a single global",
            "  residual standard deviation, two report a GP posterior standard deviation with",
            "  fixed kernel hyperparameters. Calibration is therefore not compared like for like.",
            "- No significance test was preregistered, so no difference between models or epochs",
            "  in this report is a statistical claim.",
            "- The AME editions are not independent samples: each edition re-evaluates earlier",
            "  measurements, so consecutive epochs share evaluation methodology and correlated",
            "  inputs.",
            "",
            _heading(17),
            "",
            "| Id | Status | Preregistered | Actual | Changes numbers | Reference |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for deviation in metrics["deviations"]:
        lines.append(
            f"| {deviation['id']} | {deviation['status']} | {deviation['preregistered']} | "
            f"{deviation['actual']} | {deviation['affects_numbers']} | `{deviation['reference']}` |"
        )
    lines.extend(
        [
            "",
            "No metric was added to the preregistered set after scoring, no model was refit, and",
            "no hyperparameter was changed. The protocol code digest of every epoch still matches",
            "its preregistration, which the committed-experiment test suite checks on every run.",
            "",
            _heading(18),
            "",
            "```bash",
            f"python {REPRODUCE_SCRIPT}",
            "```",
            "",
            "The script, in order: verifies the committed artifact hashes of every epoch,",
            "validates every preregistration and the protocol code digest, replays scoring from",
            "the sealed predictions against the raw truth table, rebuilds the longitudinal",
            "aggregate, rebuilds this report with its tables and figures, and compares the result",
            f"against `{SHA256SUMS_FILE}`.",
            "",
            "It never refits a model. Refitting requires the explicit flag:",
            "",
            "```bash",
            f"python {REPRODUCE_SCRIPT} --refit",
            "```",
            "",
            "which fits into a scratch directory, never into `experiments/`, and compares the",
            "recomputed metric hashes with the committed ones.",
            "",
            "Raw AME tables are not committed. Download them to the declared paths first:",
            "",
            "```text",
        ]
    )
    for edition in metrics["editions"]:
        lines.append(f"{edition['source_uri']}")
        lines.append(f"  -> {edition['raw_relpath']}  sha256 {edition['raw_sha256']}")
    lines.extend(
        [
            "```",
            "",
            "Without those files the hash verification, the aggregate rebuild, and the report",
            "rebuild still run; the truth replay reports itself as skipped instead of passing",
            "silently.",
            "",
            _heading(19),
            "",
            f"`{SHA256SUMS_FILE}` in this directory is a `sha256sum`-compatible manifest of every",
            f"generated file, and `{ARTIFACT_MANIFEST_JSON}` lists every committed input the",
            "generator read, with its hash and its role.",
            "",
            "```bash",
            f"cd {REPORT_DIRNAME} && sha256sum -c {SHA256SUMS_FILE}",
            "```",
            "",
            "Load-bearing hashes of the series:",
            "",
            "| Experiment | Preregistration | Sealed predictions | Model comparison |",
            "| --- | --- | --- | --- |",
        ]
    )
    for epoch in epochs:
        lines.append(
            f"| {epoch['experiment_id']} | `{epoch['preregistration_hash']}` | "
            f"`{epoch['sealed_predictions_sha256']}` | `{epoch['model_comparison_sha256']}` |"
        )
    lines.extend(
        [
            "",
            f"Published aggregate `{metrics['aggregate_source']['path']}` sha256 "
            f"`{metrics['aggregate_source']['sha256']}`.",
            "",
            "```text",
            f"atlas_pir_ref        = {metrics['atlas_pir_ref']}",
            f"protocol_code_digest = {metrics['protocol_code_digest']}",
            "```",
            "",
            _heading(20),
            "",
            f"Recommended release tag after audit: `{RELEASE_TAG}`, pointing at a commit that",
            "contains the preregistrations, the sealed hashes, the score outputs, this report,",
            "and the reproduction script.",
            "",
            "The next gate is WO-09, EZ-B002 Geographic Nuclear-Chart Holdout: withhold a",
            "contiguous region of the known chart instead of a historical edition, and ask",
            "whether the same three models can reconstruct it. EZ-B002 does not start until",
            "this report exists, the reproduction replay passes, unresolved data or parser issues",
            "are documented, and any protocol change is versioned rather than edited in place.",
            "",
            "The machine-readable form of this decision, including the failure list, is",
            f"`{BENCHMARK_STATUS_JSON}`. It has no single PASS field: engineering status covers",
            "protocol integrity only, and the scientific verdict stays null.",
            "",
        ]
    )
    return "\n".join(lines)


def readme_markdown(metrics: dict[str, Any], files: list[str]) -> str:
    lines = [
        f"# {REPORT_TITLE}",
        "",
        "Generated by `elementzero.reporting.historical` from committed artifacts only. Rebuild",
        f"and verify with `python {REPRODUCE_SCRIPT}`.",
        "",
        "## Contents",
        "",
        "| File | What it is |",
        "| --- | --- |",
        f"| `{REPORT_MARKDOWN}` | the report itself, all 20 required sections |",
        f"| `{AGGREGATE_METRICS_JSON}` | machine-readable source of every table in the report |",
        f"| `{MODEL_TABLE_CSV}` | primary and calibration metrics, one row per epoch and model |",
        f"| `{DISTANCE_TABLE_CSV}` | metrics per nearest-training L1 distance bucket |",
        f"| `{BENCHMARK_STATUS_JSON}` | machine-readable status, failures, and next gate |",
        f"| `{ARTIFACT_MANIFEST_JSON}` | every committed input the generator read, with hashes |",
        f"| `{FIGURES_DIRNAME}/` | deterministic SVG figures, generated from the committed JSON |",
        f"| `{SHA256SUMS_FILE}` | `sha256sum -c` manifest of every file in this directory |",
        "",
        "## Reading rules",
        "",
        f"- Numbers in `{REPORT_MARKDOWN}` are rounded for display. The exact values are in",
        f"  `{AGGREGATE_METRICS_JSON}` and in the CSV files, where floats use the 12-digit",
        "  canonical form from ADR-0002.",
        f"- Quantities the preregistration did not declare carry the `{POST_HOC_LABEL}` label",
        "  wherever they appear.",
        "- All three epochs and all three models are present, including the poorly behaved",
        "  combinations. Nothing is dropped and no model is labelled best.",
        "- Figures are secondary to the tables and are generated from the committed artifacts",
        "  they declare in `aggregate_metrics.json -> figures`.",
        "",
        "## Series covered",
        "",
        "| Experiment | Training | Truth | N |",
        "| --- | --- | --- | --- |",
    ]
    for epoch in metrics["epochs"]:
        lines.append(
            f"| {epoch['experiment_id']} | {epoch['training_edition']} | {epoch['truth_edition']} | "
            f"{epoch['n_targets']} |"
        )
    lines.extend(
        [
            "",
            "## Files in this directory",
            "",
        ]
    )
    lines.extend(f"- `{name}`" for name in files)
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Build and write                                                             #
# --------------------------------------------------------------------------- #


def build_report(*, root: str | Path | None = None) -> dict[str, Any]:
    """Assemble the whole report in memory, from committed artifacts only."""
    series = load_series(root)
    metrics = build_metrics(series)
    figures = build_figures(series, metrics)
    metrics["figures"] = [
        {"file": f"{FIGURES_DIRNAME}/{f['file']}", "title": f["title"], "kind": f["kind"], "sources": f["sources"]}
        for f in figures
    ]
    status = build_status(metrics)
    inputs = sorted(
        {(i["path"], i["sha256"], i["role"]) for entry in series["epochs"] for i in entry["inputs"]}
        | {
            (
                series["aggregate_source"]["path"],
                series["aggregate_source"]["sha256"],
                series["aggregate_source"]["role"],
            )
        }
    )
    generated = [
        README_FILE,
        REPORT_MARKDOWN,
        AGGREGATE_METRICS_JSON,
        MODEL_TABLE_CSV,
        DISTANCE_TABLE_CSV,
        ARTIFACT_MANIFEST_JSON,
        BENCHMARK_STATUS_JSON,
        *[f"{FIGURES_DIRNAME}/{f['file']}" for f in figures],
        SHA256SUMS_FILE,
    ]
    artifact_manifest = {
        "report_version": REPORT_VERSION,
        "report_dir": REPORT_DIRNAME,
        "generator": "elementzero.reporting.historical",
        "generation_rule": (
            "every value is read from a committed artifact; the generator never refits a "
            "model, never reads a raw AME table, and never uses wall-clock time or live git "
            "state, so a rebuild from the same artifacts is byte-identical"
        ),
        "verification_command": f"python {REPRODUCE_SCRIPT}",
        "hash_manifest": SHA256SUMS_FILE,
        "inputs": [{"path": path, "sha256": digest, "role": role} for path, digest, role in inputs],
        "outputs": generated,
    }
    return {
        "report_version": REPORT_VERSION,
        "root": str(series["root"]),
        "metrics": metrics,
        "status": status,
        "artifact_manifest": artifact_manifest,
        "figures": figures,
        "model_table_csv": csv_table(MODEL_COLUMNS, metrics["rows"]),
        "distance_table_csv": csv_table(DISTANCE_COLUMNS, metrics["distance_rows"]),
        "markdown": report_markdown(metrics),
        "readme": readme_markdown(metrics, generated),
        "generated_files": generated,
    }


def write_report(
    *,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the report tree and its ``sha256sum``-compatible manifest."""
    base = Path(root or REPO_ROOT)
    payload = report or build_report(root=base)
    dest = Path(out_dir or base / REPORT_DIRNAME)
    (dest / FIGURES_DIRNAME).mkdir(parents=True, exist_ok=True)

    written: dict[str, str] = {}

    def write(relpath: str, text: str) -> None:
        path = dest / relpath
        path.write_text(text, encoding="utf-8")
        written[relpath] = sha256_file(path)

    write(README_FILE, payload["readme"])
    write(REPORT_MARKDOWN, payload["markdown"])
    write(AGGREGATE_METRICS_JSON, canonical_json(payload["metrics"]) + "\n")
    write(MODEL_TABLE_CSV, payload["model_table_csv"])
    write(DISTANCE_TABLE_CSV, payload["distance_table_csv"])
    write(ARTIFACT_MANIFEST_JSON, canonical_json(payload["artifact_manifest"]) + "\n")
    write(BENCHMARK_STATUS_JSON, canonical_json(payload["status"]) + "\n")
    for figure in payload["figures"]:
        write(f"{FIGURES_DIRNAME}/{figure['file']}", figure["svg"])

    stale = [
        path
        for path in sorted(dest.rglob("*"))
        if path.is_file()
        and str(path.relative_to(dest)) not in written
        and path.name != SHA256SUMS_FILE
    ]
    if stale:
        raise ProtocolError(
            "the report directory holds files this generator did not write: "
            f"{[str(p.relative_to(dest)) for p in stale]}"
        )

    manifest = "\n".join(f"{written[relpath]}  {relpath}" for relpath in sorted(written)) + "\n"
    (dest / SHA256SUMS_FILE).write_text(manifest, encoding="utf-8")
    return {
        "out_dir": str(dest),
        "files": dict(written),
        "sha256sums": manifest,
        "report": payload,
    }


def verify_report_hashes(report_dir: str | Path) -> dict[str, Any]:
    """Check ``SHA256SUMS.txt`` against what is on disk, both directions."""
    base = Path(report_dir)
    manifest_path = base / SHA256SUMS_FILE
    if not manifest_path.is_file():
        raise ProtocolError(f"{manifest_path} is missing")
    recorded: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relpath = line.split("  ", 1)
        recorded[relpath] = digest
    present = {
        str(path.relative_to(base)): sha256_file(path)
        for path in sorted(base.rglob("*"))
        if path.is_file() and path.name != SHA256SUMS_FILE
    }
    missing = sorted(set(recorded) - set(present))
    extra = sorted(set(present) - set(recorded))
    changed = sorted(k for k in set(recorded) & set(present) if recorded[k] != present[k])
    return {
        "report_dir": str(base),
        "n_files": len(recorded),
        "missing": missing,
        "extra": extra,
        "changed": changed,
        "ok": not (missing or extra or changed),
    }


def compare_to_committed(
    *,
    root: str | Path | None = None,
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild in memory and diff against the committed report tree."""
    base = Path(root or REPO_ROOT)
    payload = report or build_report(root=base)
    dest = base / REPORT_DIRNAME
    rebuilt = {
        README_FILE: payload["readme"],
        REPORT_MARKDOWN: payload["markdown"],
        AGGREGATE_METRICS_JSON: canonical_json(payload["metrics"]) + "\n",
        MODEL_TABLE_CSV: payload["model_table_csv"],
        DISTANCE_TABLE_CSV: payload["distance_table_csv"],
        ARTIFACT_MANIFEST_JSON: canonical_json(payload["artifact_manifest"]) + "\n",
        BENCHMARK_STATUS_JSON: canonical_json(payload["status"]) + "\n",
        **{f"{FIGURES_DIRNAME}/{f['file']}": f["svg"] for f in payload["figures"]},
    }
    missing = [name for name in rebuilt if not (dest / name).is_file()]
    differing = [
        name
        for name in rebuilt
        if (dest / name).is_file() and (dest / name).read_text(encoding="utf-8") != rebuilt[name]
    ]
    committed: set[str] = set()
    if dest.is_dir():
        committed = {
            str(path.relative_to(dest))
            for path in sorted(dest.rglob("*"))
            if path.is_file() and path.name != SHA256SUMS_FILE
        }
    return {
        "report_dir": str(dest),
        "exists": dest.is_dir(),
        "missing": sorted(missing),
        "differing": sorted(differing),
        "extra": sorted(committed - set(rebuilt)),
        "ok": dest.is_dir() and not missing and not differing and not (committed - set(rebuilt)),
    }


__all__ = [
    "AGGREGATE_METRICS_JSON",
    "ARTIFACT_MANIFEST_JSON",
    "BENCHMARK_STATUS_JSON",
    "DISTANCE_TABLE_CSV",
    "FIGURES_DIRNAME",
    "MODEL_TABLE_CSV",
    "POST_HOC_FIELDS",
    "POST_HOC_LABEL",
    "README_FILE",
    "REPORT_DIRNAME",
    "REPORT_MARKDOWN",
    "REPORT_VERSION",
    "REQUIRED_SECTIONS",
    "SHA256SUMS_FILE",
    "assert_no_missing_primary_metric",
    "build_report",
    "compare_to_committed",
    "display",
    "load_series",
    "verify_report_hashes",
    "write_report",
]
