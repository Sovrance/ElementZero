"""B004 preregistration (WO-15 spec section 18).

Everything the verdict can depend on is frozen here before truth is read:
the target rule, the roster, the independence groups, the metrics, the
uncertainty policy, the failure policy, the claim vocabulary, and — the
part that is easiest to fudge later — what performance would *mean*.
"""

from __future__ import annotations

from typing import Any

from elementzero.evidence.hashing import sha256_hex
from elementzero.physics_backends import (
    BACKEND_COVARIANT,
    BACKEND_GOGNY,
    BACKEND_SKYRME,
    GROUP_COVARIANT_RHB,
    GROUP_GOGNY_HFB,
    GROUP_SKYRME_HFB,
)

B004_CREATED_AT = "2026-08-16T20:00:00Z"
TRUTH_EDITION = "AME2020"

# Metrics (spec section 19), fixed before scoring.
METRICS = (
    "n_target",
    "n_predicted",
    "coverage_fraction",
    "MAE_keV",
    "MedAE_keV",
    "RMSE_keV",
    "NLPD",
    "coverage_68",
    "coverage_90",
    "coverage_95",
    "calibration_error_90",
)

STRATA = (
    "z_band",
    "nearest_freeze_distance_L1",
    "frontier_direction",
    "shell_adjacent",
    "odd_policy_class",
)

# Uncertainty policy (spec section 17). Declared in advance, never tuned
# to B004 truth after unlock.
UNCERTAINTY_POLICY_ID = "ez-b004-uncertainty-v1"
BASIS_PROBE_SHELLS = 16
PAIRING_PROBE_DELTA = 10.0
UNCERTAINTY_POLICY = (
    f"{UNCERTAINTY_POLICY_ID}: each prediction carries a Gaussian sigma built "
    "from two directly measured components and nothing else. Numerical "
    f"uncertainty is |E(N_shells={BASIS_PROBE_SHELLS}) - E(N_shells=14)| for "
    "that same nuclide. Parameter uncertainty is the change in the predicted "
    f"mass when each fitted pairing strength moves by {PAIRING_PROBE_DELTA} "
    "MeV fm^3, combined in quadrature. Family disagreement is reported "
    "separately and never folded into a single family's sigma. A floor of "
    "1 keV prevents a degenerate zero-width interval. No component is "
    "rescaled after truth unlock"
)

MODEL_ROSTER = (
    {
        "backend_id": BACKEND_SKYRME,
        "physics_family": GROUP_SKYRME_HFB,
        "role": "blind_physics_candidate",
    },
    {
        "backend_id": BACKEND_GOGNY,
        "physics_family": GROUP_GOGNY_HFB,
        "role": "blind_physics_candidate",
    },
    {
        "backend_id": BACKEND_COVARIANT,
        "physics_family": GROUP_COVARIANT_RHB,
        "role": "modern_reference_only",
    },
)

FAILURE_POLICY = (
    "a nonconverged or unsupported solve is recorded with its failure class "
    "and excluded from that model's metrics; coverage_fraction reports the "
    "exact loss. No target is dropped from the manifest to improve a "
    "coverage number, and no missing prediction is imputed"
)

CLAIM_VOCABULARY = (
    "MULTI_FAMILY_BLIND_EVIDENCE_ESTABLISHED",
    "SINGLE_FAMILY_BLIND_EVIDENCE_ONLY",
    "NO_BLIND_FAMILY_EVIDENCE",
    "B004_NOT_EVALUABLE",
)

# --------------------------------------------------------------------------- #
# Gate E: what performance means, preregistered                               #
# --------------------------------------------------------------------------- #

LEGACY_INHERITED_REFERENCE_KEV = 150.0

PERFORMANCE_INTERPRETATION_ID = "ez-b004-interpretation-v1"
PERFORMANCE_INTERPRETATION = (
    f"{PERFORMANCE_INTERPRETATION_ID}: B004 v1 is a CHARACTERIZATION "
    "challenge, and its pass criterion is protocol integrity plus coverage, "
    "not mass accuracy. The reason is stated before scoring: SkM* and D1S "
    "are pre-freeze functionals that were never calibrated as mass models, "
    "so a mass RMS in the MeV range is the expected outcome and would not "
    "falsify anything. Inheriting the 150 keV EZ-B002-v2 value as a pass bar "
    "here would be a category error, so it is carried only as "
    "LEGACY_INHERITED_REFERENCE for continuity of reporting and is not a "
    "gate. Accuracy is reported in full, per target and per stratum, with no "
    "threshold attached"
)

