"""WO-14 protocol constants: tracks, scopes, statuses, and claim limits."""

from __future__ import annotations

WO14_CREATED_AT = "2026-08-16T17:00:00Z"

TRUTH_EDITION = "AME2020"

B002_BLIND_ID = "EZ-B002-v2-real-blind"
B002_RECON_ID = "EZ-B002-v2-real-recon"
B003_BLIND_ID = "EZ-B003-v2-real-blind"
B003_RECON_ID = "EZ-B003-v2-real-recon"

TRACK_BLIND = "BLIND"
TRACK_RECONSTRUCTION = "RECONSTRUCTION"

# Scientific scopes (spec section 14).
SCOPE_CONTROL_BLIND_GEOGRAPHIC = "CONTROL_BLIND_GEOGRAPHIC"
SCOPE_RECONSTRUCTION_GEOGRAPHIC = "RECONSTRUCTION_GEOGRAPHIC"
SCOPE_PHYSICS_BLIND_MASS_EDGE = "PHYSICS_BLIND_MASS_EDGE"
SCOPE_PHYSICS_BLIND_EDGE_STRUCTURE = "PHYSICS_BLIND_EDGE_STRUCTURE"
SCOPE_FULL_BLIND_SHELL_REDISCOVERY = "FULL_BLIND_SHELL_REDISCOVERY"
SCOPE_RECONSTRUCTION_SHELL_STRUCTURE = "RECONSTRUCTION_SHELL_STRUCTURE"

# B002 blind is control-only and may never be labeled physics validation.
B002_BLIND_PROHIBITED_SCOPES = (
    "PHYSICS_BLIND_GEOGRAPHIC_VALIDATION",
    "FEDERATED_BLIND_GEOGRAPHIC_VALIDATION",
    "FRONTIER_RIGHT_TO_EXTRAPOLATE",
)

# The inherited synthetic qualification criterion is exactly the frozen v2
# gate, and it is labeled as such — never a universal real-world standard.
INHERITED_CRITERION_LABEL = "INHERITED_SYNTHETIC_QUALIFICATION_CRITERION"

# Eligible model rosters, fixed by the committed WO-13 eligibility matrix.
B002_BLIND_MODELS = (
    "EZ-SEMF-LS-v1",
    "EZ-GP-DIRECT-v1",
    "EZ-SEMF-GP-RESIDUAL-v1",
    "EZ-GP-OPTIMIZED-CONTROL-v1",
)
# Reconstruction rosters follow the COMMITTED WO-13 claim facts, not the
# illustrative full-federation roster: on these real targets the committed
# eligibility marks the FRDM95 lineage INELIGIBLE_UNKNOWN_PROVENANCE outside
# its 12 blind targets (unknown is not permission, on any track) and the
# combiners inherit that poison, so only the proven-provenance BSkG3
# lineage carries publishable reconstruction rows. FRDM95's real-data role
# is the BLIND track on its 12 historical-blind targets — a stronger claim
# than reconstruction, kept strictly separate.
RECON_MODELS = (
    "EZ-BSKG3-TABLE-v1",
    "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",
)
RECON_EXCLUDED_MODELS = {
    "EZ-FRDM95-TABLE-v1": (
        "committed WO-13 eligibility: INELIGIBLE_UNKNOWN_PROVENANCE outside "
        "its 12 historical-blind targets; blind credit only via the BLIND track"
    ),
    "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1": (
        "inherits the FRDM95 unknown-provenance base outside the 12 blind targets"
    ),
    "EZ-FED-UNIFORM-ENSEMBLE-v1": (
        "combiner contains the unknown-provenance FRDM95 lineage; a combiner "
        "cannot hide an ineligible contributor"
    ),
    "EZ-FED-VALIDATION-WEIGHTED-v1": (
        "combiner contains the unknown-provenance FRDM95 lineage; a combiner "
        "cannot hide an ineligible contributor"
    ),
    "EZ-SEMF-LS-v1": "blind-track control; cross-referenced for comparison only",
    "EZ-GP-DIRECT-v1": "blind-track control; cross-referenced for comparison only",
    "EZ-SEMF-GP-RESIDUAL-v1": (
        "blind-track control; cross-referenced for comparison only"
    ),
    "EZ-GP-OPTIMIZED-CONTROL-v1": (
        "blind-track control; cross-referenced for comparison only"
    ),
}
RECON_ROSTER_RULE = (
    "ez-wo14-recon-roster-v1: reconstruction runs execute exactly the models "
    "the committed WO-13 claim facts admit on every target of the track; "
    "unknown provenance is not permission on any track, a combiner cannot "
    "hide an ineligible contributor, and blind-track results are "
    "cross-referenced for comparison rather than re-run under a weaker label"
)

B003_BLIND_MODELS = B002_BLIND_MODELS + (
    "EZ-FRDM95-TABLE-v1",
    "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
)
BLIND_PHYSICS_FAMILY = "macroscopic_microscopic_frdm"

# Status vocabulary (spec section 15).
STATUS_TOP = (
    "ENGINEERING_PASS_SCIENTIFIC_PASS",
    "ENGINEERING_PASS_SCIENTIFIC_MIXED",
    "ENGINEERING_PASS_SCIENTIFIC_NOT_MET",
    "ENGINEERING_PASS_GATE_NOT_EVALUABLE",
    "INPUT_INTEGRITY_FAILURE",
    "CLAIM_INTEGRITY_FAILURE",
    "INFRASTRUCTURE_FAILURE",
)

NO_POST_TRUTH_TUNING_RULE = (
    "ez-wo14-no-post-truth-tuning-v1: after REAL-BLIND truth unlock, model "
    "definitions, hyperparameters, fit/calibration split, subfederation "
    "membership rule, combination rule, uncertainty rule, thresholds, and "
    "shell observable definitions are frozen; any change requires a new "
    "protocol and a new experiment id"
)
