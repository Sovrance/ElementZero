"""WO-04 exception: the packaging overlay must be immutable-pin only and loud."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "tools" / "ensure_atlas_pir.py"
EXCEPTION_DOC = REPO_ROOT / "docs" / "migrations" / "WO-04-atlas-packaging-exception.md"


def _load_tool():
    spec = importlib.util.spec_from_file_location("ensure_atlas_pir", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = _load_tool()


def _git_repo(path: Path, *, tracked: dict[str, str]) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    for name, content in tracked.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_mutable_atlas_refs_are_refused():
    for ref in ("main", "master", "HEAD", "latest", "origin/main", ""):
        with pytest.raises(ValueError):
            TOOL.assert_immutable_ref(ref)
    with pytest.raises(ValueError):
        TOOL.assert_immutable_ref("31d76d0")
    assert TOOL.assert_immutable_ref("31D76D094F1206E64A6920DA4775D0A684618357") == (
        "31d76d094f1206e64a6920da4775d0a684618357"
    )


def test_locked_ref_is_an_immutable_sha():
    lock = json.loads((REPO_ROOT / "atlas.lock.json").read_text(encoding="utf-8"))
    assert TOOL.assert_immutable_ref(lock["ref"]) == lock["ref"].lower()


def test_packaged_upstream_needs_no_overlay(tmp_path):
    clone = tmp_path / "atlas"
    ref = _git_repo(clone, tracked={"pyproject.toml": "[project]\nname='x'\n"})
    assert TOOL.upstream_is_packaged(clone, ref) is True


def test_overlay_is_detected_as_an_exception_not_as_upstream_packaging(tmp_path):
    clone = tmp_path / "atlas"
    ref = _git_repo(clone, tracked={"pir/__init__.py": "__version__='0.1.0'\n"})
    assert TOOL.upstream_is_packaged(clone, ref) is False

    stamp = TOOL.write_overlay_exception(clone, ref)
    assert (clone / "pyproject.toml").is_file()
    assert "sovrance-atlas-pir" in (clone / "pyproject.toml").read_text(encoding="utf-8")

    # The stamp records the exception; the pin is unchanged and pir is not vendored.
    payload = json.loads(stamp.read_text(encoding="utf-8"))
    assert stamp.name == ".elementzero_overlay_exception"
    assert payload["exception_id"] == TOOL.OVERLAY_EXCEPTION_ID
    assert payload["atlas_ref"] == ref
    assert payload["approved_by_document"] == TOOL.EXCEPTION_DOC
    assert payload["vendors_pir_into_elementzero"] is False

    # A written overlay must never be mistaken for upstream packaging metadata.
    assert TOOL.upstream_is_packaged(clone, ref) is False


def test_no_overlay_mode_refuses_to_create_packaging_metadata(tmp_path, monkeypatch, capsys):
    clone = tmp_path / "atlas"
    ref = _git_repo(clone, tracked={"pir/__init__.py": "__version__='0.1.0'\n"})
    monkeypatch.setattr(TOOL, "REF", ref)
    monkeypatch.setattr(TOOL, "clone_pin", lambda _ref: clone)

    def _fail(*_args, **_kwargs):
        raise AssertionError("verifier mode must not install or mutate anything")

    monkeypatch.setattr(TOOL, "run", _fail)
    monkeypatch.setattr(TOOL, "write_overlay_exception", _fail)
    assert TOOL.main(["--no-overlay"]) == 3
    assert not (clone / "pyproject.toml").exists()
    assert TOOL.EXCEPTION_DOC in capsys.readouterr().err


def test_exception_document_states_pin_and_unblocks_wo05():
    text = EXCEPTION_DOC.read_text(encoding="utf-8")
    assert "31d76d094f1206e64a6920da4775d0a684618357" in text
    assert "WO-04-ATLAS-PACKAGING-OVERLAY-EXCEPTION-v1" in text
    assert "read-only" in text
    assert "WO-05" in text
    for adr in ("docs/adr/ADR-0001-atlas-pir-boundary.md", "docs/architecture/atlas-integration.md"):
        assert "WO-04-atlas-packaging-exception.md" in (REPO_ROOT / adr).read_text(encoding="utf-8")
