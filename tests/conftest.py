from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import (
    synthetic_editions,
    write_small_synthetic_chart,
    write_small_synthetic_shell_chart,
    write_synthetic_chart,
    write_synthetic_shell_chart,
)


@pytest.fixture
def synthetic_sources(tmp_path: Path) -> tuple[Path, Path]:
    return synthetic_editions(tmp_path)


@pytest.fixture
def synthetic_chart(tmp_path: Path) -> Path:
    """One frozen snapshot for EZ-B002: a smooth nuclear-like chart, all Z bands."""
    return write_synthetic_chart(tmp_path / "chart" / "chart.mas20")


@pytest.fixture
def small_synthetic_chart(tmp_path: Path) -> Path:
    """A cheaper single-band chart for tests that only need one region."""
    return write_small_synthetic_chart(tmp_path / "chart" / "small_chart.mas20")


@pytest.fixture
def synthetic_shell_chart(tmp_path: Path) -> Path:
    """EZ-B003: the same smooth surface with two injected shell-like kinks."""
    return write_synthetic_shell_chart(tmp_path / "chart" / "shell_chart.mas20")


@pytest.fixture
def small_synthetic_shell_chart(tmp_path: Path) -> Path:
    """A cheaper shell chart: one injected neutron closure, fewer chains."""
    return write_small_synthetic_shell_chart(tmp_path / "chart" / "small_shell_chart.mas20")
