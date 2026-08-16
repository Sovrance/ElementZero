"""WO-05: the preregistration must be hashable, frozen, and truth-free."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.helpers import write_ame_table

from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
from elementzero.data.amdc import load_edition
from elementzero.data.observations import TRUTH_BEARING_FIELDS
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.hashing import canonical_json
from elementzero.experiments.epochs import EPOCHS, EpochSpec, epoch_for
from elementzero.experiments.preregister import (
    EXPERIMENT_PROTOCOL_VERSION,
    METRICS_POLICY_FILE,
    MODEL_SUITE_FILE,
    PREREGISTRATION_FILES,
    PREREGISTRATION_HASH_FILE,
    PROTOCOL_FILE,
    build_payloads,
    preregistration_hash,
    validate_preregistration,
    write_preregistration,
)
from elementzero.models.gp_residual import _KERNEL

FAKE_COMMIT = "a" * 40


@pytest.fixture
def epoch() -> EpochSpec:
    return epoch_for("EZ-B001-A")


@pytest.fixture
def prereg(tmp_path, epoch, monkeypatch):
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    training = tmp_path / "training.mas03"
    truth = tmp_path / "truth.mas12"
    training.write_bytes(b"training edition bytes\n")
    truth.write_bytes(b"later edition bytes\n")
    experiment_dir = tmp_path / "EZ-B001-A"
    result = write_preregistration(
        epoch=epoch,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
    )
    return experiment_dir, result


def test_preregistration_hash_stable(prereg, tmp_path, epoch, monkeypatch):
    experiment_dir, result = prereg
    recorded = (experiment_dir / PREREGISTRATION_HASH_FILE).read_text(encoding="utf-8").strip()
    assert recorded == result["preregistration_hash"]
    assert recorded == preregistration_hash(experiment_dir)

    # Rewriting the same preregistration elsewhere reproduces the same digest.
    monkeypatch.setenv("ELEMENTZERO_COMMIT", FAKE_COMMIT)
    other = tmp_path / "again"
    again = write_preregistration(
        epoch=epoch,
        experiment_dir=other,
        training_source=tmp_path / "training.mas03",
        truth_source=tmp_path / "truth.mas12",
    )
    assert again["preregistration_hash"] == recorded

    # Any edit to a hashed file invalidates the recorded digest.
    payload = json.loads((experiment_dir / METRICS_POLICY_FILE).read_text(encoding="utf-8"))
    payload["primary_metrics"] = list(payload["primary_metrics"])[:-1]
    (experiment_dir / METRICS_POLICY_FILE).write_text(
        canonical_json(payload) + "\n", encoding="utf-8"
    )
    assert preregistration_hash(experiment_dir) != recorded
    with pytest.raises(ProtocolError):
        validate_preregistration(experiment_dir)


def test_preregistration_hash_covers_exactly_the_five_json_files(prereg):
    experiment_dir, _ = prereg
    assert set(PREREGISTRATION_FILES) == {
        "metrics_policy.json",
        "model_suite.json",
        "protocol.json",
        "source_manifest.json",
        "target_policy.json",
    }
    protocol = json.loads((experiment_dir / PROTOCOL_FILE).read_text(encoding="utf-8"))
    assert protocol["preregistration_files"] == sorted(PREREGISTRATION_FILES)

    # Prose is outside the hash on purpose; editing it cannot invalidate a seal.
    before = preregistration_hash(experiment_dir)
    md = experiment_dir / "PREREGISTRATION.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nappended prose\n", encoding="utf-8")
    assert preregistration_hash(experiment_dir) == before


def test_truth_hash_is_forbidden(prereg):
    experiment_dir, _ = prereg
    protocol = json.loads((experiment_dir / PROTOCOL_FILE).read_text(encoding="utf-8"))
    truth_hash = protocol["later_edition"]["raw_sha256"]
    assert protocol["forbidden_source_hashes"] == [truth_hash]
    assert truth_hash not in protocol["allowed_source_hashes"]
    report = validate_preregistration(experiment_dir)
    assert report["truth_source_hash"] == truth_hash

    protocol["forbidden_source_hashes"] = []
    _rewrite(experiment_dir, PROTOCOL_FILE, protocol)
    with pytest.raises(LeakageError):
        validate_preregistration(experiment_dir)


def test_model_suite_exactly_three_models(prereg):
    experiment_dir, _ = prereg
    suite = json.loads((experiment_dir / MODEL_SUITE_FILE).read_text(encoding="utf-8"))
    assert suite["model_ids"] == list(SUITE_MODEL_IDS)
    assert len(suite["models"]) == 3
    for model in suite["models"]:
        assert model["features"] == ["Z", "N", "A"]
        assert model["random_state"] == 0
        assert model["uncertainty_method"]
        assert model["implementation_path"].startswith("src/elementzero/")

    suite["models"] = suite["models"][:2]
    _rewrite(experiment_dir, MODEL_SUITE_FILE, suite)
    with pytest.raises(ProtocolError):
        validate_preregistration(experiment_dir)


def test_declared_gp_hyperparameters_match_the_implementation():
    payloads = build_payloads(
        epoch=epoch_for("EZ-B001-A"),
        training_source_sha256="1" * 64,
        truth_source_sha256="2" * 64,
        ez_commit=FAKE_COMMIT,
    )
    declared = [
        m["hyperparameters"]["kernel"]
        for m in payloads[MODEL_SUITE_FILE]["models"]
        if "kernel" in m["hyperparameters"]
    ]
    assert len(declared) == 2
    params = _KERNEL.get_params(deep=True)
    live = {
        "constant_value": params["k1__k1__constant_value"],
        "length_scale": params["k1__k2__length_scale"],
        "noise_level": params["k2__noise_level"],
    }
    for kernel in declared:
        assert kernel["constant_value"] == live["constant_value"]
        assert kernel["length_scale"] == live["length_scale"]
        assert kernel["noise_level"] == live["noise_level"]
        assert kernel["optimizer"] is None


def test_target_policy_preserves_old_estimated_targets(tmp_path):
    """An old estimated row stays a target once the later edition makes it eligible."""
    from tests.helpers import toy_mass_excess

    from elementzero.data.amdc.ame2003 import EDITION as AME2003
    from elementzero.data.amdc.ame2020 import EDITION as AME2020

    old_rows = [
        (10, 10, "X", toy_mass_excess(10, 10), 12.0, False),
        # Estimated in the earlier edition: not training truth, still a valid target.
        (11, 12, "X", toy_mass_excess(11, 12), 300.0, True),
    ]
    later_rows = [
        (10, 10, "X", toy_mass_excess(10, 10), 10.0, False),
        (11, 12, "X", toy_mass_excess(11, 12), 20.0, False),
    ]
    old = write_ame_table(tmp_path / "old.mas03", old_rows, AME2003)
    later = write_ame_table(tmp_path / "later.mas20", later_rows, AME2020)

    manifest = prepare_targets(
        later_source=later,
        edition_id="AME2020",
        known_source=old,
        known_edition_id="AME2003",
    )
    ids = {t["nuclide_id"] for t in manifest["targets"]}
    assert ids == {"Z11-N12"}

    # The preregistered policy states the same rule the code implements.
    payloads = build_payloads(
        epoch=epoch_for("EZ-B001-A"),
        training_source_sha256="1" * 64,
        truth_source_sha256="2" * 64,
        ez_commit=FAKE_COMMIT,
    )
    target_policy = payloads["target_policy.json"]
    assert "does not remove a target" in target_policy["estimated_row_rule"]
    assert target_policy["rule"]["target_ids"].endswith("minus training_eligible_ids")


def test_preregistration_contains_no_truth_values(prereg):
    experiment_dir, _ = prereg
    for name in PREREGISTRATION_FILES:
        payload = json.loads((experiment_dir / name).read_text(encoding="utf-8"))
        _assert_no_truth_keys(payload, name)

    protocol = json.loads((experiment_dir / PROTOCOL_FILE).read_text(encoding="utf-8"))
    protocol["training"]["mass_excess_keV"] = -1234.5
    _rewrite(experiment_dir, PROTOCOL_FILE, protocol)
    with pytest.raises(LeakageError):
        validate_preregistration(experiment_dir)


def test_mutable_atlas_ref_rejected(prereg):
    experiment_dir, _ = prereg
    from elementzero.errors import AtlasContractError

    protocol = json.loads((experiment_dir / PROTOCOL_FILE).read_text(encoding="utf-8"))
    protocol["atlas_pir_ref"] = "main"
    _rewrite(experiment_dir, PROTOCOL_FILE, protocol)
    with pytest.raises(AtlasContractError):
        validate_preregistration(experiment_dir)


def test_uncommitted_elementzero_sha_rejected(tmp_path, epoch, monkeypatch):
    monkeypatch.setenv("ELEMENTZERO_COMMIT", f"{'b' * 40}-dirty")
    training = tmp_path / "t.mas03"
    truth = tmp_path / "l.mas12"
    training.write_bytes(b"a\n")
    truth.write_bytes(b"b\n")
    experiment_dir = tmp_path / "dirty"
    write_preregistration(
        epoch=epoch,
        experiment_dir=experiment_dir,
        training_source=training,
        truth_source=truth,
    )
    with pytest.raises(ProtocolError):
        validate_preregistration(experiment_dir)


def test_unknown_metric_rejected(prereg):
    experiment_dir, _ = prereg
    metrics = json.loads((experiment_dir / METRICS_POLICY_FILE).read_text(encoding="utf-8"))
    metrics["primary_metrics"] = [*metrics["primary_metrics"], "R2_after_the_fact"]
    _rewrite(experiment_dir, METRICS_POLICY_FILE, metrics)
    with pytest.raises(ProtocolError):
        validate_preregistration(experiment_dir)


def test_unknown_model_rejected(prereg):
    experiment_dir, _ = prereg
    suite = json.loads((experiment_dir / MODEL_SUITE_FILE).read_text(encoding="utf-8"))
    suite["model_ids"] = [*suite["model_ids"][:2], "EZ-MYSTERY-NET-v9"]
    suite["models"][2]["model_id"] = "EZ-MYSTERY-NET-v9"
    _rewrite(experiment_dir, MODEL_SUITE_FILE, suite)
    with pytest.raises(ProtocolError):
        validate_preregistration(experiment_dir)


def test_all_declared_epochs_share_one_protocol_version_and_suite():
    digests = set()
    for experiment_id in EPOCHS:
        payloads = build_payloads(
            epoch=epoch_for(experiment_id),
            training_source_sha256="3" * 64,
            truth_source_sha256="4" * 64,
            ez_commit=FAKE_COMMIT,
        )
        protocol = payloads[PROTOCOL_FILE]
        assert protocol["protocol_version"] == EXPERIMENT_PROTOCOL_VERSION
        assert protocol["model_ids"] == list(SUITE_MODEL_IDS)
        digests.add(protocol["protocol_code_digest"])
    assert len(digests) == 1


def test_declared_epoch_editions_are_parseable_and_ordered():
    order = ["EZ-B001-A", "EZ-B001-B", "EZ-B001-C"]
    assert list(EPOCHS) == order
    for previous, following in zip(order, order[1:]):
        assert EPOCHS[previous].truth_edition == EPOCHS[following].training_edition
    for spec in EPOCHS.values():
        assert spec.training_edition in {"AME2003", "AME2012", "AME2016", "AME2020"}
        assert callable(load_edition)


def _rewrite(experiment_dir: Path, name: str, payload: dict) -> None:
    (experiment_dir / name).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    digest = preregistration_hash(experiment_dir)
    (experiment_dir / PREREGISTRATION_HASH_FILE).write_text(digest + "\n", encoding="utf-8")


def _assert_no_truth_keys(node, where: str) -> None:
    if isinstance(node, dict):
        assert not TRUTH_BEARING_FIELDS.intersection(node), where
        for key, value in node.items():
            _assert_no_truth_keys(value, f"{where}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _assert_no_truth_keys(item, f"{where}[{index}]")
