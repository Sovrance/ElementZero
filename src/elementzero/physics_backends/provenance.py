"""Solver source identity, licensing, and parameterization chronology.

Two independent provenance questions, deliberately kept apart:

    1. the SOLVER  — which code, which archive, which hash, which licence
    2. the PARAMETERS — which published parameterization, published when

WO-15 exists because (1) says nothing about (2). A 1970s solver running a
2010s functional is a modern model; the code's age is irrelevant. Only the
parameterization's publication date bounds what evidence could possibly
have entered the fit.
"""

from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_file, sha256_hex
from elementzero.physics_backends import (
    BACKEND_COVARIANT,
    BACKEND_DATA_RELPATH,
    BACKEND_GOGNY,
    BACKEND_SKYRME,
    GROUP_COVARIANT_RHB,
    GROUP_GOGNY_HFB,
    GROUP_SKYRME_HFB,
)

# --------------------------------------------------------------------------- #
# Solver archives                                                             #
# --------------------------------------------------------------------------- #

# Pinned by sha256 over the published archive, exactly as the model-table
# program pins AMDC and BSkG/FRDM files. Both archives were retrieved and
# verified in this environment; the digests are the authority.
SOLVER_SOURCES: dict[str, dict[str, Any]] = {
    "HFBTHO": {
        "solver_name": "HFBTHO",
        "solver_version": "HFBTHO-AD (Zenodo 16249941)",
        "archive_filename": "hfbtho.tar.gz",
        "archive_sha256": (
            "89818ef33b1f504c3f57fc1e754145c8639013229b047932221907ff0b2e75bb"
        ),
        "download_url": (
            "https://zenodo.org/api/records/16249941/files/hfbtho.tar.gz/content"
        ),
        "record_url": "https://zenodo.org/records/16249941",
        "license": "GPL-3.0-or-later",
        "license_evidence": (
            "GPLv3 header in every source file; LLNL-CODE-728299 / "
            "LLNL-CODE-573953"
        ),
        "publication": (
            "HFBTHO v3.00, Comput. Phys. Commun. 220 (2017) 363-375; "
            "HFBTHO-AD, Comput. Phys. Commun. 320 (2026) 109955"
        ),
        "redistribution_allowed": True,
        "families_served": [GROUP_SKYRME_HFB, GROUP_GOGNY_HFB],
    },
    "DIRHB": {
        "solver_name": "DIRHB",
        "solver_version": "DIRHB package (revised), Mendeley cx55fkbjy6 v1",
        "archive_filename": "dirhb.tar.gz",
        "archive_sha256": (
            "04e3657e68a8dcd1e59eadcce44cea0c4ab257f2ed72d30802e13ab1316517cd"
        ),
        "download_url": (
            "https://data.mendeley.com/public-files/datasets/cx55fkbjy6/files/"
            "aa59747b-2824-4a20-8c64-40faa8318a90/file_downloaded"
        ),
        "record_url": "https://data.mendeley.com/datasets/cx55fkbjy6",
        "license": "CPC non-profit use licence",
        "license_evidence": (
            "Mendeley data_licence field of the CPC Program Library record; "
            "non-profit use permitted, redistribution restricted"
        ),
        "publication": (
            "Niksic, Paar, Vretenar, Ring, Comput. Phys. Commun. 185 (2014) "
            "1808-1821"
        ),
        # The archive is fetched, never vendored: the CPC licence does not
        # grant redistribution the way GPLv3 does.
        "redistribution_allowed": False,
        "families_served": [GROUP_COVARIANT_RHB],
    },
}

# --------------------------------------------------------------------------- #
# Parameterization chronology                                                 #
# --------------------------------------------------------------------------- #

# The freeze boundary WO-13 established for the FRDM95 program: a
# parameterization published after this date cannot be historically blind
# on post-1995 evidence, whatever its solver.
FIT_FREEZE_CUTOFF = "1995-12-01"

