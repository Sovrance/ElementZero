"""WO-14 input integrity guard (spec section 2).

Before any prediction, every immutable input is re-hashed and compared to
the pins captured at the WO-14 input baseline (the merged WO-13 head).
Any mismatch is INPUT_INTEGRITY_FAILURE and the work order STOPS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_file

INPUT_INTEGRITY_FAILURE = "INPUT_INTEGRITY_FAILURE"

WO12_REGISTRY_HASH = "9a9e4c8ac12f6b983c464f8ef7bc8162ebbfa9a305d39f4e60e8cdb9848361ec"
WO12_PROTOCOL_HASH = "117b60ccfbde52a3eef1e5e5acdeae8197275d073d122752a8b75b33500cd686"

# sha256 pins over the committed evidence files, captured at the WO-14
# input baseline (WO-13 merge d551ae8).
PINNED_INPUT_HASHES: dict[str, str] = {
    "reports/adjudication/wo11/wo11_adjudication_report.json": (
        "93b3199f1b6d3c084ccdfa5f736bb7d4c3f41390b297b222a4145bf6211eb87e"
    ),
    "reports/adjudication/wo11/model_readiness.json": (
        "0e6a25d118d971b51f1c4f0415402107e271835baa1091b4fa66f593095fdaf2"
    ),
    "reports/adjudication/wo11/artifact_inventory.json": (
        "65940fa91912e21bd8111a8fa4a5e6eeb77e7dac88cc32baa701b24a24ac2f14"
    ),
    "reports/model_federation/wo12/federation_manifest.json": (
        "70e683e38b7e4c393980ceb6aa45f4daaf64495bd47a8999f631a0e69dc0f8ac"
    ),
    "reports/model_federation/wo12/synthetic_qualification.json": (
        "fd9b75f1e60b5669d6c80bd536043b8374997f7d7ea0249cacc17e22bcfeb327"
    ),
    "reports/eligibility/wo13/model_training_provenance.json": (
        "673e3a9cc579102044137c5135fdc00eebb4486e3717deb505c16714aa1eee9e"
    ),
    "reports/eligibility/wo13/target_eligibility_matrix.json": (
        "4c473fc1f0904460255a51352b051238fd96d3b337d3ac25a331c240bc33f430"
    ),
    "reports/eligibility/wo13/subfederation_summary.json": (
        "b2c5736c36ea44c5abd8a2c62f730d6c39af56033fcdabc03560e5d88857dffc"
    ),
    "reports/eligibility/wo13/b002_real_claim_plan.json": (
        "e45255730ece1e617dea9eb7b08a7834508613537b71c7a81b59c5459f41cb53"
    ),
    "reports/eligibility/wo13/b003_real_claim_plan.json": (
        "81085ac3ada349bd6c4a21199ef5e3ec84b7f2eae18fb762da3fb5b453ae9e59"
    ),
    "reports/eligibility/wo13/wo13_gate_status.json": (
        "51909ec8f2e6f31e8912173baa1d6e5f8cf7585eaf4d6639978a48d8fad1eb0e"
    ),
    "experiments/EZ-B002-v2/PROTOCOL.json": (
        "608c84c8d25ada5ab588fa3778677456c99cc47e645a3a0a1871ca5944fcc5e3"
    ),
    "experiments/EZ-B003-v2/PROTOCOL.json": (
        "e74faf7567283c096beeb7cf10c97932685e4629f457e501c11820aeae587f21"
    ),
}


def verify_inputs(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    """Re-hash every immutable input; raise on the first mismatch."""
    from elementzero.adjudication.artifact_audit import (
        assert_v1_evidence_unchanged,
        build_artifact_inventory,
    )
    from elementzero.evidence.ledger import read_json

    root = Path(repo_root or REPO_ROOT)
    checked: dict[str, str] = {}
    for relpath, pinned in sorted(PINNED_INPUT_HASHES.items()):
        digest = sha256_file(root / relpath)
        if digest != pinned:
            raise ProtocolError(
                f"{INPUT_INTEGRITY_FAILURE}: {relpath} hashes {digest}, "
                f"pinned {pinned}; WO-14 must stop"
            )
        checked[relpath] = digest

    inventory = build_artifact_inventory()
    assert_v1_evidence_unchanged(inventory)

    manifest = read_json(root / "reports/model_federation/wo12/federation_manifest.json")
    if manifest["registry_hash"] != WO12_REGISTRY_HASH:
        raise ProtocolError(f"{INPUT_INTEGRITY_FAILURE}: registry hash changed")
    for experiment_id in ("EZ-B002-v2", "EZ-B003-v2"):
        protocol = read_json(root / "experiments" / experiment_id / "PROTOCOL.json")
        if protocol["protocol_hash"] != WO12_PROTOCOL_HASH:
            raise ProtocolError(
                f"{INPUT_INTEGRITY_FAILURE}: {experiment_id} protocol hash changed"
            )
    return {
        "work_order": "WO-14",
        "status": "INPUTS_VERIFIED",
        "v1_inventory_unchanged": True,
        "wo12_registry_hash": WO12_REGISTRY_HASH,
        "wo12_protocol_hash": WO12_PROTOCOL_HASH,
        "pinned_files": checked,
        "rule": (
            "any mismatch is INPUT_INTEGRITY_FAILURE and WO-14 stops before "
            "a single prediction is generated"
        ),
    }
