"""Generic content-addressed scientific certificates."""
from __future__ import annotations
from typing import Any, Dict
from .canonical import canonical_json, sha256_hex

VOLATILE_KEYS = frozenset({"created_at","generated_at","timestamp_utc","wall_time_s"})

def certificate_content(body: Dict[str, Any]) -> Dict[str, Any]:
    return {k:v for k,v in body.items() if k not in VOLATILE_KEYS and k != "content_sha256"}

def create_certificate(body: Dict[str, Any]) -> Dict[str, Any]:
    out=dict(body)
    out["content_sha256"] = sha256_hex(certificate_content(out))
    return out

def verify_certificate(cert: Dict[str, Any]) -> bool:
    expected=cert.get("content_sha256")
    return bool(expected) and expected == sha256_hex(certificate_content(cert))

def scientific_identity(cert: Dict[str, Any]) -> str:
    return sha256_hex(certificate_content(cert))
