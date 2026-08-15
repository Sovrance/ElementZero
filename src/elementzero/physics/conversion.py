"""Atomic mass / binding-energy conversion using pinned constants.

ASCII-first normative equations:

    M_atom_u = A + mass_excess_keV / u_to_keV
    B_MeV = (Z*m_H_u + N*m_n_u - M_atom_u) * u_to_MeV

Inverse:

    mass_excess_MeV = (Z*m_H_u + N*m_n_u - A) * u_to_MeV - B_MeV
    mass_excess_keV = 1000 * mass_excess_MeV
"""

from __future__ import annotations

from .constants import M_H_U, M_N_U, U_TO_KEV, U_TO_MEV


def atomic_mass_u(*, a: int, mass_excess_keV: float) -> float:
    return float(a) + float(mass_excess_keV) / U_TO_KEV


def binding_energy_MeV(*, z: int, n: int, mass_excess_keV: float) -> float:
    a = int(z) + int(n)
    m_atom_u = atomic_mass_u(a=a, mass_excess_keV=mass_excess_keV)
    return (int(z) * M_H_U + int(n) * M_N_U - m_atom_u) * U_TO_MEV


def mass_excess_keV_from_binding(*, z: int, n: int, binding_MeV: float) -> float:
    a = int(z) + int(n)
    mass_excess_MeV = (int(z) * M_H_U + int(n) * M_N_U - a) * U_TO_MEV - float(binding_MeV)
    return 1000.0 * mass_excess_MeV
