#!/usr/bin/env python3
"""Enforce the protocol v2.0.0 environment pin (WO-201).

    python tools/check_environment_pin.py

`protocol/protocol.json` declares the interpreter and library versions under
which v2 results are recorded, and states the rule it is enforcing:

    an unpinned environment is a protocol violation, not a footnote

WO-11 recorded that strict byte replay held under CPython 3.12 but that
content-addressed ids over raw IEEE floats shifted by one ULP under 3.11. A
recorded number whose environment is unknown is therefore not replayable, and a
v2 run on an unpinned stack is refused rather than annotated.

Exit codes:

    0  the running environment matches every pinned version
    1  at least one mismatch (reported, one line per component)
    2  the pin itself could not be read

The interpreter is compared on major.minor.micro. Libraries are compared on the
exact string in the pin, because a patch release of numpy or scikit-learn can
move a float in the last place and that is precisely what the pin exists to
detect.

This checker deliberately imports nothing from `elementzero`: it must be able to
run before the package is installed, and it must not be able to pass because a
package-level import silently succeeded.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "protocol" / "protocol.json"

# Pin key in protocol.json -> importable module name.
LIBRARY_MODULES = {
    "numpy": "numpy",
    "scipy": "scipy",
    "scikit_learn": "sklearn",
}

VERSION_KEYS = ("python", *LIBRARY_MODULES)

# Pin keys that carry prose or are checked by a dedicated routine rather than by
# string equality against a version. An unrecognised key is an error: a pin
# component nobody checks is worse than no pin at all.
NON_VERSION_KEYS = frozenset(
    {
        "rule",
        "blas_threads",
        "blas_note",
        "blas_backend_recorded_not_pinned",
        "enforced_by",
    }
)

BLAS_THREAD_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
)


def load_pin(protocol_path: Path) -> dict[str, str]:
    document = json.loads(protocol_path.read_text())
    pin = document.get("environment_pin")
    if not isinstance(pin, dict):
        raise KeyError(f"{protocol_path} has no environment_pin block")
    return pin


def observed_versions() -> dict[str, str | None]:
    seen: dict[str, str | None] = {"python": platform.python_version()}
    for key, module_name in LIBRARY_MODULES.items():
        try:
            seen[key] = importlib.import_module(module_name).__version__
        except ImportError:
            seen[key] = None
    return seen


def compare_versions(pin: dict[str, object], seen: dict[str, str | None]) -> list[str]:
    """Return one failure line per mismatched or missing version component."""
    failures: list[str] = []
    unrecognised = sorted(set(pin) - set(VERSION_KEYS) - NON_VERSION_KEYS)
    if unrecognised:
        failures.append(
            f"environment_pin declares {unrecognised} that this checker does not verify; "
            "a pin component nobody checks is worse than no pin at all"
        )
    for key in VERSION_KEYS:
        if key not in pin:
            failures.append(f"{key}: absent from environment_pin")
            continue
        expected, actual = pin[key], seen.get(key)
        if actual is None:
            failures.append(f"{key}: pinned {expected}, NOT INSTALLED")
        elif actual != expected:
            failures.append(f"{key}: pinned {expected}, running {actual}")
    return failures


def compare_blas_threads(pin: dict[str, object]) -> list[str]:
    """Verify the BLAS thread count, which is part of the pin for a measured reason.

    OpenBLAS reductions sum partial results in a thread-count-dependent order.
    `reports/v2/replay_environment.json` records two distinct byte streams from
    the same pinned library versions at different thread counts, so an unset
    thread count means the run is not byte-replayable even on its own host.
    """
    expected = pin.get("blas_threads")
    if expected is None:
        return []
    failures = []
    for name in BLAS_THREAD_ENV:
        actual = os.environ.get(name)
        if actual is None:
            failures.append(f"{name}: pinned {expected}, UNSET (BLAS picks its own thread count)")
        elif actual != str(expected):
            failures.append(f"{name}: pinned {expected}, running {actual}")
    return failures


def blas_report() -> list[str]:
    """The BLAS build and dispatched SIMD level: recorded, not pinned.

    These are properties of the host CPU and cannot be pinned by declaration.
    They are printed so every run states them, and they are the reason byte
    replay is a per-host claim rather than a portable one.
    """
    try:
        import numpy as np
    except ImportError:
        return ["  blas           (numpy not installed)"]
    config = np.show_config(mode="dicts") or {}
    blas = (config.get("Build Dependencies", {}) or {}).get("blas", {})
    simd = config.get("SIMD Extensions", {}) or {}
    return [
        f"  blas           recorded {blas.get('name')} {blas.get('version')}",
        f"  simd           recorded baseline={simd.get('baseline')} found={simd.get('found')}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    args = parser.parse_args()

    try:
        pin = load_pin(args.protocol)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ENVIRONMENT_PIN: UNREADABLE ({exc})", file=sys.stderr)
        return 2

    seen = observed_versions()
    failures = compare_versions(pin, seen) + compare_blas_threads(pin)

    for key in VERSION_KEYS:
        expected = pin.get(key, "(unpinned)")
        print(f"  {key:<14} pinned {str(expected):<10} running {seen.get(key) or '(missing)'}")
    if "blas_threads" in pin:
        observed_threads = ", ".join(
            f"{name}={os.environ.get(name) or '(unset)'}" for name in BLAS_THREAD_ENV
        )
        print(f"  {'blas_threads':<14} pinned {str(pin['blas_threads']):<10} running {observed_threads}")
    for line in blas_report():
        print(line)

    if failures:
        print("ENVIRONMENT_PIN: VIOLATION", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        print(
            "\nA v2 run on an unpinned stack is a protocol violation, not a footnote. "
            "Install the pinned versions and fix the BLAS thread count, or bump "
            "protocol_version and rerun the comparable benchmarks under the new pin.",
            file=sys.stderr,
        )
        return 1

    print("ENVIRONMENT_PIN: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
