"""Source manifests and the license/availability gate for external tables.

Every imported physics table records the WO-12 section 6 fields. The raw
files live under ``data/model_tables/`` (gitignored, like the AME tables);
the manifests, hashes, golden fixtures, and parsers are committed.

Availability in this work order, with the documented fallback ladders:

    Brussels Skyrme-EDF family (skyrme_edf_bskg)
        BSkG5   preferred — publication table not retrievable (no public
                machine-readable host reachable): BLOCKED_AVAILABILITY
        BSkG4   fallback — arXiv source carries no ancillary table, EPJA
                supplementary unreachable: BLOCKED_AVAILABILITY
        BSkG3   approved family representative — publicly hosted on BRUSLIB
                for redistribution as part of the Brussels nuclear library

    FRDM family (macroscopic_microscopic_frdm)
        FRDM2012  preferred — canonical LANL T2 host unreachable from every
                  tested egress, ADNDT supplementary is paywalled:
                  BLOCKED_AVAILABILITY
        FRDM95    approved family representative — publicly distributed by
                  the IAEA in RIPL-3

    DRHBc (relativistic_edf_drhbc)
        optional — mass-table host unreachable: BLOCKED_AVAILABILITY; WO-12
        completion is explicitly not blocked on it (section 9).

A blocked table cannot participate in a frozen v2 protocol (section 24); the
registry enforces that gate at registration time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.model_tables.parser import MODEL_TABLE_PARSER_VERSION
from elementzero.errors import SchemaError
from elementzero.evidence.hashing import sha256_file

TABLES_RELPATH = "data/model_tables"

STATUS_APPROVED = "APPROVED"
STATUS_APPROVED_REFERENCE_ONLY = "APPROVED_REFERENCE_ONLY"
STATUS_BLOCKED_LICENSE = "BLOCKED_LICENSE"
STATUS_BLOCKED_AVAILABILITY = "BLOCKED_AVAILABILITY"
STATUS_BLOCKED_REPRODUCIBILITY = "BLOCKED_REPRODUCIBILITY"

ALLOWED_LICENSE_STATUSES = (
    STATUS_APPROVED,
    STATUS_APPROVED_REFERENCE_ONLY,
    STATUS_BLOCKED_LICENSE,
    STATUS_BLOCKED_AVAILABILITY,
    STATUS_BLOCKED_REPRODUCIBILITY,
)

MANIFEST_REQUIRED_FIELDS = (
    "source_url",
    "publication",
    "publication_doi",
    "raw_sha256",
    "parser_version",
    "table_version",
    "model_id",
    "observables",
    "units",
    "license_status",
)

# Pinned hashes of the raw tables as acquired for WO-12. The fetch tool
# re-downloads and refuses a file whose hash moved.
BSKG3_SHA256 = "6caff2762ea1ce8deb3707ac16d286bdb084ea97fdf084d5783a157fb20543b6"
FRDM95_SHA256 = "3ac1c1777031cde8cd6848de78c780205d8c5103070ba38c6723d098ee7e518b"

REGISTERED_TABLES: dict[str, dict[str, Any]] = {
    "BSKG3": {
        "source_url": "https://www.astro.ulb.ac.be/bruslib/nucdata/bskg03-dat",
        "publication": (
            "G. Grams, W. Ryssens, G. Scamps, S. Goriely, N. Chamel, "
            "Skyrme-Hartree-Fock-Bogoliubov mass models on a 3D mesh: III. "
            "From atomic nuclei to neutron stars, Eur. Phys. J. A 59, 270 "
            "(2023); table publicly distributed via BRUSLIB"
        ),
        "publication_doi": "https://doi.org/10.1140/epja/s10050-023-01158-6",
        "raw_sha256": BSKG3_SHA256,
        "parser_version": MODEL_TABLE_PARSER_VERSION,
        "table_version": "bskg03-dat (BRUSLIB)",
        "model_id": "EZ-BSKG3-TABLE-v1",
        "observables": ["atomic_mass_excess_keV"],
        "units": "table MeV -> canonical keV via the shared conversion layer",
        "license_status": STATUS_APPROVED,
        "license_note": (
            "Publicly hosted on BRUSLIB (Brussels Nuclear Library for "
            "Astrophysics Applications) for scientific use with citation. The "
            "raw file stays gitignored; the repository commits its hash, this "
            "manifest, and small quoted golden rows."
        ),
        "filename": "bskg03.dat",
        "family": "bskg",
        "independence_group": "skyrme_edf_bskg",
        "fallback_for": ["BSKG5", "BSKG4"],
    },
    "FRDM95": {
        "source_url": "https://www-nds.iaea.org/RIPL-3/masses/mass-frdm95.dat",
        "publication": (
            "P. Moller, J.R. Nix, W.D. Myers, W.J. Swiatecki, Nuclear "
            "ground-state masses and deformations, At. Data Nucl. Data "
            "Tables 59, 185 (1995); RIPL-3 distribution by the IAEA"
        ),
        "publication_doi": "https://doi.org/10.1006/adnd.1995.1002",
        "raw_sha256": FRDM95_SHA256,
        "parser_version": MODEL_TABLE_PARSER_VERSION,
        "table_version": "mass-frdm95.dat (RIPL-3, 2007-12-10)",
        "model_id": "EZ-FRDM95-TABLE-v1",
        "observables": ["atomic_mass_excess_keV"],
        "units": "table MeV -> canonical keV via the shared conversion layer",
        "license_status": STATUS_APPROVED,
        "license_note": (
            "Distributed by the IAEA Nuclear Data Section as part of RIPL-3 "
            "for scientific use with citation. Raw file gitignored; hash, "
            "manifest, and golden rows committed."
        ),
        "filename": "mass-frdm95.dat",
        "family": "frdm",
        "independence_group": "macroscopic_microscopic_frdm",
        "fallback_for": ["FRDM2012"],
    },
    "BSKG5": {
        "source_url": "https://doi.org/10.1016/j.physletb.2026.140590",
        "publication": (
            "G. Grams et al., Skyrme-Hartree-Fock-Bogoliubov mass models on a "
            "3D mesh: V. The N2LO extension of the Skyrme EDF, Phys. Lett. B "
            "(2026)"
        ),
        "publication_doi": "https://doi.org/10.1016/j.physletb.2026.140590",
        "raw_sha256": None,
        "parser_version": MODEL_TABLE_PARSER_VERSION,
        "table_version": "not acquired",
        "model_id": "EZ-BSKG5-TABLE-v1",
        "observables": ["atomic_mass_excess_keV"],
        "units": "table MeV -> canonical keV via the shared conversion layer",
        "license_status": STATUS_BLOCKED_AVAILABILITY,
        "license_note": (
            "Preferred backbone. No public machine-readable table reachable: "
            "BRUSLIB hosts the series only through bskg03-dat, and the "
            "publisher supplementary is not openly retrievable. Import path: "
            "place the published table under data/model_tables/ and record "
            "its sha256 here; the BSkG-series parser already reads the "
            "BRUSLIB column layout."
        ),
        "filename": "bskg05.dat",
        "family": "bskg",
        "independence_group": "skyrme_edf_bskg",
        "fallback_for": [],
    },
    "FRDM2012": {
        "source_url": "https://t2.lanl.gov/nis/molleretal/publications/ADNDT-FRDM2012.html",
        "publication": (
            "P. Moller, A.J. Sierk, T. Ichikawa, H. Sagawa, Nuclear "
            "ground-state masses and deformations: FRDM(2012), At. Data "
            "Nucl. Data Tables 109-110, 1 (2016)"
        ),
        "publication_doi": "https://doi.org/10.1016/j.adt.2015.10.002",
        "raw_sha256": None,
        "parser_version": MODEL_TABLE_PARSER_VERSION,
        "table_version": "not acquired",
        "model_id": "EZ-FRDM2012-TABLE-v1",
        "observables": ["atomic_mass_excess_keV"],
        "units": "table MeV -> canonical keV via the shared conversion layer",
        "license_status": STATUS_BLOCKED_AVAILABILITY,
        "license_note": (
            "Preferred backbone. The canonical LANL T2 host is unreachable "
            "from every tested egress (connection refused / 503) and the "
            "ADNDT supplementary is paywalled. Import path: download "
            "ADNDT-FRDM2012-TABLE.dat when the host recovers, place it under "
            "data/model_tables/, record its sha256 here, and extend the "
            "parser with the published (3I5,4F10.2,4F10.3,5F10.2,F10.3,"
            "2F10.2) layout."
        ),
        "filename": "ADNDT-FRDM2012-TABLE.dat",
        "family": "frdm",
        "independence_group": "macroscopic_microscopic_frdm",
        "fallback_for": [],
    },
    "DRHBC": {
        "source_url": "http://drhbcmasstable.pku.edu.cn",
        "publication": (
            "K. Zhang et al. (DRHBc Mass Table Collaboration), Nuclear mass "
            "table in deformed relativistic Hartree-Bogoliubov theory in "
            "continuum, arXiv:2201.03216"
        ),
        "publication_doi": "https://arxiv.org/abs/2201.03216",
        "raw_sha256": None,
        "parser_version": MODEL_TABLE_PARSER_VERSION,
        "table_version": "not acquired",
        "model_id": "EZ-DRHBC-TABLE-v1",
        "observables": ["atomic_mass_excess_keV"],
        "units": "table MeV -> canonical keV via the shared conversion layer",
        "license_status": STATUS_BLOCKED_AVAILABILITY,
        "license_note": (
            "Optional third family (WO-12 section 9): host unreachable in "
            "this environment. WO-12 completion is not blocked on it."
        ),
        "filename": "drhbc.dat",
        "family": "drhbc",
        "independence_group": "relativistic_edf_drhbc",
        "fallback_for": [],
    },
}


def source_manifest(table_id: str) -> dict[str, Any]:
    """The committed manifest for one registered table, field-validated."""
    if table_id not in REGISTERED_TABLES:
        raise SchemaError(f"unknown model table {table_id!r}")
    manifest = dict(REGISTERED_TABLES[table_id])
    missing = [f for f in MANIFEST_REQUIRED_FIELDS if f not in manifest]
    if missing:
        raise SchemaError(f"table manifest {table_id} is missing fields: {missing}")
    if manifest["license_status"] not in ALLOWED_LICENSE_STATUSES:
        raise SchemaError(f"table manifest {table_id} has unknown license_status")
    return manifest


def table_path(table_id: str, *, repo_root: str | Path | None = None) -> Path:
    manifest = source_manifest(table_id)
    return Path(repo_root or REPO_ROOT) / TABLES_RELPATH / manifest["filename"]


def table_available(table_id: str, *, repo_root: str | Path | None = None) -> bool:
    """True when the raw file is present AND its hash matches the manifest."""
    manifest = source_manifest(table_id)
    if manifest["raw_sha256"] is None:
        return False
    path = table_path(table_id, repo_root=repo_root)
    return path.is_file() and sha256_file(path) == manifest["raw_sha256"]


def assert_table_intact(table_id: str, *, repo_root: str | Path | None = None) -> Path:
    manifest = source_manifest(table_id)
    path = table_path(table_id, repo_root=repo_root)
    if manifest["raw_sha256"] is None:
        raise SchemaError(
            f"table {table_id} has no pinned hash ({manifest['license_status']}); "
            "it cannot be loaded into a frozen protocol"
        )
    if not path.is_file():
        raise SchemaError(
            f"table {table_id} is not present at {path}; run "
            "tools/fetch_model_tables.py to acquire it from the recorded source"
        )
    digest = sha256_file(path)
    if digest != manifest["raw_sha256"]:
        raise SchemaError(
            f"table {table_id} at {path} has sha256 {digest}, expected "
            f"{manifest['raw_sha256']}; refusing a moved source"
        )
    return path
