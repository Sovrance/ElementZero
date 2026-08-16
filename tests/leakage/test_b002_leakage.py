"""EZ-B002 leakage controls: the region boundary is enforced in code (WO-09).

EZ-B001 can enforce blindness at the filesystem boundary because the later
edition is a different file. A geographic holdout has no second file: training
and truth live in the same snapshot. Every test here attacks that geometric
boundary from a different direction.
"""

from __future__ import annotations

import json

import pytest

from elementzero.benchmark.b002_freeze import (
    GeographicFreeze,
    assert_split_geometry,
    freeze_geographic_split,
    load_geographic_freeze,
)
from elementzero.benchmark.b002_predict import (
    _assert_manifest_free_of_targets,
    load_region_targets,
    predict_region_run,
)
from elementzero.benchmark.b002_prepare import (
    SPLIT_MANIFEST_FILE,
    TARGETS_FILE,
    eligible_observations,
    load_split_manifest,
    prepare_geographic_split,
    split_digest,
)
from elementzero.benchmark.b002_score import score_region_run
from elementzero.benchmark.regions import rectangle_region, region_manifest_hash
from elementzero.data.observations import TRUTH_BEARING_FIELDS
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json

EDITION = "AME2020"
REGION = rectangle_region(12, 15, 13, 17)
CREATED_AT = "2026-01-01T00:00:00Z"


def _split(tmp_path, source, region=REGION):
    return prepare_geographic_split(
        source=source,
        edition_id=EDITION,
        region=region,
        region_manifest_hash=region_manifest_hash([region]),
        out_dir=tmp_path / "region",
    )


def _sealed(tmp_path, source, region=REGION):
    split = _split(tmp_path, source, region)
    freeze = freeze_geographic_split(
        source=source,
        edition_id=EDITION,
        split_manifest=tmp_path / "region" / SPLIT_MANIFEST_FILE,
        output=tmp_path / "region" / "freeze.json",
    )
    return split, freeze


# --------------------------------------------------------------------------- #
# The split itself                                                            #
# --------------------------------------------------------------------------- #


def test_region_targets_excluded_from_training(tmp_path, small_synthetic_chart):
    split, freeze = _sealed(tmp_path, small_synthetic_chart)
    manifest = split["split_manifest"]
    targets = set(manifest["target_nuclide_ids"])
    training = set(manifest["training_nuclide_ids"])

    assert targets
    assert training
    assert not targets & training
    # The partition is exactly the eligible set, with nothing dropped.
    eligible = {o.nuclide_id for o in eligible_observations(small_synthetic_chart, EDITION)}
    assert targets | training == eligible
    assert len(targets) + len(training) == len(eligible)

    region = split["region"]
    assert all(region.contains_id(nid) for nid in targets)
    assert not any(region.contains_id(nid) for nid in training)

    # The freeze pins the same partition, and the identities the model may fit
    # are exactly the outside ones.
    assert set(freeze.freeze.training_nuclide_ids) == training
    assert set(freeze.target_nuclide_ids) == targets
    assert not set(freeze.freeze.training_nuclide_ids) & set(freeze.target_nuclide_ids)
    assert freeze.freeze.training_identity_digest == identity_digest(sorted(training))
    assert freeze.target_identity_digest == identity_digest(sorted(targets))


