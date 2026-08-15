import pytest

from elementzero.data.identity import NuclideIdentity, nuclide_id, parse_nuclide_id, validate_a


def test_canonical_nuclide_id():
    assert nuclide_id(82, 126) == "Z82-N126"
    assert parse_nuclide_id("Z82-N126") == (82, 126)
    ident = NuclideIdentity.from_zn(2, 2)
    assert ident.A == 4
    assert ident.to_dict()["nuclide_id"] == "Z2-N2"


def test_a_equals_z_plus_n():
    validate_a(8, 8, 16)
    with pytest.raises(ValueError):
        validate_a(8, 8, 17)
