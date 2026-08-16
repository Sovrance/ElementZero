"""Golden-row and integrity validation for external model tables.

Two layers:

    golden fixtures   small verbatim excerpts of the public tables, committed
                      with expected canonical values. They pin the parser: a
                      format drift or a broken conversion fails here without
                      needing the full raw file.

    full-table audit  when the raw file is present (fetched by
                      tools/fetch_model_tables.py), its sha256 must equal the
                      manifest hash and the parse must cover the golden rows
                      with identical values.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.model_tables.manifests import (
    source_manifest,
    table_available,
    table_path,
)
from elementzero.data.model_tables.parser import (
    ParsedTable,
    parse_bskg_table,
    parse_frdm_ripl_table,
)
from elementzero.errors import SchemaError
from elementzero.evidence.hashing import sha256_file

GOLDEN_EXPECTED_RELPATH = "tests/fixtures/model_tables/golden_expected.json"

_PARSERS = {
    "BSKG3": parse_bskg_table,
    "FRDM95": parse_frdm_ripl_table,
}


def load_golden_expectations(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root or REPO_ROOT)
    return json.loads((root / GOLDEN_EXPECTED_RELPATH).read_text(encoding="utf-8"))


def parse_table(table_id: str, path: str | Path) -> ParsedTable:
    if table_id not in _PARSERS:
        raise SchemaError(f"no parser is registered for table {table_id!r}")
    return _PARSERS[table_id](path, table_id=table_id)


def validate_golden_rows(table_id: str, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Parse the committed golden fixture and compare exact canonical values."""
    root = Path(repo_root or REPO_ROOT)
    expected = load_golden_expectations(repo_root=root)[table_id]
    parsed = parse_table(table_id, root / expected["golden_file"])
    mismatches = []
    for nuclide_id, want in sorted(expected["rows"].items()):
        row = parsed.get(want["Z"], want["N"])
        if row is None:
            mismatches.append({"nuclide_id": nuclide_id, "error": "missing from parse"})
            continue
        if row.A != want["A"] or row.mass_excess_keV != want["mass_excess_keV"]:
            mismatches.append(
                {
                    "nuclide_id": nuclide_id,
                    "expected_mass_excess_keV": want["mass_excess_keV"],
                    "parsed_mass_excess_keV": row.mass_excess_keV,
                }
            )
            continue
        want_dev = want["experimental_minus_calculated_keV"]
        got_dev = row.experimental_minus_calculated_keV
        if want_dev is None:
            if got_dev is not None:
                mismatches.append({"nuclide_id": nuclide_id, "error": "unexpected deviation"})
        elif got_dev is None or abs(got_dev - want_dev) > 1.0e-6:
            mismatches.append(
                {
                    "nuclide_id": nuclide_id,
                    "expected_deviation_keV": want_dev,
                    "parsed_deviation_keV": got_dev,
                }
            )
    return {
        "table_id": table_id,
        "golden_file": expected["golden_file"],
        "n_golden_rows": len(expected["rows"]),
        "mismatches": mismatches,
        "ok": not mismatches,
    }


def validate_full_table(table_id: str, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Hash + parse + golden-value audit of the raw file when present."""
    root = Path(repo_root or REPO_ROOT)
    manifest = source_manifest(table_id)
    path = table_path(table_id, repo_root=root)
    if not table_available(table_id, repo_root=root):
        return {
            "table_id": table_id,
            "status": "ABSENT",
            "note": (
                f"raw table not present or hash mismatch at {path}; run "
                "tools/fetch_model_tables.py"
            ),
        }
    parsed = parse_table(table_id, path)
    expected = load_golden_expectations(repo_root=root)[table_id]
    mismatches = []
    for nuclide_id, want in sorted(expected["rows"].items()):
        row = parsed.get(want["Z"], want["N"])
        if row is None or row.mass_excess_keV != want["mass_excess_keV"]:
            mismatches.append(nuclide_id)
    return {
        "table_id": table_id,
        "status": "OK" if not mismatches else "GOLDEN_MISMATCH",
        "raw_sha256": sha256_file(path),
        "manifest_sha256": manifest["raw_sha256"],
        "n_rows": parsed.n_rows,
        "empirical_rms_keV": parsed.empirical_rms_keV,
        "golden_mismatches": mismatches,
    }
