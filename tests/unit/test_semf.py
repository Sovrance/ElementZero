from tests.helpers import toy_mass_excess

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.physics.semf import fit_semf, mass_excess_keV, pairing_sign


def test_pairing_sign():
    assert pairing_sign(8, 8) == 1
    assert pairing_sign(7, 7) == -1
    assert pairing_sign(8, 7) == 0


def test_semf_recovers_toy_masses():
    obs = []
    for z in range(8, 20):
        n = z
        obs.append(
            MassObservation(
                nuclide=NuclideIdentity.from_zn(z, n),
                mass_excess_keV=toy_mass_excess(z, n),
                uncertainty_keV=10.0,
                source_edition="AME2003",
                source_release_date="2003-12-22",
                source_record_status="evaluated_non_estimated",
                raw_source_hash="0" * 64,
            )
        )
    coeffs = fit_semf(obs)
    err = [abs(mass_excess_keV(o.Z, o.N, coeffs) - o.mass_excess_keV) for o in obs]
    assert max(err) < 1.0
