"""ElementZero: nuclear-mass prediction with Atlas PIR evidence."""

from __future__ import annotations

__version__ = "0.2.0"
__atlas_pir_contract__ = "0.1.0"

BENCHMARK_EZ_B001 = "EZ-B001"
BENCHMARK_EZ_B001_TITLE = "EZ-B001 — Historical Nuclear Mass Prediction"
LEGACY_ZME_B001 = "ZME-B001"

# Scoring/evidence protocol version. Bump this when the protocol changes and
# rerun every comparable epoch; never reuse it across incompatible protocols.
BENCHMARK_PROTOCOL_VERSION = "0.3.0"

__all__ = [
    "__version__",
    "__atlas_pir_contract__",
    "BENCHMARK_EZ_B001",
    "BENCHMARK_EZ_B001_TITLE",
    "BENCHMARK_PROTOCOL_VERSION",
    "LEGACY_ZME_B001",
]
