from __future__ import annotations

from pathlib import Path

import pytest

# tests.helpers imports elementzero (and through it the pinned Atlas PIR), but
# the schema-validation CI job runs bare pytest with no scientific stack
# installed. Fixtures therefore import helpers lazily, exactly like the
# pre-WO-09 conftest did, so collecting a dependency-free test module never
# pulls the whole package in.


@pytest.fixture
def synthetic_sources(tmp_path: Path) -> tuple[Path, Path]:
    from tests.helpers import synthetic_editions

    return synthetic_editions(tmp_path)


@pytest.fixture
def synthetic_chart(tmp_path: Path) -> Path:
    """One frozen snapshot for EZ-B002: a smooth nuclear-like chart, all Z bands."""
    from tests.helpers import write_synthetic_chart

    return write_synthetic_chart(tmp_path / "chart" / "chart.mas20")


@pytest.fixture
def small_synthetic_chart(tmp_path: Path) -> Path:
    """A cheaper single-band chart for tests that only need one region."""
    from tests.helpers import write_small_synthetic_chart

    return write_small_synthetic_chart(tmp_path / "chart" / "small_chart.mas20")


@pytest.fixture
def synthetic_shell_chart(tmp_path: Path) -> Path:
    """EZ-B003: the same smooth surface with two injected shell-like kinks."""
    from tests.helpers import write_synthetic_shell_chart

    return write_synthetic_shell_chart(tmp_path / "chart" / "shell_chart.mas20")


@pytest.fixture
def small_synthetic_shell_chart(tmp_path: Path) -> Path:
    """A cheaper shell chart: one injected neutron closure, fewer chains."""
    from tests.helpers import write_small_synthetic_shell_chart

    return write_small_synthetic_shell_chart(tmp_path / "chart" / "small_shell_chart.mas20")
