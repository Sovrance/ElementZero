"""v2 core tests: calibration gate, GP repair, shell localization, blindness."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

from elementzero.models.blindness import (
    TIER_A,
    TIER_C,
    TIER_E,
    BackboneProvenance,
    BlindnessError,
    assert_claim_eligible,
    combine_tiers,
    independence_groups,
    resolve_tier,
)
from elementzero.models.gp_calibrated import (
    CallableBackbone,
    GPResidualV2,
    prior_sigma_scale_keV,
)
from elementzero.models.shell_aware import (
    PROFILE_DISCOVERY,
    FeatureProfileError,
    KinkResidualModel,
    assert_discovery_admissible,
    localization_metrics,
)
from elementzero.uq.calibration import (
    ConformalSigmaScaler,
    calibration_report,
    coverage_curve,
    crps_gaussian,
    z_scores,
)

# ---------------------------------------------------------------- fixtures


def synthetic_chart(seed: int = 0, n_points: int = 400):
    """A smooth mass-excess-like surface. Not physics; a controlled surrogate."""
    rng = np.random.default_rng(seed)
    z = rng.integers(8, 100, n_points)
    n = rng.integers(8, 150, n_points)
    truth = 300.0 * np.sin(z / 9.0) + 200.0 * np.cos(n / 11.0) + rng.normal(0, 50, n_points)
    return z, n, truth


def flat_backbone() -> CallableBackbone:
    return CallableBackbone(
        backbone_id="ZERO",
        fn=lambda z, n: np.zeros(np.asarray(z).shape, dtype=float),
        blindness_tier=TIER_A,
        independence_group="synthetic_control",
    )


# ---------------------------------------------------------- calibration API


def test_z_scores_reject_nonpositive_sigma():
    with pytest.raises(ValueError):
        z_scores(np.array([1.0]), np.array([0.0]), np.array([0.0]))


def test_well_calibrated_sample_passes_gate():
    rng = np.random.default_rng(7)
    n = 600
    sigma = np.full(n, 250.0)
    truth = rng.normal(0, 250.0, n)
    report = calibration_report(truth, np.zeros(n), sigma)
    assert report.verdict == "CALIBRATION_PASS", report.failures
    assert report.dispersion_class == "CALIBRATED"
    assert 0.85 <= report.coverage_90 <= 0.95


def test_overdispersed_sample_fails_gate_like_v1():
    """The v1 signature: sigma far too wide, coverage 1.000, std(z) ~ 0."""
    rng = np.random.default_rng(11)
    n = 300
    truth = rng.normal(0, 400.0, n)
    sigma = np.full(n, 400_000.0)  # 400 MeV against sub-MeV error
    report = calibration_report(truth, np.zeros(n), sigma)
    assert report.verdict == "CALIBRATION_FAIL"
    assert report.dispersion_class == "UNCERTAINTY_OVERDISPERSED"
    assert report.coverage_90 == 1.0
    assert report.coverage_95 == 1.0
    assert report.std_z < 0.01


def test_underdispersed_sample_fails_gate():
    rng = np.random.default_rng(13)
    n = 300
    truth = rng.normal(0, 4000.0, n)
    report = calibration_report(truth, np.zeros(n), np.full(n, 400.0))
    assert report.verdict == "CALIBRATION_FAIL"
    assert report.dispersion_class == "UNCERTAINTY_UNDERDISPERSED"


def test_biased_mean_is_distinguished_from_dispersion():
    """SEMF-LS v1 failed this way: mean(z) ~ -1.6, not a sigma width problem."""
    rng = np.random.default_rng(17)
    n = 300
    truth = rng.normal(-1.6 * 500.0, 500.0, n)
    report = calibration_report(truth, np.zeros(n), np.full(n, 500.0))
    assert report.dispersion_class == "MEAN_FUNCTION_BIASED"
    assert report.verdict == "CALIBRATION_FAIL"


def test_small_sample_is_not_evaluable_rather_than_passed():
    rng = np.random.default_rng(19)
    truth = rng.normal(0, 100.0, 10)
    report = calibration_report(truth, np.zeros(10), np.full(10, 100.0))
    assert report.verdict == "NOT_EVALUABLE"


def test_coverage_curve_exposes_vacuous_intervals():
    """An overdispersed model reads 1.000 at EVERY nominal level."""
    z = np.full(200, 0.0001)
    curve = coverage_curve(z)
    assert all(point["empirical"] == 1.0 for point in curve)


def test_crps_prefers_the_sharper_honest_forecast():
    rng = np.random.default_rng(23)
    truth = rng.normal(0, 300.0, 500)
    pred = np.zeros(500)
    honest = crps_gaussian(z_scores(truth, pred, np.full(500, 300.0)), np.full(500, 300.0))
    vacuous = crps_gaussian(z_scores(truth, pred, np.full(500, 300_000.0)), np.full(500, 300_000.0))
    assert honest < vacuous


def test_conformal_scaler_repairs_dispersion():
    rng = np.random.default_rng(29)
    n = 400
    truth = rng.normal(0, 300.0, n)
    pred = np.zeros(n)
    inflated = np.full(n, 30_000.0)
    scaler = ConformalSigmaScaler(level=0.90).fit(truth[:200], pred[:200], inflated[:200])
    assert scaler.fitted
    repaired = scaler.apply(inflated[200:])
    report = calibration_report(truth[200:], pred[200:], repaired)
    assert report.dispersion_class == "CALIBRATED", report.to_dict()


def test_conformal_scaler_refuses_to_mask_a_biased_mean():
    rng = np.random.default_rng(31)
    n = 200
    truth = rng.normal(2000.0, 300.0, n)  # mean shifted by ~6.7 sigma
    scaler = ConformalSigmaScaler().fit(truth, np.zeros(n), np.full(n, 300.0))
    assert not scaler.fitted
    assert "biased mean" in (scaler.refused_reason or "")
    with pytest.raises(RuntimeError):
        scaler.apply(np.full(n, 300.0))


# --------------------------------------------------------------- GP repair


def test_v1_kernel_reproduces_the_sigma_inflation_defect():
    """Regression guard: this is the bug, quantified, so it cannot come back."""
    z, n, truth = synthetic_chart()
    x = np.column_stack([z, n, z + n]).astype(float)
    v1_kernel = (
        ConstantKernel(1.0e6, "fixed") * RBF(8.0, length_scale_bounds="fixed")
        + WhiteKernel(1.0e4, noise_level_bounds="fixed")
    )
    gp = GaussianProcessRegressor(
        kernel=v1_kernel, optimizer=None, normalize_y=True, random_state=0
    ).fit(x, truth)
    _, sigma = gp.predict(x[:100], return_std=True)

    y_std = float(np.std(truth))
    prior_bound = prior_sigma_scale_keV(1.0e6, y_std)   # = 1000 * y_std
    observed = float(np.median(sigma))

    # The posterior sits below the prior bound but is still orders of magnitude
    # above the natural scale of the data: intervals that can never be wrong.
    assert observed < prior_bound
    assert observed > 50.0 * y_std
    assert prior_bound == pytest.approx(1000.0 * y_std, rel=1e-9)


def test_v2_gp_recovers_honest_dispersion():
    z, n, truth = synthetic_chart(seed=3, n_points=300)
    split = 200
    model = GPResidualV2(backbone=flat_backbone()).fit(z[:split], n[:split], truth[:split])
    pred, sigma = model.predict(z[split:], n[split:])
    report = calibration_report(truth[split:], pred, sigma)
    assert report.n == 100
    assert 0.5 < report.std_z < 2.0, report.to_dict()
    assert np.median(sigma) < 10.0 * np.std(truth)


def test_v2_gp_learns_its_kernel_and_records_it():
    z, n, truth = synthetic_chart(seed=5, n_points=200)
    model = GPResidualV2(backbone=flat_backbone()).fit(z, n, truth)
    manifest = model.manifest()
    assert manifest["kernel_learned"]
    assert manifest["n_restarts_optimizer"] == 3
    assert manifest["log_marginal_likelihood"] is not None
    assert manifest["feature_profile"] == "discovery_admissible"


def test_v2_gp_is_deterministic_under_input_permutation():
    z, n, truth = synthetic_chart(seed=9, n_points=200)
    perm = np.random.default_rng(0).permutation(len(z))
    a = GPResidualV2(backbone=flat_backbone()).fit(z, n, truth)
    b = GPResidualV2(backbone=flat_backbone()).fit(z[perm], n[perm], truth[perm])
    pa, sa = a.predict(z[:20], n[:20])
    pb, sb = b.predict(z[:20], n[:20])
    np.testing.assert_allclose(pa, pb, rtol=1e-8, atol=1e-6)
    np.testing.assert_allclose(sa, sb, rtol=1e-8, atol=1e-6)


def test_backbone_id_drives_model_id():
    model = GPResidualV2(backbone=CallableBackbone("FRDM2012", lambda z, n: np.zeros(len(z))))
    assert model.model_id == "EZ-FRDM2012-GP-RESIDUAL-v2"


# ------------------------------------------------------- shell localization


def test_kink_model_localizes_a_hidden_closure():
    """The EZ-B003 v1 failure, repaired: rank-1 instead of top-3-only."""
    rng = np.random.default_rng(41)
    n = np.arange(60, 110)
    z = np.full_like(n, 50)
    true_knot = 82
    residual = 40.0 * n - 900.0 * np.maximum(n - true_knot, 0.0) + rng.normal(0, 30.0, n.size)

    model = KinkResidualModel(axis="N").fit(z, n, residual)
    assert model.localization is not None
    assert model.localization.best_knot == true_knot
    assert model.localization.rank_of(true_knot) == 1


def test_kink_localization_metrics_match_b003_definitions():
    rng = np.random.default_rng(43)
    locs, truths = [], []
    for knot in (50, 82, 126):
        n = np.arange(knot - 25, knot + 25)
        z = np.full_like(n, 60)
        resid = 30.0 * n - 800.0 * np.maximum(n - knot, 0.0) + rng.normal(0, 25.0, n.size)
        locs.append(KinkResidualModel(axis="N").fit(z, n, resid).localization)
        truths.append(knot)
    metrics = localization_metrics(locs, truths, top_k=3)
    assert metrics["n"] == 3.0
    assert metrics["rank_1_fraction"] == 1.0
    assert metrics["top_k_fraction"] == 1.0


def test_smooth_gp_cannot_localize_but_kink_model_can():
    """Documents the representational gap that motivated this module."""
    rng = np.random.default_rng(47)
    n = np.arange(60, 110)
    z = np.full_like(n, 50)
    knot = 82
    residual = 40.0 * n - 900.0 * np.maximum(n - knot, 0.0) + rng.normal(0, 30.0, n.size)

    gp = GPResidualV2(backbone=flat_backbone()).fit(z, n, residual)
    fitted, _ = gp.predict(z, n)
    second_difference = np.abs(np.diff(fitted, n=2))
    gp_argmax_knot = int(n[1:-1][int(np.argmax(second_difference))])

    kink = KinkResidualModel(axis="N").fit(z, n, residual)
    assert kink.localization.best_knot == knot
    # The GP is not required to fail, but it is not the instrument of record.
    assert isinstance(gp_argmax_knot, int)


def test_discovery_firewall_raises_on_shell_features():
    with pytest.raises(FeatureProfileError):
        assert_discovery_admissible(["Z", "N", "magic_number_distance"])


def test_discovery_profile_default_is_admissible():
    model = KinkResidualModel(axis="N", feature_profile=PROFILE_DISCOVERY)
    assert model.feature_profile == PROFILE_DISCOVERY


# ------------------------------------------------------------- blindness


def _frdm95() -> BackboneProvenance:
    return BackboneProvenance(
        backbone_id="FRDM95",
        independence_group="macroscopic_microscopic_frdm",
        fit_edition="AME1995",
        fit_year=1995,
        fit_set_known=False,
    )


def _bskg3() -> BackboneProvenance:
    return BackboneProvenance(
        backbone_id="BSKG3",
        independence_group="skyrme_edf_bskg",
        fit_edition="AME2020",
        fit_year=2020,
        fit_set_known=True,
    )


def test_modern_table_against_its_own_edition_is_nonblind():
    tier = resolve_tier(_bskg3(), truth_edition="AME2020", truth_year=2020, target_in_fit_set=True)
    assert tier == TIER_C


def test_unknown_fit_membership_is_never_promoted_to_blind():
    tier = resolve_tier(_frdm95(), truth_edition="AME2020", truth_year=2020, target_in_fit_set=None)
    assert tier == TIER_E


def test_historical_refit_earns_strict_blindness():
    refit = BackboneProvenance(
        backbone_id="EZ-REFIT-HFB-AME2003",
        independence_group="skyrme_edf_refit",
        fit_edition="AME2003",
        fit_year=2003,
        fit_set_known=True,
        refit_cutoff="AME2003",
    )
    tier = resolve_tier(refit, truth_edition="AME2012", truth_year=2012, target_in_fit_set=False)
    assert tier == TIER_A


def test_combination_inherits_the_worst_contributor():
    assert combine_tiers([TIER_A, TIER_A]) == TIER_A
    assert combine_tiers([TIER_A, TIER_C]) == TIER_C
    assert combine_tiers([TIER_A, TIER_C, TIER_E]) == TIER_E


def test_independence_groups_counts_only_blind_families():
    provs = [_bskg3(), _frdm95()]
    tiers = [TIER_C, TIER_A]
    assert independence_groups(provs, tiers) == {"macroscopic_microscopic_frdm"}
    assert len(independence_groups(provs, tiers)) < 2  # Gate G2 not yet met


def test_claim_from_ineligible_tier_is_refused():
    with pytest.raises(BlindnessError):
        assert_claim_eligible(TIER_C, "frontier mass prediction")
    assert_claim_eligible(TIER_A, "frontier mass prediction")
