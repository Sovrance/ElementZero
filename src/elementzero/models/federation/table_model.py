"""External physics tables as federation participants.

A ``TableMassModel`` never fits anything: its physics was computed by its
authors. ``fit`` only records the training identities (so the sealed
pipeline's training-digest checks stay meaningful) and the training lattice
(for nearest-training distances). ``predict`` is a table lookup with an
explicit coverage status — a nuclide the table does not carry is
``OUT_OF_TABLE``, never a zero.

The within-model sigma is the table's own empirical rms deviation against the
experimental masses quoted in the same file — computed at parse time from the
file, not quoted from memory — and it is an honest statement about the model
against *real* masses. On a synthetic qualification chart it is reported
unchanged: qualification exercises the mechanics, and a physics table is
expected to disagree with a toy surface.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from elementzero.benchmark.distance import nearest_training, training_lattice
from elementzero.data.identity import NuclideIdentity
from elementzero.data.model_tables.parser import ParsedTable
from elementzero.data.observations import MassObservation
from elementzero.models.federation.protocol import (
    STATUS_AVAILABLE,
    STATUS_OUT_OF_TABLE,
    STATUS_UNSUPPORTED_NUCLIDE,
    FederationPrediction,
    NuclearMassModel,
)

UNCERTAINTY_POLICY_TABLE_RMS = (
    "within-model sigma = the table's own empirical rms deviation against the "
    "experimental masses quoted in the same file, computed at parse time"
)

TRAINING_POLICY_TABLE = (
    "no fitting: the table is a frozen published physics calculation; fit() "
    "records training identities and lattice only"
)

MIN_TABLE_SIGMA_KEV = 1.0


class TableMassModel(NuclearMassModel):
    def __init__(
        self,
        *,
        model_id: str,
        family_id: str,
        independence_group: str,
        table: ParsedTable,
        source_manifest: dict[str, Any],
    ) -> None:
        self.model_id = model_id
        self.family_id = family_id
        self.independence_group = independence_group
        self.source_manifest = dict(source_manifest)
        self.training_policy = TRAINING_POLICY_TABLE
        self.uncertainty_policy = UNCERTAINTY_POLICY_TABLE_RMS
        self._table = table
        self._sigma_keV = max(table.empirical_rms_keV or MIN_TABLE_SIGMA_KEV, MIN_TABLE_SIGMA_KEV)
        self._fitted_ids: tuple[str, ...] = ()
        self._lattice: tuple[tuple[int, int], ...] = ()

    def fit(self, observations: Sequence[MassObservation]) -> None:
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))
        self._lattice = training_lattice(self._fitted_ids)

    def _distance(self, z: int, n: int) -> int | None:
        if not self._lattice:
            return None
        return int(nearest_training(z=z, n=n, lattice=self._lattice)["nearest_training_L1"])

    def predict(self, nuclide: NuclideIdentity) -> FederationPrediction:
        z, n = nuclide.Z, nuclide.N
        if z < 1 or n < 0:
            return FederationPrediction(
                nuclide=nuclide,
                status=STATUS_UNSUPPORTED_NUCLIDE,
                model_id=self.model_id,
                nearest_training_L1=self._distance(z, n),
            )
        row = self._table.get(z, n)
        if row is None:
            return FederationPrediction(
                nuclide=nuclide,
                status=STATUS_OUT_OF_TABLE,
                model_id=self.model_id,
                nearest_training_L1=self._distance(z, n),
            )
        return FederationPrediction(
            nuclide=nuclide,
            status=STATUS_AVAILABLE,
            model_id=self.model_id,
            point_keV=row.mass_excess_keV,
            within_model_std_keV=self._sigma_keV,
            nearest_training_L1=self._distance(z, n),
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "family_id": self.family_id,
            "independence_group": self.independence_group,
            # Identity lookup only: the table is addressed by (Z, N). Its
            # physics-internal shell structure is its own; no shell label or
            # magic-number feature enters from our side.
            "features": ["Z", "N", "A"],
            "table_id": self._table.table_id,
            "table_n_rows": self._table.n_rows,
            "table_raw_sha256": self.source_manifest.get("raw_sha256"),
            "empirical_rms_keV": self._table.empirical_rms_keV,
            "sigma_keV": self._sigma_keV,
            "parser_version": self._table.parser_version,
            "predictive_distribution": "gaussian",
            "uncertainty_method": self.uncertainty_policy,
            "training_policy": self.training_policy,
            "fitted_nuclide_ids": list(self._fitted_ids),
        }
