"""EZ-B003 end to end on a synthetic chart with an injected shell discontinuity.

WO-10 section 8 asks for exactly this rehearsal *before* any known closure is
scored, so that the benchmark mechanics can be checked where the answer is known
by construction. The five steps it lists are the five steps tested here:

    hide the shell neighborhood
    reconstruct masses
    derive S2n/S2p
    compute delta2n/delta2p
    rank the hidden feature

The synthetic surface is the EZ-B002 toy surface plus two injected kinks in the
binding energy, ``-g * max(0, x - x0)`` on each axis (``tests/helpers.py``). A
kink of that shape puts a spike of exactly ``+2g`` into the shell-gap indicator
at the closure and nothing anywhere else in the same parity class, so "did the
benchmark find the injected feature" has an arithmetic answer rather than an
impression.

The control is the same chart with both kinks moved off the lattice. It isolates
the injected feature from the smooth background: on the kinked chart the withheld
closure ranks first in every scored chain, and on the control chart it does not.

What these tests do *not* claim: that the frozen model suite rediscovers the
feature. It largely does not, and the committed experiment records that as a
CRITERION_NOT_MET result. These tests pin down the instrument.
"""

from __future__ import annotations

import json

import pytest
from tests.helpers import (
    INJECTED_NEUTRON_CLOSURE,
    INJECTED_PROTON_CLOSURE,
    INJECTED_NEUTRON_GAP_MeV,
    INJECTED_PROTON_GAP_MeV,
    write_unkinked_synthetic_shell_chart,
)

from elementzero import B003_PROTOCOL_VERSION, BENCHMARK_EZ_B003, BENCHMARK_PROTOCOL_VERSION
from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.b003_finalize import finalize_shell_run
from elementzero.benchmark.b003_freeze import freeze_shell_split, load_shell_freeze
from elementzero.benchmark.b003_predict import (
    MODEL_SUITE_ID_B003,
    load_shell_targets,
    predict_shell_run,
    run_shell_suite,
)
from elementzero.benchmark.b003_prepare import (
    PROFILE_DISCOVERY,
    SPLIT_MANIFEST_FILE,
    SUPPORT_FILE,
    TARGETS_FILE,
    eligible_observations,
    eligible_points,
    prepare_shell_split,
)
from elementzero.benchmark.b003_score import (
    CHALLENGE_COMPARISON_JSON,
    CHALLENGE_COMPARISON_MARKDOWN,
    SCOPE_SYNTHETIC,
    SHELL_AGGREGATE_JSON,
    SHELL_AGGREGATE_MARKDOWN,
    aggregate_challenges,
    build_surfaces,
    chain_rows,
    score_shell_run,
    score_shell_suite,
)
from elementzero.benchmark.model_suite import SUITE_MODEL_IDS
from elementzero.benchmark.shell_masks import (
    STATUS_EVALUABLE,
    STATUS_NOT_EVALUABLE,
    challenge_manifest_hash,
    generate_challenges,
)
from elementzero.benchmark.shell_metrics import (
    REDISCOVERY_CRITERION_ID,
    SURFACE_PREDICTION,
    SURFACE_TRUTH,
    VERDICT_MET,
    VERDICT_NOT_MET,
    VERDICT_NOT_YET_SCORED,
)
from elementzero.cli import main
from elementzero.data.amdc import load_edition
from elementzero.errors import ProtocolError
from elementzero.evidence.atlas_adapter import read_atlas_facts
from elementzero.evidence.ledger import is_finalized
from elementzero.experiments.b003_runner import (
    CHALLENGES_FILE,
    CRITERION_FILE,
    CRITERION_HASH_FILE,
    SEALED_PREDICTIONS_FILE,
    score_b003,
    seal_b003,
    select_challenges_for_source,
)
from elementzero.experiments.runner import verify_sha256sums
from elementzero.physics.separation import (
    OBSERVABLE_DELTA2N,
    OBSERVABLE_DELTA2P,
    delta2n,
    delta2p,
    s2n,
    s2p,
)

EDITION = "AME2020"
CREATED_AT = "2026-01-01T00:00:00Z"
SCHEMAS = REPO_ROOT / "schemas"

