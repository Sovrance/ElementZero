"""WO-11.8 / WO-11.9 — dev fixtures are new, and the shell firewall holds."""

from __future__ import annotations

import json

import pytest

from elementzero.adjudication.ablations import (
    B002_DEV_FIXTURE_ID,
    B002_DEV_REGION_ID,
    B003_DEV_FIXTURE_ID,
    B003_DEV_NEUTRON_CLOSURE,
    B003_DEV_PROTON_CLOSURE,
    DEV_FEATURE_POLICIES,
    HYPERPARAMETER_GRID,
    assert_dev_shell_features,
    write_b002_dev_chart,
    write_b003_dev_chart,
)
from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import LeakageError
from elementzero.evidence.hashing import sha256_file

COMMITTED_MATRIX = REPO_ROOT / "reports" / "adjudication" / "wo11" / "ablation_matrix.json"


def test_dev_ablation_uses_new_fixture_ids(tmp_path):
    matrix = json.loads(COMMITTED_MATRIX.read_text(encoding="utf-8"))
    fixture_ids = {row["dev_fixture_id"] for row in matrix["rows"]}
    assert fixture_ids == {B002_DEV_FIXTURE_ID, B003_DEV_FIXTURE_ID}
    assert not any("v1" in fid.split("-")[-1] for fid in fixture_ids)

    # The dev charts are different surfaces from the committed v1 fixtures.
    b002_dev = sha256_file(write_b002_dev_chart(tmp_path / "b002.mas20"))
    b003_dev = sha256_file(write_b003_dev_chart(tmp_path / "b003.mas20"))
    v1_b002 = sha256_file(REPO_ROOT / "tests" / "fixtures" / "b002" / "synthetic_chart_v1.mas20")
    v1_b003 = sha256_file(
        REPO_ROOT / "tests" / "fixtures" / "b003" / "synthetic_shell_chart_v1.mas20"
    )
    assert b002_dev not in (v1_b002, v1_b003)
    assert b003_dev not in (v1_b002, v1_b003)
    assert matrix["fixtures"][B002_DEV_FIXTURE_ID]["chart_sha256"] == b002_dev
    assert matrix["fixtures"][B003_DEV_FIXTURE_ID]["chart_sha256"] == b003_dev

    # Different withheld geometry: a region that is not a v1 region, and
    # closures that are not the v1 injected pair (N0=50, Z0=28).
    sealed = json.loads(
        (REPO_ROOT / "experiments" / "EZ-B002-v1" / "SEALED_PREDICTIONS.json").read_text(
            encoding="utf-8"
        )
    )
    assert B002_DEV_REGION_ID not in sealed["region_ids"]
    assert (B003_DEV_NEUTRON_CLOSURE, B003_DEV_PROTON_CLOSURE) != (50, 28)


def test_dev_matrix_covers_the_preregistered_grid():
    matrix = json.loads(COMMITTED_MATRIX.read_text(encoding="utf-8"))
    for fixture_id in (B002_DEV_FIXTURE_ID, B003_DEV_FIXTURE_ID):
        policies = {
            r["feature_policy_id"]
            for r in matrix["rows"]
            if r["dev_fixture_id"] == fixture_id and r["hyperparameter_variant"] == "hp-baseline"
        }
        assert policies == set(DEV_FEATURE_POLICIES)
        variants = {
            r["hyperparameter_variant"]
            for r in matrix["rows"]
            if r["dev_fixture_id"] == fixture_id
        }
        assert variants == set(HYPERPARAMETER_GRID)


def test_shell_dev_feature_firewall():
    for policy in DEV_FEATURE_POLICIES.values():
        assert_dev_shell_features(policy)
    for forbidden in (
        ("Z", "N", "A", "distance_to_50"),
        ("Z", "N", "A", "magic_label"),
        ("Z", "N", "A", "shellDistance"),
        ("Z", "N", "A", "Distance-To-82"),
        ("Z", "N", "A", "known_closure_flag"),
    ):
        with pytest.raises(LeakageError):
            assert_dev_shell_features(forbidden)
