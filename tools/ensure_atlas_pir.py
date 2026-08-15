#!/usr/bin/env python3
"""Install the commit-pinned Atlas PIR package.

Atlas at the reviewed baseline has no pyproject.toml yet. This tool clones the
immutable SHA from atlas.lock.json and, if packaging metadata is missing,
writes the recommended sovrance-atlas-pir skeleton into the clone only.
It does not copy pir/ into ElementZero.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "atlas.lock.json").read_text(encoding="utf-8"))
REF = LOCK["ref"]
REPO = LOCK["git_url"]
CACHE = Path(ROOT / ".cache" / "atlas-pir" / REF)
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


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    if REF in {"main", "master", "HEAD"} or not REF or len(REF) != 40:
        print("refusing to install a mutable or unresolved Atlas ref", file=sys.stderr)
        return 2
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not (CACHE / ".git").exists():
        run(["git", "clone", REPO, str(CACHE)])
    run(["git", "fetch", "--depth", "1", "origin", REF], cwd=CACHE)
    run(["git", "checkout", "--force", REF], cwd=CACHE)
    if not (CACHE / "pyproject.toml").exists():
        (CACHE / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
        print(f"wrote packaging overlay for pre-packaging Atlas SHA {REF}", flush=True)
    run([sys.executable, "-m", "pip", "install", "-e", str(CACHE)])
    code = (
        "import pir; from pir import Artifact, Fact, FactStore, Hypothesis, "
        "Intervention, forward, intervention_search; print(pir.__version__)"
    )
    run([sys.executable, "-c", code])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
