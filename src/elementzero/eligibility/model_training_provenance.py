"""ModelTrainingProvenance records (WO-13 spec sections 3 and 8).

Every model allowed into a real benchmark carries a frozen record of what
its parameters were fitted on, how confidently that is known, and what
blind-use policy follows. The records are documentation of published fact,
not inference: where exact fit membership is unavailable it says so, and
unknown is never treated as permission.
"""

from __future__ import annotations

from typing import Any

from elementzero.eligibility.claim_types import (
    CONFIDENCE_EXACT,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    STRICT_BLIND_CONFIDENCE_RULE,
    assert_confidence,
)
from elementzero.errors import ProtocolError

# Documented BSkG3 fit provenance (Grams et al. 2023): the parameter
# adjustment used AME2020-era experimental masses across the fitted domain.
BSKG3_FIT_POLICY = (
    "ez-wo13-bskg3-ame2020-nonblind-v1: any AME2020 target within the BSkG3 "
    "fitted mass domain is NONBLIND_REFERENCE unless exact model-fit "
    "membership proves exclusion. Publication date is not a blind cutoff, "
    "and masking a mass inside ElementZero does not unsee it for BSkG3."
)

# Documented FRDM95 fit provenance (Moller-Nix-Myers-Swiatecki 1995): the
# constants were adjusted to a 1989-era experimental mass set (the published
# description quotes 1654 masses). The exact membership list is not machine-
# readably distributed; WO-13 therefore uses a conservative historical
# cutoff with an explicit approximation flag and never assumes blindness.
FRDM95_FIT_POLICY = (
    "ez-wo13-frdm95-conservative-historical-v1: exact fit membership is "
    "unavailable, so a target is HISTORICAL_BLIND only when it was not even "
    "a parsed record in the earliest available snapshot (AME1995, an "
    "explicit later-bound proxy for the 1989 fit-era knowledge) and later "
    "became eligible evidence; a target already known by AME1995 is "
    "INELIGIBLE_UNKNOWN_PROVENANCE because membership in the 1654-mass fit "
    "set can be neither proven nor excluded. Unknown is not permission."
)

FRDM95_APPROXIMATION_FLAG = (
    "ame1995-proxy-for-1989-fit-era: AME1995 membership is used as a "
    "conservative LATER bound on 1989 fit-era knowledge (fit set is a "
    "subset of 1989 knowledge, which is a subset of AME1995-era knowledge "
    "for practical purposes); absence from AME1995 is therefore strong "
    "evidence of absence from the fit, while presence proves nothing "
    "either way"
)

BASELINE_FIT_POLICY = (
    "ez-wo13-baseline-freeze-blind-v1: the fit set of a refittable "
    "ElementZero baseline is controlled by the sealed KnowledgeFreeze; "
    "STRICT_BLIND is granted per target from the frozen fit/calibration/"
    "target identity digests and the feature policy, which exclude the "
    "target by construction"
)

DERIVED_FIT_POLICY = (
    "ez-wo13-derived-lineage-v1: residual wrappers and combiners have no "
    "fit provenance of their own beyond the freeze-controlled residual/"
    "weight fitting; their blind-use policy is inherited as the worst "
    "status of their component lineage"
)

_BASELINE_IDS = (
    "EZ-SEMF-LS-v1",
    "EZ-GP-DIRECT-v1",
    "EZ-SEMF-GP-RESIDUAL-v1",
    "EZ-GP-OPTIMIZED-CONTROL-v1",
)

_BASELINE_GROUPS = {
    "EZ-SEMF-LS-v1": "liquid_drop_baseline",
    "EZ-GP-DIRECT-v1": "statistical_gp",
    "EZ-SEMF-GP-RESIDUAL-v1": "statistical_gp",
    "EZ-GP-OPTIMIZED-CONTROL-v1": "statistical_gp",
}

_BASELINE_FAMILIES = {
    "EZ-SEMF-LS-v1": "semf_least_squares",
    "EZ-GP-DIRECT-v1": "gp_direct",
    "EZ-SEMF-GP-RESIDUAL-v1": "semf_gp_residual",
    "EZ-GP-OPTIMIZED-CONTROL-v1": "gp_optimized_control",
}


