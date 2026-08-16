"""WO-13 claim taxonomy (spec section 4) and provenance confidence levels.

Claims order by strength; eligibility inheritance always takes the WORST
status in a lineage, so no residual wrapper or combiner can launder nonblind
evidence into a blind claim.
"""

from __future__ import annotations

from elementzero.errors import ProtocolError

# -- claim types (spec section 4) ------------------------------------------- #

STRICT_BLIND = "STRICT_BLIND"
HISTORICAL_BLIND = "HISTORICAL_BLIND"
PARTIALLY_BLIND = "PARTIALLY_BLIND"
NONBLIND_REFERENCE = "NONBLIND_REFERENCE"
RECONSTRUCTION_REFERENCE = "RECONSTRUCTION_REFERENCE"
INELIGIBLE_UNKNOWN_PROVENANCE = "INELIGIBLE_UNKNOWN_PROVENANCE"

CLAIM_TYPES = (
    STRICT_BLIND,
    HISTORICAL_BLIND,
    PARTIALLY_BLIND,
    NONBLIND_REFERENCE,
    RECONSTRUCTION_REFERENCE,
    INELIGIBLE_UNKNOWN_PROVENANCE,
)

# Blind-gate admissible claims. PARTIALLY_BLIND may never satisfy a strict
# blind gate; RECONSTRUCTION_REFERENCE is a deliberate nonblind track.
BLIND_CLAIM_TYPES = (STRICT_BLIND, HISTORICAL_BLIND)

# Severity for worst-of inheritance: higher = worse. UNKNOWN provenance is
# ranked worst of all — unknown is not permission, and a lineage containing
# an unknown link can never be published under any blind or reference label.
_CLAIM_SEVERITY = {
    STRICT_BLIND: 0,
    HISTORICAL_BLIND: 1,
    PARTIALLY_BLIND: 2,
    RECONSTRUCTION_REFERENCE: 3,
    NONBLIND_REFERENCE: 4,
    INELIGIBLE_UNKNOWN_PROVENANCE: 5,
}

# -- provenance confidence (spec section 8) --------------------------------- #

CONFIDENCE_EXACT = "EXACT"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"
CONFIDENCE_UNKNOWN = "UNKNOWN"

PROVENANCE_CONFIDENCE_LEVELS = (
    CONFIDENCE_EXACT,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    CONFIDENCE_UNKNOWN,
)

_CONFIDENCE_RANK = {level: i for i, level in enumerate(PROVENANCE_CONFIDENCE_LEVELS)}

STRICT_BLIND_CONFIDENCE_RULE = (
    "ez-wo13-strict-confidence-v1: STRICT_BLIND requires provenance "
    "confidence EXACT or HIGH; a benchmark-specific policy may permit "
    "HISTORICAL_BLIND from a documented cutoff at lower confidence, but "
    "UNKNOWN provenance blocks every blind claim"
)


def assert_claim_type(value: str) -> str:
    if value not in CLAIM_TYPES:
        raise ProtocolError(f"unknown claim type {value!r}")
    return value


def assert_confidence(value: str) -> str:
    if value not in PROVENANCE_CONFIDENCE_LEVELS:
        raise ProtocolError(f"unknown provenance confidence {value!r}")
    return value


def worst_claim(*claims: str) -> str:
    """The worst (least blind) claim of a lineage. Order-independent."""
    if not claims:
        raise ProtocolError("worst_claim needs at least one claim")
    for claim in claims:
        assert_claim_type(claim)
    return max(claims, key=lambda c: _CLAIM_SEVERITY[c])


def weakest_confidence(*levels: str) -> str:
    if not levels:
        raise ProtocolError("weakest_confidence needs at least one level")
    for level in levels:
        assert_confidence(level)
    return max(levels, key=lambda v: _CONFIDENCE_RANK[v])


def is_blind_claim(claim: str) -> bool:
    return assert_claim_type(claim) in BLIND_CLAIM_TYPES


def strict_gate_eligible(claim: str, confidence: str) -> bool:
    """May this claim enter a strict blind gate?

    STRICT_BLIND needs EXACT/HIGH confidence. HISTORICAL_BLIND is admitted
    only where a benchmark claim manifest allows it (checked by the caller);
    here it needs at least a documented (non-UNKNOWN) confidence.
    """
    assert_claim_type(claim)
    assert_confidence(confidence)
    if claim == STRICT_BLIND:
        return confidence in (CONFIDENCE_EXACT, CONFIDENCE_HIGH)
    if claim == HISTORICAL_BLIND:
        return confidence != CONFIDENCE_UNKNOWN
    return False
