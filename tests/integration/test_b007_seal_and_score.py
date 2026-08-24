"""WO-206 — the seal-then-score round trip, driven through the real CLIs.

The point of EZ-B007 is that the scoring step runs unattended, years later,
against an edition nobody has seen, with no refit and no human judgement. That
property cannot be checked by reading the script; it has to be executed. So this
test builds a synthetic "current" edition, seals a forecast against it, then
builds a synthetic "future" edition in which some of the sealed targets have
become measured, and scores one against the other in a subprocess.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from tests.helpers import toy_mass_excess, write_ame_table

from elementzero.data.amdc.common import AME_MAS20_COLUMNS, EditionSpec

pytestmark = pytest.mark.v2_protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = EditionSpec("AME2020", "2021-03-01", AME_MAS20_COLUMNS, year=2020)

Z_LO, Z_HI = 8, 44
EDGE_OFFSET = 6            # n >= z + EDGE_OFFSET is unmeasured in the "current" edition
PROMOTED_OFFSET = 2        # how much of that edge the "future" edition measures


def _rows(promote_edge: bool):
    rows = []
    for z in range(Z_LO, Z_HI):
        for n in range(z - 2, z + 9):
            estimated = n >= z + EDGE_OFFSET
            if estimated and promote_edge and n < z + EDGE_OFFSET + PROMOTED_OFFSET:
                estimated = False  # this nuclide got measured in the new edition
            rows.append((z, n, "Xx", toy_mass_excess(z, n), 5.0, estimated))
    return rows


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / script), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


@pytest.fixture
def sealed(tmp_path, monkeypatch):
    """Seal a forecast against a synthetic 'current' edition."""
    current = write_ame_table(tmp_path / "current.mas20", _rows(promote_edge=False), SPEC)

    # Point the sealing script's verified loader at the synthetic table.
    import elementzero.experiments.b007_prospective as b007
    from elementzero.data.amdc.common import parse_ame_mass_table_detailed

    observations, _ = parse_ame_mass_table_detailed(current, SPEC)
    measured, extrapolated = b007.split_by_measurement_status(observations)
    assert measured and extrapolated, "fixture must contain both kinds of record"

    model = b007.fit_forecast_model(measured, hyperparameter_subsample=120)
    targets = b007.build_target_manifest(extrapolated, measured)
    predictions = b007.predict_targets(model, targets)
    references = b007.build_reference_extrapolations(extrapolated)
    tier, tier_detail = b007.resolve_forecast_tier()

    seal_dir = tmp_path / "EZ-B007-test"
    seal_dir.mkdir()
    seal = {
        "experiment_id": b007.EXPERIMENT_ID,
        "forecast_policy_id": b007.FORECAST_POLICY_ID,
        "hash_rule": b007.SEAL_HASH_RULE,
        "blindness_tier": tier,
        "claim_eligible": False,
        "n_predictions": len(predictions),
        "predictions": predictions,
    }
    seal["seal_sha256"] = b007.seal_digest(seal)
    (seal_dir / "SEALED_PREDICTIONS.json").write_text(json.dumps(seal))
    (seal_dir / "forecast_protocol.json").write_text(
        json.dumps({"blindness": tier_detail, "claim_eligibility": {"claim_eligible": False}})
    )
    (seal_dir / "reference_extrapolations.json").write_text(json.dumps(references))
    (seal_dir / "targets.json").write_text(
        json.dumps({"benchmark_id": b007.BENCHMARK_ID, "targets": targets})
    )
    return seal_dir, tmp_path


def test_scoring_a_future_edition_needs_no_refit(sealed, tmp_path):
    seal_dir, work = sealed
    future = write_ame_table(work / "future.mas20", _rows(promote_edge=True), SPEC)
    out = work / "scoring"

    proc = _run(
        "score_b007_forecast.py",
        "--seal", str(seal_dir),
        "--edition", str(future),
        "--edition-id", "AME_TEST_FUTURE",
        "--edition-year", "2030",
        "--out", str(out),
    )
    assert proc.returncode == 0, proc.stderr

    report = json.loads((out / "SCORE_REPORT.json").read_text())
    # ADR-0002: canonical JSON renders finite floats as 12-significant-digit
    # strings, so numeric fields come back as text, exactly as in the frozen v1
    # artifacts. Parse rather than "fix" the serializer.
    assert report["seal_verified"] is True
    assert report["refit_performed"] is False
    # some targets became measured, and the rest are correctly left unscored
    assert report["n_scoreable"] > 0
    assert report["n_scoreable"] < report["n_sealed"]
    assert report["n_scoreable"] + report["n_still_unmeasured"] == report["n_sealed"]
    assert float(report["model"]["mae_keV"]) > 0
    assert report["amdc_extrapolation_baseline"] is not None
    assert report["model_beats_amdc_baseline"] in (True, False)
    assert report["by_distance_bucket"]


def test_scoring_refuses_a_tampered_seal(sealed, tmp_path):
    """The seal is evidence only if altering it is detected."""
    seal_dir, work = sealed
    path = seal_dir / "SEALED_PREDICTIONS.json"
    seal = json.loads(path.read_text())
    seal["predictions"][0]["predicted_mass_excess_keV"] += 1000.0
    path.write_text(json.dumps(seal))

    future = write_ame_table(work / "future2.mas20", _rows(promote_edge=True), SPEC)
    proc = _run(
        "score_b007_forecast.py",
        "--seal", str(seal_dir),
        "--edition", str(future),
        "--edition-id", "AME_TEST_FUTURE",
        "--out", str(work / "scoring2"),
    )
    assert proc.returncode != 0
    assert "seal digest mismatch" in (proc.stdout + proc.stderr)


def test_sealing_refuses_to_overwrite_an_existing_seal(sealed):
    """A prospective seal is evidence because it predates the answers."""
    seal_dir, _ = sealed
    proc = _run("seal_b007_forecast.py", "--out", str(seal_dir))
    assert proc.returncode != 0
    assert "refusing to overwrite an existing seal" in (proc.stdout + proc.stderr)
