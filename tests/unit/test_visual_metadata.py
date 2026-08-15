from elementzero.errors import VisualError
from elementzero.visuals.metadata import load_element_metadata, metadata_for


def test_element_metadata_has_1_to_200():
    records = load_element_metadata()
    assert set(records) == set(range(1, 201))
    assert records[1]["symbol"] == "H"
    assert records[1]["name"] == "Hydrogen"
    assert records[1]["known_status"] == "known_element"
    assert records[26]["symbol"] == "Fe"
    assert records[118]["symbol"] == "Og"
    assert records[119]["symbol"] == "E119"
    assert records[119]["name"] == "Element 119"
    assert records[119]["known_status"] == "unknown_element"
    assert records[200]["symbol"] == "E200"


def test_missing_element_metadata_rejected():
    try:
        metadata_for(0)
    except VisualError as exc:
        assert "missing" in str(exc).lower() or "Z=0" in str(exc)
    else:
        raise AssertionError("expected VisualError for missing metadata")
    try:
        metadata_for(201)
    except VisualError:
        return
    raise AssertionError("expected VisualError for Z=201")
