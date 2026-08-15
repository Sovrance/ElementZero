"""Canonical nuclide identity.

A = Z + N
nuclide_id = "Z{Z}-N{N}"

Element symbol/name is metadata and is never canonical identity.
"""

from __future__ import annotations

from dataclasses import dataclass


def nuclide_id(z: int, n: int) -> str:
    if z < 0 or n < 0:
        raise ValueError(f"Z and N must be non-negative, got Z={z} N={n}")
    return f"Z{int(z)}-N{int(n)}"


def mass_number(z: int, n: int) -> int:
    return int(z) + int(n)


def parse_nuclide_id(value: str) -> tuple[int, int]:
    if not value.startswith("Z") or "-N" not in value:
        raise ValueError(f"invalid nuclide_id {value!r}; expected Z{{Z}}-N{{N}}")
    z_part, n_part = value.split("-N", 1)
    z = int(z_part[1:])
    n = int(n_part)
    return z, n


def validate_a(z: int, n: int, a: int) -> None:
    expected = mass_number(z, n)
    if int(a) != expected:
        raise ValueError(f"A={a} is inconsistent with Z={z} N={n} (A must equal Z+N={expected})")


@dataclass(frozen=True)
class NuclideIdentity:
    Z: int
    N: int

    @property
    def A(self) -> int:
        return self.Z + self.N

    @property
    def nuclide_id(self) -> str:
        return nuclide_id(self.Z, self.N)

    def to_dict(self) -> dict:
        return {
            "nuclide_id": self.nuclide_id,
            "Z": self.Z,
            "N": self.N,
            "A": self.A,
        }

    @classmethod
    def from_zn(cls, z: int, n: int) -> NuclideIdentity:
        return cls(Z=int(z), N=int(n))