NEUTRON_CHALLENGE = f"neutron-N{INJECTED_NEUTRON_CLOSURE}"
PROTON_CHALLENGE = f"proton-Z{INJECTED_PROTON_CLOSURE}"
INJECTED_SPIKES_MeV = {
    NEUTRON_CHALLENGE: 2.0 * INJECTED_NEUTRON_GAP_MeV,
    PROTON_CHALLENGE: 2.0 * INJECTED_PROTON_GAP_MeV,
}


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _challenge(source, challenge_id):
    """The mask and support verdict the preregistered rules produce for one closure."""
    generated = generate_challenges(eligible_points(source, EDITION))
    return next(c for c in generated["challenges"] if c.challenge_id == challenge_id), generated


def _exact_surfaces(source, challenge):
    """Surfaces whose masked values are the withheld truth itself.

    This measures the instrument, not a model: it answers "given a *perfect*
    reconstruction of the withheld masses, does the pipeline surface the injected
    feature?" A model is scored separately, through the sealed pipeline.
    """
    mask = challenge.mask
    observations = [o for o in load_edition(EDITION, str(source)) if o.ground_truth_eligible]
    truth_rows = [
        {"Z": o.Z, "N": o.N, "mass_excess_keV": o.mass_excess_keV} for o in observations
    ]
    exact = [
        {"nuclide_id": o.nuclide_id, "mass_excess_keV": o.mass_excess_keV}
        for o in observations
        if mask.contains(o.Z, o.N)
    ]
    return build_surfaces(mask=mask, truth_rows=truth_rows, predictions=exact)


def _exact_rows(source, challenge_id):
    challenge, _ = _challenge(source, challenge_id)
    surfaces = _exact_surfaces(source, challenge)
    rows = chain_rows(
        mask=challenge.mask,
        supported_chains=challenge.supported_chains,
        unsupported_chains=challenge.unsupported_chains,
        surfaces=surfaces,
    )
    return challenge, surfaces, rows


def _split_and_freeze(tmp_path, source, challenge_id=NEUTRON_CHALLENGE, name="challenge"):
    challenge, generated = _challenge(source, challenge_id)
    assert challenge.status == STATUS_EVALUABLE, challenge.reasons
    cdir = tmp_path / name
    split = prepare_shell_split(
        source=source,
        edition_id=EDITION,
        mask=challenge.mask,
        challenge_manifest_hash=challenge_manifest_hash(generated["challenges"]),
        out_dir=cdir,
        profile=PROFILE_DISCOVERY,
    )
    freeze_shell_split(
        source=source,
        edition_id=EDITION,
        split_manifest=cdir / SPLIT_MANIFEST_FILE,
        output=cdir / "freeze.json",
    )
    shell = load_shell_freeze(cdir / "freeze.json")
    return challenge, split, shell, load_shell_targets(cdir / TARGETS_FILE), cdir


