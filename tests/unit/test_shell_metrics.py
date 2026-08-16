"""Discovery diagnostics and the frozen rediscovery criterion (WO-10 6, 9, 10).

The tests build binding surfaces by hand so that the answer is known by
construction: a ramp of size ``g`` in the binding energy puts ``+2g`` in the
indicator at the kink and zero elsewhere in the same parity class. That makes it
possible to check ``sign_recovered`` and ``local_peak_rank`` against a value
nobody had to measure.
"""

from __future__ import annotations

import pytest

from elementzero.benchmark.shell_masks import STATUS_EVALUABLE, STATUS_NOT_EVALUABLE, neutron_mask
from elementzero.benchmark.shell_metrics import (
    HYPOTHESIS_H0,
    HYPOTHESIS_H1,
    MAX_CALIBRATION_ERROR_90,
    MIN_RANK_1_FRACTION,
    MIN_SIGN_FRACTION,
    MIN_TOP_K_FRACTION,
    OUTSIDE_TOP_3,
    RANK_1,
    REDISCOVERY_CRITERION_ID,
    SURFACE_PREDICTION,
    SURFACE_TRUTH,
    TOP_3,
    TOP_K,
    VERDICT_MET,
    VERDICT_NOT_MET,
    VERDICT_NOT_YET_SCORED,
    aggregate_discovery,
    chain_discovery_row,
    closure_discovery_metrics,
    evaluate_criterion,
    hypothesis_resolution,
    hypothesis_statements,
    peak_ranking,
    rediscovery_criterion,
    sign_of,
    sign_recovered,
)
from elementzero.errors import ProtocolError, SchemaError
from elementzero.physics.separation import (
    ORIGIN_PREDICTION,
    ORIGIN_TRAINING_TRUTH,
    ORIGIN_TRUTH,
    BindingSurface,
    delta2n,
)

CLOSURE = 50
GAP_MeV = 1.5
CHAINS = range(24, 31)
COORDINATES = range(40, 61)
MASK = neutron_mask(CLOSURE, z_min=24, z_max=30)


def _smooth(z: int, n: int) -> float:
    """A curved but featureless binding surface, in MeV."""
    return 8.0 * z + 7.0 * n - 0.004 * n * n - 0.003 * z * z


def _truth_surface(gap: float = GAP_MeV) -> BindingSurface:
    values = {
        (z, n): _smooth(z, n) - gap * max(0, n - CLOSURE) for z in CHAINS for n in COORDINATES
    }
    origins = {
        point: ORIGIN_TRUTH if MASK.contains(*point) else ORIGIN_TRAINING_TRUTH
        for point in values
    }
    return BindingSurface(values=values, origins=origins)


def _prediction_surface(*, recovered_fraction: float, gap: float = GAP_MeV) -> BindingSurface:
    """Training truth outside the mask; inside it, a reconstruction.

    ``recovered_fraction`` of the chains get the true value back (a perfect
    rediscovery of that chain); the rest get a smooth interpolation with the kink
    ironed out, which is what a featureless interpolator produces.
    """
    truth = _truth_surface(gap)
    chains = list(CHAINS)
    n_recovered = round(recovered_fraction * len(chains))
    recovered = set(chains[:n_recovered])
    values: dict[tuple[int, int], float] = {}
    origins: dict[tuple[int, int], str] = {}
    for (z, n), value in truth.values.items():
        if not MASK.contains(z, n):
            values[(z, n)] = value
            origins[(z, n)] = ORIGIN_TRAINING_TRUTH
            continue
        origins[(z, n)] = ORIGIN_PREDICTION
        if z in recovered:
            values[(z, n)] = value
        else:
            # Linear interpolation between the two-step neighbors: no curvature,
            # so the indicator at the closure collapses to zero.
            lower = truth.get(z, CLOSURE - 2)
            upper = truth.get(z, CLOSURE + 2)
            values[(z, n)] = lower + (upper - lower) * (n - (CLOSURE - 2)) / 4.0
    return BindingSurface(values=values, origins=origins)


def _rows(*, recovered_fraction: float, gap: float = GAP_MeV):
    truth = _truth_surface(gap)
    prediction = _prediction_surface(recovered_fraction=recovered_fraction, gap=gap)
    return [
        chain_discovery_row(
            mask=MASK, chain=chain, truth_surface=truth, predicted_surface=prediction
        )
        for chain in CHAINS
    ]


# --------------------------------------------------------------------------- #
# Signs                                                                       #
# --------------------------------------------------------------------------- #


