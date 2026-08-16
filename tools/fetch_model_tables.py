#!/usr/bin/env python3
"""Fetch the registered external mass-model tables and verify their hashes.

Raw published tables stay out of git (WO-12 section 6); this tool downloads
every APPROVED registered table from its recorded public source into
``data/model_tables/`` and refuses any file whose sha256 differs from the
pinned manifest hash.

    python tools/fetch_model_tables.py            # fetch what is missing
    python tools/fetch_model_tables.py --verify   # verify what is present
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from elementzero.data.model_tables.manifests import (  # noqa: E402
    REGISTERED_TABLES,
    STATUS_APPROVED,
    table_path,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify only, no downloads")
    args = parser.parse_args(argv)
    failures = 0
    for table_id, manifest in sorted(REGISTERED_TABLES.items()):
        if manifest["license_status"] != STATUS_APPROVED or manifest["raw_sha256"] is None:
            print(f"{table_id}: {manifest['license_status']} — skipped (see manifest note)")
            continue
        destination = table_path(table_id, repo_root=ROOT)
        if destination.is_file():
            digest = sha256_file(destination)
            if digest == manifest["raw_sha256"]:
                print(f"{table_id}: present, hash OK")
                continue
            print(f"{table_id}: HASH MISMATCH at {destination} ({digest}); refusing")
            failures += 1
            continue
        if args.verify:
            print(f"{table_id}: MISSING at {destination}")
            failures += 1
            continue
        print(f"{table_id}: downloading {manifest['source_url']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(manifest["source_url"], timeout=120) as response:
            raw = response.read()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest["raw_sha256"]:
            print(f"{table_id}: downloaded hash {digest} != pinned {manifest['raw_sha256']}")
            failures += 1
            continue
        destination.write_bytes(raw)
        print(f"{table_id}: fetched, hash OK ({len(raw)} bytes)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
