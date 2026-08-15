"""Pinned unit-conversion constants.

A constants change creates a new normalization version. These values are
engineering pins for ElementZero v0.2, not a claim about a unique CODATA
edition being the only admissible set.
"""

from __future__ import annotations

NORMALIZER_VERSION = "ez-norm-v1"

# Atomic mass unit energy equivalents.
U_TO_MEV = 931.49410242
U_TO_KEV = 931494.10242

# Hydrogen-1 atomic mass and neutron mass in unified atomic mass units.
M_H_U = 1.00782503224
M_N_U = 1.00866491595

CONSTANTS_MANIFEST = {
    "normalizer_version": NORMALIZER_VERSION,
    "u_to_MeV": U_TO_MEV,
    "u_to_keV": U_TO_KEV,
    "m_H_u": M_H_U,
    "m_n_u": M_N_U,
}
