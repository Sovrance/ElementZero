"""Repository identity helpers used in freezes and certificates."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from elementzero.atlas_pin import REPO_ROOT, atlas_pir_ref


def _git(args: list[str], cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd or REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def elementzero_commit() -> str:
    env = os.environ.get("ELEMENTZERO_COMMIT")
    if env:
        return env
    sha = _git(["rev-parse", "HEAD"])
    if not sha:
        return "uncommitted"
    dirty = _git(["status", "--porcelain"])
    if dirty:
        return f"{sha}-dirty"
    return sha


def runtime_library_versions() -> dict[str, str]:
    versions = {"elementzero": _pkg_version("elementzero")}
    for name in ("numpy", "scipy", "sklearn", "pir"):
        versions[name] = _pkg_version(name)
    return versions


def _pkg_version(name: str) -> str:
    import sys

    if name == "pir":
        mod = sys.modules.get("pir")
        if mod is None:
            return "pinned"
        return str(getattr(mod, "__version__", "unknown"))
    try:
        mod = __import__(name)
        return str(getattr(mod, "__version__", "unknown"))
    except Exception:
        return "unavailable"


def provenance_identity() -> dict[str, str]:
    return {
        "atlas_repository": "https://github.com/Sovrance/Atlas",
        "atlas_pir_ref": atlas_pir_ref(),
        "elementzero_commit": elementzero_commit(),
    }