def _baseline_record(model_id: str) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "family_id": _BASELINE_FAMILIES[model_id],
        "independence_group": _BASELINE_GROUPS[model_id],
        "publication": "ElementZero internal refittable baseline",
        "publication_date": "n/a",
        "fit_data_description": (
            "refit per sealed run on the freeze-approved training corpus; "
            "the sealed KnowledgeFreeze pins fit, calibration, and target "
            "identity digests and the feature policy"
        ),
        "fit_source_editions": ["per-run KnowledgeFreeze training corpus"],
        "fit_cutoff_date": None,
        "exact_fit_membership_available": True,
        "exact_fit_membership_source": (
            "sealed freeze.json training_identity_digest per run"
        ),
        "exact_fit_membership_hash": None,
        "calibration_sources": ["ez-wo12-calibration-split-v1 on the fit corpus"],
        "hyperparameter_sources": [
            "frozen model configuration (no target-dependent selection)"
        ],
        "provenance_confidence": CONFIDENCE_EXACT,
        "default_blind_use_policy": BASELINE_FIT_POLICY,
        "evidence_sources": [
            "elementzero.evidence.freezes.KnowledgeFreeze",
            "sealed split manifests (identity-only)",
        ],
    }


def _derived_record(
    model_id: str,
    *,
    family_id: str,
    independence_group: str,
    base_model_ids: list[str],
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "family_id": family_id,
        "independence_group": independence_group,
        "publication": "ElementZero derived federation participant",
        "publication_date": "n/a",
        "fit_data_description": (
            "derived lineage: residual/weight fitting is freeze-controlled; "
            f"physics provenance is inherited from {sorted(base_model_ids)}"
        ),
        "fit_source_editions": ["per-run KnowledgeFreeze training corpus"],
        "fit_cutoff_date": None,
        "exact_fit_membership_available": True,
        "exact_fit_membership_source": (
            "sealed freeze.json fit/calibration identity digests per run"
        ),
        "exact_fit_membership_hash": None,
        "calibration_sources": ["ez-wo12-calibration-split-v1 on the fit corpus"],
        "hyperparameter_sources": ["ez-wo12-residual-gp-v1 frozen configuration"],
        "provenance_confidence": CONFIDENCE_EXACT,
        "default_blind_use_policy": DERIVED_FIT_POLICY,
        "evidence_sources": [
            "elementzero.models.federation lineage facts",
            *sorted(f"inherits:{m}" for m in base_model_ids),
        ],
    }


MODEL_TRAINING_PROVENANCE: dict[str, dict[str, Any]] = {
    **{model_id: _baseline_record(model_id) for model_id in _BASELINE_IDS},
    "EZ-BSKG3-TABLE-v1": {
        "model_id": "EZ-BSKG3-TABLE-v1",
        "family_id": "skyrme_edf_hfb",
        "independence_group": "skyrme_edf_bskg",
        "publication": (
            "G. Grams et al., 'Skyrme-Hartree-Fock-Bogoliubov mass models "
            "on a 3D mesh: III. From atomic nuclei to neutron stars', "
            "Eur. Phys. J. A 59, 270 (2023)"
        ),
        "publication_date": "2023-11-01",
        "fit_data_description": (
            "BSkG3 parameter adjustment against AME2020-era experimental "
            "masses across the fitted mass domain (plus additional nuclear-"
            "matter and fission constraints)"
        ),
        "fit_source_editions": ["AME2020"],
        "fit_cutoff_date": "2021-03-01",
        "exact_fit_membership_available": False,
        "exact_fit_membership_source": None,
        "exact_fit_membership_hash": None,
        "calibration_sources": ["AME2020-era experimental masses"],
        "hyperparameter_sources": ["published BSkG3 protocol"],
        "provenance_confidence": CONFIDENCE_HIGH,
        "default_blind_use_policy": BSKG3_FIT_POLICY,
        "evidence_sources": [
            "https://doi.org/10.1140/epja/s10050-023-01158-6",
            "https://arxiv.org/abs/2307.14276",
        ],
    },
    "EZ-FRDM95-TABLE-v1": {
        "model_id": "EZ-FRDM95-TABLE-v1",
        "family_id": "macroscopic_microscopic",
        "independence_group": "macroscopic_microscopic_frdm",
        "publication": (
            "P. Moller, J. R. Nix, W. D. Myers, W. J. Swiatecki, 'Nuclear "
            "ground-state masses and deformations', At. Data Nucl. Data "
            "Tables 59, 185 (1995)"
        ),
        "publication_date": "1995-03-01",
        "fit_data_description": (
            "FRDM(1992) constants adjusted to a 1989-era experimental mass "
            "set (published description quotes 1654 masses); the exact "
            "membership list is not machine-readably distributed"
        ),
        "fit_source_editions": ["1989-era evaluated masses (pre-AME1995)"],
        "fit_cutoff_date": "1989-12-31",
        "exact_fit_membership_available": False,
        "exact_fit_membership_source": None,
        "exact_fit_membership_hash": None,
        "calibration_sources": ["same 1989-era mass set"],
        "hyperparameter_sources": ["published FRDM protocol"],
        "provenance_confidence": CONFIDENCE_MEDIUM,
        "default_blind_use_policy": FRDM95_FIT_POLICY,
        "evidence_sources": [
            "https://doi.org/10.1006/adnd.1995.1002",
            "https://www.osti.gov/biblio/86405",
            "https://arxiv.org/abs/nucl-th/9710049",
            FRDM95_APPROXIMATION_FLAG,
        ],
    },
    "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1": _derived_record(
        "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",
        family_id="skyrme_edf_hfb+gp_residual",
        independence_group="residual_ml",
        base_model_ids=["EZ-BSKG3-TABLE-v1"],
    ),
    "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1": _derived_record(
        "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
        family_id="macroscopic_microscopic+gp_residual",
        independence_group="residual_ml",
        base_model_ids=["EZ-FRDM95-TABLE-v1"],
    ),
    "EZ-FED-UNIFORM-ENSEMBLE-v1": _derived_record(
        "EZ-FED-UNIFORM-ENSEMBLE-v1",
        family_id="federation_combination",
        independence_group="model_combination",
        base_model_ids=[
            "EZ-BSKG3-TABLE-v1",
            "EZ-FRDM95-TABLE-v1",
            "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",
            "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
        ],
    ),
    "EZ-FED-VALIDATION-WEIGHTED-v1": _derived_record(
        "EZ-FED-VALIDATION-WEIGHTED-v1",
        family_id="federation_combination",
        independence_group="model_combination",
        base_model_ids=[
            "EZ-BSKG3-TABLE-v1",
            "EZ-FRDM95-TABLE-v1",
            "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",
            "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
        ],
    ),
}

