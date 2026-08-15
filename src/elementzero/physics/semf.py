"""Semi-empirical mass formula (SEMF) with least-squares coefficient fit.

ASCII-first:

    A = Z + N
    B(Z,N) = a_v*A
           - a_s*A^(2/3)
           - a_c*Z*(Z-1)/A^(1/3)
           - a_a*(N-Z)^2/A
           + a_p*pairing_sign/sqrt(A)

    pairing_sign = +1  even-even
    pairing_sign = -1  odd-odd
    pairing_sign =  0  otherwise
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from elementzero.data.observations import MassObservation
from elementzero.physics.conversion import binding_energy_MeV, mass_excess_keV_from_binding

MODEL_ID_SEMF_LS = "EZ-SEMF-LS-v1"


def pairing_sign(z: int, n: int) -> int:
    z_even = int(z) % 2 == 0
    n_even = int(n) % 2 == 0
    if z_even and n_even:
        return 1
    if (not z_even) and (not n_even):
        return -1
    return 0


def design_row(z: int, n: int) -> list[float]:
    a = float(int(z) + int(n))
    if a <= 0:
        raise ValueError("A must be positive")
    return [
        a,
        -(a ** (2.0 / 3.0)),
        -(int(z) * (int(z) - 1)) / (a ** (1.0 / 3.0)),
        -((int(n) - int(z)) ** 2) / a,
        pairing_sign(z, n) / (a ** 0.5),
    ]


@dataclass(frozen=True)
class SEMFCoefficients:
    a_v: float
    a_s: float
    a_c: float
    a_a: float
    a_p: float

    def to_dict(self) -> dict[str, float]:
        return {
            "a_v": self.a_v,
            "a_s": self.a_s,
            "a_c": self.a_c,
            "a_a": self.a_a,
            "a_p": self.a_p,
        }

    def as_array(self) -> np.ndarray:
        return np.array([self.a_v, self.a_s, self.a_c, self.a_a, self.a_p], dtype=float)


def binding_MeV(z: int, n: int, coeffs: SEMFCoefficients) -> float:
    row = np.array(design_row(z, n), dtype=float)
    return float(row @ coeffs.as_array())


def mass_excess_keV(z: int, n: int, coeffs: SEMFCoefficients) -> float:
    return mass_excess_keV_from_binding(z=z, n=n, binding_MeV=binding_MeV(z, n, coeffs))


def fit_semf(observations: Sequence[MassObservation]) -> SEMFCoefficients:
    if len(observations) < 5:
        raise ValueError("SEMF least-squares fit requires at least 5 nuclides")
    x = np.array([design_row(o.Z, o.N) for o in observations], dtype=float)
    y = np.array(
        [binding_energy_MeV(z=o.Z, n=o.N, mass_excess_keV=o.mass_excess_keV) for o in observations],
        dtype=float,
    )
    coeffs, *_ = np.linalg.lstsq(x, y, rcond=None)
    return SEMFCoefficients(*[float(c) for c in coeffs])


def semf_manifest(coeffs: SEMFCoefficients) -> dict[str, Any]:
    return {"model_id": MODEL_ID_SEMF_LS, "coefficients": coeffs.to_dict()}