PARAMETERIZATIONS: dict[str, dict[str, Any]] = {
    "SIII": {
        "functional_class": "skyrme_zero_range_edf",
        "publication_year": 1975,
        "publication": "Beiner, Flocard, Van Giai, Quentin, Nucl. Phys. A238 (1975) 29",
        "calibration_membership": "PARTIAL",
        "calibration_note": (
            "fitted to selected spherical nuclei and nuclear-matter "
            "properties; the exact nuclide list is published in prose, not "
            "as a machine-readable membership set"
        ),
    },
    "SKM*": {
        "functional_class": "skyrme_zero_range_edf",
        "publication_year": 1982,
        "publication": (
            "Bartel, Quentin, Brack, Guet, Hakansson, Nucl. Phys. A386 (1982) 79"
        ),
        "calibration_membership": "PARTIAL",
        "calibration_note": (
            "refit of SkM constrained by the fission barrier of 240Pu plus "
            "nuclear-matter and selected finite-nucleus data; exact nuclide "
            "membership is not machine-readable"
        ),
    },
    "SKP": {
        "functional_class": "skyrme_zero_range_edf",
        "publication_year": 1984,
        "publication": "Dobaczewski, Flocard, Treiner, Nucl. Phys. A422 (1984) 103",
        "calibration_membership": "PARTIAL",
        "calibration_note": "pairing-oriented Skyrme parameterization",
    },
    "SLY4": {
        "functional_class": "skyrme_zero_range_edf",
        "publication_year": 1998,
        "publication": "Chabanat et al., Nucl. Phys. A635 (1998) 231",
        "calibration_membership": "PARTIAL",
        "calibration_note": "post-freeze parameterization",
    },
    "UNE0": {
        "functional_class": "skyrme_zero_range_edf",
        "publication_year": 2010,
        "publication": "Kortelainen et al., Phys. Rev. C 82, 024313 (2010)",
        "calibration_membership": "EXACT",
        "calibration_note": (
            "UNEDF0 publishes its calibration dataset explicitly, but the "
            "fit postdates the freeze"
        ),
    },
    "D1": {
        "functional_class": "gogny_finite_range",
        "publication_year": 1980,
        "publication": "Decharge, Gogny, Phys. Rev. C 21 (1980) 1568",
        "calibration_membership": "PARTIAL",
        "calibration_note": "original finite-range Gogny parameterization",
    },
    "D1S": {
        "functional_class": "gogny_finite_range",
        "publication_year": 1984,
        "publication": (
            "Berger, Girod, Gogny, Nucl. Phys. A428 (1984) 23c; "
            "Comput. Phys. Commun. 63 (1991) 365"
        ),
        "calibration_membership": "PARTIAL",
        "calibration_note": (
            "surface-energy refit of D1 for fission; exact nuclide "
            "membership is not machine-readable"
        ),
    },
    "D1N": {
        "functional_class": "gogny_finite_range",
        "publication_year": 2008,
        "publication": "Chappert, Girod, Hilaire, Phys. Lett. B 668 (2008) 420",
        "calibration_membership": "PARTIAL",
        "calibration_note": "post-freeze parameterization",
    },
    "DD-ME2": {
        "functional_class": "covariant_meson_exchange",
        "publication_year": 2005,
        "publication": "Lalazissis, Niksic, Vretenar, Ring, Phys. Rev. C 71, 024312 (2005)",
        "calibration_membership": "PARTIAL",
        "calibration_note": (
            "density-dependent meson-exchange functional fitted to binding "
            "energies, radii and nuclear-matter data of 2005 vintage"
        ),
    },
    "DD-PC1": {
        "functional_class": "covariant_point_coupling",
        "publication_year": 2008,
        "publication": "Niksic, Vretenar, Ring, Phys. Rev. C 78, 034318 (2008)",
        "calibration_membership": "PARTIAL",
        "calibration_note": "post-freeze point-coupling functional",
    },
}

