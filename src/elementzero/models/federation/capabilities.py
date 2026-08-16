"""Capability descriptors for federation participants (WO-12 section 5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from elementzero.models.federation.protocol import COVERAGE_STATUSES, OOD_POLICY_ID

ROLE_CONTROL = "CONTROL"
ROLE_PHYSICS_BACKBONE = "PHYSICS_BACKBONE"
ROLE_RESIDUAL_CHALLENGER = "RESIDUAL_CHALLENGER"
ROLE_COMBINER = "COMBINER"

ROLES = (ROLE_CONTROL, ROLE_PHYSICS_BACKBONE, ROLE_RESIDUAL_CHALLENGER, ROLE_COMBINER)


@dataclass(frozen=True)
class ModelCapabilities:
    model_id: str
    role: str
    observables: tuple[str, ...] = ("atomic_mass_excess_keV",)
    uncertainty_native: bool = True
    uncertainty_decomposed: bool = True
    full_chart_coverage: bool = False
    coverage_statuses: tuple[str, ...] = tuple(COVERAGE_STATUSES)
    ood_policy_id: str = OOD_POLICY_ID

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("observables", "coverage_statuses"):
            payload[key] = list(payload[key])
        return payload


def federation_capability_summary(
    capability_list: list[ModelCapabilities],
) -> dict[str, Any]:
    return {
        "model_count": len(capability_list),
        "roles": sorted({c.role for c in capability_list}),
        "observables": sorted({o for c in capability_list for o in c.observables}),
        "by_model": {c.model_id: c.to_dict() for c in capability_list},
    }
