"""Historical AME source chronology (WO-13 spec section 6).

Exact versioned source records for AME1995..AME2020, and a chronology
service answering:

    was_target_eligible_by(nuclide_id, source_id)
    was_target_known_by(nuclide_id, source_id)

"eligible" means ground-truth-eligible evaluated evidence (non-estimated);
"known" means any parsed record, estimated/extrapolated included — the
conservative notion for model-knowledge questions, because a model builder
could have used an estimated mass too.

Historical knowledge is never decided from Z or A ranges: membership comes
from parsing the hashed snapshot itself. The committed chronology carries
the full identity sets, so downstream eligibility runs (and CI) never need
the raw snapshots; when the raw files are present the chronology is
re-derived and byte-verified against the committed record.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.data.amdc import EDITIONS
from elementzero.data.amdc.common import PARSER_VERSION, parse_ame_mass_table_detailed
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import sha256_file

RAW_DATA_RELPATH = "data/amdc"

# Raw snapshot pins. AME2003..AME2020 hashes equal the committed WO-01..10
# data-audit records (experiments/EZ-B001-*/data_audit); AME1995 is pinned
# here for the first time from the official AMDC distribution.
HISTORICAL_SOURCES: dict[str, dict[str, Any]] = {
    "AME1995": {
        "source_id": "AME1995",
        "edition": "AME1995",
        "release_date": "1995-12-01",
        "raw_filename": "mass_rmd.mas95",
        "raw_sha256": "f05e9bf4041f2921f82a96186452b6d5d23d57ae4c62f476e5dea40a41e60943",
        "source_url": "https://amdc.impcas.ac.cn/masstables/Ame1995/mass_rmd.mas95",
        "publication": (
            "G. Audi, A. H. Wapstra, 'The 1995 update to the atomic mass "
            "evaluation', Nuclear Physics A 595 (1995) 409"
        ),
    },
    "AME2003": {
        "source_id": "AME2003",
        "edition": "AME2003",
        "release_date": "2003-12-22",
        "raw_filename": "mass.mas03",
        "raw_sha256": "33405560376f2adfb190beec44213523ec79149804df94e436d608019a4c70d1",
        "source_url": "https://amdc.impcas.ac.cn/masstables/Ame2003/mass.mas03",
        "publication": (
            "G. Audi, A. H. Wapstra, C. Thibault, 'The AME2003 atomic mass "
            "evaluation (II)', Nuclear Physics A 729 (2003) 337"
        ),
    },
    "AME2012": {
        "source_id": "AME2012",
        "edition": "AME2012",
        "release_date": "2012-12-01",
        "raw_filename": "mass.mas12",
        "raw_sha256": "81e887c71c2c54c76caea36fd861b195a7f3eeb77d04b520e05fa97e0eedd7f3",
        "source_url": "https://amdc.impcas.ac.cn/masstables/Ame2012/mass.mas12",
        "publication": (
            "M. Wang et al., 'The AME2012 atomic mass evaluation (II)', "
            "Chinese Physics C 36 (2012) 1603"
        ),
    },
    "AME2016": {
        "source_id": "AME2016",
        "edition": "AME2016",
        "release_date": "2017-03-01",
        "raw_filename": "mass16.txt",
        "raw_sha256": "2167f57a2a98331e4649b2dd2b658a9006ed4fba1975729ebfe52a42b4b9218a",
        "source_url": "https://amdc.impcas.ac.cn/masstables/Ame2016/mass16.txt",
        "publication": (
            "M. Wang et al., 'The AME2016 atomic mass evaluation (II)', "
            "Chinese Physics C 41 (2017) 030003"
        ),
    },
    "AME2020": {
        "source_id": "AME2020",
        "edition": "AME2020",
        "release_date": "2021-03-01",
        "raw_filename": "mass_1.mas20.txt",
        "raw_sha256": "e8599c6d7f724fac91934e59f1b9de8fb8f63e820f4b39456b790665ed2a3307",
        "source_url": "https://www-nds.iaea.org/amdc/ame2020/mass_1.mas20.txt",
        "publication": (
            "M. Wang et al., 'The AME2020 atomic mass evaluation (II)', "
            "Chinese Physics C 45 (2021) 030003"
        ),
    },
}

SOURCE_ORDER = ("AME1995", "AME2003", "AME2012", "AME2016", "AME2020")

CHRONOLOGY_RULE = (
    "ez-wo13-chronology-v1: historical knowledge is decided by parsed "
    "membership in a hashed source snapshot, never by Z or A ranges. "
    "'known' counts every parsed record including estimated/extrapolated "
    "values; 'eligible' counts ground-truth-eligible evaluated records only."
)


def snapshot_path(source_id: str, *, repo_root: str | Path | None = None) -> Path:
    record = HISTORICAL_SOURCES[source_id]
    return Path(repo_root or REPO_ROOT) / RAW_DATA_RELPATH / record["raw_filename"]


def snapshots_available(*, repo_root: str | Path | None = None) -> bool:
    return all(snapshot_path(s, repo_root=repo_root).is_file() for s in SOURCE_ORDER)


def build_chronology(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Parse every pinned snapshot and derive the full chronology record."""
    sources: dict[str, Any] = {}
    for source_id in SOURCE_ORDER:
        record = dict(HISTORICAL_SOURCES[source_id])
        path = snapshot_path(source_id, repo_root=repo_root)
        if not path.is_file():
            raise ProtocolError(
                f"historical snapshot {source_id} is not present at {path}; "
                "fetch it with tools/fetch_ame_sources.py"
            )
        digest = sha256_file(path)
        if digest != record["raw_sha256"]:
            raise ProtocolError(
                f"{source_id} snapshot hash {digest} does not match the "
                f"pinned {record['raw_sha256']}"
            )
        spec, _loader = EDITIONS[source_id]
        observations, report = parse_ame_mass_table_detailed(path, spec)
        known_ids = sorted(o.nuclide_id for o in observations)
        eligible_ids = sorted(
            o.nuclide_id for o in observations if o.ground_truth_eligible
        )
        record.update(
            {
                "parser_version": PARSER_VERSION,
                "parse_report": report.to_dict(),
                "n_known": len(known_ids),
                "n_eligible": len(eligible_ids),
                "normalized_identity_digest": identity_digest(known_ids),
                "eligible_identity_digest": identity_digest(eligible_ids),
                "known_nuclide_ids": known_ids,
                "eligible_nuclide_ids": eligible_ids,
            }
        )
        sources[source_id] = record
    return {
        "work_order": "WO-13",
        "rule": CHRONOLOGY_RULE,
        "source_order": list(SOURCE_ORDER),
        "sources": sources,
    }


