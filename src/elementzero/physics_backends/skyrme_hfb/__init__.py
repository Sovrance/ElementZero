"""Skyrme mass-oriented refit support (WO-15B stream A).

WO-15 could fit two numbers: the neutron and proton pairing strengths.
That is not a mass fit, and the 9.6 MeV blind MAE said so. Fitting the
bulk of a Skyrme functional needs HFBTHO to accept coupling constants
directly, which its distributed build does not do — the capability
exists upstream behind the ``READ_FUNCTIONAL`` compile flag, off by
default and stale against its own variables module.

The parameterization it exposes is the infinite-nuclear-matter form
used by the UNEDF fits: saturation density and energy, incompressibility,
symmetry energy and its slope, isoscalar effective mass, surface,
pairing and spin-orbit couplings. That is a mass-oriented basis, which
is exactly what this stream needs.
"""

from __future__ import annotations

READ_FUNCTIONAL_BINARY = "hfbtho_readfunc_build"
FUNCTIONAL_FILE = "hfbtho_FUNCTIONAL.dat"

# Column order is fixed by upstream's replace_functional subroutine.
INM_PARAMETER_NAMES = (
    "RHO_NM",
    "E_NM",
    "K_NM",
    "ASS_NM",
    "LASS_NM",
    "SMASS_NM",
    "CrDr_0",
    "CrDr_1",
    "CpV0_0",
    "CpV0_1",
    "CrdJ_0",
    "CrdJ_1",
)

# SkM* as HFBTHO itself derives it, read from the solver's own printed
# nuclear-matter block rather than recomputed here, with the WO-15
# REFIT_STRICT pairing in the CpV0 slots. Equivalence against the
# named-functional binary is verified, not assumed.
SKYRME_BASELINE_INM = {
    "RHO_NM": 0.160318515964671449,
    "E_NM": -15.7762359616147627,
    "K_NM": 216.657542303868979,
    "ASS_NM": 30.0323865018228560,
    "LASS_NM": 45.7703887670942962,
    "SMASS_NM": 1.26826090316085582,
    "CrDr_0": -68.2031250000000000,
    "CrDr_1": 17.1093750000000000,
    "CpV0_0": -325.000000000000000,
    "CpV0_1": -140.000000000000000,
    "CrdJ_0": -97.5000000000000000,
    "CrdJ_1": -32.5000000000000000,
}

BASELINE_SOURCE = (
    "ez-wo15b-skyrme-baseline-v1: the starting vector is HFBTHO's own "
    "nuclear-matter block for SKM*, printed by the solver when run with the "
    "WO-15 REFIT_STRICT pairing, not a value recomputed from the (t,x) "
    "parameters by this repository. Equivalence between the named-functional "
    "binary and the READ_FUNCTIONAL binary fed this vector is checked before "
    "any refit is allowed to run"
)

UPSTREAM_PATCH = (
    "ez-wo15b-hfbtho-readfunc-patch-v1: hfbtho_read_functional.f90 as "
    "distributed reads a variable parameter count into an allocatable "
    "functional_vector, but hfbtho_variables declares n_func_param as a "
    "Parameter (12) and functional_vector as a fixed-size array, so the "
    "subroutine does not compile against its own module. The patch replaces "
    "the assignment-and-allocate with a count check against the declared "
    "size. No physics path is touched, and the equivalence check is what "
    "demonstrates that"
)


def functional_file_text(values: dict[str, float]) -> str:
    """The two-line hfbtho_FUNCTIONAL.dat upstream expects."""
    ordered = [values[name] for name in INM_PARAMETER_NAMES]
    header = "! " + " ".join(INM_PARAMETER_NAMES)
    return header + "\n" + " ".join(repr(v) for v in ordered) + "\n"


__all__ = [
    "BASELINE_SOURCE",
    "FUNCTIONAL_FILE",
    "INM_PARAMETER_NAMES",
    "READ_FUNCTIONAL_BINARY",
    "SKYRME_BASELINE_INM",
    "UPSTREAM_PATCH",
    "functional_file_text",
]
