from __future__ import annotations
import math
# Pinned scaffold constants. Real runs must bind constants to a normalization manifest.
M_H_U = 1.00782503223
M_N_U = 1.00866491595
U_TO_MEV = 931.49410242

def mass_excess_to_binding_mev(Z,N,mass_excess_keV):
    A=Z+N
    M_atom_u=A + (mass_excess_keV/1000.0)/U_TO_MEV
    return (Z*M_H_U + N*M_N_U - M_atom_u)*U_TO_MEV

def binding_to_mass_excess_kev(Z,N,binding_mev):
    A=Z+N
    me_mev=(Z*M_H_U + N*M_N_U - A)*U_TO_MEV - binding_mev
    return 1000.0*me_mev

def pairing_sign(Z,N):
    if Z%2==0 and N%2==0: return 1.0
    if Z%2==1 and N%2==1: return -1.0
    return 0.0
