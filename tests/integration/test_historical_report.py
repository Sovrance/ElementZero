"""WO-08: the historical benchmark report is complete, honest, and reproducible.

These tests read the committed repository, not a fixture. The report is a record
of the sealed EZ-B001 series, so the properties worth testing are not "does it
render" but:

* nothing is missing (every epoch, every model, every preregistered metric),
* the prose agrees with the machine-readable payload byte for byte,
* every post-hoc addition carries the POST_HOC label,
* the poor results are still there,
* a clean checkout rebuilds the same bytes, without refitting a model.

The suite skips only when the committed series itself is absent, which keeps a
partial checkout honest instead of silently passing.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
from pathlib import Path
from typing import Any

import pytest

from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file
from elementzero.experiments.aggregate import (
    AGGREGATE_DIRNAME,
    AGGREGATE_JSON,
    DISTANCE_COLUMNS,
    MODEL_COLUMNS,
)
from elementzero.experiments.epochs import EPOCH_ORDER
from elementzero.experiments.preregister import (
    METRIC_KEY_ALIASES,
    PRIMARY_METRICS,
)
from elementzero.reporting.historical import (
    AGGREGATE_METRICS_JSON,
    ARTIFACT_MANIFEST_JSON,
    BENCHMARK_STATUS_JSON,
    DISTANCE_TABLE_CSV,
    FIGURES_DIRNAME,
    MODEL_TABLE_CSV,
    POST_HOC_FIELDS,
    POST_HOC_LABEL,
    README_FILE,
    REPORT_DIRNAME,
    REPORT_MARKDOWN,
    REQUIRED_SECTIONS,
    SHA256SUMS_FILE,
    assert_no_missing_primary_metric,
    build_report,
    display,
    verify_report_hashes,
    write_report,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / REPORT_DIRNAME
REPRODUCE_SCRIPT = REPO_ROOT / "scripts" / "reproduce_historical_report.py"
MODEL_IDS = ("EZ-SEMF-LS-v1", "EZ-GP-DIRECT-v1", "EZ-SEMF-GP-RESIDUAL-v1")


def _series_is_committed() -> bool:
    aggregate = REPO_ROOT / AGGREGATE_DIRNAME / AGGREGATE_JSON
    return aggregate.is_file() and all(
        (REPO_ROOT / "experiments" / experiment_id / "model_comparison.json").is_file()
        for experiment_id in EPOCH_ORDER
    )


pytestmark = pytest.mark.skipif(
    not _series_is_committed(),
    reason="the scored EZ-B001 series is not committed in this checkout",
)


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    """The report rebuilt in memory from the committed artifacts."""
    return build_report(root=REPO_ROOT)


@pytest.fixture(scope="module")
def metrics(report: dict[str, Any]) -> dict[str, Any]:
    return report["metrics"]


@pytest.fixture(scope="module")
def markdown(report: dict[str, Any]) -> str:
    return report["markdown"]


@pytest.fixture(scope="module")
def reproduce_module():
    """Import scripts/reproduce_historical_report.py, which is not a package."""
    spec = importlib.util.spec_from_file_location("wo08_reproduce", REPRODUCE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def markdown_tables(text: str) -> list[list[dict[str, str]]]:
    """Every pipe table in the document, as a list of column->cell mappings."""
    tables: list[list[dict[str, str]]] = []
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if header is None:
                header = cells
            elif set("".join(cells)) <= set("- "):
                continue
            else:
                rows.append(dict(zip(header, cells)))
            continue
        if header is not None:
            if rows:
                tables.append(rows)
            header, rows = None, []
    if header is not None and rows:
        tables.append(rows)
    return tables


def tables_with_columns(text: str, columns: tuple[str, ...]) -> list[list[dict[str, str]]]:
    return [t for t in markdown_tables(text) if set(columns) <= set(t[0])]


def csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def canonical(value: Any) -> Any:
    """Round-trip through canonical JSON, which is how numbers are committed.

    Committed artifacts store every float as a 12-digit canonical string
    (ADR-0002), so an in-memory float only compares equal to a committed value
    after the same serialisation.
    """
    return json.loads(canonical_json(value))


# --------------------------------------------------------------------------- #
# Required test 1: nothing is omitted                                         #
# --------------------------------------------------------------------------- #


def test_report_contains_all_models_and_epochs(metrics, markdown, report):
    """3 epochs x 3 models, in the payload, in the CSV, and in the prose."""
    assert list(metrics["experiment_ids"]) == list(EPOCH_ORDER)
    assert list(metrics["model_ids"]) == list(MODEL_IDS)

    expected = {(e, m) for e in EPOCH_ORDER for m in MODEL_IDS}
    assert {(r["experiment_id"], r["model_id"]) for r in metrics["rows"]} == expected
    assert len(metrics["rows"]) == 9

    # The primary table in section 12 carries every pair, so no epoch or model
    # can be dropped for behaving badly.
    longitudinal = tables_with_columns(markdown, ("Experiment", "Model", "MAE", "NLPD", "Cov90"))
    assert longitudinal, "no primary metric table found in the report"
    assert expected <= {
        (row["Experiment"], row["Model"]) for table in longitudinal for row in table
    }

    # Each epoch gets its own results section naming all three models.
    for experiment_id in EPOCH_ORDER:
        assert f"## {REQUIRED_SECTIONS.index(f'{experiment_id} results') + 1}. {experiment_id} results" in markdown
    for model_id in MODEL_IDS:
        assert model_id in markdown

    model_csv = csv_rows(report["model_table_csv"])
    assert list(model_csv[0]) == list(MODEL_COLUMNS)
    assert {(r["experiment_id"], r["model_id"]) for r in model_csv} == expected

    distance_csv = csv_rows(report["distance_table_csv"])
    assert list(distance_csv[0]) == list(DISTANCE_COLUMNS)
    assert {(r["experiment_id"], r["model_id"]) for r in distance_csv} == expected


def test_report_has_all_twenty_required_sections(markdown):
    assert len(REQUIRED_SECTIONS) == 20
    headings = re.findall(r"^## (\d+)\. (.+)$", markdown, flags=re.MULTILINE)
    assert [title for _, title in headings] == list(REQUIRED_SECTIONS)
    assert [int(number) for number, _ in headings] == list(range(1, 21))


# --------------------------------------------------------------------------- #
# Required test 2: prose agrees with the machine-readable payload             #
# --------------------------------------------------------------------------- #


def test_report_metrics_match_json(metrics, markdown, report):
    """Every rendered number is the display form of the committed value."""
    committed = json.loads(
        (REPO_ROOT / AGGREGATE_DIRNAME / AGGREGATE_JSON).read_text(encoding="utf-8")
    )
    # The report may not invent or reshape the published aggregate.
    assert canonical(metrics["rows"]) == committed["rows"]
    assert canonical(metrics["distance_rows"]) == committed["distance_rows"]
    assert canonical(metrics["region_rows"]) == committed["region_rows"]
    assert metrics["aggregate_matches_published"] is True

    by_key = {(r["experiment_id"], r["model_id"]): r for r in metrics["rows"]}
    rendered = {
        "N": "n",
        "MAE": "MAE_keV",
        "MedAE": "MedAE_keV",
        "RMSE": "RMSE_keV",
        "NLPD": "NLPD",
        "Cov90": "coverage_90",
        "Cov95": "coverage_95",
    }
    checked = 0
    for table in tables_with_columns(markdown, ("Experiment", "Model", "MAE", "NLPD", "Cov90")):
        for row in table:
            source = by_key[(row["Experiment"], row["Model"])]
            for column, key in rendered.items():
                assert row[column] == display(source[key]), (row["Experiment"], row["Model"], column)
                checked += 1
    assert checked >= 9 * len(rendered), "the primary metrics were not rendered anywhere"

    # Calibration is rendered from the same rows, both nominal levels.
    calibration = {(r["experiment_id"], r["model_id"]): r for r in metrics["calibration_rows"]}
    for table in tables_with_columns(markdown, ("Experiment", "Model", "CalErr90", "CalErr95")):
        for row in table:
            source = calibration[(row["Experiment"], row["Model"])]
            assert row["CalErr90"] == display(source["cal_error_90"])
            assert row["CalErr95"] == display(source["cal_error_95"])

    # Distance buckets, including the empty ones.
    distance = {
        (r["experiment_id"], r["model_id"], r["distance_bucket"]): r for r in metrics["distance_rows"]
    }
    seen_buckets = set()
    for table in tables_with_columns(markdown, ("Experiment", "Model", "DistanceBucket", "RMSE")):
        for row in table:
            source = distance[(row["Experiment"], row["Model"], row["DistanceBucket"])]
            assert row["N"] == display(source["n"])
            assert row["MAE"] == display(source["MAE_keV"])
            assert row["RMSE"] == display(source["RMSE_keV"])
            seen_buckets.add((row["Experiment"], row["Model"], row["DistanceBucket"]))
    assert seen_buckets == set(distance), "a distance bucket was dropped from the prose"

    # The written payload is the same object the prose was rendered from.
    written = json.loads((REPORT_DIR / AGGREGATE_METRICS_JSON).read_text(encoding="utf-8"))
    assert written == json.loads(canonical_json(metrics))


def test_committed_report_matches_a_rebuild(report, tmp_path):
    """Acceptance gate: a clean checkout rebuilds byte-identical files."""
    written = write_report(out_dir=tmp_path / "rebuild", root=REPO_ROOT, report=report)
    for relpath, digest in written["files"].items():
        committed = REPORT_DIR / relpath
        assert committed.is_file(), relpath
        assert sha256_file(committed) == digest, relpath
    committed_manifest = (REPORT_DIR / SHA256SUMS_FILE).read_text(encoding="utf-8")
    assert committed_manifest == written["sha256sums"]


# --------------------------------------------------------------------------- #
# Required test 3: figures come from committed artifacts                      #
# --------------------------------------------------------------------------- #


def test_figures_build_from_committed_artifacts(report, metrics):
    """Each figure declares its committed sources, and plots exactly their rows."""
    figures = report["figures"]
    assert figures, "the report has no figures"

    expected_files = {f"predicted_vs_truth_{e}.svg" for e in EPOCH_ORDER}
    expected_files |= {f"abs_error_vs_distance_{e}.svg" for e in EPOCH_ORDER}
    expected_files |= {
        "mae_kev_by_epoch.svg",
        "rmse_kev_by_epoch.svg",
        "nlpd_by_epoch.svg",
        "coverage_90_by_epoch.svg",
        "coverage_95_by_epoch.svg",
    }
    assert {f["file"] for f in figures} == expected_files

    n_targets = {e["experiment_id"]: e["n_targets"] for e in metrics["epochs"]}
    for figure in figures:
        assert figure["svg"].startswith('<svg xmlns="http://www.w3.org/2000/svg"')
        assert figure["svg"].rstrip().endswith("</svg>")
        assert figure["sources"], figure["file"]
        # Every declared source is a committed file at the declared hash, so a
        # figure cannot be drawn from hand-edited data.
        for source in figure["sources"]:
            path = REPO_ROOT / source["path"]
            assert path.is_file(), source["path"]
            assert sha256_file(path) == source["sha256"], source["path"]

        committed = REPORT_DIR / FIGURES_DIRNAME / figure["file"]
        assert committed.is_file(), figure["file"]
        assert committed.read_text(encoding="utf-8") == figure["svg"]

        if figure["kind"] == "scatter":
            # One plotted point per scored prediction per model: no subsampling,
            # no smoothing, no invented point.
            experiment_id = figure["file"].rsplit("_", 1)[-1].removesuffix(".svg")
            assert figure["svg"].count("<circle ") == n_targets[experiment_id] * len(MODEL_IDS)
        else:
            column = {
                "mae_kev_by_epoch.svg": "MAE_keV",
                "rmse_kev_by_epoch.svg": "RMSE_keV",
                "nlpd_by_epoch.svg": "NLPD",
                "coverage_90_by_epoch.svg": "coverage_90",
                "coverage_95_by_epoch.svg": "coverage_95",
            }[figure["file"]]
            bars = figure["svg"].count('stroke-width="0.4"')
            assert bars == sum(1 for r in metrics["rows"] if r[column] is not None)

    # Referenced from the prose and recorded in the payload with their sources.
    assert {f["file"] for f in metrics["figures"]} == {
        f"{FIGURES_DIRNAME}/{name}" for name in expected_files
    }


def test_figures_are_deterministic(report):
    """The same committed artifacts produce the same SVG bytes."""
    again = build_report(root=REPO_ROOT)
    assert {f["file"]: f["svg"] for f in again["figures"]} == {
        f["file"]: f["svg"] for f in report["figures"]
    }


# --------------------------------------------------------------------------- #
# Required test 4: reproduction does not refit                                #
# --------------------------------------------------------------------------- #


class _FitEntered(Exception):
    """Raised by the tripwire below when a model fit is entered."""


def _trip_on_fit(monkeypatch) -> None:
    """Make every model fit raise, so entering one is impossible to miss."""
    from elementzero.models import gp_residual

    def guard(self, observations):
        raise _FitEntered(type(self).__name__)

    for name in ("SEMFLeastSquaresModel", "GPDirectModel", "SEMFGPResidualModel"):
        monkeypatch.setattr(getattr(gp_residual, name), "fit", guard)


def test_reproduce_report_does_not_refit_by_default(reproduce_module, monkeypatch, tmp_path):
    """Without --refit, no model fit is ever entered."""
    _trip_on_fit(monkeypatch)

    summary = reproduce_module.reproduce(
        root=REPO_ROOT,
        out_dir=tmp_path / "rebuild",
        replay=False,
    )
    assert summary["refit"] is False
    steps = {step["step"]: step for step in summary["steps"]}
    assert steps["refit"]["status"] == "not_executed"
    assert steps["refit"]["refit"] is False
    assert steps["verify_hashes"]["status"] == "pass"
    assert steps["rebuild_aggregate"]["status"] == "pass"
    assert steps["rebuild_report"]["status"] == "pass"
    assert steps["rebuild_report"]["differing"] == []
    assert steps["rebuild_report"]["missing"] == []
    assert steps["rebuild_report"]["sha256sums_matches_rebuild"] is True
    assert summary["failed_steps"] == []
    assert summary["status"] == "pass"


def test_reproduce_refit_is_opt_in(reproduce_module, monkeypatch, tmp_path):
    """--refit exists, defaults to off, and is the only path that fits.

    The second half is what makes the test above meaningful: the same tripwire
    that stays silent on the default path fires as soon as ``--refit`` is
    passed, so "no fit happened" is an observation rather than a tautology.
    """
    assert reproduce_module.build_parser().parse_args([]).refit is False
    assert reproduce_module.build_parser().parse_args(["--refit"]).refit is True

    _trip_on_fit(monkeypatch)
    with pytest.raises(_FitEntered):
        reproduce_module.reproduce(
            root=REPO_ROOT,
            refit=True,
            out_dir=tmp_path / "refit-probe",
            replay=False,
        )


# --------------------------------------------------------------------------- #
# Required test 5: the hash manifest is complete                              #
# --------------------------------------------------------------------------- #


def test_sha_manifest_complete(report):
    """SHA256SUMS.txt covers every generated file, and every file is listed."""
    result = verify_report_hashes(REPORT_DIR)
    assert result["missing"] == []
    assert result["extra"] == []
    assert result["changed"] == []
    assert result["ok"], result

    listed = {
        line.split("  ", 1)[1]
        for line in (REPORT_DIR / SHA256SUMS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    on_disk = {
        str(p.relative_to(REPORT_DIR))
        for p in REPORT_DIR.rglob("*")
        if p.is_file() and p.name != SHA256SUMS_FILE
    }
    assert listed == on_disk
    assert listed == set(report["generated_files"]) - {SHA256SUMS_FILE}
    for required in (
        README_FILE,
        REPORT_MARKDOWN,
        AGGREGATE_METRICS_JSON,
        MODEL_TABLE_CSV,
        DISTANCE_TABLE_CSV,
        ARTIFACT_MANIFEST_JSON,
        BENCHMARK_STATUS_JSON,
    ):
        assert required in listed, required
    assert any(name.startswith(f"{FIGURES_DIRNAME}/") for name in listed)


def test_artifact_manifest_records_every_input_hash(report):
    """Acceptance gate: artifact hashes verify against the committed inputs."""
    manifest = report["artifact_manifest"]
    assert manifest["inputs"], "the manifest records no inputs"
    for entry in manifest["inputs"]:
        path = REPO_ROOT / entry["path"]
        assert path.is_file(), entry["path"]
        assert sha256_file(path) == entry["sha256"], entry["path"]
        assert entry["role"]
    recorded = {entry["path"] for entry in manifest["inputs"]}
    aggregate_relpath = f"{AGGREGATE_DIRNAME}/{AGGREGATE_JSON}"
    assert aggregate_relpath in recorded
    for experiment_id in EPOCH_ORDER:
        assert any(f"experiments/{experiment_id}/" in path for path in recorded), experiment_id
    assert set(manifest["outputs"]) == set(report["generated_files"])


# --------------------------------------------------------------------------- #
# Required test 6: post-hoc quantities are labelled                           #
# --------------------------------------------------------------------------- #


def test_posthoc_fields_labeled(metrics, markdown):
    """Nothing added after preregistration is presented as preregistered."""
    assert metrics["post_hoc"]["label"] == POST_HOC_LABEL
    assert list(metrics["post_hoc"]["fields"]) == list(POST_HOC_FIELDS)

    for field in POST_HOC_FIELDS:
        assert metrics["metric_status"][field] == POST_HOC_LABEL, field
    for metric in PRIMARY_METRICS:
        assert metrics["metric_status"][metric] == "preregistered", metric
    # A preregistered metric is never relabelled, and the two sets are disjoint.
    assert not set(POST_HOC_FIELDS) & set(PRIMARY_METRICS)

    # The metrics table in section 8 carries a status column for every quantity.
    status_tables = tables_with_columns(markdown, ("Quantity", "status"))
    assert status_tables, "section 8 has no status column"
    rendered = {row["Quantity"]: row["status"] for table in status_tables for row in table}
    for field in POST_HOC_FIELDS:
        assert rendered[field] == POST_HOC_LABEL, field
    for metric in PRIMARY_METRICS:
        assert rendered[metric] == "preregistered", metric

    # Every post-hoc table in the report carries the label on each row.
    for table in markdown_tables(markdown):
        if "status" not in table[0] or "Quantity" in table[0]:
            continue
        for row in table:
            assert row["status"] in {POST_HOC_LABEL, "preregistered"}, row

    # Each post-hoc section says so in prose, not only in a table cell.
    for heading in ("POST_HOC drift across epochs", "POST_HOC monotonicity screen"):
        assert heading in markdown

    # Every post-hoc derived row is labelled in the payload too.
    for row in metrics["known_failures"]:
        assert row["label"] == POST_HOC_LABEL
    assert all(f in markdown for f in POST_HOC_FIELDS)


def test_deviations_are_disclosed(metrics, markdown):
    """Acceptance gate: deviations are listed, including the post-hoc additions."""
    ids = {d["id"] for d in metrics["deviations"]}
    assert "post-hoc-diagnostics" in ids
    assert not [d for d in metrics["deviations"] if d["status"] == "violation"], metrics["deviations"]
    for deviation in metrics["deviations"]:
        assert deviation["preregistered"]
        assert deviation["actual"]
        assert deviation["reference"]
        assert deviation["id"] in markdown


# --------------------------------------------------------------------------- #
# Required test 7: no primary metric is missing                               #
# --------------------------------------------------------------------------- #


def test_no_missing_primary_metric(metrics):
    """Every preregistered primary metric is present for every epoch and model."""
    aggregate = {
        "experiment_ids": metrics["experiment_ids"],
        "rows": metrics["rows"],
    }
    assert_no_missing_primary_metric(aggregate)
    for row in metrics["rows"]:
        for metric in PRIMARY_METRICS:
            key = METRIC_KEY_ALIASES.get(metric, metric)
            assert row[key] is not None, (row["experiment_id"], row["model_id"], metric)


def test_dropping_a_metric_or_a_row_is_rejected(metrics):
    """The completeness check is real: removing anything raises."""
    without_metric = {
        "experiment_ids": list(metrics["experiment_ids"]),
        "rows": [dict(row) for row in metrics["rows"]],
    }
    without_metric["rows"][0]["NLPD"] = None
    with pytest.raises(ProtocolError):
        assert_no_missing_primary_metric(without_metric)

    without_model = {
        "experiment_ids": list(metrics["experiment_ids"]),
        "rows": [r for r in metrics["rows"] if r["model_id"] != "EZ-GP-DIRECT-v1"],
    }
    with pytest.raises(ProtocolError):
        assert_no_missing_primary_metric(without_model)


# --------------------------------------------------------------------------- #
# Acceptance gates: poor results retained, status file, statistical honesty    #
# --------------------------------------------------------------------------- #


def test_poor_results_are_retained(metrics, markdown):
    """The badly behaved combinations are named, not quietly dropped."""
    failures = metrics["known_failures"]
    assert failures, "the screen found nothing, which the committed series contradicts"
    assert all(f["retained"] is True for f in failures)

    kinds = {f["kind"] for f in failures}
    # The committed series has an undercovering model and two overcovering ones.
    assert any(k.startswith("undercoverage") for k in kinds)
    assert any(k.startswith("overcoverage") for k in kinds)

    # Any model-epoch that fails the screen still appears with all its metrics.
    reported = {(r["experiment_id"], r["model_id"]) for r in metrics["rows"]}
    for failure in failures:
        if "->" in failure["experiment_id"]:
            continue
        assert (failure["experiment_id"], failure["model_id"]) in reported
        assert failure["detail"]

    # Section 15 lists them in prose as well.
    failure_tables = tables_with_columns(markdown, ("Kind", "Experiment", "Model", "Detail"))
    assert failure_tables
    listed = {row["Kind"] for table in failure_tables for row in table}
    assert listed == kinds


def test_benchmark_status_has_required_fields():
    """WO-08 section 8, and no single accuracy-driven PASS."""
    status = json.loads((REPORT_DIR / BENCHMARK_STATUS_JSON).read_text(encoding="utf-8"))
    for key in (
        "protocol_version",
        "experiments_completed",
        "models",
        "engineering_status",
        "scientific_summary",
        "known_failures",
        "next_gate",
    ):
        assert key in status, key

    assert [e["experiment_id"] for e in status["experiments_completed"]] == list(EPOCH_ORDER)
    assert [m["model_id"] for m in status["models"]] == list(MODEL_IDS)
    for model in status["models"]:
        assert model["epochs_reported"] == list(EPOCH_ORDER)

    # engineering_status is protocol integrity only; the scientific verdict is null.
    engineering = status["engineering_status"]
    assert engineering["gates_pass"] is True
    assert all(engineering["gates"].values()), engineering["gates"]
    assert status["scientific_summary"]["verdict"] is None
    assert "PASS" not in {str(v) for v in status.values()}
    assert status["next_gate"]["work_order"] == "WO-09"
    assert status["known_failures"] == status["known_failures"]
    assert status["known_failures"], "a failure list of zero would hide the calibration results"


def test_report_makes_no_unpreregistered_significance_claim(markdown, metrics):
    """WO-08 section 5: no significance language, no physics-learning claim."""
    lowered = markdown.lower()
    for forbidden in ("p-value", "p value", "statistically significant", "learned nuclear physics"):
        # The words may only appear where the report disclaims them.
        for line in lowered.splitlines():
            if forbidden in line:
                assert any(
                    marker in line for marker in ("no ", "not ", "never", "without")
                ), f"unqualified {forbidden!r}: {line}"
    assert metrics["allowed_conclusions"]
    assert metrics["forbidden_conclusions"]
    for claim in metrics["forbidden_conclusions"]:
        assert claim in markdown
    assert "best model" not in lowered


def test_readme_and_reproduction_command_are_published(report):
    readme = (REPORT_DIR / README_FILE).read_text(encoding="utf-8")
    assert readme == report["readme"]
    assert "scripts/reproduce_historical_report.py" in readme
    assert SHA256SUMS_FILE in readme
    markdown = (REPORT_DIR / REPORT_MARKDOWN).read_text(encoding="utf-8")
    assert "python scripts/reproduce_historical_report.py" in markdown
    assert "--refit" in markdown


def test_atlas_evidence_chain_is_documented(metrics, markdown):
    """WO-08 section 6: the stage diagram plus the code identities."""
    assert list(metrics["evidence_chain"]) == [
        "source",
        "normalized dataset",
        "freeze",
        "model fit",
        "prediction set",
        "finalization",
        "truth",
        "validation",
    ]
    for stage in metrics["evidence_chain"]:
        assert stage in markdown, stage
    assert metrics["atlas_pir_ref"] in markdown
    assert metrics["protocol_code_digest"] in markdown
    for epoch in metrics["epochs"]:
        assert epoch["elementzero_commit"] in markdown, epoch["experiment_id"]