# The falsifiable part, fixed in advance.
MIN_COVERAGE_FRACTION = 0.60
BLIND_EVIDENCE_CRITERION_ID = "ez-b004-blind-evidence-criterion-v1"
BLIND_EVIDENCE_CRITERION = (
    f"{BLIND_EVIDENCE_CRITERION_ID}: MULTI_FAMILY_BLIND_EVIDENCE_ESTABLISHED "
    "requires, on this preregistered target set and before any truth is "
    "read: at least two backends whose independence verdict is INDEPENDENT "
    "and whose blind eligibility is true; each of them achieving a converged "
    f"prediction on at least {MIN_COVERAGE_FRACTION:.0%} of the targets with "
    "a complete convergence record per target; each carrying an uncertainty "
    "built only from the declared components; and the two families "
    "belonging to different functional classes. Failing any clause yields "
    "SINGLE_FAMILY_BLIND_EVIDENCE_ONLY or NO_BLIND_FAMILY_EVIDENCE, which "
    "are reported rather than repaired"
)

STRUCTURAL_POLICY = (
    "ez-b004-structural-v1: a derived two-neutron separation energy is "
    "scored only where every component mass is itself a converged blind "
    "prediction of the same family. Central-target blindness does not "
    "propagate to neighbours; a shell-adjacent result is reported as "
    "shell-adjacent evidence and never as shell rediscovery"
)

NO_POST_SCORE_CHANGE_RULE = (
    "ez-b004-no-post-score-change-v1: after truth unlock, no threshold, "
    "metric definition, roster entry, uncertainty component, target, or "
    "claim label may change. A different choice requires a new protocol "
    "version and a new experiment id"
)


def build_protocol(
    *,
    freeze_id: str,
    freeze_hash: str,
    target_manifest: dict[str, Any],
    parameter_artifacts: dict[str, str],
    independence_groups: list[str],
) -> dict[str, Any]:
    """The schema-exact, hash-sealed B004 preregistration."""
    protocol = {
        "experiment_id": "EZ-B004-v1",
        "created_at": B004_CREATED_AT,
        "freeze_id": freeze_id,
        "freeze_hash": freeze_hash,
        "truth_edition": TRUTH_EDITION,
        "truth_locked": True,
        "target_rule_hash": target_manifest["target_rule_hash"],
        "target_rule": target_manifest["target_rule"],
        "target_identity_digest": target_manifest["target_identity_digest"],
        "n_targets": target_manifest["n_targets"],
        "odd_policy": target_manifest["odd_policy"],
        "model_roster": [dict(m) for m in MODEL_ROSTER],
        "parameter_artifacts": dict(sorted(parameter_artifacts.items())),
        "independence_groups": sorted(independence_groups),
        "metrics": list(METRICS),
        "strata": list(STRATA),
        "uncertainty_policy_id": UNCERTAINTY_POLICY_ID,
        "uncertainty_policy": UNCERTAINTY_POLICY,
        "basis_probe_shells": BASIS_PROBE_SHELLS,
        "pairing_probe_delta": PAIRING_PROBE_DELTA,
        "combination_policy": (
            "no combiner runs in B004 v1: raw physics families are scored "
            "individually so independence counting stays on raw families "
            "(spec section 16). Federation is a later act"
        ),
        "failure_policy": FAILURE_POLICY,
        "claim_vocabulary": list(CLAIM_VOCABULARY),
        "performance_interpretation_id": PERFORMANCE_INTERPRETATION_ID,
        "performance_interpretation": PERFORMANCE_INTERPRETATION,
        "legacy_inherited_reference_keV": LEGACY_INHERITED_REFERENCE_KEV,
        "legacy_reference_status": "LEGACY_INHERITED_REFERENCE",
        "blind_evidence_criterion_id": BLIND_EVIDENCE_CRITERION_ID,
        "blind_evidence_criterion": BLIND_EVIDENCE_CRITERION,
        "min_coverage_fraction": MIN_COVERAGE_FRACTION,
        "structural_policy": STRUCTURAL_POLICY,
        "no_post_score_change_rule": NO_POST_SCORE_CHANGE_RULE,
        "small_sample_note": target_manifest["small_sample_note"],
    }
    protocol["protocol_hash"] = sha256_hex(protocol)
    return protocol
