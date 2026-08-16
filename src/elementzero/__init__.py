"""ElementZero: nuclear-mass prediction with Atlas PIR evidence."""

from __future__ import annotations

__version__ = "0.2.0"
__atlas_pir_contract__ = "0.1.0"

BENCHMARK_EZ_B001 = "EZ-B001"
BENCHMARK_EZ_B001_TITLE = "EZ-B001 — Historical Nuclear Mass Prediction"
LEGACY_ZME_B001 = "ZME-B001"

BENCHMARK_EZ_B002 = "EZ-B002"
BENCHMARK_EZ_B002_TITLE = "EZ-B002 — Geographic Nuclear-Chart Holdout"

BENCHMARK_EZ_B003 = "EZ-B003"
BENCHMARK_EZ_B003_TITLE = "EZ-B003 — Hidden Shell Rediscovery Challenge"

# Scoring/evidence protocol version. Bump this when the protocol changes and
# rerun every comparable epoch; never reuse it across incompatible protocols.
BENCHMARK_PROTOCOL_VERSION = "0.3.0"

# EZ-B002 experiment protocol version (WO-09). v1 is characterization only: it
# declares no accuracy pass/fail threshold.
B002_PROTOCOL_VERSION = "1.0.0"

# EZ-B003 experiment protocol version (WO-10). v1 preregisters a rediscovery
# criterion whose thresholds are frozen on synthetic mechanics before any closure
# of an evaluated mass table is scored.
B003_PROTOCOL_VERSION = "1.0.0"

__all__ = [
    "__version__",
    "__atlas_pir_contract__",
    "B002_PROTOCOL_VERSION",
    "B003_PROTOCOL_VERSION",
    "BENCHMARK_EZ_B001",
    "BENCHMARK_EZ_B001_TITLE",
    "BENCHMARK_EZ_B002",
    "BENCHMARK_EZ_B002_TITLE",
    "BENCHMARK_EZ_B003",
    "BENCHMARK_EZ_B003_TITLE",
    "BENCHMARK_PROTOCOL_VERSION",
    "LEGACY_ZME_B001",
]
