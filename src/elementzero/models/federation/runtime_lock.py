"""Runtime lock for v2 protocols (WO-12 section 23).

Strict byte replay is promised only on the reference runtime captured here;
on any other runtime the promise is scientific equivalence at the canonical
12-significant-digit serialization. WO-11 measured exactly this boundary
(1-ULP drift in raw-float payloads across interpreter lines), so the lock
records everything that moved it: interpreter, array stack, BLAS/LAPACK
identity, OS, and architecture.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any

from elementzero.evidence.hashing import canonical_json

RUNTIME_LOCK_FILE = "runtime.lock.json"

REQUIRED_LOCK_FIELDS = (
    "python_version",
    "python_minor",
    "python_implementation",
    "numpy_version",
    "scipy_version",
    "sklearn_version",
    "blas_lapack",
    "operating_system",
    "architecture",
    "replay_policy",
)

REPLAY_POLICY = (
    "strict byte replay is required on the reference runtime recorded here; "
    "on any other runtime the requirement is scientific equivalence under "
    "canonical 12-significant-digit serialization (ADR-0002)"
)


def _blas_identity() -> dict[str, Any]:
    try:
        import numpy

        config = numpy.show_config(mode="dicts")
        dependencies = config.get("Build Dependencies", {})
        identity = {}
        for name in ("blas", "lapack"):
            entry = dependencies.get(name, {})
            identity[name] = {
                "name": entry.get("name"),
                "version": entry.get("version"),
            }
        return identity
    except Exception:  # pragma: no cover - identity is best-effort by spec
        return {"blas": {"name": None, "version": None}, "lapack": {"name": None, "version": None}}


def capture_runtime() -> dict[str, Any]:
    import numpy
    import scipy
    import sklearn

    return {
        "python_version": platform.python_version(),
        "python_minor": f"{sys.version_info[0]}.{sys.version_info[1]}",
        "python_implementation": platform.python_implementation(),
        "numpy_version": numpy.__version__,
        "scipy_version": scipy.__version__,
        "sklearn_version": sklearn.__version__,
        "blas_lapack": _blas_identity(),
        "operating_system": platform.system(),
        "architecture": platform.machine(),
        "replay_policy": REPLAY_POLICY,
    }


def write_runtime_lock(path: str | Path) -> dict[str, Any]:
    lock = capture_runtime()
    Path(path).write_text(canonical_json(lock) + "\n", encoding="utf-8")
    return lock


def read_runtime_lock(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_lock_complete(lock: dict[str, Any]) -> dict[str, Any]:
    missing = [f for f in REQUIRED_LOCK_FIELDS if f not in lock or lock[f] in (None, "")]
    if missing:
        from elementzero.errors import SchemaError

        raise SchemaError(f"runtime lock is missing fields: {missing}")
    return lock


def compare_runtime(lock: dict[str, Any]) -> dict[str, Any]:
    """REFERENCE_MATCH on the locked runtime, SCIENTIFIC_EQUIVALENCE elsewhere.

    Every dimension the lock records because it can move bytes participates
    in the match — interpreter line and implementation, the array stack,
    BLAS/LAPACK identity, OS, and architecture. A single differing dimension
    downgrades the promise to scientific equivalence; claiming byte replay on
    a runtime that only partially matches would be an incorrect guarantee.
    """
    current = capture_runtime()
    keys = (
        "python_minor",
        "python_implementation",
        "numpy_version",
        "scipy_version",
        "sklearn_version",
        "blas_lapack",
        "operating_system",
        "architecture",
    )
    deltas = {k: {"locked": lock.get(k), "current": current.get(k)} for k in keys
              if lock.get(k) != current.get(k)}
    return {
        "mode": "REFERENCE_MATCH" if not deltas else "SCIENTIFIC_EQUIVALENCE",
        "deltas": deltas,
        "replay_policy": REPLAY_POLICY,
    }
