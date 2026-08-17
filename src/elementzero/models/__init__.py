"""ElementZero model ladder.

v1 (frozen): `gp_residual` — the SEMF-backed GP residual model and the
GP-direct control. Both are demoted to permanent controls under protocol
v2.0.0 and are never rerun under a v2 model id.

v2: the backbone is an injected dependency rather than a hard-coded SEMF, the
GP kernel is learned rather than frozen, a kink-capable residual class exists
for shell localization, and every prediction carries a blindness tier.

    gp_calibrated  backbone + learned-kernel GP residual, honest sigma
    shell_aware    free-knot hinge residual, discovery-profile firewall
    blindness      tiers, inheritance, independence groups, claim gate
"""

from elementzero.models.blindness import (
    BLINDNESS_MODULE_VERSION,
    TIER_A,
    TIER_B,
    TIER_C,
    TIER_D,
    TIER_E,
    BackboneProvenance,
    BlindnessError,
    assert_claim_eligible,
    combine_tiers,
    independence_groups,
    resolve_tier,
)
from elementzero.models.gp_calibrated import (
    GP_MODULE_VERSION,
    Backbone,
    CallableBackbone,
    GPResidualV2,
)
from elementzero.models.gp_residual import (
    MODEL_ID_GP_DIRECT,
    MODEL_ID_SEMF_GP,
    SEMFGPResidualModel,
    build_model,
)
from elementzero.models.shell_aware import (
    SHELL_MODULE_VERSION,
    FeatureProfileError,
    KinkLocalization,
    KinkResidualModel,
    localization_metrics,
)

__all__ = [
    # v1 controls
    "MODEL_ID_GP_DIRECT",
    "MODEL_ID_SEMF_GP",
    "SEMFGPResidualModel",
    "build_model",
    # v2 backbone + residual tiers
    "GP_MODULE_VERSION",
    "Backbone",
    "CallableBackbone",
    "GPResidualV2",
    "SHELL_MODULE_VERSION",
    "FeatureProfileError",
    "KinkLocalization",
    "KinkResidualModel",
    "localization_metrics",
    # v2 blindness ledger
    "BLINDNESS_MODULE_VERSION",
    "TIER_A",
    "TIER_B",
    "TIER_C",
    "TIER_D",
    "TIER_E",
    "BackboneProvenance",
    "BlindnessError",
    "assert_claim_eligible",
    "combine_tiers",
    "independence_groups",
    "resolve_tier",
]
