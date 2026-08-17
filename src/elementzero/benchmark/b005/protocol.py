"""The EZ-B005-v1 preregistration (WO-15B v0.5.2 §11, §13).

Frozen before predictions are generated, which is the whole point: the
gates are numbers chosen while the outcome is still unknown. Gate C is
two-sided on purpose — a model cannot pass by being vague any more than
by being overconfident — and the 150 keV legacy figure appears only as
an inherited reference, never as a bar.
"""

from __future__ import annotations

from typing import Any

from elementzero.benchmark.b005 import (
    B005_ID,
    COVERAGE90_MAX,
    COVERAGE90_MIN,
    MAE_KEV_MAX,
    MIN_TARGETS_EVALUABLE,
    MIN_TARGETS_PREFERRED,
    P95_ABS_ERROR_KEV_MAX,
    RESULT_VOCABULARY,
    S2N_MAE_KEV_MAX,
    WO16_GATE_RULE,
)
from elementzero.benchmark.b005.readiness import SIGMA_VALID_FRACTION_MIN
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.model_discrepancy.ood_v2 import OOD_POLICY, OOD_POLICY_ID
from elementzero.model_discrepancy.protocol import FEATURE_POLICY
from elementzero.model_discrepancy.sigma_provenance import COMPOSITION_POLICY
from elementzero.readiness import CHILD_FAMILY_RULE, TRUTH_FIREWALL_RULE

B005_CREATED_AT = "2026-08-17T10:00:00Z"
TRUTH_EDITION = "AME2020"

LEGACY_INHERITED_REFERENCE_KEV = 150.0

GATES = {
    "A_independence": "at least two independent blind-eligible physics families",
    "B_sigma_provenance": (
        f"per qualifying family, at least {SIGMA_VALID_FRACTION_MIN:.0%} of "
        "mass rows carry a valid sigma provenance"
    ),
    "C_calibration": (
        f"coverage_90 within [{COVERAGE90_MIN}, {COVERAGE90_MAX}] computed on "
        "sigma-valid rows only"
    ),
    "D_accuracy": f"MAE <= {MAE_KEV_MAX:.0f} keV",
    "E_catastrophic": (
        f"95th-percentile absolute error <= {P95_ABS_ERROR_KEV_MAX:.0f} keV"
    ),
    "F_structure": (
        f"blind S2n MAE <= {S2N_MAE_KEV_MAX:.0f} keV where evaluable, "
        "otherwise STRUCTURAL_GATE_NOT_EVALUABLE"
    ),
}

PERFORMANCE_INTERPRETATION = (
    "ez-wo15b-b005-interpretation-v1: B005 asks whether calibrated blind "
    "families are accurate and honestly uncertain enough to earn WO-16. "
    "Unlike B004, which was a characterization challenge, these gates are "
    "pass bars and were fixed before any prediction was generated. The "
    f"{LEGACY_INHERITED_REFERENCE_KEV:.0f} keV figure inherited from "
    "EZ-B002-v2 is carried as LEGACY_INHERITED_REFERENCE only and is not a "
    "gate. Failing these gates is a reportable outcome, not a reason to "
    "move them"
)


def build_protocol(
    *,
    target_manifest: dict[str, Any],
    model_roster: list[dict[str, Any]],
    independence_groups: list[str],
    parameter_artifacts: dict[str, str],
    discrepancy_artifacts: dict[str, str],
    calibration_artifacts: dict[str, str],
) -> dict[str, Any]:
    """The schema-exact, hash-sealed B005 preregistration."""
    protocol = {
        "experiment_id": B005_ID,
        "created_at": B005_CREATED_AT,
        "truth_edition": TRUTH_EDITION,
        "truth_locked": True,
        "target_rule_id": target_manifest["target_rule_id"],
        "target_rule": target_manifest["target_rule"],
        "target_rule_hash": target_manifest["target_rule_hash"],
        "target_identity_digest": target_manifest["target_identity_digest"],
        "n_targets": target_manifest["n_targets"],
        "claim_blindness_class": target_manifest["claim_blindness_class"],
        "blindness_taxonomy": target_manifest["blindness_taxonomy"],
        "strict_exhaustion_finding": target_manifest[
            "strict_exhaustion_finding"
        ],
        "odd_policy": target_manifest["odd_policy"],
        "model_roster": [dict(m) for m in model_roster],
        "independence_groups": sorted(independence_groups),
        "child_family_rule": CHILD_FAMILY_RULE,
        "parameter_artifacts": dict(sorted(parameter_artifacts.items())),
        "discrepancy_artifacts": dict(sorted(discrepancy_artifacts.items())),
        "calibration_artifacts": dict(sorted(calibration_artifacts.items())),
        "thresholds": {
            "mae_keV_max": 2000,
            "coverage90_min": 0.8,
            "coverage90_max": 0.98,
            "p95_abs_error_keV_max": 5000,
            "sigma_provenance_fraction_min": SIGMA_VALID_FRACTION_MIN,
            "s2n_mae_keV_max": S2N_MAE_KEV_MAX,
        },
        "gates": dict(sorted(GATES.items())),
        "min_targets_preferred": MIN_TARGETS_PREFERRED,
        "min_targets_evaluable": MIN_TARGETS_EVALUABLE,
        "sigma_composition_policy": COMPOSITION_POLICY,
        "discrepancy_feature_policy": FEATURE_POLICY,
        "ood_policy_id": OOD_POLICY_ID,
        "ood_policy": OOD_POLICY,
        "truth_firewall_rule": TRUTH_FIREWALL_RULE,
        "performance_interpretation": PERFORMANCE_INTERPRETATION,
        "legacy_inherited_reference_keV": LEGACY_INHERITED_REFERENCE_KEV,
        "legacy_reference_status": "LEGACY_INHERITED_REFERENCE",
        "claim_vocabulary": list(RESULT_VOCABULARY),
        "wo16_gate_rule": WO16_GATE_RULE,
        "no_post_score_change_rule": (
            "no threshold, gate, roster entry or blindness label may change "
            "after truth is unlocked"
        ),
    }
    protocol["protocol_hash"] = sha256_hex(canonical_json(protocol))
    return protocol


__all__ = [
    "B005_CREATED_AT",
    "GATES",
    "LEGACY_INHERITED_REFERENCE_KEV",
    "PERFORMANCE_INTERPRETATION",
    "TRUTH_EDITION",
    "build_protocol",
]