FREEZE_ADMISSIBILITY_RULE = (
    "ez-wo15-parameterization-chronology-v1: a published parameterization is "
    "freeze-admissible only when its publication predates the freeze cutoff. "
    "The solver's age is irrelevant — a 1990s code running a 2010s functional "
    "is a modern model. Publication date bounds what evidence could have "
    "entered the fit; exact calibration membership decides whether the class "
    "is HISTORICAL_FROZEN_EXACT or HISTORICAL_FROZEN_PARTIAL."
)


def parameterization_admissible(name: str, *, cutoff: str = FIT_FREEZE_CUTOFF) -> bool:
    """Does this published parameterization predate the freeze?"""
    record = PARAMETERIZATIONS.get(name.upper())
    if record is None:
        raise ProtocolError(
            f"parameterization {name!r} has no chronology record; unknown "
            "provenance is never assumed admissible"
        )
    return record["publication_year"] < int(cutoff[:4])


# --------------------------------------------------------------------------- #
# Source verification and build manifests                                     #
# --------------------------------------------------------------------------- #


def backend_data_dir(*, repo_root: str | Path | None = None) -> Path:
    return Path(repo_root or REPO_ROOT) / BACKEND_DATA_RELPATH


def verify_archive(solver: str, *, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Re-hash the fetched archive against its pin."""
    record = SOLVER_SOURCES[solver]
    path = backend_data_dir(repo_root=repo_root) / record["archive_filename"]
    if not path.is_file():
        raise ProtocolError(
            f"{path} is missing; fetch it with tools/fetch_physics_backends.py"
        )
    digest = sha256_file(path)
    if digest != record["archive_sha256"]:
        raise ProtocolError(
            f"{solver} archive hashes {digest}, pinned "
            f"{record['archive_sha256']}; WO-15 stops"
        )
    return {
        "solver": solver,
        "archive_path": str(path),
        "archive_sha256": digest,
        "verified": True,
    }


def source_tree_digest(paths: list[Path]) -> str:
    """Order-independent digest over a set of source files."""
    return sha256_hex(
        {"files": sorted({str(p.name): sha256_file(p) for p in paths}.items())}
    )


def archive_member_digests(solver: str, *, repo_root: str | Path | None = None) -> dict[str, str]:
    """Per-member digests read straight from the pinned archive.

    Reading from the archive rather than the extracted tree means the
    record cannot drift with a stray edit on disk.
    """
    record = SOLVER_SOURCES[solver]
    path = backend_data_dir(repo_root=repo_root) / record["archive_filename"]
    digests: dict[str, str] = {}
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            digests[member.name] = sha256_hex(handle.read().decode("latin-1"))
    return dict(sorted(digests.items()))


def build_manifest(
    *,
    solver: str,
    binary_path: str | Path,
    compiler: str,
    compiler_version: str,
    build_flags: str,
    notes: str = "",
) -> dict[str, Any]:
    """The record that makes one built executable identifiable."""
    binary = Path(binary_path)
    if not binary.is_file():
        raise ProtocolError(f"built solver {binary} is missing")
    payload = {
        "solver": solver,
        "solver_version": SOLVER_SOURCES[solver]["solver_version"],
        "archive_sha256": SOLVER_SOURCES[solver]["archive_sha256"],
        "binary_relname": binary.name,
        "binary_sha256": sha256_file(binary),
        "compiler": compiler,
        "compiler_version": compiler_version,
        "build_flags": build_flags,
        "notes": notes,
    }
    payload["build_manifest_hash"] = sha256_hex(payload)
    return payload


def compiler_version(compiler: str = "gfortran") -> str:
    try:
        out = subprocess.run(
            [compiler, "-dumpversion"], capture_output=True, check=False
        )
        return out.stdout.decode().strip() or "unknown"
    except OSError:
        return "unavailable"


BACKEND_SOLVER = {
    BACKEND_SKYRME: "HFBTHO",
    BACKEND_GOGNY: "HFBTHO",
    BACKEND_COVARIANT: "DIRHB",
}
