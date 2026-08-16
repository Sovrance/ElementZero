"""Brussels Skyrme-EDF (BSkG series) backbone adapter (WO-12 section 7).

Required role: PHYSICS_BACKBONE, independence group ``skyrme_edf_bskg``.

Preference ladder, applied at build time against the license/availability
gate:

    BSkG5 (preferred)  ->  BSkG4 (spec fallback)  ->  BSkG3 (family
    representative, publicly hosted on BRUSLIB)

The ladder never silently substitutes: the review record names every
candidate, its status, and why it was or was not selected. Table values are
normalized through the one shared conversion layer in
``elementzero.data.model_tables.parser`` — no adapter-local mass arithmetic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from elementzero.data.model_tables.manifests import (
    STATUS_APPROVED,
    assert_table_intact,
    source_manifest,
    table_available,
)
from elementzero.data.model_tables.validation import parse_table
from elementzero.errors import ProtocolError
from elementzero.models.federation import GROUP_SKYRME_EDF_BSKG
from elementzero.models.federation.protocol import NuclearMassModel
from elementzero.models.federation.table_model import TableMassModel

# BSkG4 has no registered acquirable table in this environment; the ladder
# documents it as considered-and-unavailable rather than skipping silently.
PREFERENCE_LADDER = ("BSKG5", "BSKG4", "BSKG3")

_UNREGISTERED_NOTE = {
    "BSKG4": (
        "considered as the spec fallback; no public machine-readable table "
        "is reachable (arXiv source of 2411.08007 carries no ancillary "
        "table, EPJA supplementary unreachable), so it is not registered as "
        "an acquirable source"
    ),
}


@dataclass(frozen=True)
class BackboneSelection:
    review: dict[str, Any]
    builder: Callable[[], NuclearMassModel]


def review_ladder(*, repo_root=None) -> dict[str, Any]:
    entries = []
    selected = None
    for table_id in PREFERENCE_LADDER:
        if table_id in _UNREGISTERED_NOTE:
            entries.append(
                {
                    "table_id": table_id,
                    "license_status": "BLOCKED_AVAILABILITY",
                    "available": False,
                    "note": _UNREGISTERED_NOTE[table_id],
                }
            )
            continue
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
        "family": "bskg",
        "independence_group": GROUP_SKYRME_EDF_BSKG,
        "preference_ladder": list(PREFERENCE_LADDER),
        "candidates": entries,
        "selected_manifest": selected,
    }


def build_bskg_backbone(*, repo_root=None) -> BackboneSelection:
    review = review_ladder(repo_root=repo_root)
    selected = review["selected_manifest"]
    if selected is None:
        raise ProtocolError(
            "no BSkG-family table is APPROVED and available; run "
            "tools/fetch_model_tables.py or record a governance exception"
        )
    table_id = next(
        t for t in PREFERENCE_LADDER if t not in _UNREGISTERED_NOTE
        and source_manifest(t)["model_id"] == selected["model_id"]
    )

    def _build() -> NuclearMassModel:
        path = assert_table_intact(table_id, repo_root=repo_root)
        return TableMassModel(
            model_id=selected["model_id"],
            family_id=selected["family"],
            independence_group=GROUP_SKYRME_EDF_BSKG,
            table=parse_table(table_id, path),
            source_manifest=selected,
        )

    return BackboneSelection(review=review, builder=_build)
