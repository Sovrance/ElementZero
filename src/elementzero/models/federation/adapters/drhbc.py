"""Optional DRHBc backbone adapter (WO-12 section 9).

Role: PHYSICS_BACKBONE_CHALLENGER, independence group
``relativistic_edf_drhbc``. The DRHBc mass-table host is unreachable in this
environment, so the adapter reports BLOCKED_AVAILABILITY and WO-12 completion
is explicitly not blocked on it.
"""

from __future__ import annotations

from typing import Any

from elementzero.data.model_tables.manifests import source_manifest, table_available


def review_drhbc(*, repo_root=None) -> dict[str, Any]:
    manifest = source_manifest("DRHBC")
    return {
        "family": "drhbc",
        "independence_group": manifest["independence_group"],
        "role": "PHYSICS_BACKBONE_CHALLENGER",
        "optional": True,
        "candidates": [
            {
                "table_id": "DRHBC",
                "license_status": manifest["license_status"],
                "available": table_available("DRHBC", repo_root=repo_root),
                "note": manifest["license_note"],
            }
        ],
        "selected_manifest": None,
        "blocking_rule": "WO-12 section 9: completion is not blocked on DRHBc",
    }