# --------------------------------------------------------------------------- #
# WO-10 section 8, required test: test_synthetic_shell_peak_recovery           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("challenge_id", [NEUTRON_CHALLENGE, PROTON_CHALLENGE])
def test_synthetic_shell_peak_recovery(tmp_path, synthetic_shell_chart, challenge_id):
    """The five mechanics of WO-10 section 8, on both injected closures."""
    control = write_unkinked_synthetic_shell_chart(tmp_path / "control.mas20")
    challenge, surfaces, rows = _exact_rows(synthetic_shell_chart, challenge_id)
    _control_challenge, _control_surfaces, control_rows = _exact_rows(control, challenge_id)
    mask = challenge.mask
    indicator = mask.indicator
    spike = INJECTED_SPIKES_MeV[challenge_id]

    # 1. Hide the shell neighborhood: three closure-axis values wide, and every
    #    chain that holds an eligible nucleus in it.
    assert mask.hidden_values == (mask.closure - 1, mask.closure, mask.closure + 1)
    assert mask.closure == (
        INJECTED_NEUTRON_CLOSURE if challenge_id == NEUTRON_CHALLENGE else INJECTED_PROTON_CLOSURE
    )
    assert indicator == (
        OBSERVABLE_DELTA2N if challenge_id == NEUTRON_CHALLENGE else OBSERVABLE_DELTA2P
    )
    eligible = eligible_points(synthetic_shell_chart, EDITION)
    hidden = {p for p in eligible if mask.contains(*p)}
    assert hidden and len(hidden) == challenge.n_targets
    # No eligible nucleus anywhere in the neighborhood survives outside the mask,
    # so no unmasked chain still carries the injected feature.
    assert not [
        p for p in eligible if mask.closure_coordinate(*p) in mask.hidden_values and p not in hidden
    ]

    # 2. Reconstruct masses: every scored chain has both surfaces populated.
    scored = [r for r in rows if r["status"] == STATUS_EVALUABLE]
    assert len(scored) >= 3
    assert [r["chain"] for r in scored] == list(challenge.supported_chains)

    # 3. Derive S2n/S2p, and 4. compute delta2n/delta2p, through the definitions.
    for row in scored:
        z, n = row["Z"], row["N"]
        truth = surfaces["truth"]
        if indicator == OBSERVABLE_DELTA2N:
            first = s2n(truth, z=z, n=n)
            second = s2n(truth, z=z, n=n + 2)
            assert first is not None and second is not None
            assert delta2n(truth, z=z, n=n) == pytest.approx(first - second, abs=1e-9)
        else:
            first = s2p(truth, z=z, n=n)
            second = s2p(truth, z=z + 2, n=n)
            assert first is not None and second is not None
            assert delta2p(truth, z=z, n=n) == pytest.approx(first - second, abs=1e-9)

    # 5. Rank the hidden feature. The injected kink is worth exactly +2g in the
    #    indicator at the closure, at every chain, and nothing else changes.
    control_by_chain = {r["chain"]: r for r in control_rows}
    for row in scored:
        baseline = control_by_chain[row["chain"]]
        assert baseline["status"] == STATUS_EVALUABLE
        assert row[f"true_{indicator}"] - baseline[f"true_{indicator}"] == pytest.approx(
            spike, abs=1e-6
        )
        # With the feature present the withheld closure is the local peak...
        assert row["true_local_peak_rank"] == 1
        assert row["local_peak_rank"] == 1
        assert row["sign_recovered"] is True
        assert row[f"absolute_{indicator}_error"] == pytest.approx(0.0, abs=1e-9)
        assert row["predicted_peak"]["rank_bucket"] == "rank_1"
        assert row["n_peak_candidates"] >= 3

    # ...and on the control chart, where nothing was injected, it is not. If this
    # ever passed, the "rank 1" above would be an artifact of the smooth surface
    # rather than a detection of the injected feature.
    assert not all(r["true_local_peak_rank"] == 1 for r in control_rows if r["local_peak_rank"])


