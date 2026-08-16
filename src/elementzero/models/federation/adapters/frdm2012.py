"""FRDM (macroscopic-microscopic) backbone adapter (WO-12 section 8).

Required role: PHYSICS_BACKBONE, independence group
``macroscopic_microscopic_frdm`` — deliberately distinct from the Skyrme
EDF/HFB family; the purpose is model-family diversity, not recency.

Preference ladder:

    FRDM2012 (preferred; canonical LANL host unreachable in this
    environment) -> FRDM95 (family representative, publicly distributed by
    the IAEA in RIPL-3)
"""

from __future__ import annotations

from typing import Any

from elementzero.data.model_tables.manifests import (
    STATUS_APPROVED,
    assert_table_intact,
    source_manifest,
    table_available,
)
from elementzero.data.model_tables.validation import parse_table
from elementzero.errors import ProtocolError
from elementzero.models.federation import GROUP_MACRO_MICRO_FRDM
from elementzero.models.federation.adapters.bskg5 import BackboneSelection
from elementzero.models.federation.protocol import NuclearMassModel
from elementzero.models.federation.table_model import TableMassModel

PREFERENCE_LADDER = ("FRDM2012", "FRDM95")


def review_ladder(*, repo_root=None) -> dict[str, Any]:
    entries = []
    selected = None
    for table_id in PREFERENCE_LADDER:
        manifest = source_manifest(table_id)
        available = table_available(table_id, repo_root=repo_root)
        entries.append(
            {
                "table_id": table_id,
                "license_status": manifest["license_status"],
                "available": available,
                "note": manifest["license_note"],
            }
        )
        if selected is None and manifest["license_status"] == STATUS_APPROVED and available:
            selected = manifest
    return {
        "family": "frdm",
        "independence_group": GROUP_MACRO_MICRO_FRDM,
        "preference_ladder": list(PREFERENCE_LADDER),
        "candidates": entries,
        "selected_manifest": selected,
    }


def build_frdm_backbone(*, repo_root=None) -> BackboneSelection:
    review = review_ladder(repo_root=repo_root)
    selected = review["selected_manifest"]
    if selected is None:
        raise ProtocolError(
            "no FRDM-family table is APPROVED and available; run "
            "tools/fetch_model_tables.py or record a governance exception"
        )
    table_id = next(
        t for t in PREFERENCE_LADDER if source_manifest(t)["model_id"] == selected["model_id"]
    )

    def _build() -> NuclearMassModel:
        path = assert_table_intact(table_id, repo_root=repo_root)
        return TableMassModel(
            model_id=selected["model_id"],
            family_id=selected["family"],
            independence_group=GROUP_MACRO_MICRO_FRDM,
            table=parse_table(table_id, path),
            source_manifest=selected,
        )

    return BackboneSelection(review=review, builder=_build)
