from tests.helpers import toy_mass_excess

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.models.gp_residual import SEMFGPResidualModel


def _obs(z: int, n: int) -> MassObservation:
    return MassObservation(
        nuclide=NuclideIdentity.from_zn(z, n),
        mass_excess_keV=toy_mass_excess(z, n, noise=0.05 * z),
        uncertainty_keV=10.0,
        source_edition="AME2003",
        source_release_date="2003-12-22",
        source_record_status="experimental",
        raw_source_hash="cd" * 32,
    )


def test_gp_residual_predicts():
    model = SEMFGPResidualModel()
    train = [_obs(z, z) for z in range(8, 18)]
    model.fit(train)
    pred = model.predict(NuclideIdentity.from_zn(18, 19))
    assert pred.model_id == "EZ-SEMF-GP-RESIDUAL-v1"
    assert "p90" in pred.intervals
    assert model.manifest()["features"] == ["Z", "N", "A"]