def test_target_truth_in_features_rejected(tmp_path, small_synthetic_chart):
    split, freeze = _sealed(tmp_path, small_synthetic_chart)
    targets_path = tmp_path / "region" / TARGETS_FILE
    clean = load_region_targets(targets_path)
    assert clean
    for target in clean:
        assert set(target) == {"nuclide_id", "Z", "N", "A"}

    # 1. A truth value smuggled into the target manifest the model reads.
    for field in sorted(TRUTH_BEARING_FIELDS):
        payload = json.loads(targets_path.read_text(encoding="utf-8"))
        payload["targets"][0][field] = 1.0
        bad = tmp_path / f"bad_targets_{field}.json"
        bad.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(LeakageError):
            load_region_targets(bad)

    # 2. A truth value anywhere in the split manifest, at any nesting depth.
    manifest_path = tmp_path / "region" / SPLIT_MANIFEST_FILE
    for mutation in (
        {"mass_excess_keV": -1234.5},
        {"region": {**split["split_manifest"]["region"], "mass_excess_keV": 1.0}},
    ):
        payload = {**json.loads(manifest_path.read_text(encoding="utf-8")), **mutation}
        bad = tmp_path / "bad_split.json"
        bad.write_text(canonical_json(payload), encoding="utf-8")
        with pytest.raises(LeakageError):
            load_split_manifest(bad)

    # 3. A fitted model manifest that memorized a withheld identity.
    withheld = list(freeze.target_nuclide_ids)
    _assert_manifest_free_of_targets({"fitted_nuclide_ids": ["Z1-N1"]}, withheld)
    with pytest.raises(LeakageError):
        _assert_manifest_free_of_targets({"fitted_nuclide_ids": withheld[:1]}, withheld)
    with pytest.raises(LeakageError):
        _assert_manifest_free_of_targets(
            {"debug": {"nearest": {"id": withheld[0]}}}, withheld
        )


def test_split_manifest_that_misplaces_a_nuclide_is_rejected(tmp_path, small_synthetic_chart):
    split = _split(tmp_path, small_synthetic_chart)
    manifest_path = tmp_path / "region" / SPLIT_MANIFEST_FILE
    base = json.loads(manifest_path.read_text(encoding="utf-8"))
    inside = base["target_nuclide_ids"][0]
    outside = base["training_nuclide_ids"][0]

    def rewrite(**changes):
        payload = {**base, **changes}
        path = tmp_path / "mutated_split.json"
        path.write_text(canonical_json(payload), encoding="utf-8")
        return path

    def resealed(**changes):
        """A mutation with every digest recomputed, so only geometry can object."""
        payload = {**base, **changes}
        payload["split_digest"] = split_digest(
            raw_source_hash=payload["raw_source_hash"],
            region_manifest_hash=payload["region_manifest_hash"],
            training_identity_digest=payload["training_identity_digest"],
            target_identity_digest=payload["target_identity_digest"],
            feature_policy_hash=payload["feature_policy_hash"],
        )
        return rewrite(**payload)

    # A target moved into training.
    training = sorted([*base["training_nuclide_ids"], inside])
    with pytest.raises(LeakageError):
        load_split_manifest(
            resealed(
                training_nuclide_ids=training,
                training_identity_digest=identity_digest(training),
            )
        )
    # A training nucleus claimed as a target.
    targets = sorted([*base["target_nuclide_ids"], outside])
    with pytest.raises(LeakageError):
        load_split_manifest(
            resealed(
                target_nuclide_ids=targets,
                target_identity_digest=identity_digest(targets),
            )
        )
    # Digests and the split digest are each independently load-bearing.
    with pytest.raises(ProtocolError):
        load_split_manifest(rewrite(target_identity_digest="0" * 64))
    with pytest.raises(ProtocolError):
        load_split_manifest(rewrite(split_digest="0" * 64))
    with pytest.raises(ProtocolError):
        load_split_manifest(rewrite(region_id="rect-Z1-2-N1-2"))
    assert split["split_manifest"]["split_digest"] == base["split_digest"]


