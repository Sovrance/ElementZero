"""Benchmark claim manifests and claim-aware aggregation (WO-13 sections 16-21).

Two tracks per real benchmark:

    REAL-BLIND    only STRICT_BLIND / HISTORICAL_BLIND lineages; the strict
                  gate applies; REAL_BLIND_GATE_NOT_EVALUABLE is a valid
                  outcome.
    REAL-RECON    reconstruction/reference comparison; every row is labeled
                  NONBLIND_REFERENCE / RECONSTRUCTION_REFERENCE /
                  PARTIALLY_BLIND; this track never grants blind
                  extrapolation status and reconstruction is not
                  rediscovery.

Improvement flags are computed from preregistered metrics, never assumed:
protocol qualification, federation improvement, and blind-gate eligibility
are three independent facts.
"""

from __future__ import annotations

from typing import Any

from elementzero.eligibility.claim_types import (
    HISTORICAL_BLIND,
    INELIGIBLE_UNKNOWN_PROVENANCE,
    NONBLIND_REFERENCE,
    PARTIALLY_BLIND,
    RECONSTRUCTION_REFERENCE,
    STRICT_BLIND,
    assert_claim_type,
)
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_hex

TRACK_BLIND = "BLIND"
TRACK_RECONSTRUCTION = "RECONSTRUCTION"

BLIND_TRACK_CLAIMS = (STRICT_BLIND, HISTORICAL_BLIND)
RECON_TRACK_CLAIMS = (
    NONBLIND_REFERENCE,
    RECONSTRUCTION_REFERENCE,
    PARTIALLY_BLIND,
)

CLAIM_SECTION_RULE = (
    "ez-wo13-claim-sections-v1: never one mixed leaderboard. Section A: "
    "strict/historical blind; B: partially blind; C: nonblind reference; "
    "D: reconstruction reference; E: ineligible/unknown provenance. "
    "Metrics can be identical across sections; claims cannot."
)

CLAIM_SECTIONS = {
    "A_STRICT_HISTORICAL_BLIND": (STRICT_BLIND, HISTORICAL_BLIND),
    "B_PARTIALLY_BLIND": (PARTIALLY_BLIND,),
    "C_NONBLIND_REFERENCE": (NONBLIND_REFERENCE,),
    "D_RECONSTRUCTION_REFERENCE": (RECONSTRUCTION_REFERENCE,),
    "E_INELIGIBLE_UNKNOWN": (INELIGIBLE_UNKNOWN_PROVENANCE,),
}

RECON_NOT_REDISCOVERY_RULE = (
    "ez-wo13-recon-not-rediscovery-v1: the reconstruction track measures "
    "whether a trained physics federation reproduces and localizes "
    "established structure it may already have seen; it is never called "
    "rediscovery, never satisfies a blind gate, and never upgrades a "
    "primary validation stage"
)

THRESHOLD_INHERITANCE_RULE = (
    "ez-wo13-threshold-inheritance-v1: the frozen v2 qualification "
    "thresholds are inherited as qualification criteria, hashed and "
    "asserted unchanged; passing them on real data is NOT a validated "
    "real-world performance standard unless a separate preregistration "
    "justifies that claim before scoring, and no new real-data threshold "
    "may be invented after looking at real results"
)


def claim_section(claim_type: str) -> str:
    assert_claim_type(claim_type)
    for section, claims in CLAIM_SECTIONS.items():
        if claim_type in claims:
            return section
    raise ProtocolError(f"claim type {claim_type!r} has no section")


