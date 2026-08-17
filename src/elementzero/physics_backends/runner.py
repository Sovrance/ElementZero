"""Solver execution: isolated work dirs, timeouts, no silent imputation.

Each solve runs in its own scratch directory so concurrent solves cannot
overwrite one another's namelists or output files — the HFBTHO and DIRHB
executables both read and write fixed filenames in the working directory.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from elementzero.errors import ProtocolError
from elementzero.physics_backends import BACKEND_DATA_RELPATH
from elementzero.physics_backends.provenance import backend_data_dir

DEFAULT_TIMEOUT_S = 900

# The physics is the solver's; the reproducibility is ours. Threads are
# pinned to 1 so a solve's result cannot depend on how many cores were
# free when it ran.
DETERMINISM_ENV = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
}

DETERMINISM_RULE = (
    "ez-wo15-solver-determinism-v1: every solve runs single-threaded in an "
    "isolated working directory with a fixed timeout, so a result depends on "
    "the parameter artifact and the nuclide alone — never on machine load or "
    "on a neighbouring solve's leftover files"
)


def hfbtho_binary(*, repo_root: str | Path | None = None) -> Path:
    path = backend_data_dir(repo_root=repo_root) / "hfbtho_gogny_build"
    if not path.is_file():
        raise ProtocolError(
            f"{path} is missing; build it with tools/build_physics_backends.sh"
        )
    return path


def dirhb_binary(*, repo_root: str | Path | None = None) -> Path:
    path = backend_data_dir(repo_root=repo_root) / "dirhbs_run"
    if not path.is_file():
        raise ProtocolError(
            f"{path} is missing; build it with tools/build_physics_backends.sh"
        )
    return path


def run_solver(
    *,
    binary: str | Path,
    work_dir: str | Path,
    input_files: Mapping[str, str],
    timeout_s: int = DEFAULT_TIMEOUT_S,
    stdout_name: str = "run.log",
) -> dict[str, Any]:
    """Run one solve in a clean directory; never raise on solver failure."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    for name, content in input_files.items():
        (work_dir / name).write_text(content, encoding="utf-8")

    env = {**os.environ, **DETERMINISM_ENV}
    try:
        completed = subprocess.run(
            [str(Path(binary).resolve())],
            cwd=work_dir,
            capture_output=True,
            timeout=timeout_s,
            check=False,
            env=env,
        )
        (work_dir / stdout_name).write_bytes(
            completed.stdout + b"\n" + completed.stderr
        )
        return {
            "returncode": completed.returncode,
            "timed_out": False,
            "work_dir": str(work_dir),
        }
    except subprocess.TimeoutExpired:
        (work_dir / stdout_name).write_text(
            f"TIMEOUT after {timeout_s}s\n", encoding="utf-8"
        )
        return {"returncode": None, "timed_out": True, "work_dir": str(work_dir)}


__all__ = [
    "BACKEND_DATA_RELPATH",
    "DEFAULT_TIMEOUT_S",
    "DETERMINISM_RULE",
    "dirhb_binary",
    "hfbtho_binary",
    "run_solver",
]
