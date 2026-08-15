from elementzero.visuals import LAYOUT_EXTENDED_200, LAYOUT_STANDARD_118
from elementzero.visuals.metadata import load_layout, position_for


def test_standard_layout_positions_known_elements():
    layout = load_layout(LAYOUT_STANDARD_118)
    assert layout["layout_profile"] == LAYOUT_STANDARD_118
    assert set(layout["positions"]) == set(range(1, 119))
    assert position_for(1, LAYOUT_STANDARD_118) == {"row": 1, "column": 1}
    assert position_for(2, LAYOUT_STANDARD_118) == {"row": 1, "column": 18}
    assert position_for(26, LAYOUT_STANDARD_118) == {"row": 4, "column": 8}
    assert position_for(57, LAYOUT_STANDARD_118) == {"row": 8, "column": 3}
    assert position_for(72, LAYOUT_STANDARD_118) == {"row": 6, "column": 4}
    assert position_for(118, LAYOUT_STANDARD_118) == {"row": 7, "column": 18}


def test_extended_layout_has_positions_1_to_200():
    layout = load_layout(LAYOUT_EXTENDED_200)
    assert set(layout["positions"]) == set(range(1, 201))
    assert "not official IUPAC" in layout["disclaimer"]
    assert position_for(119, LAYOUT_EXTENDED_200) == {"row": 10, "column": 1}
    assert position_for(200, LAYOUT_EXTENDED_200) == {"row": 14, "column": 10}
    # standard_118 still supplies coordinates for the required 200-row state
    assert position_for(120, LAYOUT_STANDARD_118)["row"] >= 10