def test_freeze_refuses_a_swapped_region_source_or_digest(tmp_path, small_synthetic_chart):
    _split, freeze = _sealed(tmp_path, small_synthetic_chart)
    payload = freeze.to_dict()

    # Geometry: a target outside the region, or a training nucleus inside it.
    with pytest.raises(LeakageError):
        assert_split_geometry(
            region=freeze.region,
            training_nuclide_ids=freeze.freeze.training_nuclide_ids,
            target_nuclide_ids=[*freeze.target_nuclide_ids, "Z1-N1"],
        )
    with pytest.raises(LeakageError):
        assert_split_geometry(
            region=freeze.region,
            training_nuclide_ids=[*freeze.freeze.training_nuclide_ids, freeze.target_nuclide_ids[0]],
            target_nuclide_ids=freeze.target_nuclide_ids,
        )

    # A region swapped inside a sealed freeze leaves every withheld nucleus
    # outside the declared block.
    swapped = {**payload, "region": rectangle_region(30, 33, 30, 34).to_dict()}
    swapped["region_id"] = "rect-Z30-33-N30-34"
    with pytest.raises(LeakageError):
        GeographicFreeze.from_dict(swapped)
    with pytest.raises(ProtocolError):
        GeographicFreeze.from_dict({**payload, "region_manifest_hash": "0" * 64})
    with pytest.raises(ProtocolError):
        GeographicFreeze.from_dict({**payload, "split_digest": "0" * 64})
    with pytest.raises(ProtocolError):
        GeographicFreeze.from_dict({**payload, "benchmark_id": "EZ-B001"})
    for key in ("region", "region_manifest_hash", "split_digest", "target_nuclide_ids"):
        with pytest.raises(ProtocolError):
            GeographicFreeze.from_dict({k: v for k, v in payload.items() if k != key})

    # Freezing against a different snapshot than the split was built on.
    other = tmp_path / "other.mas20"
    other.write_text(small_synthetic_chart.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ProtocolError):
        freeze_geographic_split(
            source=other,
            edition_id=EDITION,
            split_manifest=tmp_path / "region" / SPLIT_MANIFEST_FILE,
        )
    with pytest.raises(ProtocolError):
        freeze_geographic_split(
            source=small_synthetic_chart,
            edition_id="AME2003",
            split_manifest=tmp_path / "region" / SPLIT_MANIFEST_FILE,
        )


# --------------------------------------------------------------------------- #
# Prediction                                                                  #
# --------------------------------------------------------------------------- #


