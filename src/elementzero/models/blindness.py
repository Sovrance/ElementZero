"""Blindness tiers and inheritance (v2).

The WO-13 rule, promoted from a report finding to enforced code:

    A target hidden from ElementZero is not automatically blind to an
    imported physics table.

A published global mass model was itself fitted to an atomic mass evaluation.
If a target is inside that fit set, the model has already seen the answer, and
wrapping it in a blind residual learner does not restore blindness. This is the
temporal-leakage problem, and it is the reason v2 refuses to publish one mixed
leaderboard.

TIERS (ordered worst-to-best is the inverse of this list)

    A_STRICT_BLIND          fit cutoff strictly precedes the truth edition, and
                            the target was not in the fit set
    B_PARTIAL_BLIND         some targets blind, some not; scored separately
    C_NONBLIND_REFERENCE    the model saw the truth; useful as a reference,
                            never as a blind claim
    D_RECONSTRUCTION        reconstruction of withheld-but-known values where
                            blindness is not claimed at all
    E_INELIGIBLE_UNKNOWN    fit-set membership unknown; never assumed blind

Combination inherits the WORST contributor. An ensemble containing one
non-blind member is not blind, and it may not be reweighted into blindness.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

BLINDNESS_MODULE_VERSION = "ez-blind-v2.0.0"

TIER_A = "A_STRICT_BLIND"
TIER_B = "B_PARTIAL_BLIND"
TIER_C = "C_NONBLIND_REFERENCE"
TIER_D = "D_RECONSTRUCTION"
TIER_E = "E_INELIGIBLE_UNKNOWN"

# Lower rank == stronger claim. Combination takes the maximum rank present.
_TIER_RANK = {TIER_A: 0, TIER_B: 1, TIER_C: 2, TIER_D: 3, TIER_E: 4}

CLAIM_ELIGIBLE_TIERS = frozenset({TIER_A})


class BlindnessError(RuntimeError):
    """Raised when a claim is attempted from an ineligible tier."""


@dataclass(frozen=True)
class BackboneProvenance:
    """What a physics backbone was fitted to, and how confidently we know it."""

    backbone_id: str
    independence_group: str
    fit_edition: str | None  # e.g. "AME2020"; None when unfitted (pure theory)
    fit_year: int | None
    fit_set_known: bool  # can we enumerate exactly which nuclides it was fit to?
    refit_cutoff: str | None = None  # set for EZ historical refit builds

    def to_dict(self) -> dict[str, Any]:
        return {
            "backbone_id": self.backbone_id,
            "independence_group": self.independence_group,
            "fit_edition": self.fit_edition,
            "fit_year": self.fit_year,
            "fit_set_known": self.fit_set_known,
            "refit_cutoff": self.refit_cutoff,
        }


def resolve_tier(
    provenance: BackboneProvenance,
    truth_edition: str,
    truth_year: int,
    target_in_fit_set: bool | None = None,
) -> str:
    """Blindness tier of one backbone against one truth edition.

    `target_in_fit_set=None` means membership is unknown, which is decisive:
    unknown provenance is never promoted to blind.
    """
    effective_cutoff = provenance.refit_cutoff or provenance.fit_edition

    if effective_cutoff is None:
        # A model with no empirical fit cannot have seen the target.
        return TIER_A

    if not provenance.fit_set_known and target_in_fit_set is None:
        return TIER_E

    if target_in_fit_set is True:
        return TIER_C

    cutoff_year = provenance.fit_year
    if provenance.refit_cutoff is not None and cutoff_year is None:
        raise ValueError("a refit build must record fit_year")

    if cutoff_year is not None and cutoff_year < truth_year:
        return TIER_A if target_in_fit_set is False else TIER_E

    if cutoff_year is not None and cutoff_year >= truth_year:
        return TIER_C

    return TIER_E


def combine_tiers(tiers: Iterable[str]) -> str:
    """A combination inherits its worst contributor. No reweighting escape."""
    tier_list = list(tiers)
    if not tier_list:
        raise ValueError("cannot combine an empty tier set")
    unknown = sorted(set(tier_list) - set(_TIER_RANK))
    if unknown:
        raise ValueError(f"unknown blindness tiers: {unknown}")
    return max(tier_list, key=lambda t: _TIER_RANK[t])


def independence_groups(provenances: Sequence[BackboneProvenance], tiers: Sequence[str]) -> set[str]:
    """Distinct physics-independence groups among strictly blind backbones.

    v2 Gate G2 requires at least two. WO-13 found exactly one
    (`macroscopic_microscopic_frdm`), which is why the historical-refit work
    order exists rather than a relaxation of the blind definition.
    """
    if len(provenances) != len(tiers):
        raise ValueError("provenances and tiers must have equal length")
    return {p.independence_group for p, t in zip(provenances, tiers) if t in CLAIM_ELIGIBLE_TIERS}


def assert_claim_eligible(tier: str, claim: str) -> None:
    if tier not in CLAIM_ELIGIBLE_TIERS:
        raise BlindnessError(
            f"claim {claim!r} requires tier in {sorted(CLAIM_ELIGIBLE_TIERS)}, got {tier!r}; "
            "report the result in its own section instead of promoting it"
        )
