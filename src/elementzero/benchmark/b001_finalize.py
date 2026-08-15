"""Finalize the prediction ledger before any truth unlock."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.evidence.ledger import finalize_run


def finalize(run_dir: str | Path) -> dict[str, Any]:
    return finalize_run(Path(run_dir))
