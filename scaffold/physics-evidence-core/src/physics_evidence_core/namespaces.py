"""Namespace discipline and cross-namespace transform rules.

Hard constraint #6: cross-namespace references require an explicit, typed
transform record. Illegal *promotion* toward higher warrant (e.g.
``effective`` -> ``global`` without a transform) must raise. This module owns
the rule; :mod:`pir.provenance` enforces it when linking facts.

The design keeps two ideas separate:

* **Direction / abstraction rank** — a partial order over namespaces used only
  to name what counts as a *promotion* (raw evidence toward a universal claim).
  A promotion is exactly a transition to a strictly higher rank.
* **Transform requirement** — ANY transition between distinct namespaces needs
  a transform record; a promotion additionally may not be implicit.

We do not hard-code which physical transforms are legal (that is Stage 2's
typed-transform registry). Stage 1 enforces only that the transform is
*declared and typed* when namespaces differ, and that promotions are never
silent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .types import Namespace

# Abstraction rank: raw measured bytes at the bottom, universal/global claims
# at the top. Crossing upward is a "promotion" and must be transform-mediated.
_RANK = {
    Namespace.raw: 0,
    Namespace.apparatus: 1,
    Namespace.operational: 2,
    Namespace.effective: 3,
    Namespace.domain: 4,
    Namespace.latent: 5,
    Namespace.gauge: 5,
    Namespace.invariant: 6,
    Namespace.global_: 7,
    Namespace.analyst: 2,   # annotations live beside operational acts
}


class IllegalNamespacePromotion(Exception):
    """Raised when a fact links across namespaces toward higher warrant without
    a declared, typed transform record."""


@dataclass(frozen=True)
class NamespaceTransform:
    """A typed transform mediating a cross-namespace reference.

    ``type_signature`` is a free string in Stage 1 (e.g.
    ``"effective->global via RG_fixed_point(scale-independent)"``); Stage 2's
    symbolic bridge will refine it into a checkable type.
    """

    name: str
    from_namespace: Namespace
    to_namespace: Namespace
    type_signature: str

    def is_promotion(self) -> bool:
        return _RANK[self.to_namespace] > _RANK[self.from_namespace]


def rank(ns: Namespace) -> int:
    return _RANK[ns]


def is_promotion(from_ns: Namespace, to_ns: Namespace) -> bool:
    """True iff moving ``from_ns`` -> ``to_ns`` increases abstraction rank."""
    return _RANK[to_ns] > _RANK[from_ns]


def require_transform(
    from_ns: Namespace,
    to_ns: Namespace,
    transform: Optional[NamespaceTransform],
) -> None:
    """Validate a cross-namespace reference.

    * Same namespace -> always allowed, transform optional.
    * Different namespaces -> a transform record is REQUIRED and must match the
      endpoints. If the move is a promotion, the transform not being present is
      the classic "illegal promotion" and raises with that name.
    """
    if from_ns == to_ns:
        return
    if transform is None:
        if is_promotion(from_ns, to_ns):
            raise IllegalNamespacePromotion(
                f"illegal promotion {from_ns.value!r} -> {to_ns.value!r}: "
                "a higher-warrant namespace requires an explicit typed "
                "transform record (hard constraint #6)"
            )
        raise IllegalNamespacePromotion(
            f"cross-namespace reference {from_ns.value!r} -> {to_ns.value!r} "
            "requires a declared typed transform record"
        )
    if transform.from_namespace != from_ns or transform.to_namespace != to_ns:
        raise IllegalNamespacePromotion(
            f"transform {transform.name!r} declares "
            f"{transform.from_namespace.value}->{transform.to_namespace.value} "
            f"but the reference is {from_ns.value}->{to_ns.value}"
        )
    if not transform.type_signature:
        raise IllegalNamespacePromotion(
            f"transform {transform.name!r} must carry a non-empty type_signature"
        )
