"""Canonical JSON + content-addressing (hard constraint #9).

The store is content-addressed, so serialization must be *bit-for-bit stable*
across machines and Python builds. Rules:

* keys sorted;
* exact rationals (:class:`fractions.Fraction`) serialized as strings ``"p/q"``
  in lowest terms with an explicit denominator -- NEVER as floats;
* floats rendered with :func:`repr` (Python guarantees the shortest round-trip
  string since 3.1) and rejected when non-finite;
* tuples treated as lists;
* enums reduced to their ``.value``.

A fact/artifact ID is ``<prefix>_sha256_<first 16 hex of the digest>`` of the
canonical bytes of its *content + provenance skeleton*, so identical evidence
lands on identical IDs regardless of who computed it.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from fractions import Fraction
from typing import Any


def _canonicalize(obj: Any) -> Any:
    """Recursively convert ``obj`` into a JSON-safe, canonical structure."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Fraction):
        # Lowest-terms string with explicit denominator, e.g. "7/1250", "3".
        return f"{obj.numerator}/{obj.denominator}"
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise ValueError(
                "non-finite float is not canonically serializable; use an "
                "exact Fraction or a bounded interval instead"
            )
        return obj
    if isinstance(obj, str) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _canonicalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(v) for v in obj]
    # Dataclass-like: fall back to a `to_dict` if present.
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return _canonicalize(to_dict())
    raise TypeError(f"object of type {type(obj).__name__} is not canonical-JSON serializable")


def canonical_json(obj: Any) -> str:
    """Deterministic UTF-8 JSON string: sorted keys, no incidental whitespace."""
    return json.dumps(
        _canonicalize(obj),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(obj: Any) -> bytes:
    return canonical_json(obj).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    """Full sha256 hex digest of the canonical bytes of ``obj``."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def content_id(prefix: str, payload: Any, length: int = 16) -> str:
    """Content-addressed ID: ``<prefix>_sha256_<digest[:length]>``."""
    digest = sha256_hex(payload)
    return f"{prefix}_sha256_{digest[:length]}"


def parse_fraction(value: str) -> Fraction:
    """Inverse of the Fraction serialization; accepts ``"p/q"`` or ``"p"``."""
    return Fraction(value)
