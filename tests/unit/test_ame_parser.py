from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.helpers import write_ame_table

from elementzero.benchmark.b001_prepare import prepare_targets
from elementzero.data.amdc import load_ame2003, load_ame2012, load_ame2016, load_ame2020
from elementzero.data.amdc.ame2003 import EDITION as E2003
from elementzero.data.amdc.ame2012 import EDITION as E2012
from elementzero.data.amdc.ame2016 import EDITION as E2016
from elementzero.data.amdc.ame2020 import EDITION as E2020
from elementzero.data.amdc.common import (
    AME_MAS03_COLUMNS,
    AME_MAS12_COLUMNS,
    AME_MAS16_COLUMNS,
    AME_MAS20_COLUMNS,
    EditionSpec,
    _parse_ame_number,
    format_ame_line,
    parse_ame_line,
    parse_ame_mass_table_detailed,
)
from elementzero.data.observations import (
    RECORD_STATUS_DIRECT_MEASUREMENT,
    RECORD_STATUS_EVALUATED_ESTIMATED,
    RECORD_STATUS_EVALUATED_NON_ESTIMATED,
    RECORD_STATUS_EXTRAPOLATED,
)
from elementzero.evidence.hashing import sha256_hex

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "amdc"


def _assert_golden(stem: str, loader) -> None:
    path = FIXTURES / f"{stem}_golden.txt"
    expected = json.loads((FIXTURES / f"{stem}_golden.expected.json").read_text())
    rows = loader(path)
    assert len(rows) == len(expected)
    for obs, exp in zip(rows, expected, strict=True):
        assert obs.Z == exp["Z"]
        assert obs.N == exp["N"]
        assert obs.A == exp["A"]
        assert obs.element_symbol == exp["element_symbol"]
        assert abs(obs.mass_excess_keV - exp["mass_excess_keV"]) < 1e-12
        assert abs(obs.uncertainty_keV - exp["uncertainty_keV"]) < 1e-12
        assert obs.estimated_mass is exp["estimated_mass"]
        assert obs.estimated_uncertainty is exp["estimated_uncertainty"]
        assert obs.source_origin == exp["source_origin"]
        assert obs.source_record_status == exp["source_record_status"]
        assert obs.ground_truth_eligible is exp["ground_truth_eligible"]


def test_ame2003_golden_rows():
    _assert_golden("ame2003", load_ame2003)


def test_ame2012_golden_rows():
    _assert_golden("ame2012", load_ame2012)


def test_ame2016_golden_rows():
    _assert_golden("ame2016", load_ame2016)


def test_ame2020_golden_rows():
    _assert_golden("ame2020", load_ame2020)


def test_ame2020_wider_mass_columns():
    assert AME_MAS20_COLUMNS.mass_excess == (28, 42)
    assert AME_MAS20_COLUMNS.mass_excess_unc == (42, 54)
    assert AME_MAS03_COLUMNS.mass_excess == (28, 41)
    assert AME_MAS03_COLUMNS is not AME_MAS20_COLUMNS
    assert AME_MAS12_COLUMNS is not AME_MAS20_COLUMNS
    assert AME_MAS16_COLUMNS is not AME_MAS20_COLUMNS
    line = next(
        line
        for line in (FIXTURES / "ame2020_golden.txt").read_text().splitlines()
        if "1 H" in line
    )
    digest = sha256_hex(b"fixture")
    obs_new, _ = parse_ame_line(line, E2020, digest)
    obs_old, reason = parse_ame_line(
        line, EditionSpec("wrong", "x", AME_MAS03_COLUMNS), digest
    )
    assert obs_new is not None
    assert abs(obs_new.mass_excess_keV - 7288.971064) < 1e-12
    assert obs_old is None or abs(obs_old.mass_excess_keV - 7288.971064) > 1e-9
    assert reason in {None, "malformed", "invalid_A"}


def test_estimated_row_not_ground_truth(tmp_path):
    path = write_ame_table(
        tmp_path / "mass.mas20",
        [(100, 150, "Fm", 12345.0, 200.0, True)],
        E2020,
    )
    row = load_ame2020(path)[0]
    assert row.estimated_mass is True
    assert row.ground_truth_eligible is False
    assert row.source_record_status in {
        RECORD_STATUS_EVALUATED_ESTIMATED,
        RECORD_STATUS_EXTRAPOLATED,
    }


