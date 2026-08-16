import pytest
from tests.helpers import toy_mass_excess

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.models.gp_residual import (
    MODEL_ID_GP_DIRECT,
    MODEL_ID_SEMF_GP,
    MODEL_ID_SEMF_LS,
    SEMFGPResidualModel,
    build_model,
)
from elementzero.models.model_manifest import model_manifest
from elementzero.models.protocol import (
    MIN_PREDICTIVE_STD_KEV,
    UNCERTAINTY_METHOD_GP_RETURN_STD,
    UNCERTAINTY_METHOD_TRAINING_RESIDUAL_STD,
)

SUITE = (MODEL_ID_SEMF_LS, MODEL_ID_GP_DIRECT, MODEL_ID_SEMF_GP)


def _obs(z: int, n: int) -> MassObservation:
    return MassObservation(
        nuclide=NuclideIdentity.from_zn(z, n),
        mass_excess_keV=toy_mass_excess(z, n, noise=0.05 * z),
        uncertainty_keV=10.0,
        source_edition="AME2003",
        source_release_date="2003-12-22",
        source_record_status="evaluated_non_estimated",
        raw_source_hash="cd" * 32,
    )


def _train():
    return [_obs(z, z) for z in range(8, 18)]


def test_gp_residual_predicts():
    model = SEMFGPResidualModel()
    model.fit(_train())
    pred = model.predict(NuclideIdentity.from_zn(18, 19))
    assert pred.model_id == MODEL_ID_SEMF_GP
    assert "p90" in pred.intervals
    assert model.manifest()["features"] == ["Z", "N", "A"]


@pytest.mark.parametrize("model_id", SUITE)
def test_prediction_serializes_std(model_id):
    model = build_model(model_id)
    model.fit(_train())
    pred = model.predict(NuclideIdentity.from_zn(18, 19))
    payload = pred.to_dict()
    assert payload["std_keV"] == pred.std_keV
    assert payload["std_keV"] >= MIN_PREDICTIVE_STD_KEV
    assert payload["predictive_distribution"] == "gaussian"
    assert payload["uncertainty_method"]
    # Reported intervals are exactly the Gaussian quantiles of mu and sigma.
    mu, sigma = payload["mass_excess_keV"], payload["std_keV"]
    assert payload["intervals"]["p90"] == [
        pytest.approx(mu - 1.6448536269514722 * sigma),
        pytest.approx(mu + 1.6448536269514722 * sigma),
    ]
    assert payload["intervals"]["p95"] == [
        pytest.approx(mu - 1.959963984540054 * sigma),
        pytest.approx(mu + 1.959963984540054 * sigma),
    ]


@pytest.mark.parametrize(
    ("model_id", "method"),
    [
        (MODEL_ID_SEMF_LS, UNCERTAINTY_METHOD_TRAINING_RESIDUAL_STD),
        (MODEL_ID_GP_DIRECT, UNCERTAINTY_METHOD_GP_RETURN_STD),
        (MODEL_ID_SEMF_GP, UNCERTAINTY_METHOD_GP_RETURN_STD),
    ],
)
def test_every_model_manifest_states_its_uncertainty_method(model_id, method):
    model = build_model(model_id)
    model.fit(_train())
    payload = model.manifest()
    assert payload["uncertainty_method"] == method
    assert payload["predictive_distribution"] == "gaussian"
    manifest = model_manifest(
        model_id=model_id,
        model_payload=payload,
        freeze_id="frz",
        feature_policy_id="ez-b001-identity-zn-v1",
    )
    assert manifest["uncertainty_method"] == method
    assert model.predict(NuclideIdentity.from_zn(18, 19)).uncertainty_method == method


def test_semf_least_squares_sigma_is_the_training_residual_std():
    model = build_model(MODEL_ID_SEMF_LS)
    model.fit(_train())
    pred = model.predict(NuclideIdentity.from_zn(18, 19))
    assert pred.std_keV == pytest.approx(model.residual_std)
    assert model.manifest()["residual_std_keV"] == pytest.approx(model.residual_std)


def test_model_manifest_without_uncertainty_method_is_rejected():
    with pytest.raises(ValueError):
        model_manifest(
            model_id="EZ-SEMF-LS-v1",
            model_payload={"model_id": "EZ-SEMF-LS-v1"},
            freeze_id="frz",
            feature_policy_id="ez-b001-identity-zn-v1",
        )
