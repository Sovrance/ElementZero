"""Target-by-model blindness records (WO-13 spec sections 9-12).

One TargetBlindnessRecord per (target, model). The base decisions live
here; residual and combiner lineages inherit through
``residual_eligibility`` and ``combination_eligibility`` — the worst status
always wins, so nothing downstream can launder a nonblind base.
"""

from __future__ import annotations

from typing import Any

from elementzero.data.identity import parse_nuclide_id
from elementzero.eligibility.claim_types import (
    CONFIDENCE_EXACT,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    HISTORICAL_BLIND,
    INELIGIBLE_UNKNOWN_PROVENANCE,
    NONBLIND_REFERENCE,
    STRICT_BLIND,
    strict_gate_eligible,
)
from elementzero.eligibility.historical_sources import SourceChronology
from elementzero.eligibility.model_training_provenance import (
    BASE_MODEL_OF,
    BASELINE_MODEL_IDS,
    COMBINER_COMPONENTS,
    MODEL_TRAINING_PROVENANCE,
)
from elementzero.errors import ProtocolError

ELIGIBILITY_MATRIX_RULE = (
    "ez-wo13-eligibility-matrix-v1: one record per target x model; base "
    "decisions from documented model-fit provenance and the hashed source "
    "chronology; residual and combiner records inherit the worst status of "
    "their lineage. A target hidden from ElementZero is not automatically "
    "blind to an imported physics table."
)


def _record_shell(
    *,
    benchmark_id: str,
    experiment_id: str,
    nuclide_id: str,
    model_id: str,
    target_truth_edition: str,
) -> dict[str, Any]:
    z, n = parse_nuclide_id(nuclide_id)
    return {
        "benchmark_id": benchmark_id,
        "experiment_id": experiment_id,
        "nuclide_id": nuclide_id,
        "Z": z,
        "N": n,
        "A": z + n,
        "model_id": model_id,
        "independence_group": MODEL_TRAINING_PROVENANCE[model_id][
            "independence_group"
        ],
        "target_truth_edition": target_truth_edition,
        "base_fit_overlap": None,
        "residual_fit_overlap": None,
        "calibration_overlap": None,
        "hyperparameter_overlap": None,
        "combination_weight_overlap": None,
        "fit_cutoff_date": MODEL_TRAINING_PROVENANCE[model_id]["fit_cutoff_date"],
        "target_known_at_cutoff": None,
        "exact_fit_membership": None,
        "evidence_sources": list(
            MODEL_TRAINING_PROVENANCE[model_id]["evidence_sources"]
        ),
    }


def _finish(record: dict[str, Any], *, claim: str, confidence: str, reason: str):
    record["claim_type"] = claim
    record["provenance_confidence"] = confidence
    record["strict_gate_eligible"] = strict_gate_eligible(claim, confidence)
    record["eligibility_reason"] = reason
    return record


def baseline_record(
    *,
    benchmark_id: str,
    experiment_id: str,
    nuclide_id: str,
    model_id: str,
    target_truth_edition: str,
) -> dict[str, Any]:
    """Refittable baseline: the sealed freeze excludes the target by design."""
    if model_id not in BASELINE_MODEL_IDS:
        raise ProtocolError(f"{model_id} is not a refittable baseline")
    record = _record_shell(
        benchmark_id=benchmark_id,
        experiment_id=experiment_id,
        nuclide_id=nuclide_id,
        model_id=model_id,
        target_truth_edition=target_truth_edition,
    )
    record.update(
        base_fit_overlap=False,
        residual_fit_overlap=False,
        calibration_overlap=False,
        hyperparameter_overlap=False,
        combination_weight_overlap=False,
        exact_fit_membership=False,
    )
    return _finish(
        record,
        claim=STRICT_BLIND,
        confidence=CONFIDENCE_EXACT,
        reason=(
            "fit set is controlled by the sealed KnowledgeFreeze: the "
            "target identity is excluded from fit, calibration, and "
            "hyperparameter selection by the frozen identity digests and "
            "feature policy, enforced at seal and score time"
        ),
    )


def bskg3_record(
    *,
    benchmark_id: str,
    experiment_id: str,
    nuclide_id: str,
    target_truth_edition: str,
    chronology: SourceChronology,
) -> dict[str, Any]:
    """BSkG3 against AME2020 defaults NONBLIND_REFERENCE (spec section 10)."""
    record = _record_shell(
        benchmark_id=benchmark_id,
        experiment_id=experiment_id,
        nuclide_id=nuclide_id,
        model_id="EZ-BSKG3-TABLE-v1",
        target_truth_edition=target_truth_edition,
    )
    if target_truth_edition == "AME2020":
        record.update(
            base_fit_overlap=True,
            target_known_at_cutoff=chronology.was_target_known_by(
                nuclide_id, "AME2020"
            ),
            exact_fit_membership=None,  # unavailable; overlap is the default
        )
        return _finish(
            record,
            claim=NONBLIND_REFERENCE,
            confidence=CONFIDENCE_HIGH,
            reason=(
                "the published BSkG3 parameter adjustment used AME2020-era "
                "experimental masses; without exact fit membership proving "
                "exclusion, every AME2020 target in the fitted domain is "
                "nonblind by default — hiding the mass inside ElementZero "
                "does not unsee it"
            ),
        )
    # A non-AME2020 truth edition is not part of WO-13's real plans; refuse
    # to guess rather than invent an eligibility.
    return _finish(
        record,
        claim=INELIGIBLE_UNKNOWN_PROVENANCE,
        confidence=CONFIDENCE_MEDIUM,
        reason=(
            f"no frozen BSkG3 policy exists for truth edition "
            f"{target_truth_edition!r}; unknown is not permission"
        ),
    )