# Physics lineage relationships the eligibility engine walks.
BASE_MODEL_OF = {
    "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1": "EZ-BSKG3-TABLE-v1",
    "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1": "EZ-FRDM95-TABLE-v1",
}

COMBINER_COMPONENTS = {
    "EZ-FED-UNIFORM-ENSEMBLE-v1": [
        "EZ-BSKG3-TABLE-v1",
        "EZ-FRDM95-TABLE-v1",
        "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",
        "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
    ],
    "EZ-FED-VALIDATION-WEIGHTED-v1": [
        "EZ-BSKG3-TABLE-v1",
        "EZ-FRDM95-TABLE-v1",
        "EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1",
        "EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1",
    ],
}

BASELINE_MODEL_IDS = _BASELINE_IDS
PHYSICS_TABLE_MODEL_IDS = ("EZ-BSKG3-TABLE-v1", "EZ-FRDM95-TABLE-v1")


def provenance_record(model_id: str) -> dict[str, Any]:
    try:
        return dict(MODEL_TRAINING_PROVENANCE[model_id])
    except KeyError as exc:
        raise ProtocolError(
            f"{model_id} has no ModelTrainingProvenance record; a model "
            "without provenance may not enter a real benchmark"
        ) from exc


def audit_models(*, registry_manifest: dict[str, Any]) -> dict[str, Any]:
    """Every registered participant must carry a consistent record."""
    participants = registry_manifest["participants"]
    missing = sorted(set(participants) - set(MODEL_TRAINING_PROVENANCE))
    extra = sorted(set(MODEL_TRAINING_PROVENANCE) - set(participants))
    if missing:
        raise ProtocolError(f"models without training provenance: {missing}")
    mismatched = []
    for model_id, payload in sorted(participants.items()):
        record = MODEL_TRAINING_PROVENANCE[model_id]
        assert_confidence(record["provenance_confidence"])
        if record["independence_group"] != payload["independence_group"]:
            mismatched.append(model_id)
    if mismatched:
        raise ProtocolError(
            f"provenance independence groups disagree with the registry: {mismatched}"
        )
    return {
        "work_order": "WO-13",
        "strict_blind_confidence_rule": STRICT_BLIND_CONFIDENCE_RULE,
        "n_models": len(participants),
        "records": {m: MODEL_TRAINING_PROVENANCE[m] for m in sorted(participants)},
        "records_not_in_registry": extra,
        "status": "COMPLETE",
    }