class SourceChronology:
    """Membership queries over a built or committed chronology payload."""

    def __init__(self, payload: dict[str, Any]) -> None:
        if payload.get("rule") != CHRONOLOGY_RULE:
            raise ProtocolError(
                "chronology payload does not carry the frozen chronology rule"
            )
        self._sources = payload["sources"]
        self._known = {
            source_id: frozenset(entry["known_nuclide_ids"])
            for source_id, entry in self._sources.items()
        }
        self._eligible = {
            source_id: frozenset(entry["eligible_nuclide_ids"])
            for source_id, entry in self._sources.items()
        }

    @classmethod
    def build(cls, *, repo_root: str | Path | None = None) -> SourceChronology:
        return cls(build_chronology(repo_root=repo_root))

    @classmethod
    def from_committed(cls, path: str | Path) -> SourceChronology:
        import json

        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def _assert_source(self, source_id: str) -> None:
        if source_id not in self._sources:
            raise ProtocolError(f"unknown historical source {source_id!r}")

    def was_target_eligible_by(self, nuclide_id: str, source_id: str) -> bool:
        """Ground-truth-eligible evaluated evidence in that snapshot?"""
        self._assert_source(source_id)
        return nuclide_id in self._eligible[source_id]

    def was_target_known_by(self, nuclide_id: str, source_id: str) -> bool:
        """Any parsed record (estimated included) in that snapshot?"""
        self._assert_source(source_id)
        return nuclide_id in self._known[source_id]

    def source_record(self, source_id: str) -> dict[str, Any]:
        self._assert_source(source_id)
        entry = dict(self._sources[source_id])
        # The id lists stay in the committed artifact; queries go through
        # the membership API so callers never re-derive them ad hoc.
        entry.pop("known_nuclide_ids", None)
        entry.pop("eligible_nuclide_ids", None)
        return entry