def test_prediction_refuses_a_training_corpus_that_reaches_into_the_region(
    tmp_path, small_synthetic_chart
):
    _split, freeze = _sealed(tmp_path, small_synthetic_chart)
    targets = load_region_targets(tmp_path / "region" / TARGETS_FILE)
    payload = freeze.to_dict()

    # A freeze whose training list was widened to include a withheld nucleus.
    # Every digest is recomputed, so nothing but the geometry can catch it.
    leaked = sorted([*payload["training_nuclide_ids"], payload["target_nuclide_ids"][0]])
    tampered = {
        **payload,
        "training_nuclide_ids": leaked,
        "training_identity_digest": identity_digest(leaked),
    }
    tampered["split_digest"] = split_digest(
        raw_source_hash=tampered["raw_source_hash"],
        region_manifest_hash=tampered["region_manifest_hash"],
        training_identity_digest=tampered["training_identity_digest"],
        target_identity_digest=tampered["target_identity_digest"],
        feature_policy_hash=tampered["feature_policy_hash"],
    )
    with pytest.raises(LeakageError):
        GeographicFreeze.from_dict(tampered)

    # A target manifest that does not match the freeze cannot be predicted.
    with pytest.raises(LeakageError):
        predict_region_run(
            geographic_freeze=freeze,
            targets=targets[:-1],
            source=small_synthetic_chart,
            edition_id=EDITION,
            run_dir=tmp_path / "run_short",
            created_at=CREATED_AT,
        )
    # A snapshot the freeze never allowed cannot be fitted.
    other = tmp_path / "other.mas20"
    other.write_text(small_synthetic_chart.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(LeakageError):
        predict_region_run(
            geographic_freeze=freeze,
            targets=targets,
            source=other,
            edition_id=EDITION,
            run_dir=tmp_path / "run_other",
            created_at=CREATED_AT,
        )
    with pytest.raises(LeakageError):
        predict_region_run(
            geographic_freeze=freeze,
            targets=targets,
            source=small_synthetic_chart,
            edition_id="AME2003",
            run_dir=tmp_path / "run_edition",
            created_at=CREATED_AT,
        )


def test_sealed_run_artifacts_carry_no_truth_value(tmp_path, small_synthetic_chart):
    _split, freeze = _sealed(tmp_path, small_synthetic_chart)
    targets = load_region_targets(tmp_path / "region" / TARGETS_FILE)
    run_dir = tmp_path / "run"
    result = predict_region_run(
        geographic_freeze=freeze,
        targets=targets,
        source=small_synthetic_chart,
        edition_id=EDITION,
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    truth = {
        o.nuclide_id: o.mass_excess_keV
        for o in eligible_observations(small_synthetic_chart, EDITION)
    }
    withheld = set(freeze.target_nuclide_ids)
    # No withheld identity may be quoted anywhere in the fitted model manifest.
    manifest_text = (run_dir / "model_manifest.json").read_text(encoding="utf-8")
    assert not [nid for nid in withheld if f'"{nid}"' in manifest_text]
    manifest = json.loads(manifest_text)
    assert not withheld & set(manifest["model"]["fitted_nuclide_ids"])
    assert manifest["model"]["features"] == ["Z", "N", "A"]
    for prediction in result["predictions"]:
        assert prediction["nuclide_id"] in withheld
        assert prediction["mass_excess_keV"] != truth[prediction["nuclide_id"]]
        assert prediction["nearest_training_L1"] >= 1
    for certificate in result["certificates"]:
        assert certificate["benchmark_id"] == "EZ-B002"
        assert certificate["region_id"] == freeze.region_id
        assert certificate["region_manifest_hash"] == freeze.region_manifest_hash
        assert certificate["split_digest"] == freeze.split_digest
        assert certificate["nearest_training_L1"] >= 1


# --------------------------------------------------------------------------- #
# Scoring                                                                     #
# --------------------------------------------------------------------------- #


def test_scoring_refuses_an_unsealed_run_or_a_swapped_truth_table(
    tmp_path, small_synthetic_chart
):
    _split, freeze = _sealed(tmp_path, small_synthetic_chart)
    targets = load_region_targets(tmp_path / "region" / TARGETS_FILE)
    run_dir = tmp_path / "run"
    predict_region_run(
        geographic_freeze=freeze,
        targets=targets,
        source=small_synthetic_chart,
        edition_id=EDITION,
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    # Truth inside the region may not be read before the run is finalized.
    with pytest.raises(LeakageError):
        score_region_run(
            run_dir=run_dir,
            truth_source=small_synthetic_chart,
            truth_edition_id=EDITION,
            out_dir=tmp_path / "score",
            created_at=CREATED_AT,
        )

    from elementzero.benchmark.b002_finalize import finalize_region_run

    finalize_region_run(run_dir, created_at=CREATED_AT)
    # A geographic holdout has exactly one snapshot; a different table would
    # silently change the benchmark.
    other = tmp_path / "other.mas20"
    other.write_text(small_synthetic_chart.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ProtocolError):
        score_region_run(
            run_dir=run_dir,
            truth_source=other,
            truth_edition_id=EDITION,
            out_dir=tmp_path / "score_other",
            created_at=CREATED_AT,
        )
    report = score_region_run(
        run_dir=run_dir,
        truth_source=small_synthetic_chart,
        truth_edition_id=EDITION,
        out_dir=tmp_path / "score_ok",
        created_at=CREATED_AT,
    )
    assert report["metrics"]["n"] == len(targets)
    sealed = load_geographic_freeze(run_dir / "freeze.json")
    assert report["region_id"] == sealed.region_id

    # Sigma comes from the model, so every sealed prediction must carry one. In
    # a sealed run the marker catches the edit first, which is the point: the
    # sigma check is a backstop behind the seal, not a substitute for it.
    stripped = [
        {k: v for k, v in pred.items() if k != "std_keV"}
        for pred in json.loads((run_dir / "predictions.json").read_text(encoding="utf-8"))
    ]
    (run_dir / "predictions.json").write_text(canonical_json(stripped), encoding="utf-8")
    with pytest.raises(LeakageError):
        score_region_run(
            run_dir=run_dir,
            truth_source=small_synthetic_chart,
            truth_edition_id=EDITION,
            out_dir=tmp_path / "score_nosigma",
            created_at=CREATED_AT,
        )


def test_finalize_refuses_a_run_that_is_not_a_geographic_holdout(tmp_path):
    from elementzero.benchmark.b002_finalize import finalize_region_run
    from elementzero.evidence.ledger import write_run_artifact

    run_dir = tmp_path / "not_b002"
    with pytest.raises(ProtocolError):
        finalize_region_run(run_dir)
    write_run_artifact(run_dir, "run_manifest", {"benchmark_id": "EZ-B001"})
    with pytest.raises(ProtocolError):
        finalize_region_run(run_dir)
    write_run_artifact(run_dir, "run_manifest", {"benchmark_id": "EZ-B002"})
    with pytest.raises(ProtocolError):
        finalize_region_run(run_dir)
