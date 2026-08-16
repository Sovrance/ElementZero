"""Two-nucleon separation energies and shell-gap indicators (EZ-B003, WO-10).

Every quantity here is *derived*. Nothing in this module is a new measurement:
each value is an algebraic combination of binding energies that are themselves
algebraic combinations of mass excesses (``physics/conversion.py``). A large
``delta2n`` is therefore not independent evidence from the masses it was built
from, and Atlas provenance must say so (WO-10 section 4).

ASCII-first normative equations:

    B(Z,N)        = binding_energy_MeV(z=Z, n=N, mass_excess_keV=...)

    S2n(Z,N)      = B(Z,N)   - B(Z,N-2)
    S2p(Z,N)      = B(Z,N)   - B(Z-2,N)

    delta2n(Z,N)  = S2n(Z,N) - S2n(Z,N+2)
                  = 2*B(Z,N) - B(Z,N-2) - B(Z,N+2)
    delta2p(Z,N)  = S2p(Z,N) - S2p(Z+2,N)
                  = 2*B(Z,N) - B(Z-2,N) - B(Z+2,N)

The expanded forms are the reason a neighborhood mask of half-width one is
enough to make the indicator at a closure a genuine prediction: at ``N = N0``
only ``B(Z,N0)`` is withheld, while ``B(Z,N0-2)`` and ``B(Z,N0+2)`` stay in the
training corpus. The predicted indicator is then a frozen, preregistered mix of
one predicted mass and two training masses, and the direction of that mix is
fixed before any hidden truth is read.

A large positive local change in delta2n or delta2p can indicate shell
structure. It does not establish a magic number: every local maximum of a noisy
surface is a local maximum of something (WO-10 section 5).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from elementzero.errors import ProtocolError, SchemaError
from elementzero.physics.conversion import binding_energy_MeV

SEPARATION_POLICY_ID = "ez-b003-separation-observables-v1"

OBSERVABLE_S2N = "S2n"
OBSERVABLE_S2P = "S2p"
OBSERVABLE_DELTA2N = "delta2n"
OBSERVABLE_DELTA2P = "delta2p"
DERIVED_OBSERVABLES: tuple[str, ...] = (
    OBSERVABLE_S2N,
    OBSERVABLE_S2P,
    OBSERVABLE_DELTA2N,
    OBSERVABLE_DELTA2P,
)

# Origin labels for the points of a binding surface. "prediction" marks a point
# a model supplied for a masked nucleus; "training_truth" marks a point the
# freeze already allowed the model to see; "truth" marks a point read from the
# snapshot after the run was sealed.
ORIGIN_PREDICTION = "prediction"
ORIGIN_TRAINING_TRUTH = "training_truth"
ORIGIN_TRUTH = "truth"
ORIGINS: tuple[str, ...] = (ORIGIN_PREDICTION, ORIGIN_TRAINING_TRUTH, ORIGIN_TRUTH)

DERIVED_OBSERVABLE_RULE = (
    "ez-b003-derived-observable-v1: S2n, S2p, delta2n, and delta2p are algebraic "
    "combinations of the binding energies used to compute them, and those binding "
    "energies are algebraic combinations of mass excesses. A derived observable is "
    "not independent evidence from its inputs: it re-expresses them. Atlas facts "
    "for these quantities carry derived = true, independent_evidence = false, and "
    "the exact input identities."
)

SHELL_INDICATOR_CAVEAT = (
    "A large positive local change in delta2n or delta2p is consistent with shell "
    "structure; it is not proof of a magic number. No local maximum is promoted to "
    "a closure claim, and no p-value is reported without a preregistered null model."
)

Point = tuple[int, int]


# --------------------------------------------------------------------------- #
# Binding surface                                                             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BindingSurface:
    """(Z, N) -> binding energy in MeV, with the origin of every point.

    The origins are load-bearing rather than decorative: a derived observable is
    only interesting when at least one of its inputs was withheld, and a scoring
    report has to be able to say which inputs those were.
    """

    values: Mapping[Point, float]
    origins: Mapping[Point, str]

    def __post_init__(self) -> None:
        missing = sorted(set(self.values) - set(self.origins))
        if missing:
            raise SchemaError(f"binding surface points without an origin: {missing[:5]}")
        unknown = sorted({o for o in self.origins.values() if o not in ORIGINS})
        if unknown:
            raise SchemaError(f"unsupported binding-surface origins: {unknown}")

    def __contains__(self, point: object) -> bool:
        return point in self.values

    def get(self, z: int, n: int) -> float | None:
        return self.values.get((int(z), int(n)))

    def origin(self, z: int, n: int) -> str | None:
        return self.origins.get((int(z), int(n)))

    @property
    def points(self) -> list[Point]:
        return sorted(self.values)

    def counts_by_origin(self) -> dict[str, int]:
        return {
            origin: sum(1 for value in self.origins.values() if value == origin)
            for origin in ORIGINS
        }


def binding_energy_from_mass_excess(*, z: int, n: int, mass_excess_keV: float) -> float:
    """B(Z,N) in MeV from a mass excess in keV, using the pinned constants."""
    return binding_energy_MeV(z=z, n=n, mass_excess_keV=float(mass_excess_keV))


def binding_surface(rows: Iterable[Mapping[str, Any]]) -> BindingSurface:
    """Build a binding surface from ``{Z, N, mass_excess_keV, origin}`` rows.

    A repeated (Z, N) is refused instead of being resolved by iteration order:
    silently letting one row win is exactly how a predicted value would be
    overwritten by the truth it is supposed to be compared against.
    """
    values: dict[Point, float] = {}
    origins: dict[Point, str] = {}
    for row in rows:
        z, n = int(row["Z"]), int(row["N"])
        origin = str(row.get("origin", ORIGIN_TRUTH))
        if origin not in ORIGINS:
            raise SchemaError(f"unsupported binding-surface origin {origin!r}")
        point = (z, n)
        if point in values:
            raise ProtocolError(
                f"binding surface received two values for Z{z}-N{n} "
                f"({origins[point]} and {origin}); a surface point must be unambiguous"
            )
        values[point] = binding_energy_from_mass_excess(
            z=z, n=n, mass_excess_keV=float(row["mass_excess_keV"])
        )
        origins[point] = origin
    if not values:
        raise ProtocolError("a binding surface needs at least one point")
    return BindingSurface(values=values, origins=origins)


# --------------------------------------------------------------------------- #
# Input geometry                                                              #
# --------------------------------------------------------------------------- #


def s2n_inputs(z: int, n: int) -> tuple[Point, ...]:
    return ((int(z), int(n)), (int(z), int(n) - 2))


def s2p_inputs(z: int, n: int) -> tuple[Point, ...]:
    return ((int(z), int(n)), (int(z) - 2, int(n)))


def delta2n_inputs(z: int, n: int) -> tuple[Point, ...]:
    return ((int(z), int(n) - 2), (int(z), int(n)), (int(z), int(n) + 2))


def delta2p_inputs(z: int, n: int) -> tuple[Point, ...]:
    return ((int(z) - 2, int(n)), (int(z), int(n)), (int(z) + 2, int(n)))


INPUT_GEOMETRY = {
    OBSERVABLE_S2N: s2n_inputs,
    OBSERVABLE_S2P: s2p_inputs,
    OBSERVABLE_DELTA2N: delta2n_inputs,
    OBSERVABLE_DELTA2P: delta2p_inputs,
}

DEFINITIONS = {
    OBSERVABLE_S2N: "S2n(Z,N) = B(Z,N) - B(Z,N-2)",
    OBSERVABLE_S2P: "S2p(Z,N) = B(Z,N) - B(Z-2,N)",
    OBSERVABLE_DELTA2N: "delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2) = 2*B(Z,N) - B(Z,N-2) - B(Z,N+2)",
    OBSERVABLE_DELTA2P: "delta2p(Z,N) = S2p(Z,N) - S2p(Z+2,N) = 2*B(Z,N) - B(Z-2,N) - B(Z+2,N)",
}


def observable_inputs(observable: str, *, z: int, n: int) -> tuple[Point, ...]:
    if observable not in INPUT_GEOMETRY:
        raise SchemaError(
            f"unsupported derived observable {observable!r}; supported are {list(DERIVED_OBSERVABLES)}"
        )
    return INPUT_GEOMETRY[observable](z, n)


def is_computable(surface: BindingSurface, observable: str, *, z: int, n: int) -> bool:
    """True when every input point of the observable is on the surface."""
    return all(point in surface for point in observable_inputs(observable, z=z, n=n))


def computable_points(
    observable: str,
    surface: BindingSurface,
    *,
    candidates: Sequence[Point] | None = None,
) -> list[Point]:
    points = sorted(candidates) if candidates is not None else surface.points
    return [p for p in points if is_computable(surface, observable, z=p[0], n=p[1])]


# --------------------------------------------------------------------------- #
# The observables                                                             #
# --------------------------------------------------------------------------- #


def s2n(surface: BindingSurface, *, z: int, n: int) -> float | None:
    """B(Z,N) - B(Z,N-2) in MeV, or None when an input is missing."""
    here, below = (surface.get(z, n), surface.get(z, n - 2))
    if here is None or below is None:
        return None
    return here - below


def s2p(surface: BindingSurface, *, z: int, n: int) -> float | None:
    """B(Z,N) - B(Z-2,N) in MeV, or None when an input is missing."""
    here, below = (surface.get(z, n), surface.get(z - 2, n))
    if here is None or below is None:
        return None
    return here - below


def delta2n(surface: BindingSurface, *, z: int, n: int) -> float | None:
    """S2n(Z,N) - S2n(Z,N+2) in MeV, or None when an input is missing."""
    here = s2n(surface, z=z, n=n)
    above = s2n(surface, z=z, n=n + 2)
    if here is None or above is None:
        return None
    return here - above


def delta2p(surface: BindingSurface, *, z: int, n: int) -> float | None:
    """S2p(Z,N) - S2p(Z+2,N) in MeV, or None when an input is missing."""
    here = s2p(surface, z=z, n=n)
    above = s2p(surface, z=z + 2, n=n)
    if here is None or above is None:
        return None
    return here - above


OBSERVABLE_FUNCTIONS = {
    OBSERVABLE_S2N: s2n,
    OBSERVABLE_S2P: s2p,
    OBSERVABLE_DELTA2N: delta2n,
    OBSERVABLE_DELTA2P: delta2p,
}


def observable_value(
    observable: str, surface: BindingSurface, *, z: int, n: int
) -> float | None:
    if observable not in OBSERVABLE_FUNCTIONS:
        raise SchemaError(
            f"unsupported derived observable {observable!r}; supported are {list(DERIVED_OBSERVABLES)}"
        )
    return OBSERVABLE_FUNCTIONS[observable](surface, z=z, n=n)


# --------------------------------------------------------------------------- #
# Derivation records                                                          #
# --------------------------------------------------------------------------- #


def derivation_record(
    observable: str,
    surface: BindingSurface,
    *,
    z: int,
    n: int,
) -> dict[str, Any]:
    """One derived value plus the exact inputs and their origins.

    The record is the unit that Atlas stores, which is why it carries
    ``derived`` and ``independent_evidence`` explicitly: a reader of the evidence
    graph must not have to infer that a shell gap is a re-expression of masses.
    """
    inputs = observable_inputs(observable, z=z, n=n)
    value = observable_value(observable, surface, z=z, n=n)
    input_records = [
        {
            "nuclide_id": f"Z{iz}-N{inn}",
            "Z": iz,
            "N": inn,
            "origin": surface.origin(iz, inn),
            "present": (iz, inn) in surface,
        }
        for iz, inn in inputs
    ]
    return {
        "observable": observable,
        "separation_policy_id": SEPARATION_POLICY_ID,
        "definition": DEFINITIONS[observable],
        "nuclide_id": f"Z{int(z)}-N{int(n)}",
        "Z": int(z),
        "N": int(n),
        "value_MeV": value,
        "computable": value is not None,
        "derived": True,
        "independent_evidence": False,
        "derived_from": [r["nuclide_id"] for r in input_records],
        "input_origins": [r["origin"] for r in input_records],
        "inputs": input_records,
        "derivation_rule": DERIVED_OBSERVABLE_RULE,
    }


def separation_policy() -> dict[str, Any]:
    """The frozen description of these observables, for a preregistration."""
    return {
        "separation_policy_id": SEPARATION_POLICY_ID,
        "observables": list(DERIVED_OBSERVABLES),
        "definitions": dict(DEFINITIONS),
        "units": "MeV",
        "binding_energy_source": "src/elementzero/physics/conversion.py::binding_energy_MeV",
        "derived": True,
        "independent_evidence": False,
        "derivation_rule": DERIVED_OBSERVABLE_RULE,
        "shell_indicator_caveat": SHELL_INDICATOR_CAVEAT,
        "training_rule": (
            "No model is trained on a derived target. Models predict mass excess; "
            "binding energy and every separation observable are computed afterwards."
        ),
    }
