from __future__ import annotations

import ast
from pathlib import Path

from elementzero.atlas_pin import REPO_ROOT

SRC = REPO_ROOT / "src" / "elementzero"

FORBIDDEN = (
    "b1_moment_solver",
    "b2_process_solver",
    "b3_electroweak",
    "b4_area_pipeline",
    "b5_cluster",
    "b6_qnec",
    "b7_onsager",
    "b8_grammar",
    "b9_circuit",
    "b10_cv_channel",
    "b12_rgrc",
    "b13_cdl",
    "generator",
    "canon",
    "atlas_engine",
)

ALLOWED_PIR_FILES = {"atlas_adapter.py"}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_production_imports_do_not_touch_atlas_research_modules():
    violations = []
    for path in SRC.rglob("*.py"):
        for name in _imports(path):
            root = name.split(".")[0]
            if root in FORBIDDEN or any(name.startswith(f"{mod}.") for mod in FORBIDDEN):
                violations.append((path, name))
            if root == "pir" and path.name not in ALLOWED_PIR_FILES:
                violations.append((path, name))
    assert violations == []
