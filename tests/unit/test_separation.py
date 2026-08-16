"""Derived separation observables (WO-10 sections 3, 4, 5).

Every quantity in ``elementzero.physics.separation`` is an algebraic combination
of binding energies, so these tests are written the same way: build a binding
surface from mass excesses, then check the observable against the definition
computed independently from ``binding_energy_MeV``. A test that recomputed the
value with the same helper it is testing would only assert that the function
calls itself.
"""

from __future__ import annotations

import pytest

from elementzero.errors import ProtocolError, SchemaError
from elementzero.physics.conversion import binding_energy_MeV
from elementzero.physics.separation import (
    DERIVED_OBSERVABLES,
    OBSERVABLE_DELTA2N,
    OBSERVABLE_DELTA2P,
    OBSERVABLE_S2N,
    OBSERVABLE_S2P,
    ORIGIN_PREDICTION,
    ORIGIN_TRAINING_TRUTH,
    ORIGIN_TRUTH,
    SEPARATION_POLICY_ID,
    BindingSurface,
    binding_surface,
    computable_points,
    delta2n,
    delta2p,
    derivation_record,
    is_computable,
    observable_inputs,
    observable_value,
    s2n,
    s2p,
    separation_policy,
)

TOL = 1e-9


def _mass_excess(z: int, n: int) -> float:
    """A deterministic, non-symmetric toy surface in keV.

    Asymmetry matters: a surface that is symmetric in Z and N would let a swapped
    S2n/S2p implementation pass.
    """
    return -8000.0 + 137.0 * z - 91.0 * n + 3.5 * z * n - 1.25 * n * n


def _rows(points, origin: str = ORIGIN_TRUTH):
    return [
        {"Z": z, "N": n, "mass_excess_keV": _mass_excess(z, n), "origin": origin}
        for z, n in points
    ]


def _B(z: int, n: int) -> float:
    return binding_energy_MeV(z=z, n=n, mass_excess_keV=_mass_excess(z, n))


def _grid(z_lo=20, z_hi=30, n_lo=24, n_hi=34):
    return [(z, n) for z in range(z_lo, z_hi + 1) for n in range(n_lo, n_hi + 1)]


# --------------------------------------------------------------------------- #
# WO-10 section 4                                                             #
# --------------------------------------------------------------------------- #


def test_S2n_from_binding():
    """S2n(Z,N) = B(Z,N) - B(Z,N-2), in MeV."""
    surface = binding_surface(_rows(_grid()))
    for z in range(22, 29):
        for n in range(26, 33):
            expected = _B(z, n) - _B(z, n - 2)
            assert s2n(surface, z=z, n=n) == pytest.approx(expected, abs=TOL)
            assert observable_value(OBSERVABLE_S2N, surface, z=z, n=n) == pytest.approx(
                expected, abs=TOL
            )
    # It is a *two*-neutron separation: the one-neutron difference is different.
    assert s2n(surface, z=24, n=28) != pytest.approx(_B(24, 28) - _B(24, 27), abs=1e-6)
    # A missing input is None, never a silently wrong number.
    edge = binding_surface(_rows([(24, 28), (24, 30)]))
    assert s2n(edge, z=24, n=30) == pytest.approx(_B(24, 30) - _B(24, 28), abs=TOL)
    assert s2n(edge, z=24, n=28) is None
    assert observable_inputs(OBSERVABLE_S2N, z=24, n=30) == ((24, 30), (24, 28))


def test_S2p_from_binding():
    """S2p(Z,N) = B(Z,N) - B(Z-2,N), in MeV, and it is not S2n."""
    surface = binding_surface(_rows(_grid()))
    for z in range(22, 29):
        for n in range(26, 33):
            expected = _B(z, n) - _B(z - 2, n)
            assert s2p(surface, z=z, n=n) == pytest.approx(expected, abs=TOL)
            assert observable_value(OBSERVABLE_S2P, surface, z=z, n=n) == pytest.approx(
                expected, abs=TOL
            )
            # The toy surface is asymmetric, so a Z/N mix-up would show here.
            assert s2p(surface, z=z, n=n) != pytest.approx(s2n(surface, z=z, n=n), abs=1e-6)
    edge = binding_surface(_rows([(24, 28), (26, 28)]))
    assert s2p(edge, z=26, n=28) == pytest.approx(_B(26, 28) - _B(24, 28), abs=TOL)
    assert s2p(edge, z=24, n=28) is None
    assert observable_inputs(OBSERVABLE_S2P, z=26, n=28) == ((26, 28), (24, 28))


