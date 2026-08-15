#!/usr/bin/env python3
"""Install the commit-pinned Atlas PIR package.

Order of preference (WO-04):

1. If the pinned Atlas commit already carries its own ``pyproject.toml``,
   install it unchanged. No file inside the clone is created or modified.
2. Otherwise fall back to the formally approved temporary overlay documented in
   ``docs/migrations/WO-04-atlas-packaging-exception.md``: write the recommended
   ``sovrance-atlas-pir`` metadata into the clone, print a WARNING, and stamp
   ``.elementzero_overlay_exception`` so the exception is visible on disk.

The overlay is never vendored into ElementZero, and a mutable Atlas ref
(``main``/``master``/``HEAD``/``latest``) is always refused.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "atlas.lock.json").read_text(encoding="utf-8"))
REF = LOCK["ref"]
REPO = LOCK["git_url"]
CACHE = Path(ROOT / ".cache" / "atlas-pir" / REF)

MUTABLE_REFS = frozenset({"main", "master", "head", "latest", "origin/main", "origin/master"})
OVERLAY_STAMP_NAME = ".elementzero_overlay_exception"
EXCEPTION_DOC = "docs/migrations/WO-04-atlas-packaging-exception.md"
OVERLAY_EXCEPTION_ID = "WO-04-ATLAS-PACKAGING-OVERLAY-EXCEPTION-v1"

PYPROJECT = """[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sovrance-atlas-pir"
version = "0.1.0"
description = "Sovrance Atlas Physics Intermediate Representation evidence substrate"
requires-python = ">=3.11"

[tool.setuptools.packages.find]
where = ["."]
include = ["pir", "pir.*"]

[tool.setuptools.package-data]
pir = ["schema/*.json", "manifest.json"]
"""

OVERLAY_WARNING = f"""
================================ WARNING ================================
Atlas commit {REF}
does not ship packaging metadata. ElementZero is installing it through the
temporary packaging overlay approved in:

    {EXCEPTION_DOC}

This overlay is an exception, not the target architecture. It writes
pyproject.toml into the local Atlas clone only; pir/ is never copied into
ElementZero, and the pin stays immutable. Retire the overlay as soon as an
upstream Atlas commit carries its own pyproject.toml.
=========================================================================
"""


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def assert_immutable_ref(ref: str | None) -> str:
    """Refuse Atlas main/HEAD and anything that is not a 40-character SHA."""
    value = (ref or "").strip()
    if not value:
        raise ValueError("Atlas ref is unresolved; atlas.lock.json must pin a commit SHA")
    if value.lower() in MUTABLE_REFS or value.lower().endswith("/main"):
        raise ValueError(f"refusing mutable Atlas ref {value!r}; pin a 40-character commit SHA")
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value.lower()):
        raise ValueError(f"Atlas ref {value!r} is not a 40-character commit SHA")
    return value.lower()


def overlay_stamp_path(clone: Path) -> Path:
    return Path(clone) / OVERLAY_STAMP_NAME


def upstream_is_packaged(clone: Path, ref: str) -> bool:
    """True when the pinned Atlas commit itself tracks packaging metadata.

    The check reads the committed tree, not the working directory, so a
    previously written overlay can never be mistaken for upstream packaging.
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref],
        cwd=str(clone),
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = set(result.stdout.split())
    return "pyproject.toml" in tracked


def write_overlay_exception(clone: Path, ref: str) -> Path:
    """Apply the approved overlay and stamp the exception next to it."""
    clone = Path(clone)
    print(OVERLAY_WARNING, file=sys.stderr, flush=True)
    (clone / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    stamp = overlay_stamp_path(clone)
    stamp.write_text(
        json.dumps(
            {
                "exception_id": OVERLAY_EXCEPTION_ID,
                "atlas_ref": ref,
                "atlas_repository": REPO,
                "approved_by_document": EXCEPTION_DOC,
                "distribution": "sovrance-atlas-pir",
                "mutates": ["pyproject.toml"],
                "vendors_pir_into_elementzero": False,
                "status": "TEMPORARY_APPROVED_EXCEPTION",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return stamp


def clone_pin(ref: str) -> Path:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not (CACHE / ".git").exists():
        run(["git", "clone", REPO, str(CACHE)])
    run(["git", "fetch", "--depth", "1", "origin", ref], cwd=CACHE)
    run(["git", "checkout", "--force", ref], cwd=CACHE)
    return CACHE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-overlay",
        action="store_true",
        help="verifier mode: install only if upstream Atlas is already packaged, never mutate the clone",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ref = assert_immutable_ref(REF)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    clone = clone_pin(ref)
    if upstream_is_packaged(clone, ref):
        print(f"Atlas {ref} ships packaging metadata; installing pin without any overlay", flush=True)
        if overlay_stamp_path(clone).exists():
            overlay_stamp_path(clone).unlink()
    elif args.no_overlay:
        print(
            f"Atlas {ref} has no packaging metadata and --no-overlay forbids writing it; "
            f"see {EXCEPTION_DOC}",
            file=sys.stderr,
        )
        return 3
    else:
        write_overlay_exception(clone, ref)
    run([sys.executable, "-m", "pip", "install", "-e", str(clone)])
    code = (
        "import pir; from pir import Artifact, Fact, FactStore, Hypothesis, "
        "Intervention, forward, intervention_search; print(pir.__version__)"
    )
    run([sys.executable, "-c", code])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
