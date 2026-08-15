"""Canonical JSON and content hashing for ElementZero artifacts.

Numeric serialization policy (ADR-0002): finite floats are rendered with
12 significant digits in scientific notation (``format(x, '.12e')``). This
is the documented exception to raw IEEE byte equality: two scientifically
identical values hash identically across platforms, and silent weakening
of reproducibility tests is not allowed.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any

FLOAT_SIGNIFICANT_DIGITS = 12
FLOAT_FORMAT = ".12e"


def canonicalize(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise ValueError("non-finite float is not canonically serializable")
        # Quantize to 12 significant digits, then keep a JSON number (not a string).
        return float(format(obj, FLOAT_FORMAT))
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return {str(k): canonicalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [canonicalize(v) for v in obj]
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return canonicalize(to_dict())
    raise TypeError(f"{type(obj).__name__} is not canonically serializable")


def canonical_json(obj: Any) -> str:
    return json.dumps(
        canonicalize(obj),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_hex(data: bytes | str | Any) -> str:
    if isinstance(data, bytes):
        payload = data
    elif isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = canonical_json(data).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    return sha256_hex(Path(path).read_bytes())


def content_id(prefix: str, payload: Any, length: int = 16) -> str:
    return f"{prefix}_{sha256_hex(payload)[:length]}"