def build_claim_manifest(
    *,
    experiment_id: str,
    claim_track: str,
    threshold_manifest: dict[str, Any],
    eligibility_manifest_hash: str,
    protocol_qualified: bool,
) -> dict[str, Any]:
    if claim_track == TRACK_BLIND:
        allowed = BLIND_TRACK_CLAIMS
        strict_gate = True
    elif claim_track == TRACK_RECONSTRUCTION:
        allowed = RECON_TRACK_CLAIMS
        strict_gate = False
    else:
        raise ProtocolError(f"unknown claim track {claim_track!r}")
    return {
        "experiment_id": experiment_id,
        "claim_track": claim_track,
        "allowed_claim_types": list(allowed),
        "strict_gate": strict_gate,
        "threshold_manifest_hash": sha256_hex(threshold_manifest),
        "eligibility_manifest_hash": eligibility_manifest_hash,
        "protocol_qualified": protocol_qualified,
        "federation_improvement_required": False,
    }


# -- improvement flags (sections 19-20), computed from committed WO-12 ------ #

_B002_BASELINE_IDS = (
    "EZ-SEMF-LS-v1",
    "EZ-GP-DIRECT-v1",
    "EZ-SEMF-GP-RESIDUAL-v1",
    "EZ-GP-OPTIMIZED-CONTROL-v1",
)
_B002_PHYSICS_IDS = (
    "EZ-BSKG3-TABLE-v1",
    "EZ-FRDM95-TABLE-v1",
    "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",
    "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
)
_B002_COMBINED_IDS = (
    "EZ-FED-UNIFORM-ENSEMBLE-v1",
    "EZ-FED-VALIDATION-WEIGHTED-v1",
)


def b002_improvement_flags(qualification: dict[str, Any]) -> dict[str, Any]:
    """B002: protocol PASS never implies the physics federation improved MAE."""
    by_model = qualification["EZ-B002-v2-qual"]["by_model"]

    def _best(ids: tuple[str, ...]) -> tuple[str, float]:
        pairs = [(m, float(by_model[m]["MAE_keV"])) for m in ids if m in by_model]
        return min(pairs, key=lambda p: p[1])

    best_baseline = _best(_B002_BASELINE_IDS)
    best_physics = _best(_B002_PHYSICS_IDS)
    best_combined = _best(_B002_COMBINED_IDS)
    improved = min(best_physics[1], best_combined[1]) < best_baseline[1]
    return {
        "protocol_qualified": qualification["EZ-B002-v2-qual"]["status"] == "PASS",
        "federation_improved_over_baseline": improved,
        "best_baseline_model": {
            "model_id": best_baseline[0],
            "MAE_keV": best_baseline[1],
        },
        "best_physics_model": {
            "model_id": best_physics[0],
            "MAE_keV": best_physics[1],
        },
        "best_combined_model": {
            "model_id": best_combined[0],
            "MAE_keV": best_combined[1],
        },
        "rule": (
            "computed from the committed synthetic qualification metrics, "
            "never assumed; the qualification passed because at least one "
            "participant met the gate, and that participant may be a "
            "statistical baseline"
        ),
    }


def b003_improvement_flags(
    qualification: dict[str, Any], *, blind_gate_eligible: bool
) -> dict[str, Any]:
    """B003: reconstruction quality is separate from blind rediscovery."""
    by_model = qualification["EZ-B003-v2-qual"]["by_model"]
    baselines = {m: by_model[m] for m in _B002_BASELINE_IDS if m in by_model}
    others = {m: p for m, p in by_model.items() if m not in baselines}
    best_baseline_rank1 = max(float(p["rank_1_fraction"]) for p in baselines.values())
    best_other_rank1 = max(float(p["rank_1_fraction"]) for p in others.values())
    best_baseline_cal = min(
        float(p["calibration_error_90"]) for p in baselines.values()
    )
    best_other_cal = min(float(p["calibration_error_90"]) for p in others.values())
    return {
        "structure_localization_improved": best_other_rank1 > best_baseline_rank1,
        "calibration_improved": best_other_cal < best_baseline_cal,
        "federation_criterion_met": bool(
            qualification["EZ-B003-v2-qual"]["models_meeting_criterion"]
        ),
        "blind_claim_eligible": blind_gate_eligible,
        "rule": (
            "a model may reconstruct shell structure well while remaining "
            "nonblind; localization, calibration, criterion, and blind "
            "eligibility are reported separately and none implies another"
        ),
    }
