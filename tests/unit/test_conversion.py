from elementzero.physics.conversion import binding_energy_MeV, mass_excess_keV_from_binding


def test_mass_binding_round_trip():
    z, n = 26, 30
    original = -26103.0
    binding = binding_energy_MeV(z=z, n=n, mass_excess_keV=original)
    back = mass_excess_keV_from_binding(z=z, n=n, binding_MeV=binding)
    assert abs(back - original) < 1e-8