def test_the_injected_peak_survives_the_whole_sealed_pipeline(tmp_path, synthetic_shell_chart):
    """A perfect reconstruction, scored through the sealed run, ranks the closure first.

    The check above works on the surfaces directly. This one goes through the
    real seal: prepare, freeze, predict, finalize, and score, with the sealed
    prediction file rewritten to the withheld truth. It is a mechanics check of
    the scoring path, so the model comparison is not involved.
    """
    challenge, _split, shell, targets, cdir = _split_and_freeze(tmp_path, synthetic_shell_chart)
    run_dir = tmp_path / "run"
    predict_shell_run(
        shell_freeze=shell,
        targets=targets,
        source=synthetic_shell_chart,
        edition_id=EDITION,
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    finalize_shell_run(run_dir, created_at=CREATED_AT)
    report = score_shell_run(
        run_dir=run_dir,
        truth_source=synthetic_shell_chart,
        truth_edition_id=EDITION,
        scope=SCOPE_SYNTHETIC,
        out_dir=tmp_path / "score",
        created_at=CREATED_AT,
    )
    # The mask, the derived observable, and the frozen criterion all travel with
    # the report, and the verdict names the scope it applies to.
    assert report["challenge_id"] == NEUTRON_CHALLENGE
    assert report["indicator"] == OBSERVABLE_DELTA2N
    assert report["scope"] == SCOPE_SYNTHETIC
    assert report["criterion"]["scope"] == SCOPE_SYNTHETIC
    assert report["criterion"]["criterion"]["criterion_id"] == REDISCOVERY_CRITERION_ID
    assert report["criterion"]["verdict"] in {VERDICT_MET, VERDICT_NOT_MET, VERDICT_NOT_YET_SCORED}
    # Truth ranks the injected closure first in every scored chain, whatever the
    # model did, which is the instrument working on a sealed run.
    scored = [r for r in report["discovery_rows"] if r["status"] == STATUS_EVALUABLE]
    assert scored
    assert all(r["true_local_peak_rank"] == 1 for r in scored)
    assert report["hypothesis_resolution"][SURFACE_TRUTH]["selected_label"] == "H1"
    assert set(report["hypothesis_statements"]) == {"H0", "H1"}
    assert "no local shell discontinuity" in report["hypothesis_statements"]["H0"]
    # The boundary statement is carried by the artifact, not only by the prose.
    assert "island of stability" in report["boundary_rule"]
    assert "Z = 154" in report["boundary_rule"]


# --------------------------------------------------------------------------- #
# The hidden truth stays hidden                                               #
# --------------------------------------------------------------------------- #


def test_the_synthetic_hidden_truth_never_reaches_the_fit(
    tmp_path, small_synthetic_shell_chart, monkeypatch
):
    """WO-10 section 8: the discovery model must not receive the hidden truth."""
    _challenge_, _split, shell, targets, _cdir = _split_and_freeze(
        tmp_path, small_synthetic_shell_chart
    )
    seen: list[list] = []
    real_build = __import__("elementzero.models.gp_residual", fromlist=["build_model"]).build_model

    def spying_build(model_id):
        model = real_build(model_id)
        real_fit = model.fit

        def fit(observations):
            seen.append(list(observations))
            return real_fit(observations)

        model.fit = fit
        return model

    monkeypatch.setattr("elementzero.benchmark.b003_predict.build_model", spying_build)
    predict_shell_run(
        shell_freeze=shell,
        targets=targets,
        source=small_synthetic_shell_chart,
        edition_id=EDITION,
        run_dir=tmp_path / "run",
        created_at=CREATED_AT,
    )
    assert len(seen) == 1
    fitted = seen[0]
    assert fitted
    withheld = set(shell.target_nuclide_ids)
    assert withheld
    # Not one row of the hidden neighborhood reached the fit, by identity...
    assert not {obs.nuclide_id for obs in fitted} & withheld
    assert not [obs for obs in fitted if shell.mask.contains(obs.Z, obs.N)]
    # ...nor by value.
    hidden_masses = {
        obs.mass_excess_keV
        for obs in eligible_observations(small_synthetic_shell_chart, EDITION)
        if obs.nuclide_id in withheld
    }
    assert not {obs.mass_excess_keV for obs in fitted} & hidden_masses
    assert {obs.nuclide_id for obs in fitted} == set(shell.freeze.training_nuclide_ids)


# --------------------------------------------------------------------------- #
# WO-10 required test: test_atlas_marks_derived_observables_as_derived         #
# --------------------------------------------------------------------------- #


def test_atlas_marks_derived_observables_as_derived(tmp_path, small_synthetic_shell_chart):
    """Every S2n/S2p/delta value in the graph says it re-expresses its inputs.

    WO-10 section 4: "They are not independent evidence from the masses used to
    compute them. Atlas provenance must mark this derivation." So every derived
    fact carries ``derived = true``, ``independent_evidence = false``, the exact
    input identities, and the origin of each input.
    """
    _challenge_, _split, shell, targets, _cdir = _split_and_freeze(
        tmp_path, small_synthetic_shell_chart
    )
    run_dir = tmp_path / "run"
    predict_shell_run(
        shell_freeze=shell,
        targets=targets,
        source=small_synthetic_shell_chart,
        edition_id=EDITION,
        run_dir=run_dir,
        created_at=CREATED_AT,
    )
    finalize_shell_run(run_dir, created_at=CREATED_AT)
    report = score_shell_run(
        run_dir=run_dir,
        truth_source=small_synthetic_shell_chart,
        truth_edition_id=EDITION,
        scope=SCOPE_SYNTHETIC,
        out_dir=tmp_path / "score",
        created_at=CREATED_AT,
    )
    facts = read_atlas_facts(tmp_path / "score", stage="score")
    derived = [f for f in facts if f["content"]["kind"] == "nuclear_derived_observable"]
    scored = [r for r in report["discovery_rows"] if r["status"] == STATUS_EVALUABLE]
    assert scored
    # One fact per surface per scored chain, and nothing is dropped.
    assert len(derived) == 2 * len(scored)
    assert {f["fact_id"] for f in derived} == set(report["derived_observable_fact_ids"])

    by_surface: dict[str, list] = {SURFACE_PREDICTION: [], SURFACE_TRUTH: []}
    for fact in derived:
        content = fact["content"]
        by_surface[content["surface"]].append(fact)
        assert content["derived"] is True
        assert content["independent_evidence"] is False
        assert content["observable"] == OBSERVABLE_DELTA2N
        assert content["separation_policy_id"] == "ez-b003-separation-observables-v1"
        # The definition and the exact inputs travel with the value.
        assert content["definition"].startswith("delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2)")
        assert len(content["derived_from"]) == 3
        assert [i["nuclide_id"] for i in content["inputs"]] == content["derived_from"]
        assert all(i["present"] for i in content["inputs"])
        assert content["challenge_id"] == NEUTRON_CHALLENGE
        assert content["mask_id"] == shell.mask.mask_id
        assert content["freeze_id"] == shell.freeze_id
        assert any("not independent evidence" in w["message"] for w in fact["warnings"])
        assert fact["depends_on_facts"]

    assert len(by_surface[SURFACE_PREDICTION]) == len(by_surface[SURFACE_TRUTH]) == len(scored)
    for fact in by_surface[SURFACE_PREDICTION]:
        # Conditioned on a model's reconstruction: proxy-level, analyst namespace.
        assert fact["content"]["model_conditioned"] is True
        assert "prediction" in fact["content"]["input_origins"]
        assert fact["content"]["model_id"] == report["model_id"]
        assert fact["evidence_level"] == "E3"
        assert fact["namespace"] == "analyst"
        assert fact["depends_on_facts"] == [report["prediction_set_fact_id"]]
    for fact in by_surface[SURFACE_TRUTH]:
        # Derived from snapshot truth only: still derived, but not model-conditioned.
        assert fact["content"]["model_conditioned"] is False
        assert "prediction" not in fact["content"]["input_origins"]
        assert fact["content"]["model_id"] is None
        assert fact["evidence_level"] == "E2"
        assert fact["namespace"] == "domain"
        assert fact["depends_on_facts"] == [report["truth_dataset_fact_id"]]

    # The discovery verdict itself is derived, model-conditioned, and E3.
    discovery = next(f for f in facts if f["content"]["kind"] == "nuclear_shell_discovery")
    assert discovery["content"]["derived"] is True
    assert discovery["content"]["independent_evidence"] is False
    assert discovery["evidence_level"] == "E3"
    assert discovery["analyzer"]["tag"] == "HEURISTIC"
    assert set(report["derived_observable_fact_ids"]) <= set(discovery["depends_on_facts"])
    assert discovery["content"]["scope"] == SCOPE_SYNTHETIC

    # And so does every row and every aggregate the report writes.
    for row in report["discovery_rows"]:
        assert row["derived"] is True
        assert row["independent_evidence"] is False
    assert report["metrics"]["discovery"]["derived"] is True
    assert report["metrics"]["discovery"]["independent_evidence"] is False
    assert report["separation_policy"]["derived"] is True
    assert "not independent evidence" in report["separation_policy"]["derivation_rule"]

    # The hypothesis pair is bookkeeping over the same derived quantities.
    hypotheses = read_atlas_facts(run_dir, stage="predict")
    hypothesis_set = next(
        f for f in hypotheses if f["content"]["kind"] == "nuclear_shell_hypothesis_set"
    )
    assert [h["label"] for h in hypothesis_set["content"]["hypotheses"]] == ["H0", "H1"]
    assert hypothesis_set["content"]["discriminating_observable"] == OBSERVABLE_DELTA2N


# --------------------------------------------------------------------------- #
# One split per suite, every closure reported                                 #
# --------------------------------------------------------------------------- #


def test_all_models_share_one_shell_split(tmp_path, small_synthetic_shell_chart):
    challenge, _split, shell, targets, cdir = _split_and_freeze(
        tmp_path, small_synthetic_shell_chart
    )
    suite_dir = cdir / "runs"
    suite = run_shell_suite(
        shell_freeze=shell,
        targets=targets,
        source=small_synthetic_shell_chart,
        edition_id=EDITION,
        suite_dir=suite_dir,
        created_at=CREATED_AT,
    )
    assert suite["model_suite_id"] == MODEL_SUITE_ID_B003
    assert suite["model_ids"] == list(SUITE_MODEL_IDS)

    masks, freezes, splits, manifests = set(), set(), set(), set()
    for model_id in SUITE_MODEL_IDS:
        run_dir = suite_dir / model_id
        assert is_finalized(run_dir)
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["benchmark_id"] == BENCHMARK_EZ_B003
        assert manifest["protocol_version"] == BENCHMARK_PROTOCOL_VERSION
        assert manifest["b003_protocol_version"] == B003_PROTOCOL_VERSION
        assert manifest["profile"] == PROFILE_DISCOVERY
        assert manifest["challenge_id"] == NEUTRON_CHALLENGE
        masks.add(manifest["mask_id"])
        freezes.add(manifest["freeze_id"])
        splits.add(manifest["split_digest"])
        manifests.add(manifest["model_manifest_hash"])
    # One mask, one freeze, one split...
    assert masks == {challenge.mask.mask_id}
    assert len(freezes) == len(splits) == 1
    # ...and three genuinely different models.
    assert len(manifests) == len(SUITE_MODEL_IDS)

    comparison = score_shell_suite(
        suite_dir=suite_dir,
        truth_source=small_synthetic_shell_chart,
        truth_edition_id=EDITION,
        scope=SCOPE_SYNTHETIC,
        created_at=CREATED_AT,
    )
    assert [row["model_id"] for row in comparison["rows"]] == list(SUITE_MODEL_IDS)
    assert comparison["challenge_id"] == NEUTRON_CHALLENGE
    assert comparison["scope"] == SCOPE_SYNTHETIC
    assert (suite_dir / CHALLENGE_COMPARISON_JSON).is_file()
    markdown = (suite_dir / CHALLENGE_COMPARISON_MARKDOWN).read_text(encoding="utf-8")
    for model_id in SUITE_MODEL_IDS:
        assert model_id in markdown
    # The ASCII definitions of the derived observables are in the report itself.
    assert "S2n(Z,N)     = B(Z,N) - B(Z,N-2)" in markdown
    assert "delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2)" in markdown
    # Truth says H1 at the injected closure for every model's report, because it
    # is a property of the chart rather than of the reconstruction.
    assert {row["truth_hypothesis"] for row in comparison["rows"]} == {"H1"}


def test_every_declared_closure_is_reported_evaluable_or_not(tmp_path, synthetic_shell_chart):
    experiment_dir = tmp_path / "EZ-B003-TEST"
    selected = select_challenges_for_source(
        source=synthetic_shell_chart,
        edition_id=EDITION,
        output=tmp_path / CHALLENGES_FILE,
        source_relpath="shell_chart.mas20",
    )
    manifest = selected["manifest"]
    # Both injected closures are supported by this chart; the other seven members
    # of the availability set are reported NOT_EVALUABLE with reasons.
    assert manifest["evaluable_challenge_ids"] == [NEUTRON_CHALLENGE, PROTON_CHALLENGE]
    assert manifest["n_challenges"] == 9
    assert manifest["n_not_evaluable"] == 7
    for entry in manifest["challenges"]:
        if entry["status"] == STATUS_NOT_EVALUABLE:
            assert entry["reasons"], entry["challenge_id"]
            assert entry["mask"] is None

    sealed = seal_b003(
        source=synthetic_shell_chart,
        edition_id=EDITION,
        challenges_path=tmp_path / CHALLENGES_FILE,
        experiment_dir=experiment_dir,
        created_at=CREATED_AT,
    )
    assert sealed["sealed"]["state"] == "PREDICTIONS_SEALED_CLOSURE_TRUTH_UNREAD"
    # WO-10 section 9: the thresholds are on disk and hashed before scoring.
    assert (experiment_dir / CRITERION_FILE).is_file()
    assert (experiment_dir / CRITERION_HASH_FILE).is_file()
    assert not (experiment_dir / SHELL_AGGREGATE_JSON).exists()
    criterion = json.loads((experiment_dir / CRITERION_FILE).read_text(encoding="utf-8"))
    assert criterion["state"] == "THRESHOLDS_FROZEN_BEFORE_ANY_CLOSURE_TRUTH_READ"
    assert criterion["evaluated_mass_table_verdict"] == VERDICT_NOT_YET_SCORED

    scored = score_b003(
        source=synthetic_shell_chart,
        edition_id=EDITION,
        experiment_dir=experiment_dir,
        created_at=CREATED_AT,
    )
    aggregate = scored["aggregate"]
    assert aggregate["challenge_ids"] == [NEUTRON_CHALLENGE, PROTON_CHALLENGE]
    assert aggregate["scope"] == SCOPE_SYNTHETIC
    # Every closure x model pair is present...
    assert {(row["challenge_id"], row["model_id"]) for row in aggregate["rows"]} == {
        (challenge_id, model_id)
        for challenge_id in aggregate["challenge_ids"]
        for model_id in SUITE_MODEL_IDS
    }
    # ...and the refused closures are carried alongside rather than dropped.
    assert {c["challenge_id"] for c in aggregate["not_evaluable_closures"]} == set(
        manifest["not_evaluable_challenge_ids"]
    )
    assert aggregate["n_not_evaluable_closures"] == 7
    for model_id in SUITE_MODEL_IDS:
        entry = aggregate["by_model"][model_id]
        assert entry["n_closures"] == 2
        assert entry["criterion"]["scope"] == SCOPE_SYNTHETIC
        assert entry["criterion"]["verdict"] in {VERDICT_MET, VERDICT_NOT_MET}
    markdown = (experiment_dir / SHELL_AGGREGATE_MARKDOWN).read_text(encoding="utf-8")
    for challenge_id in manifest["not_evaluable_challenge_ids"]:
        assert challenge_id in markdown
    assert aggregate["real_closure_status"]["thresholds_frozen"] is True
    assert aggregate["real_closure_status"]["calibrated_on"] == SCOPE_SYNTHETIC
    assert verify_sha256sums(experiment_dir)["ok"]

    # Dropping a closure from the aggregate is a protocol error.
    with pytest.raises(ProtocolError):
        aggregate_challenges(
            [r for r in scored["reports"] if r["challenge_id"] != NEUTRON_CHALLENGE],
            challenge_ids=aggregate["challenge_ids"],
            model_ids=list(SUITE_MODEL_IDS),
            challenge_manifest_hash=aggregate["challenge_manifest_hash"],
            scope=SCOPE_SYNTHETIC,
        )
    # So is re-sealing over a sealed experiment directory.
    with pytest.raises(ProtocolError):
        seal_b003(
            source=synthetic_shell_chart,
            edition_id=EDITION,
            challenges_path=tmp_path / CHALLENGES_FILE,
            experiment_dir=experiment_dir,
            created_at=CREATED_AT,
        )


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def test_cli_b003_stage_flow(tmp_path, small_synthetic_shell_chart, capsys):
    challenges_path = tmp_path / CHALLENGES_FILE
    cdir = tmp_path / "challenge"
    suite_dir = cdir / "runs"
    assert (
        main([
            "benchmark", "b003-select-challenges",
            "--source", str(small_synthetic_shell_chart),
            "--edition", EDITION,
            "--output", str(challenges_path),
        ])
        == 0
    )
    manifest = json.loads(challenges_path.read_text(encoding="utf-8"))
    assert manifest["benchmark_id"] == BENCHMARK_EZ_B003
    assert manifest["evaluable_challenge_ids"] == [NEUTRON_CHALLENGE]

    assert (
        main([
            "benchmark", "b003-prepare",
            "--source", str(small_synthetic_shell_chart),
            "--edition", EDITION,
            "--challenges", str(challenges_path),
            "--challenge-id", NEUTRON_CHALLENGE,
            "--out", str(cdir),
        ])
        == 0
    )
    for name in (SPLIT_MANIFEST_FILE, TARGETS_FILE, SUPPORT_FILE):
        assert (cdir / name).is_file()
    assert (
        main([
            "benchmark", "b003-freeze",
            "--source", str(small_synthetic_shell_chart),
            "--edition", EDITION,
            "--split-manifest", str(cdir / SPLIT_MANIFEST_FILE),
            "--output", str(cdir / "freeze.json"),
        ])
        == 0
    )
    assert (
        main([
            "benchmark", "b003-predict",
            "--source", str(small_synthetic_shell_chart),
            "--edition", EDITION,
            "--freeze", str(cdir / "freeze.json"),
            "--targets", str(cdir / TARGETS_FILE),
            "--out", str(suite_dir),
        ])
        == 0
    )
    for model_id in SUITE_MODEL_IDS:
        # b003-predict seals each run as it goes.
        assert is_finalized(suite_dir / model_id)
    assert (
        main([
            "benchmark", "b003-score",
            "--suite", str(suite_dir),
            "--source", str(small_synthetic_shell_chart),
            "--edition", EDITION,
            "--scope", SCOPE_SYNTHETIC,
        ])
        == 0
    )
    comparison = json.loads((suite_dir / CHALLENGE_COMPARISON_JSON).read_text(encoding="utf-8"))
    assert comparison["challenge_id"] == NEUTRON_CHALLENGE
    assert [row["model_id"] for row in comparison["rows"]] == list(SUITE_MODEL_IDS)

    # An unsealed run can be finalized as its own CLI stage.
    lone = tmp_path / "lone"
    predict_shell_run(
        shell_freeze=load_shell_freeze(cdir / "freeze.json"),
        targets=load_shell_targets(cdir / TARGETS_FILE),
        source=small_synthetic_shell_chart,
        edition_id=EDITION,
        run_dir=lone,
        created_at=CREATED_AT,
    )
    capsys.readouterr()
    assert main(["benchmark", "b003-finalize", "--run", str(lone)]) == 0
    assert is_finalized(lone)

    # A closure the support rule refused cannot be prepared.
    with pytest.raises(SystemExit):
        main([
            "benchmark", "b003-prepare",
            "--source", str(small_synthetic_shell_chart),
            "--edition", EDITION,
            "--challenges", str(challenges_path),
            "--challenge-id", PROTON_CHALLENGE,
            "--out", str(tmp_path / "nope"),
        ])


def test_cli_b003_experiment_flow(tmp_path, synthetic_shell_chart):
    challenges_path = tmp_path / CHALLENGES_FILE
    experiment_dir = tmp_path / "EZ-B003-CLI"
    assert (
        main([
            "benchmark", "b003-select-challenges",
            "--source", str(synthetic_shell_chart),
            "--edition", EDITION,
            "--output", str(challenges_path),
        ])
        == 0
    )
    assert (
        main([
            "benchmark", "b003-seal-experiment",
            "--source", str(synthetic_shell_chart),
            "--edition", EDITION,
            "--challenges", str(challenges_path),
            "--dir", str(experiment_dir),
            "--scope", SCOPE_SYNTHETIC,
            "--created-at", CREATED_AT,
        ])
        == 0
    )
    sealed = json.loads((experiment_dir / SEALED_PREDICTIONS_FILE).read_text(encoding="utf-8"))
    assert sealed["state"] == "PREDICTIONS_SEALED_CLOSURE_TRUTH_UNREAD"
    assert not (experiment_dir / SHELL_AGGREGATE_JSON).exists()
    assert (
        main([
            "benchmark", "b003-score-experiment",
            "--source", str(synthetic_shell_chart),
            "--edition", EDITION,
            "--dir", str(experiment_dir),
            "--created-at", CREATED_AT,
        ])
        == 0
    )
    aggregate = json.loads((experiment_dir / SHELL_AGGREGATE_JSON).read_text(encoding="utf-8"))
    assert aggregate["challenge_ids"] == sealed["challenge_ids"]
    assert verify_sha256sums(experiment_dir)["ok"]
