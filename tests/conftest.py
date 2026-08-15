from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import synthetic_editions


@pytest.fixture
def synthetic_sources(tmp_path: Path) -> tuple[Path, Path]:
    return synthetic_editions(tmp_path)
