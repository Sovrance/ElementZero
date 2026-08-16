"""Read and validate the immutable Atlas PIR pin."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from elementzero.errors import AtlasContractError

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_FORBIDDEN_REFS = frozenset({"main", "master", "HEAD", "origin/main"})

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = REPO_ROOT / "atlas.lock.json"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def load_atlas_lock(path: Path | None = None) -> dict[str, Any]:
    lock_path = path or LOCK_PATH
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    validate_atlas_ref(data.get("ref"))
    return data


def atlas_pir_ref() -> str:
    return str(load_atlas_lock()["ref"])


def validate_atlas_ref(ref: Any) -> str:
    if not isinstance(ref, str) or not ref.strip():
        raise AtlasContractError("unresolved Atlas dependency ref")
    value = ref.strip()
    if value in _FORBIDDEN_REFS or value.endswith("/main"):
        raise AtlasContractError("mutable Atlas main dependency is forbidden")
    if not _SHA40.fullmatch(value.lower()):
        raise AtlasContractError(
            f"Atlas dependency ref must be a 40-character commit SHA, got {value!r}"
        )
    return value.lower()


def pyproject_atlas_ref() -> str:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    tool_ref = data.get("tool", {}).get("elementzero", {}).get("atlas", {}).get("ref")
    if tool_ref:
        validate_atlas_ref(tool_ref)
    extras = data.get("project", {}).get("optional-dependencies", {})
    deps = list(data.get("project", {}).get("dependencies", []))
    for extra_deps in extras.values():
        deps.extend(extra_deps)
    git_refs = []
    for dep in deps:
        if "github.com/Sovrance/Atlas.git@" in dep:
            git_refs.append(dep.rsplit("@", 1)[-1].strip())
        if "sovrance-atlas-pir" in dep and "@" not in dep.split("sovrance-atlas-pir", 1)[-1]:
            raise AtlasContractError("sovrance-atlas-pir dependency is not commit-pinned")
        lowered = dep.lower()
        if "sovrance/atlas" in lowered and ("@main" in lowered or "@master" in lowered):
            raise AtlasContractError("mutable Atlas main dependency is forbidden")
    if not git_refs and not tool_ref:
        raise AtlasContractError("unresolved Atlas dependency ref")
    for ref in git_refs:
        validate_atlas_ref(ref)
        if tool_ref and validate_atlas_ref(tool_ref) != ref.lower():
            raise AtlasContractError("pyproject Atlas ref does not match tool.elementzero.atlas.ref")
    if git_refs:
        return git_refs[0].lower()
    return validate_atlas_ref(tool_ref)


def assert_pin_consistent() -> str:
    lock_ref = atlas_pir_ref()
    project_ref = pyproject_atlas_ref()
    if lock_ref != project_ref:
        raise AtlasContractError(
            f"atlas.lock.json ref {lock_ref} != pyproject.toml ref {project_ref}"
        )
    return lock_ref
