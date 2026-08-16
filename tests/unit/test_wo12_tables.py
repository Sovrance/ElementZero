"""WO-12 external-table parsers, manifests, hashes, and the shared conversion."""

from __future__ import annotations

import json

import pytest

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.model_tables.manifests import (
    MANIFEST_REQUIRED_FIELDS,
    REGISTERED_TABLES,
    STATUS_APPROVED,
    source_manifest,
    table_available,
)
from elementzero.data.model_tables.parser import (
    parse_bskg_table,
    parse_frdm_ripl_table,
    table_value_to_mass_excess_keV,
)
from elementzero.data.model_tables.validation import (
    validate_full_table,
    validate_golden_rows,
)

GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "model_tables"


def test_bskg5_golden_rows():
    """BSkG-family parser against committed public golden rows.

    The preferred BSkG5 table is BLOCKED_AVAILABILITY (see manifests); the
    family adapter parses the BRUSLIB series layout, pinned here on BSkG3
    golden rows including O-16 and 208Pb.
    """
    report = validate_golden_rows("BSKG3")
    assert report["ok"], report["mismatches"]
    parsed = parse_bskg_table(GOLDEN_DIR / "bskg03_golden.txt")
    pb208 = parsed.get(82, 126)
    assert pb208.mass_excess_keV == -23390.0
    assert pb208.experimental_minus_calculated_keV == 1640.0


def test_frdm2012_golden_rows():
    """FRDM-family parser against committed public golden rows.

    FRDM2012's canonical host is unreachable (see manifests); the family
    adapter parses the RIPL-3 FRDM95 layout, pinned here on golden rows
    including the blank-Mexp Hf-197 record and 208Pb (Mth = -21.150 MeV).
    """
    report = validate_golden_rows("FRDM95")
    assert report["ok"], report["mismatches"]
    parsed = parse_frdm_ripl_table(GOLDEN_DIR / "mass-frdm95_golden.txt")
    pb208 = parsed.get(82, 126)
    assert pb208.mass_excess_keV == -21150.0
    hf197 = parsed.get(72, 125)
    assert hf197.experimental_minus_calculated_keV is None


def test_table_hashes_recorded():
    for table_id in sorted(REGISTERED_TABLES):
        manifest = source_manifest(table_id)
        for field in MANIFEST_REQUIRED_FIELDS:
            assert field in manifest, (table_id, field)
        if manifest["license_status"] == STATUS_APPROVED:
            assert manifest["raw_sha256"], f"{table_id} is APPROVED without a pinned hash"
    review = json.loads(
        (
            REPO_ROOT / "reports" / "model_federation" / "wo12" / "license_availability_review.json"
        ).read_text(encoding="utf-8")
    )
    for table_id in ("BSKG3", "FRDM95"):
        assert review["tables"][table_id]["raw_sha256"] == source_manifest(table_id)["raw_sha256"]


def test_mass_conversion_shared():
    """One audited conversion layer; adapters do no local mass arithmetic."""
    assert table_value_to_mass_excess_keV(-4.51) == -4510.0
    assert table_value_to_mass_excess_keV(0.0) == 0.0
    # Both parsers route every value through the shared function: the golden
    # keV values are exactly the published MeV values times 1000.
    bskg = parse_bskg_table(GOLDEN_DIR / "bskg03_golden.txt")
    assert bskg.get(8, 8).mass_excess_keV == -4.51 * 1000.0
    frdm = parse_frdm_ripl_table(GOLDEN_DIR / "mass-frdm95_golden.txt")
    assert frdm.get(8, 8).mass_excess_keV == -4.84 * 1000.0


@pytest.mark.skipif(
    not (table_available("BSKG3") and table_available("FRDM95")),
    reason="raw model tables not fetched (tools/fetch_model_tables.py)",
)
def test_full_tables_verify_against_manifest_hashes():
    for table_id in ("BSKG3", "FRDM95"):
        report = validate_full_table(table_id)
        assert report["status"] == "OK", report
