import pir

from elementzero import __atlas_pir_contract__
from elementzero.atlas_pin import assert_pin_consistent
from elementzero.evidence.atlas_adapter import PUBLIC_PIR_SYMBOLS


def test_pir_version_is_supported():
    assert pir.__version__ == __atlas_pir_contract__
    assert pir.__version__ in {"0.1.0"}


def test_public_symbols_exist():
    for name in PUBLIC_PIR_SYMBOLS:
        assert hasattr(pir, name), name


def test_pin_is_immutable_and_consistent():
    ref = assert_pin_consistent()
    assert len(ref) == 40
    assert ref != "main"