def test_sign_of_has_a_noise_floor():
    assert sign_of(2.5) == 1
    assert sign_of(-2.5) == -1
    assert sign_of(0.0) == 0
    assert sign_of(1e-12) == 0
    assert sign_of(None) is None
    assert sign_recovered(1.0, 2.0) is True
    assert sign_recovered(1.0, -2.0) is False
    assert sign_recovered(1.0, 0.0) is False
    assert sign_recovered(None, 1.0) is None
    assert sign_recovered(1.0, None) is None


# --------------------------------------------------------------------------- #
# WO-10 section 6: peak localization                                          #
# --------------------------------------------------------------------------- #


def test_peak_ranking_orders_by_value_and_buckets_the_rank():
    values = {44: 0.1, 46: 0.2, 48: 2.0, 50: 3.0, 52: 0.4}
    ranked = peak_ranking(values, closure=50)
    assert ranked["local_peak_rank"] == 1
    assert ranked["rank_bucket"] == RANK_1
    assert ranked["in_top_k"] is True
    assert ranked["n_candidates"] == 5
    assert [c["coordinate"] for c in ranked["candidates"]] == [50, 48, 52, 46, 44]

    second = peak_ranking({**values, 48: 4.0}, closure=50)
    assert second["local_peak_rank"] == 2
    assert second["rank_bucket"] == TOP_3

    outside = peak_ranking({44: 9.0, 46: 8.0, 48: 7.0, 50: 3.0, 52: 6.0}, closure=50)
    assert outside["local_peak_rank"] == 5
    assert outside["rank_bucket"] == OUTSIDE_TOP_3
    assert outside["in_top_k"] is False

    # A negative indicator that is large in magnitude is not a shell gap, so the
    # primary rank is value-ordered while the magnitude rank is a side note.
    negative = peak_ranking({48: -9.0, 50: 1.0, 52: 0.5}, closure=50)
    assert negative["local_peak_rank"] == 1
    assert negative["local_peak_rank_by_magnitude"] == 2

    absent = peak_ranking(values, closure=51)
    assert absent["local_peak_rank"] is None
    assert absent["rank_bucket"] is None
    assert "no null model is preregistered" in absent["peak_rank_rule"].lower()
    with pytest.raises(ValueError):
        peak_ranking(values, closure=50, top_k=0)


def test_a_recovered_chain_ranks_the_hidden_closure_first():
    truth = _truth_surface()
    perfect = _prediction_surface(recovered_fraction=1.0)
    row = chain_discovery_row(
        mask=MASK, chain=26, truth_surface=truth, predicted_surface=perfect
    )
    assert row["status"] == STATUS_EVALUABLE
    assert row["indicator"] == "delta2n"
    assert row["nuclide_id"] == "Z26-N50"
    # The injected ramp contributes +2g at the closure; the smooth surface adds
    # its own second difference, -0.004 * (2n^2 - (n-2)^2 - (n+2)^2) = +0.032.
    assert row["true_delta2n"] == pytest.approx(2.0 * GAP_MeV + 0.032, abs=1e-6)
    assert row["predicted_delta2n"] == pytest.approx(row["true_delta2n"], abs=1e-9)
    assert row["absolute_delta2n_error"] == pytest.approx(0.0, abs=1e-9)
    assert row["sign_recovered"] is True
    assert row["local_peak_rank"] == 1
    assert row["true_local_peak_rank"] == 1
    assert row["rank_bucket"] == RANK_1
    assert row["derived"] is True and row["independent_evidence"] is False
    assert row["derivation"]["input_origins"] == [
        ORIGIN_TRAINING_TRUTH,
        ORIGIN_PREDICTION,
        ORIGIN_TRAINING_TRUTH,
    ]
    assert row["n_peak_candidates"] >= 3


def test_a_flattened_chain_loses_the_peak_but_is_still_reported():
    truth = _truth_surface()
    flat = _prediction_surface(recovered_fraction=0.0)
    row = chain_discovery_row(mask=MASK, chain=26, truth_surface=truth, predicted_surface=flat)
    assert row["status"] == STATUS_EVALUABLE
    assert row["true_delta2n"] > 2.0
    # Linear interpolation across the mask has no curvature at the closure.
    assert row["predicted_delta2n"] == pytest.approx(0.0, abs=1e-9)
    assert row["sign_recovered"] is False
    assert row["local_peak_rank"] != 1
    assert row["absolute_delta2n_error"] == pytest.approx(row["true_delta2n"], abs=1e-6)


