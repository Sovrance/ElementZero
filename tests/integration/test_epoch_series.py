"""WO-07: three epochs, one protocol, one aggregate, deterministic replay.

Two synthetic epochs stand in for B and C here so the series logic is tested
without depending on the official tables; the committed official series is
checked separately in tests/integration/test_committed_experiments.py.
"""

from __future__ import annotations

import json

import pytest
from tests.helpers import toy_mass_excess, write_ame_table

from elementzero.benchmark.model_suite import COMPARISON_JSON_NAME, SUITE_MODEL_IDS
from elementzero.data.amdc.ame2003 import EDITION as AME2003
from elementzero.data.amdc.ame2012 import EDITION as AME2012
from elementzero.data.amdc.ame2020 import EDITION as AME2020
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json
from elementzero.experiments.aggregate import (
    DISTANCE_COLUMNS,
    MODEL_COLUMNS,
    assert_one_protocol,
    build_aggregate,
    load_experiment,
    write_aggregate,
)
from elementzero.experiments.epochs import EPOCHS, EpochSpec
from elementzero.experiments.preregister import PROTOCOL_FILE, write_preregistration
from elementzero.experiments.runner import (
    replay_experiment,
    score_experiment,
    seal_experiment,
)

FAKE_COMMIT = "1" * 40

EPOCH_B = EpochSpec(
    experiment_id="EZ-B001-B",
    training_edition="AME2003",
    truth_edition="AME2012",
    created_at="2026-08-16T01:00:00Z",
)
EPOCH_C = EpochSpec(
    experiment_id="EZ-B001-C",
    training_edition="AME2012",
    truth_edition="AME2020",
    created_at="2026-08-16T02:00:00Z",
)


def _table(path, rows, spec):
    return write_ame_table(path, rows, spec)


@pytest.fixture
def series(tmp_path, monkeypatch):
    """Three nested synthetic editions: early -> middle -> late."""
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    symbol = "X"
    early, middle, late = [], [], []
    for z in range(8, 20):
        n = z
        me = toy_mass_excess(z, n)
        early.append((z, n, symbol, me, 15.0, False))
        middle.append((z, n, symbol, me + 1.0, 12.0, False))
        late.append((z, n, symbol, me + 1.5, 10.0, False))
    for z in range(20, 24):
        n = z + 1
        me = toy_mass_excess(z, n, noise=0.3)
        # Estimated when first seen, eligible later: a valid later target.
        early.append((z, n, symbol, me, 400.0, True))
        middle.append((z, n, symbol, me, 25.0, False))
        late.append((z, n, symbol, me + 0.5, 20.0, False))
    for z in range(24, 28):
        n = z + 2
        me = toy_mass_excess(z, n, noise=0.5)
        late.append((z, n, symbol, me, 30.0, False))

    sources = tmp_path / "sources"
    paths = {
        "early": _table(sources / "early.mas03", early, AME2003),
        "middle": _table(sources / "middle.mas12", middle, AME2012),
        "late": _table(sources / "late.mas20", late, AME2020),
    }
    dirs = {}
    for epoch, training, truth in (
        (EPOCH_B, paths["early"], paths["middle"]),
        (EPOCH_C, paths["middle"], paths["late"]),
    ):
        experiment_dir = tmp_path / "experiments" / epoch.experiment_id
        write_preregistration(
            epoch=epoch,
            experiment_dir=experiment_dir,
            training_source=training,
            truth_source=truth,
        )
        seal_experiment(
            epoch=epoch,
            experiment_dir=experiment_dir,
            training_source=training,
            truth_source=truth,
            subprocess_prediction=False,
        )
        score_experiment(epoch=epoch, experiment_dir=experiment_dir, truth_source=truth)
        dirs[epoch.experiment_id] = experiment_dir
    return {"dirs": dirs, "paths": paths, "tmp": tmp_path}


def test_b_target_policy(series):
    """B targets are middle-edition eligible ids minus early-edition eligible ids."""
    targets = json.loads(
        (series["dirs"]["EZ-B001-B"] / "targets.json").read_text(encoding="utf-8")
    )["targets"]
    ids = {t["nuclide_id"] for t in targets}
    # Z20-N21 .. Z23-N24 were estimated in the early edition, so they stay targets.
    assert ids == {"Z20-N21", "Z21-N22", "Z22-N23", "Z23-N24"}
    for target in targets:
        assert set(target) == {"nuclide_id", "Z", "N", "A"}


def test_c_target_policy(series):
    """C targets are late-edition eligible ids minus middle-edition eligible ids."""
    targets = json.loads(
        (series["dirs"]["EZ-B001-C"] / "targets.json").read_text(encoding="utf-8")
    )["targets"]
    ids = {t["nuclide_id"] for t in targets}
    assert ids == {"Z24-N26", "Z25-N27", "Z26-N28", "Z27-N29"}


def test_no_cross_epoch_target_leakage(series):
    b_targets = {
        t["nuclide_id"]
        for t in json.loads(
            (series["dirs"]["EZ-B001-B"] / "targets.json").read_text(encoding="utf-8")
        )["targets"]
    }
    c_freeze = json.loads((series["dirs"]["EZ-B001-C"] / "freeze.json").read_text(encoding="utf-8"))
    c_targets = {
        t["nuclide_id"]
        for t in json.loads(
            (series["dirs"]["EZ-B001-C"] / "targets.json").read_text(encoding="utf-8")
        )["targets"]
    }
    # Each epoch scores its own targets only, and no epoch trains on its own targets.
    assert not (b_targets & c_targets)
    assert not (c_targets & set(c_freeze["training_nuclide_ids"]))
    # B's targets are legitimate training data for C: they are eligible by then.
    assert b_targets <= set(c_freeze["training_nuclide_ids"])


