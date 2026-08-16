from pathlib import Path

import pytest

from elementzero.atlas_pin import REPO_ROOT, validate_atlas_ref
from elementzero.errors import AtlasContractError


def test_main_ref_is_rejected():
    with pytest.raises(AtlasContractError):
        validate_atlas_ref("main")
    with pytest.raises(AtlasContractError):
        validate_atlas_ref("origin/main")
    with pytest.raises(AtlasContractError):
        validate_atlas_ref("")
    with pytest.raises(AtlasContractError):
        validate_atlas_ref("not-a-sha")


def test_lock_file_is_sha():
    validate_atlas_ref(
        __import__("json").loads((REPO_ROOT / "atlas.lock.json").read_text())["ref"]
    )
    text = Path(REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "@main" not in text
    assert "31d76d094f1206e64a6920da4775d0a684618357" in text
    # Required install must not resolve the raw, unpackaged Atlas VCS URL.
    required = text.split("[project.optional-dependencies]", 1)[0]
    assert "sovrance-atlas-pir @ git+" not in required