def test_an_incomputable_chain_is_not_evaluable_and_says_why():
    truth = _truth_surface()
    prediction = _prediction_surface(recovered_fraction=1.0)
    row = chain_discovery_row(
        mask=MASK, chain=99, truth_surface=truth, predicted_surface=prediction
    )
    assert row["status"] == STATUS_NOT_EVALUABLE
    assert row["true_delta2n"] is None
    assert row["predicted_delta2n"] is None
    assert row["local_peak_rank"] is None
    assert row["sign_recovered"] is None
    assert any("not computable" in reason for reason in row["reasons"])


# --------------------------------------------------------------------------- #
# Aggregation                                                                 #
# --------------------------------------------------------------------------- #


def test_closure_metrics_aggregate_without_dropping_unevaluable_chains():
    rows = _rows(recovered_fraction=1.0)
    extra = chain_discovery_row(
        mask=MASK,
        chain=99,
        truth_surface=_truth_surface(),
        predicted_surface=_prediction_surface(recovered_fraction=1.0),
    )
    metrics = closure_discovery_metrics([*rows, extra], mask=MASK)
    assert metrics["challenge_id"] == "neutron-N50"
    assert metrics["indicator"] == "delta2n"
    assert metrics["n_chains"] == len(rows) + 1
    assert metrics["n_evaluable_chains"] == len(rows)
    assert metrics["n_not_evaluable_chains"] == 1
    assert metrics["not_evaluable_chains"][0]["chain"] == 99
    assert metrics["sign_recovered_fraction"] == 1.0
    assert metrics["rank_1_fraction"] == 1.0
    assert metrics["top_k_fraction"] == 1.0
    assert metrics["rank_buckets"][RANK_1] == len(rows)
    assert metrics["mean_absolute_indicator_error_MeV"] == pytest.approx(0.0, abs=1e-9)
    assert metrics["derived"] is True and metrics["independent_evidence"] is False
    assert metrics["top_k"] == TOP_K


def test_aggregate_pools_chains_and_names_every_closure():
    good = closure_discovery_metrics(_rows(recovered_fraction=1.0), mask=MASK)
    bad = closure_discovery_metrics(_rows(recovered_fraction=0.0), mask=MASK)
    pooled = aggregate_discovery([good, bad])
    assert pooled["n_closures"] == 2
    assert pooled["n_evaluable_chains"] == good["n_evaluable_chains"] * 2
    assert pooled["sign_recovered_fraction"] == pytest.approx(0.5)
    assert pooled["rank_1_fraction"] == pytest.approx(0.5)
    assert [entry["challenge_id"] for entry in pooled["per_closure"]] == [
        "neutron-N50",
        "neutron-N50",
    ]
    assert pooled["independent_evidence"] is False


# --------------------------------------------------------------------------- #
# WO-10 section 9: the frozen criterion                                       #
# --------------------------------------------------------------------------- #


def test_rediscovery_criterion_is_frozen_and_self_describing():
    criterion = rediscovery_criterion()
    assert criterion["criterion_id"] == REDISCOVERY_CRITERION_ID
    assert criterion["min_sign_fraction"] == MIN_SIGN_FRACTION
    assert criterion["min_top_k_fraction"] == MIN_TOP_K_FRACTION
    assert criterion["min_rank_1_fraction"] == MIN_RANK_1_FRACTION
    assert criterion["max_calibration_error_90"] == MAX_CALIBRATION_ERROR_90
    assert criterion["top_k"] == TOP_K
    assert "Z = 154" in criterion["scope_rule"]
    assert "no null model" in criterion["no_p_value_rule"].lower()
    assert "protocol version" in criterion["no_post_hoc_rule"]
    # Two calls must be identical: the thresholds are constants, not state.
    assert rediscovery_criterion() == criterion


