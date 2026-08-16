#!/usr/bin/env python3
"""Fetch and hash-verify the pinned historical AME snapshots (WO-13).

Raw AME tables stay gitignored (/data/); the repository commits their
sha256 pins in elementzero.eligibility.historical_sources. This tool
downloads each snapshot into data/amdc/ and refuses any byte drift.

The AME2020 canonical AMDC path currently 404s; the IAEA-NDS mirror serves
the byte-identical file (same sha256 as the committed WO-01 data audits).
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from elementzero.eligibility.historical_sources import (  # noqa: E402
    HISTORICAL_SOURCES,
    SOURCE_ORDER,
    snapshot_path,
)
from elementzero.evidence.hashing import sha256_file  # noqa: E402


def fetch(source_id: str) -> Path:
    record = HISTORICAL_SOURCES[source_id]
    dest = snapshot_path(source_id, repo_root=REPO_ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and sha256_file(dest) == record["raw_sha256"]:
        print(f"{source_id}: already present and verified")
        return dest
    url = record["source_url"]
    print(f"{source_id}: fetching {url}")
    with urllib.request.urlopen(url, timeout=120) as response:
        dest.write_bytes(response.read())
    digest = sha256_file(dest)
    if digest != record["raw_sha256"]:
        dest.unlink()
        raise SystemExit(
            f"{source_id}: downloaded hash {digest} does not match the "
            f"pinned {record['raw_sha256']}; refusing to keep the file"
        )
    print(f"{source_id}: verified {digest}")
    return dest


def main() -> None:
    for source_id in SOURCE_ORDER:
        fetch(source_id)


if __name__ == "__main__":
    main()
