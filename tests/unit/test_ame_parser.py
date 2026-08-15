from tests.helpers import write_ame_table

from elementzero.data.amdc import load_ame2003, load_ame2020
from elementzero.data.amdc.ame2020 import EDITION
from elementzero.data.amdc.common import format_ame_line
from elementzero.data.observations import RECORD_STATUS_ESTIMATED


def test_ame_round_trip_and_estimated_status(tmp_path):
    path = write_ame_table(
        tmp_path / "mass.mas20",
        [
            (8, 8, "O", -4737.00141, 0.00016, False),
            (100, 150, "Fm", 12345.0, 200.0, True),
        ],
        EDITION,
    )
    rows = load_ame2020(path)
    by_id = {r.nuclide_id: r for r in rows}
    assert by_id["Z8-N8"].ground_truth_eligible is True
    assert by_id["Z100-N150"].source_record_status == RECORD_STATUS_ESTIMATED
    assert by_id["Z100-N150"].ground_truth_eligible is False
    assert abs(by_id["Z8-N8"].mass_excess_keV + 4737.00141) < 1e-4


def test_ame2003_adapter(tmp_path):
    from elementzero.data.amdc.ame2003 import EDITION as E2003

    path = write_ame_table(
        tmp_path / "mass.mas03",
        [(2, 2, "He", 2424.91561, 0.00015, False)],
        E2003,
    )
    rows = load_ame2003(path)
    assert rows[0].source_edition == "AME2003"
    assert rows[0].nuclide_id == "Z2-N2"


def test_format_line_contains_hash_for_estimated():
    line = format_ame_line(
        n=10, z=8, a=18, el="O", mass_excess_keV=873.1, uncertainty_keV=5.0, estimated=True
    )
    assert "#" in line