def test_criterion_verdict_needs_every_check_and_records_its_scope():
    perfect = aggregate_discovery([closure_discovery_metrics(_rows(recovered_fraction=1.0), mask=MASK)])
    met = evaluate_criterion(perfect, calibration_error_90=0.02, scope="synthetic")
    assert met["verdict"] == VERDICT_MET
    assert met["scope"] == "synthetic"
    assert all(check["met"] for check in met["checks"].values())

    # Honest shell structure with dishonest uncertainties is not a pass.
    uncalibrated = evaluate_criterion(perfect, calibration_error_90=0.4, scope="synthetic")
    assert uncalibrated["verdict"] == VERDICT_NOT_MET
    assert uncalibrated["checks"]["calibration_error_90"]["met"] is False

    flat = aggregate_discovery([closure_discovery_metrics(_rows(recovered_fraction=0.0), mask=MASK)])
    missed = evaluate_criterion(flat, calibration_error_90=0.02, scope="synthetic")
    assert missed["verdict"] == VERDICT_NOT_MET
    assert missed["checks"]["sign_fraction"]["met"] is False

    # Nothing evaluable means "not yet scored", never a silent pass or fail.
    empty = aggregate_discovery([closure_discovery_metrics([], mask=MASK)])
    unscored = evaluate_criterion(empty, calibration_error_90=None, scope="AME2020")
    assert unscored["verdict"] == VERDICT_NOT_YET_SCORED

    with pytest.raises(SchemaError):
        evaluate_criterion(perfect, calibration_error_90=0.02, scope="")
    with pytest.raises(ProtocolError):
        evaluate_criterion(
            perfect,
            calibration_error_90=0.02,
            scope="synthetic",
            criterion={**rediscovery_criterion(), "criterion_id": "ez-b003-looser-v2"},
        )


# --------------------------------------------------------------------------- #
# WO-10 section 10: H0 / H1 bookkeeping                                       #
# --------------------------------------------------------------------------- #


def test_hypothesis_statements_name_the_two_structures():
    statements = hypothesis_statements(indicator="delta2n", closure_label="N = 50")
    assert set(statements) == {HYPOTHESIS_H0, HYPOTHESIS_H1}
    assert "no local shell discontinuity at N = 50" in statements[HYPOTHESIS_H0]
    assert "a local shell discontinuity at N = 50" in statements[HYPOTHESIS_H1]
    assert "delta2n" in statements[HYPOTHESIS_H1]


def test_hypothesis_resolution_needs_a_majority_of_chains():
    recovered = _rows(recovered_fraction=1.0)
    predicted = hypothesis_resolution(
        recovered, indicator="delta2n", surface=SURFACE_PREDICTION
    )
    assert predicted["selected_label"] == HYPOTHESIS_H1
    assert predicted["fraction_supporting_H1"] == 1.0
    # The truth surface carries the injected closure, so it selects H1 too. That
    # restates the chart; the prediction resolution is the benchmark question.
    truth = hypothesis_resolution(recovered, indicator="delta2n", surface=SURFACE_TRUTH)
    assert truth["selected_label"] == HYPOTHESIS_H1

    flat = _rows(recovered_fraction=0.0)
    flattened = hypothesis_resolution(flat, indicator="delta2n", surface=SURFACE_PREDICTION)
    # A flattened reconstruction puts the indicator at zero, which is H0.
    assert flattened["selected_label"] == HYPOTHESIS_H0
    assert flattened["fraction_supporting_H0"] == 1.0
    assert hypothesis_resolution(flat, indicator="delta2n", surface=SURFACE_TRUTH)[
        "selected_label"
    ] == HYPOTHESIS_H1

    # No evaluable chain, no selection.
    undecided = hypothesis_resolution([], indicator="delta2n")
    assert undecided["selected_label"] is None
    assert undecided["n_evaluable_chains"] == 0
    with pytest.raises(SchemaError):
        hypothesis_resolution(recovered, indicator="delta2n", surface="vibes")


# --------------------------------------------------------------------------- #
# Reproducibility                                                             #
# --------------------------------------------------------------------------- #


def test_shell_metrics_reproducible():
    """The same surfaces must produce the same rows, values, and ranks.

    Every function in ``shell_metrics`` is pure, so recomputing from freshly
    built surfaces has to reproduce the previous result exactly, including float
    equality: any dependence on iteration order, dict insertion order, or a
    cached surface would break here.
    """
    first_rows = _rows(recovered_fraction=0.5)
    second_rows = _rows(recovered_fraction=0.5)
    assert first_rows == second_rows

    first = closure_discovery_metrics(first_rows, mask=MASK)
    second = closure_discovery_metrics(second_rows, mask=MASK)
    assert first == second
    assert aggregate_discovery([first]) == aggregate_discovery([second])
    assert evaluate_criterion(
        aggregate_discovery([first]), calibration_error_90=0.05, scope="synthetic"
    ) == evaluate_criterion(
        aggregate_discovery([second]), calibration_error_90=0.05, scope="synthetic"
    )
    assert hypothesis_resolution(first_rows, indicator="delta2n") == hypothesis_resolution(
        second_rows, indicator="delta2n"
    )

    # And the values are the ones the definition gives, recomputed independently.
    truth = _truth_surface()
    for row in first_rows:
        expected = delta2n(truth, z=row["chain"], n=CLOSURE)
        assert row["true_delta2n"] == pytest.approx(expected, abs=1e-12)
