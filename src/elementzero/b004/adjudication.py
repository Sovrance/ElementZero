"""Derive the B004 independence adjudication from parameter artifacts.

This lives in the package rather than in the driver script because the
scoring step re-derives it and compares against the committed file: a
check that only works if preregistration and verification run the very
same code.
"""

from __future__ import annotations

from typing import Any

from elementzero.physics_backends.campaign import FAMILY_PARAMETERIZATION
from elementzero.physics_backends.independence import build_adjudication
from elementzero.physics_backends.provenance import (
    FIT_FREEZE_CUTOFF,
    PARAMETERIZATIONS,
)
from elementzero.physics_backends.registry import ROSTER


def build_adjudication_records(
    artifacts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """One adjudication record per backend, in backend-id order."""
    freeze_year = int(FIT_FREEZE_CUTOFF[:4])
    solver_of = {b: ROSTER[b]["solver"] for b in artifacts}
    records = []
    for backend_id, artifact in sorted(artifacts.items()):
        entry = ROSTER[backend_id]
        shared_solver = sorted(
            other
            for other, solver in solver_of.items()
            if other != backend_id and solver == entry["solver"]
        )
        parameterization = FAMILY_PARAMETERIZATION[backend_id]
        records.append(
            build_adjudication(
                group_id=entry["physics_family"],
                functional_class=entry["functional_class"],
                interaction_or_lagrangian_class=entry[
                    "interaction_or_lagrangian_class"
                ],
                solver=entry["solver"],
                parameter_artifact=artifact["artifact_id"],
                fit_freeze=artifact["freeze_id"],
                shared_training_data=(
                    ["AME1995 calibration set"]
                    if artifact["provenance_class"] == "REFIT_STRICT"
                    else []
                ),
                shared_parameters=[],
                derived_from_family=None,
                residual_parent=None,
                provenance_class=artifact["provenance_class"],
                parameterization_year=PARAMETERIZATIONS[parameterization][
                    "publication_year"
                ],
                freeze_year=freeze_year,
                shared_solver_with=shared_solver,
            )
        )
    return records


__all__ = ["build_adjudication_records"]
