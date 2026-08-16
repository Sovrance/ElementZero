"""The physics backend adapter contract (WO-15 BACKEND_ADAPTER_CONTRACT).

One stable ElementZero interface in front of external scientific
software. The rule that shapes every method here: a solver result is not
a prediction because a process exited zero. A nonconverged solve is a
recorded status, never a number.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from elementzero.data.identity import NuclideIdentity
from elementzero.errors import ProtocolError

# Solver statuses. SOLVER_OK is the only one that may carry a value.
SOLVER_OK = "OK"
SOLVER_NONCONVERGED = "NONCONVERGED"
SOLVER_NUMERICAL_INSTABILITY = "NUMERICAL_INSTABILITY"
SOLVER_UNSUPPORTED_NUCLIDE = "UNSUPPORTED_NUCLIDE"
SOLVER_INVALID_OUTPUT = "INVALID_OUTPUT"
SOLVER_RESOURCE_FAILURE = "RESOURCE_FAILURE"

SOLVER_STATUSES = (
    SOLVER_OK,
    SOLVER_NONCONVERGED,
    SOLVER_NUMERICAL_INSTABILITY,
    SOLVER_UNSUPPORTED_NUCLIDE,
    SOLVER_INVALID_OUTPUT,
    SOLVER_RESOURCE_FAILURE,
)

OBSERVABLE_MASS_EXCESS = "atomic_mass_excess_keV"
OBSERVABLE_BINDING = "binding_energy_MeV"

NO_SILENT_IMPUTATION_RULE = (
    "ez-wo15-no-imputation-v1: a backend never converts a nonconverged or "
    "unsupported solve into a numeric prediction. The failure is a status "
    "with a convergence record; a fallback model, if ever used, is a "
    "separately labeled model and never wears the physics family's name"
)


@dataclass(frozen=True)
class PhysicsPrediction:
    """One backend result for one nuclide (contract 'Prediction output')."""

    nuclide_id: str
    observable: str
    value: float | None
    unit: str
    solver_status: str
    convergence_record_id: str
    parameter_artifact_id: str
    backend_id: str
    physics_family: str
    source_hash: str
    output_hash: str
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.solver_status not in SOLVER_STATUSES:
            raise ProtocolError(f"unknown solver status {self.solver_status!r}")
        if self.solver_status == SOLVER_OK and self.value is None:
            raise ProtocolError(
                f"{self.backend_id}: an OK solve must carry a value"
            )
        if self.solver_status != SOLVER_OK and self.value is not None:
            raise ProtocolError(
                f"{self.backend_id}: a {self.solver_status} solve must not "
                "carry a value; missing physics is a status, never a number"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PhysicsBackend(abc.ABC):
    """Every WO-15 backend implements exactly this surface."""

    backend_id: str
    physics_family: str
    solver_name: str

    @abc.abstractmethod
    def source_identity(self) -> dict[str, Any]:
        """Archive identity: url, doi, sha256, license, publication."""

    @abc.abstractmethod
    def verify_source_hash(self) -> dict[str, Any]:
        """Re-hash the extracted source tree against the pinned digest."""

    @abc.abstractmethod
    def build(self) -> dict[str, Any]:
        """Compile the solver; return the build manifest."""

    @abc.abstractmethod
    def verify_build(self) -> dict[str, Any]:
        """Confirm the built artifact matches the recorded build manifest."""

    @abc.abstractmethod
    def verify_golden_cases(self) -> dict[str, Any]:
        """Reproduce the upstream-published reference outputs."""

    @abc.abstractmethod
    def predict(
        self,
        nuclides: Sequence[NuclideIdentity],
        parameter_artifact: dict[str, Any],
    ) -> list[PhysicsPrediction]:
        """Solve each nuclide under one immutable parameter artifact."""

    @abc.abstractmethod
    def export_parameter_artifact(self, **kwargs: Any) -> dict[str, Any]:
        """Emit the schema-exact PhysicsParameterArtifact."""

    @abc.abstractmethod
    def export_provenance(self) -> dict[str, Any]:
        """Source, build, license, and functional provenance."""

    def supports(self, nuclide: NuclideIdentity) -> bool:
        """Preregistered support policy (e.g. EVEN_EVEN_ONLY)."""
        return True