def test_non_estimated_ame_row_is_evaluated_not_direct_measurement(tmp_path):
    path = write_ame_table(
        tmp_path / "mass.mas20",
        [(8, 8, "O", -4737.00141, 0.00016, False)],
        E2020,
    )
    row = load_ame2020(path)[0]
    assert row.source_record_status == RECORD_STATUS_EVALUATED_NON_ESTIMATED
    assert row.source_record_status != RECORD_STATUS_DIRECT_MEASUREMENT
    assert row.ground_truth_eligible is True


def test_old_estimated_later_measured_identity_is_target(tmp_path):
    old = write_ame_table(
        tmp_path / "old.mas03",
        [
            (8, 8, "O", -4737.0, 0.1, False),
            (10, 12, "Ne", 100.0, 50.0, True),
        ],
        E2003,
    )
    later = write_ame_table(
        tmp_path / "later.mas20",
        [
            (8, 8, "O", -4737.0, 0.1, False),
            (10, 12, "Ne", 95.0, 1.0, False),
            (18, 19, "X", 10.0, 2.0, False),
        ],
        E2020,
    )
    manifest = prepare_targets(
        later_source=later,
        edition_id="AME2020",
        known_source=old,
        known_edition_id="AME2003",
    )
    ids = {t["nuclide_id"] for t in manifest["targets"]}
    assert "Z10-N12" in ids
    assert "Z8-N8" not in ids
    assert "Z18-N19" in ids


def test_parser_report_counts():
    _rows, report = parse_ame_mass_table_detailed(FIXTURES / "ame2003_golden.txt", E2003)
    d = report.to_dict()
    assert d["edition_id"] == "AME2003"
    assert d["parsed_records"] == 3
    assert d["eligible_records"] == 2
    assert d["estimated_records"] >= 1
    assert d["total_lines"] >= d["parsed_records"]
    assert len(d["raw_source_hash"]) == 64
    assert d["parser_version"]


def test_A_must_equal_Z_plus_N():
    line = format_ame_line(
        n=8, z=8, a=17, el="O", mass_excess_keV=-1.0, uncertainty_keV=1.0, spec=E2003
    )
    obs, reason = parse_ame_line(line, E2003, "a" * 64)
    assert obs is None
    assert reason == "invalid_A"


@pytest.mark.parametrize("edition", [E2003, E2012, E2016, E2020])
def test_round_trip_per_edition(tmp_path, edition):
    path = write_ame_table(
        tmp_path / f"{edition.edition_id}.mas",
        [
            (2, 2, "He", 2424.91561, 0.00015, False),
            (4, 1, "Be", 37000.0, 2000.0, True),
        ],
        edition,
    )
    from elementzero.data.amdc import load_edition

    rows = load_edition(edition.edition_id, str(path))
    by_id = {r.nuclide_id: r for r in rows}
    assert abs(by_id["Z2-N2"].mass_excess_keV - 2424.91561) < 1e-4
    assert by_id["Z2-N2"].ground_truth_eligible is True
    assert by_id["Z4-N1"].ground_truth_eligible is False
    assert by_id["Z4-N1"].estimated_mass is True


def test_hash_replaces_decimal_point_when_parsing():
    value, estimated = _parse_ame_number("123#45")
    assert estimated is True
    assert value == 123.45
    trailing, trailing_estimated = _parse_ame_number("37139#")
    assert trailing_estimated is True
    assert trailing == 37139.0
    measured, measured_estimated = _parse_ame_number("7288.97106")
    assert measured_estimated is False
    assert abs(measured - 7288.97106) < 1e-12


def test_format_line_contains_hash_for_estimated():
    line = format_ame_line(
        n=10,
        z=8,
        a=18,
        el="O",
        mass_excess_keV=873.1,
        uncertainty_keV=5.0,
        estimated=True,
        spec=E2016,
    )
    mass_field = line[E2016.columns.mass_excess[0] : E2016.columns.mass_excess[1]]
    unc_field = line[E2016.columns.mass_excess_unc[0] : E2016.columns.mass_excess_unc[1]]
    assert "#" in mass_field
    assert "." not in mass_field
    assert "#" in unc_field
    assert "." not in unc_field
    obs, reason = parse_ame_line(line, E2016, "a" * 64)
    assert reason is None
    assert obs is not None
    assert obs.estimated_mass is True
    assert obs.estimated_uncertainty is True
    assert abs(obs.mass_excess_keV - 873.1) < 1e-4
    assert abs(obs.uncertainty_keV - 5.0) < 1e-4
