from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def synthetic_sources(tmp_path: Path) -> tuple[Path, Path]:
    from tests.helpers import synthetic_editions

    return synthetic_editions(tmp_path)
