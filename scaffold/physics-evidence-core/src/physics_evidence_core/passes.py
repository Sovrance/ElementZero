"""Pass registry + honesty layer (Stage 1, P1c).

A *pass* is an analyzer that reads facts and asserts new ones. Every registered
pass declares a SOUND/HEURISTIC tag (hard constraint #4). The registry enforces
the honesty rules at the boundary where a pass hands a fact to the store, so a
misbehaving pass is caught even if a hand-built ``Fact`` slipped through:

* a SOUND pass may only emit E0/E1/E2 facts (it must certify what it asserts);
* a HEURISTIC pass may not emit an E0 fact, and any E3/E4 fact it emits must
  carry located ``warnings``;
* the verdict on any emitted fact is locked to the SPEC vocabulary (candidate
  labels are rejected at the model layer, re-checked here for defense in depth).

The registry itself is deliberately tiny: Stage 2 (P3) grows the
dependency-resolved analyzer runtime on top of this contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

from .models import Fact, PIRValidationError
from .types import EvidenceLevel, PassTag, Verdict


class PassHonestyViolation(Exception):
    """Raised when a pass emits a fact its tag does not license."""


@dataclass(frozen=True)
class PassSpec:
    """Static declaration of a pass. ``fn`` maps inputs -> list of Facts."""

    id: str
    version: str
    tag: PassTag
    fn: Callable[..., List[Fact]]
    description: str = ""

    def __post_init__(self):
        if not isinstance(self.tag, PassTag):
            object.__setattr__(self, "tag", PassTag(self.tag))


class PassRegistry:
    """Holds pass specs and validates every fact a pass emits."""

    def __init__(self):
        self._passes: Dict[str, PassSpec] = {}

    def register(self, spec: PassSpec) -> PassSpec:
        if spec.id in self._passes:
            raise ValueError(f"pass {spec.id!r} already registered")
        self._passes[spec.id] = spec
        return spec

    def get(self, pass_id: str) -> PassSpec:
        return self._passes[pass_id]

    def __contains__(self, pass_id: str) -> bool:
        return pass_id in self._passes

    def ids(self) -> List[str]:
        return sorted(self._passes)

    # ---- honesty enforcement --------------------------------------------- #
    @staticmethod
    def check_emission(spec: PassSpec, fact: Fact) -> None:
        """Validate one emitted fact against the pass's honesty contract."""
        # The fact must carry this pass's identity and tag.
        if fact.analyzer.tag is not spec.tag:
            raise PassHonestyViolation(
                f"pass {spec.id!r} is tagged {spec.tag.value} but emitted a "
                f"fact stamped {fact.analyzer.tag.value}"
            )
        e = fact.evidence_level
        if spec.tag is PassTag.SOUND and e in (EvidenceLevel.E3, EvidenceLevel.E4):
            raise PassHonestyViolation(
                f"SOUND pass {spec.id!r} may not emit an {e.value} fact "
                "(cannot certify simulation/proxy-level warrant)"
            )
        if spec.tag is PassTag.HEURISTIC and e is EvidenceLevel.E0:
            raise PassHonestyViolation(
                f"HEURISTIC pass {spec.id!r} may not emit an E0 (exact) fact"
            )
        if (spec.tag is PassTag.HEURISTIC and e in (EvidenceLevel.E3, EvidenceLevel.E4)
                and not fact.warnings):
            raise PassHonestyViolation(
                f"HEURISTIC pass {spec.id!r} emitted an {e.value} fact with no "
                "located warnings[]"
            )
        # Verdict lock defense-in-depth (the model already enforces this).
        if fact.verdict is not None and not isinstance(fact.verdict, Verdict):
            raise PassHonestyViolation(
                f"pass {spec.id!r} emitted a non-SPEC verdict {fact.verdict!r}"
            )

    def run(self, spec_or_id, *args, **kwargs) -> List[Fact]:
        """Execute a pass and validate every fact it returns before releasing
        them to a caller/store."""
        spec = spec_or_id if isinstance(spec_or_id, PassSpec) else self._passes[spec_or_id]
        facts = spec.fn(*args, **kwargs)
        for f in facts:
            try:
                self.check_emission(spec, f)
            except PIRValidationError as exc:  # pragma: no cover - re-wrap
                raise PassHonestyViolation(str(exc)) from exc
        return facts
