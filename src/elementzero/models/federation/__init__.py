"""WO-12 — Nuclear Model Federation v1.

A physics-rich, uncertainty-aware model federation built for the new
preregistered EZ-B002-v2 / EZ-B003-v2 qualification protocols. All v1
benchmark artifacts and all v1 baseline models are preserved unchanged; the
federation adds participants, it never replaces controls.
"""

from __future__ import annotations

WO12_ID = "WO-12"
FEDERATION_PROTOCOL_VERSION = "1.0.0"
REPORTS_RELPATH = "reports/model_federation/wo12"

# Independence groups (WO-12 section 12). A federation's diversity is counted
# in groups, never in model ids: residual variants of one base model are not
# independent models.
GROUP_LIQUID_DROP = "liquid_drop_baseline"
GROUP_STATISTICAL_GP = "statistical_gp"
GROUP_SKYRME_EDF_BSKG = "skyrme_edf_bskg"
GROUP_MACRO_MICRO_FRDM = "macroscopic_microscopic_frdm"
GROUP_RELATIVISTIC_EDF_DRHBC = "relativistic_edf_drhbc"
GROUP_RESIDUAL_ML = "residual_ml"
GROUP_COMBINATION = "model_combination"

__all__ = [
    "FEDERATION_PROTOCOL_VERSION",
    "GROUP_COMBINATION",
    "GROUP_LIQUID_DROP",
    "GROUP_MACRO_MICRO_FRDM",
    "GROUP_RELATIVISTIC_EDF_DRHBC",
    "GROUP_RESIDUAL_ML",
    "GROUP_SKYRME_EDF_BSKG",
    "GROUP_STATISTICAL_GP",
    "REPORTS_RELPATH",
    "WO12_ID",
]
