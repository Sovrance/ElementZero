"""ElementZero protocol and leakage errors."""

from __future__ import annotations


class ElementZeroError(Exception):
    """Base error for ElementZero protocol failures."""


class LeakageError(ElementZeroError):
    """Raised when later truth or a forbidden field enters a blind stage."""


class ProtocolError(ElementZeroError):
    """Raised when a benchmark stage is used out of order or inconsistently."""


class SchemaError(ElementZeroError):
    """Raised when a manifest or certificate fails schema validation."""


class AtlasContractError(ElementZeroError):
    """Raised when the Atlas PIR pin or public surface is not usable."""


class VisualError(ElementZeroError):
    """Raised when visual-table extraction, aggregation, or render fails."""