# --------------------------------------------------------------------------- #
# WO-10 section 5                                                             #
# --------------------------------------------------------------------------- #


def test_delta2n_definition():
    """delta2n = S2n(Z,N) - S2n(Z,N+2) = 2B(Z,N) - B(Z,N-2) - B(Z,N+2)."""
    surface = binding_surface(_rows(_grid()))
    for z in range(22, 29):
        for n in range(26, 31):
            from_s2n = s2n(surface, z=z, n=n) - s2n(surface, z=z, n=n + 2)
            expanded = 2.0 * _B(z, n) - _B(z, n - 2) - _B(z, n + 2)
            assert delta2n(surface, z=z, n=n) == pytest.approx(from_s2n, abs=TOL)
            assert delta2n(surface, z=z, n=n) == pytest.approx(expanded, abs=TOL)
    # The three inputs are exactly N-2, N, N+2: this is what makes a half-width
    # one mask leave the two-step neighbors in training.
    assert observable_inputs(OBSERVABLE_DELTA2N, z=24, n=50) == ((24, 48), (24, 50), (24, 52))
    partial = binding_surface(_rows([(24, 48), (24, 50)]))
    assert delta2n(partial, z=24, n=50) is None


def test_delta2p_definition():
    """delta2p = S2p(Z,N) - S2p(Z+2,N) = 2B(Z,N) - B(Z-2,N) - B(Z+2,N)."""
    surface = binding_surface(_rows(_grid()))
    for z in range(22, 27):
        for n in range(26, 33):
            from_s2p = s2p(surface, z=z, n=n) - s2p(surface, z=z + 2, n=n)
            expanded = 2.0 * _B(z, n) - _B(z - 2, n) - _B(z + 2, n)
            assert delta2p(surface, z=z, n=n) == pytest.approx(from_s2p, abs=TOL)
            assert delta2p(surface, z=z, n=n) == pytest.approx(expanded, abs=TOL)
            assert delta2p(surface, z=z, n=n) != pytest.approx(
                delta2n(surface, z=z, n=n), abs=1e-6
            )
    assert observable_inputs(OBSERVABLE_DELTA2P, z=28, n=40) == ((26, 40), (28, 40), (30, 40))
    partial = binding_surface(_rows([(26, 40), (28, 40)]))
    assert delta2p(partial, z=28, n=40) is None


def test_a_linear_binding_surface_has_zero_shell_gap():
    """No curvature, no indicator: delta2n and delta2p vanish on a plane.

    The indicator is a second difference, so it must be blind to any surface that
    is linear in the nucleon numbers. Without this, a global slope would read as
    shell structure everywhere.
    """
    values = {(z, n): 3.0 * z - 2.0 * n + 11.0 for z in range(20, 31) for n in range(24, 35)}
    surface = BindingSurface(values=values, origins=dict.fromkeys(values, ORIGIN_TRUTH))
    for z in range(24, 28):
        for n in range(28, 32):
            assert delta2n(surface, z=z, n=n) == pytest.approx(0.0, abs=TOL)
            assert delta2p(surface, z=z, n=n) == pytest.approx(0.0, abs=TOL)


def test_an_injected_kink_becomes_a_local_indicator_spike():
    """A binding ramp of size g gives delta2n = +2g at the kink and 0 elsewhere.

    This is the algebra the synthetic shell fixture relies on, checked here in
    isolation so a fixture failure and a physics failure cannot be confused.
    """
    gap = 1.5
    closure = 50
    values = {
        (z, n): 5.0 * z + 4.0 * n - gap * max(0, n - closure)
        for z in range(24, 31)
        for n in range(40, 61)
    }
    surface = BindingSurface(values=values, origins=dict.fromkeys(values, ORIGIN_TRUTH))
    for z in range(26, 29):
        assert delta2n(surface, z=z, n=closure) == pytest.approx(2.0 * gap, abs=TOL)
        for other in (closure - 4, closure - 2, closure + 2, closure + 4):
            assert delta2n(surface, z=z, n=other) == pytest.approx(0.0, abs=TOL)


# --------------------------------------------------------------------------- #
# Surfaces, origins, and derivation records                                   #
# --------------------------------------------------------------------------- #