def frdm95_record(
    *,
    benchmark_id: str,
    experiment_id: str,
    nuclide_id: str,
    target_truth_edition: str,
    chronology: SourceChronology,
) -> dict[str, Any]:
    """FRDM95 conservative historical eligibility (spec section 11)."""
    record = _record_shell(
        benchmark_id=benchmark_id,
        experiment_id=experiment_id,
        nuclide_id=nuclide_id,
        model_id="EZ-FRDM95-TABLE-v1",
        target_truth_edition=target_truth_edition,
    )
    known_1995 = chronology.was_target_known_by(nuclide_id, "AME1995")
    eligible_now = chronology.was_target_eligible_by(
        nuclide_id, target_truth_edition
    )
    record.update(target_known_at_cutoff=known_1995, exact_fit_membership=None)
    if known_1995:
        return _finish(
            record,
            claim=INELIGIBLE_UNKNOWN_PROVENANCE,
            confidence=CONFIDENCE_MEDIUM,
            reason=(
                "the target was already a parsed record in AME1995 (the "
                "conservative later-bound proxy for the 1989 fit era), so "
                "membership in the 1654-mass FRDM95 fit set can be neither "
                "proven nor excluded; unknown fit membership is never "
                "assumed blind"
            ),
        )
    if not eligible_now:
        return _finish(
            record,
            claim=INELIGIBLE_UNKNOWN_PROVENANCE,
            confidence=CONFIDENCE_MEDIUM,
            reason=(
                f"the target never became ground-truth-eligible evidence in "
                f"{target_truth_edition}; there is nothing to score blind"
            ),
        )
    record["base_fit_overlap"] = False
    return _finish(
        record,
        claim=HISTORICAL_BLIND,
        confidence=CONFIDENCE_MEDIUM,
        reason=(
            "the target was not even a parsed record in AME1995 — the "
            "explicit later-bound proxy for the 1989 fit-era knowledge — "
            "and became eligible evidence only in a later edition, with no "
            "evidence of FRDM95 fit membership; HISTORICAL_BLIND from the "
            "documented cutoff, never STRICT_BLIND, per the approximation "
            "flag in the provenance record"
        ),
    )


def base_model_record(
    *,
    benchmark_id: str,
    experiment_id: str,
    nuclide_id: str,
    model_id: str,
    target_truth_edition: str,
    chronology: SourceChronology,
) -> dict[str, Any]:
    """Dispatch for non-derived participants."""
    if model_id in BASELINE_MODEL_IDS:
        return baseline_record(
            benchmark_id=benchmark_id,
            experiment_id=experiment_id,
            nuclide_id=nuclide_id,
            model_id=model_id,
            target_truth_edition=target_truth_edition,
        )
    if model_id == "EZ-BSKG3-TABLE-v1":
        return bskg3_record(
            benchmark_id=benchmark_id,
            experiment_id=experiment_id,
            nuclide_id=nuclide_id,
            target_truth_edition=target_truth_edition,
            chronology=chronology,
        )
    if model_id == "EZ-FRDM95-TABLE-v1":
        return frdm95_record(
            benchmark_id=benchmark_id,
            experiment_id=experiment_id,
            nuclide_id=nuclide_id,
            target_truth_edition=target_truth_edition,
            chronology=chronology,
        )
    raise ProtocolError(f"{model_id} has no base eligibility rule")


def build_matrix(
    *,
    benchmark_id: str,
    experiment_id: str,
    target_ids: list[str],
    target_truth_edition: str,
    chronology: SourceChronology,
    model_ids: list[str] | None = None,
) -> dict[str, Any]:
    """The full target x model eligibility matrix for one experiment."""
    from elementzero.eligibility.combination_eligibility import combiner_record
    from elementzero.eligibility.residual_eligibility import residual_record

    models = list(model_ids or sorted(MODEL_TRAINING_PROVENANCE))
    records: list[dict[str, Any]] = []
    for nuclide_id in sorted(target_ids):
        base_records: dict[str, dict[str, Any]] = {}
        for model_id in models:
            if model_id in BASE_MODEL_OF or model_id in COMBINER_COMPONENTS:
                continue
            base_records[model_id] = base_model_record(
                benchmark_id=benchmark_id,
                experiment_id=experiment_id,
                nuclide_id=nuclide_id,
                model_id=model_id,
                target_truth_edition=target_truth_edition,
                chronology=chronology,
            )
        derived: dict[str, dict[str, Any]] = {}
        for model_id in models:
            if model_id in BASE_MODEL_OF:
                derived[model_id] = residual_record(
                    model_id=model_id,
                    base_record=base_records[BASE_MODEL_OF[model_id]],
                )
        for model_id in models:
            if model_id in COMBINER_COMPONENTS:
                contributors = {
                    cid: {**base_records, **derived}[cid]
                    for cid in COMBINER_COMPONENTS[model_id]
                }
                derived[model_id] = combiner_record(
                    model_id=model_id, contributor_records=contributors
                )
        for model_id in models:
            records.append({**base_records, **derived}[model_id])
    return {
        "work_order": "WO-13",
        "rule": ELIGIBILITY_MATRIX_RULE,
        "benchmark_id": benchmark_id,
        "experiment_id": experiment_id,
        "target_truth_edition": target_truth_edition,
        "n_targets": len(target_ids),
        "n_models": len(models),
        "model_ids": models,
        "records": records,
    }