def test_epoch_truth_hash_forbidden_during_prediction(series):
    for experiment_id, experiment_dir in series["dirs"].items():
        protocol = json.loads((experiment_dir / PROTOCOL_FILE).read_text(encoding="utf-8"))
        freeze = json.loads((experiment_dir / "freeze.json").read_text(encoding="utf-8"))
        truth_hash = protocol["later_edition"]["raw_sha256"]
        assert truth_hash in freeze["forbidden_source_hashes"], experiment_id
        assert truth_hash not in freeze["allowed_source_hashes"], experiment_id
        manifest = json.loads((experiment_dir / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        preflight = manifest["blind_workspace"]["preflight_before_prediction"]
        assert truth_hash in preflight["forbidden_source_hashes"], experiment_id
        assert preflight["status"] == "BLIND"


def test_all_epochs_use_same_model_suite(series):
    experiments = [load_experiment(d) for d in series["dirs"].values()]
    shared = assert_one_protocol(experiments)
    assert shared["model_ids"] == list(SUITE_MODEL_IDS)
    assert shared["features"] == ["Z", "N", "A"]
    for experiment in experiments:
        rows = experiment["comparison"]["rows"]
        assert [r["model_id"] for r in rows] == list(SUITE_MODEL_IDS)


def test_protocol_version_mismatch_rejected(series):
    experiments = [load_experiment(d) for d in series["dirs"].values()]
    experiments[1]["protocol"]["protocol_version"] = "1.1.0"
    with pytest.raises(ProtocolError):
        assert_one_protocol(experiments)

    experiments = [load_experiment(d) for d in series["dirs"].values()]
    experiments[0]["protocol"]["protocol_code_digest"] = "0" * 64
    with pytest.raises(ProtocolError):
        assert_one_protocol(experiments)

    experiments = [load_experiment(d) for d in series["dirs"].values()]
    experiments[0]["protocol"]["model_ids"] = ["EZ-SEMF-LS-v1"]
    with pytest.raises(ProtocolError):
        assert_one_protocol(experiments)


def test_aggregate_contains_all_rows_for_every_epoch_and_model(series):
    result = write_aggregate(
        experiment_paths=list(series["dirs"].values()),
        out_dir=series["tmp"] / "results",
    )
    payload = result["aggregate"]
    assert payload["experiment_ids"] == ["EZ-B001-B", "EZ-B001-C"]
    assert len(payload["rows"]) == 2 * len(SUITE_MODEL_IDS)
    assert {(r["experiment_id"], r["model_id"]) for r in payload["rows"]} == {
        (e, m) for e in payload["experiment_ids"] for m in SUITE_MODEL_IDS
    }
    for row in payload["rows"]:
        for column in MODEL_COLUMNS:
            assert row[column] is not None, column
    assert len(payload["distance_rows"]) == 2 * len(SUITE_MODEL_IDS) * 4
    for row in payload["distance_rows"]:
        assert set(DISTANCE_COLUMNS) <= set(row)
    for model_id in SUITE_MODEL_IDS:
        stability = payload["stability"][model_id]
        assert set(stability) == {
            "metric_drift",
            "calibration_drift",
            "target_count_drift",
            "error_vs_distance_trend",
        }
    markdown = (series["tmp"] / "results" / "aggregate_v1.md").read_text(encoding="utf-8")
    for experiment_id in payload["experiment_ids"]:
        assert experiment_id in markdown
    for model_id in SUITE_MODEL_IDS:
        assert model_id in markdown


def test_aggregate_refuses_an_epoch_with_a_missing_model(series):
    experiment_dir = series["dirs"]["EZ-B001-C"]
    comparison = json.loads((experiment_dir / COMPARISON_JSON_NAME).read_text(encoding="utf-8"))
    comparison["rows"] = comparison["rows"][:2]
    (experiment_dir / COMPARISON_JSON_NAME).write_text(
        canonical_json(comparison) + "\n", encoding="utf-8"
    )
    with pytest.raises(ProtocolError):
        build_aggregate(list(series["dirs"].values()))


def test_replay_matches_committed_metrics(series):
    for epoch, truth in ((EPOCH_B, series["paths"]["middle"]), (EPOCH_C, series["paths"]["late"])):
        replay = replay_experiment(
            epoch=epoch,
            experiment_dir=series["dirs"][epoch.experiment_id],
            truth_source=truth,
        )
        assert replay["status"] == "REPLAY_MATCHES_COMMITTED_METRICS"
        assert all(m["matches"] for m in replay["models"])


def test_declared_official_epochs_chain_the_editions():
    assert EPOCHS["EZ-B001-B"].training_edition == "AME2012"
    assert EPOCHS["EZ-B001-B"].truth_edition == "AME2016"
    assert EPOCHS["EZ-B001-C"].training_edition == "AME2016"
    assert EPOCHS["EZ-B001-C"].truth_edition == "AME2020"