def test_binding_surface_tracks_origins_and_refuses_ambiguity():
    rows = [
        {"Z": 24, "N": 48, "mass_excess_keV": -1.0, "origin": ORIGIN_TRAINING_TRUTH},
        {"Z": 24, "N": 50, "mass_excess_keV": -2.0, "origin": ORIGIN_PREDICTION},
    ]
    surface = binding_surface(rows)
    assert surface.origin(24, 50) == ORIGIN_PREDICTION
    assert surface.origin(24, 48) == ORIGIN_TRAINING_TRUTH
    assert surface.counts_by_origin() == {
        ORIGIN_PREDICTION: 1,
        ORIGIN_TRAINING_TRUTH: 1,
        ORIGIN_TRUTH: 0,
    }
    assert surface.points == [(24, 48), (24, 50)]
    assert (24, 50) in surface
    # A repeated point would let a truth value overwrite a prediction.
    with pytest.raises(ProtocolError):
        binding_surface([*rows, {**rows[1], "origin": ORIGIN_TRUTH}])
    with pytest.raises(SchemaError):
        binding_surface([{**rows[0], "origin": "guess"}])
    with pytest.raises(ProtocolError):
        binding_surface([])


def test_derivation_record_marks_the_value_derived_and_names_its_inputs():
    """WO-10 section 4: a derived observable is not independent evidence."""
    surface = binding_surface(
        [
            {"Z": 24, "N": 48, "mass_excess_keV": _mass_excess(24, 48), "origin": ORIGIN_TRAINING_TRUTH},
            {"Z": 24, "N": 50, "mass_excess_keV": _mass_excess(24, 50), "origin": ORIGIN_PREDICTION},
            {"Z": 24, "N": 52, "mass_excess_keV": _mass_excess(24, 52), "origin": ORIGIN_TRAINING_TRUTH},
        ]
    )
    record = derivation_record(OBSERVABLE_DELTA2N, surface, z=24, n=50)
    assert record["derived"] is True
    assert record["independent_evidence"] is False
    assert record["observable"] == OBSERVABLE_DELTA2N
    assert record["separation_policy_id"] == SEPARATION_POLICY_ID
    assert record["derived_from"] == ["Z24-N48", "Z24-N50", "Z24-N52"]
    assert record["input_origins"] == [
        ORIGIN_TRAINING_TRUTH,
        ORIGIN_PREDICTION,
        ORIGIN_TRAINING_TRUTH,
    ]
    assert record["computable"] is True
    assert record["value_MeV"] == pytest.approx(delta2n(surface, z=24, n=50), abs=TOL)
    assert "not independent evidence" in record["derivation_rule"]
    # An incomputable value is still recorded, with the missing input named.
    missing = derivation_record(OBSERVABLE_DELTA2N, surface, z=24, n=52)
    assert missing["computable"] is False
    assert missing["value_MeV"] is None
    assert {"nuclide_id": "Z24-N54", "Z": 24, "N": 54, "origin": None, "present": False} in missing[
        "inputs"
    ]


def test_is_computable_and_computable_points_follow_the_input_geometry():
    surface = binding_surface(_rows([(24, 46), (24, 48), (24, 50)]))
    assert is_computable(surface, OBSERVABLE_DELTA2N, z=24, n=48)
    assert not is_computable(surface, OBSERVABLE_DELTA2N, z=24, n=50)
    assert computable_points(OBSERVABLE_DELTA2N, surface) == [(24, 48)]
    assert computable_points(OBSERVABLE_S2N, surface, candidates=[(24, 48), (24, 46)]) == [
        (24, 48)
    ]


def test_unsupported_observables_are_refused():
    surface = binding_surface(_rows([(24, 48)]))
    for bad in ("S1n", "delta2", "mass_excess_keV"):
        with pytest.raises(SchemaError):
            observable_value(bad, surface, z=24, n=48)
        with pytest.raises(SchemaError):
            observable_inputs(bad, z=24, n=48)


def test_separation_policy_declares_everything_derived():
    policy = separation_policy()
    assert policy["separation_policy_id"] == SEPARATION_POLICY_ID
    assert policy["observables"] == list(DERIVED_OBSERVABLES)
    assert policy["units"] == "MeV"
    assert policy["derived"] is True
    assert policy["independent_evidence"] is False
    assert "No model is trained on a derived target" in policy["training_rule"]
    assert "not proof of a magic number" in policy["shell_indicator_caveat"]
    for observable in DERIVED_OBSERVABLES:
        assert observable in policy["definitions"]
