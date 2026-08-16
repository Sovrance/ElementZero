"""EZ-B003 discovery diagnostics: did the shell structure come back? (WO-10).

Mass metrics stay required (``elementzero.benchmark.metrics``). What this module
adds is the shell-structure question, per hidden closure (WO-10 section 6)::

    true_<indicator>            from the snapshot, read only after the seal
    predicted_<indicator>       from the sealed predictions plus training masses
    absolute_<indicator>_error  abs(predicted - true)
    sign_recovered              sign(predicted) == sign(true)
    local_peak_rank             rank of the withheld closure inside the
                                preregistered search window

Two deliberate restraints:

* the peak rank is reported as ``rank_1`` / ``top_3`` / ``outside_top_3`` and is
  never converted into a p-value, because no null model is preregistered
  (WO-10 section 6),
* nothing here promotes a local maximum to a magic number.

Every function is a pure function of its inputs, which is what makes the
diagnostics reproducible: the same sealed predictions and the same snapshot
always produce the same rows in the same order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from elementzero.benchmark.shell_masks import (
    MIN_PEAK_CANDIDATES,
    PEAK_PARITY_RULE,
    PEAK_WINDOW,
    STATUS_EVALUABLE,
    STATUS_NOT_EVALUABLE,
)
from elementzero.errors import ProtocolError, SchemaError
from elementzero.physics.separation import (
    DERIVED_OBSERVABLE_RULE,
    SHELL_INDICATOR_CAVEAT,
    BindingSurface,
    derivation_record,
    observable_value,
)

DISCOVERY_METRICS_POLICY_ID = "ez-b003-discovery-metrics-v1"

RANK_1 = "rank_1"
TOP_3 = "top_3"
OUTSIDE_TOP_3 = "outside_top_3"
PEAK_RANK_BUCKETS: tuple[str, ...] = (RANK_1, TOP_3, OUTSIDE_TOP_3)
TOP_K = 3

# Float noise floor for the sign comparison. A shell gap of a nanoelectronvolt is
# not a sign, it is arithmetic.
SIGN_EPSILON_MeV = 1.0e-9

PEAK_RANK_RULE = (
    "ez-b003-peak-rank-v1: candidates inside the preregistered search window are "
    "ordered by predicted indicator value, descending, because a shell closure "
    "shows up as a positive local excess. Ties break by the candidate coordinate, "
    "ascending. The rank of the withheld closure is reported as rank_1, top_3, or "
    "outside_top_3. A magnitude-ordered rank is reported next to it as a secondary "
    "diagnostic. Neither rank is converted into a p-value: no null model is "
    "preregistered."
)

DERIVATION_COMPOSITION_RULE = (
    "ez-b003-hybrid-derivation-v1: the predicted indicator is built from the "
    "sealed model prediction at every masked input and from the frozen training "
    "mass at every unmasked input. The composition is fixed by the mask geometry "
    "before any hidden truth is read, so it cannot be tuned after scoring. The "
    "true indicator is built from snapshot truth at every input."
)

# --------------------------------------------------------------------------- #
# Preregistered rediscovery criterion                                         #
# --------------------------------------------------------------------------- #
# WO-10 section 9. These thresholds were calibrated on the synthetic shell
# benchmark only (mechanics calibration), frozen here, and preregistered before
# any real closure of an evaluated mass table is scored. They may not be edited
# after a real scoring run: a changed threshold requires a new B003 protocol
# version and a complete rerun.

REDISCOVERY_CRITERION_ID = "ez-b003-rediscovery-criterion-v1"
MIN_SIGN_FRACTION = 0.75
MIN_TOP_K_FRACTION = 0.75
MIN_RANK_1_FRACTION = 0.50
MAX_CALIBRATION_ERROR_90 = 0.15

VERDICT_MET = "CRITERION_MET"
VERDICT_NOT_MET = "CRITERION_NOT_MET"
VERDICT_NOT_YET_SCORED = "NOT_YET_SCORED"

CRITERION_SCOPE_RULE = (
    "The criterion answers one narrow question: was known shell-related mass "
    "structure rediscovered under controlled masking? Meeting it is not evidence "
    "for any predicted new closure, and not evidence for an island of stability at "
    "Z = 154. That claim needs independent physics-model ensembles, deformation, "
    "fission, decay competition, and far larger extrapolation uncertainty."
)


def rediscovery_criterion() -> dict[str, Any]:
    """The frozen numerical thresholds, as written into a preregistration."""
    return {
        "criterion_id": REDISCOVERY_CRITERION_ID,
        "min_sign_fraction": MIN_SIGN_FRACTION,
        "min_top_k_fraction": MIN_TOP_K_FRACTION,
        "min_rank_1_fraction": MIN_RANK_1_FRACTION,
        "top_k": TOP_K,
        "max_calibration_error_90": MAX_CALIBRATION_ERROR_90,
        "unit_of_evaluation": (
            "one supported chain of one evaluable closure; fractions are over "
            "chains, and every evaluable closure is reported separately as well"
        ),
        "structure": (
            "minimum fraction with correct shell-gap sign AND minimum fraction "
            "ranked top-k AND minimum fraction ranked first AND a calibrated mass "
            "coverage requirement on the same masked targets"
        ),
        "calibration_requirement": (
            "abs(coverage_90 - 0.90) <= max_calibration_error_90 on the masked "
            "targets, so a model cannot satisfy the shell criterion with "
            "uncertainties that are not honest"
        ),
        "frozen_before": (
            "any closure of an evaluated mass table is scored; thresholds were "
            "calibrated on the synthetic shell benchmark mechanics only"
        ),
        "no_post_hoc_rule": (
            "A threshold selected after real scoring is a stop condition, not a "
            "result. Changing one requires a new B003 protocol version and a "
            "complete rerun with the old result preserved."
        ),
        "scope_rule": CRITERION_SCOPE_RULE,
        "peak_rank_rule": PEAK_RANK_RULE,
        "no_p_value_rule": (
            "No p-value is reported for peak localization: no null model is "
            "preregistered in B003 v1."
        ),
    }


# --------------------------------------------------------------------------- #
# Signs                                                                       #
# --------------------------------------------------------------------------- #


def sign_of(value: float | None, *, epsilon: float = SIGN_EPSILON_MeV) -> int | None:
    """-1, 0, or +1 with a noise floor; None for a missing value."""
    if value is None:
        return None
    if abs(float(value)) <= float(epsilon):
        return 0
    return 1 if float(value) > 0.0 else -1


def sign_recovered(
    true_value: float | None,
    predicted_value: float | None,
    *,
    epsilon: float = SIGN_EPSILON_MeV,
) -> bool | None:
    """Whether the predicted indicator has the sign of the true one."""
    true_sign = sign_of(true_value, epsilon=epsilon)
    predicted_sign = sign_of(predicted_value, epsilon=epsilon)
    if true_sign is None or predicted_sign is None:
        return None
    return true_sign == predicted_sign


# --------------------------------------------------------------------------- #
# Peak localization                                                           #
# --------------------------------------------------------------------------- #


def peak_ranking(
    values: Mapping[int, float],
    *,
    closure: int,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """Rank the closure inside the search window (see PEAK_RANK_RULE)."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    ordered = sorted(
        ((int(c), float(v)) for c, v in values.items()),
        key=lambda item: (-item[1], item[0]),
    )
    by_magnitude = sorted(
        ((int(c), float(v)) for c, v in values.items()),
        key=lambda item: (-abs(item[1]), item[0]),
    )
    coordinates = [c for c, _ in ordered]
    rank = coordinates.index(int(closure)) + 1 if int(closure) in coordinates else None
    magnitude_rank = (
        [c for c, _ in by_magnitude].index(int(closure)) + 1
        if int(closure) in coordinates
        else None
    )
    if rank is None:
        bucket = None
    elif rank == 1:
        bucket = RANK_1
    elif rank <= top_k:
        bucket = TOP_3 if top_k == TOP_K else f"top_{top_k}"
    else:
        bucket = OUTSIDE_TOP_3 if top_k == TOP_K else f"outside_top_{top_k}"
    return {
        "closure": int(closure),
        "local_peak_rank": rank,
        "local_peak_rank_by_magnitude": magnitude_rank,
        "rank_bucket": bucket,
        "in_top_k": None if rank is None else rank <= top_k,
        "top_k": int(top_k),
        "n_candidates": len(ordered),
        "candidates": [{"coordinate": c, "value_MeV": v} for c, v in ordered],
        "peak_rank_rule": PEAK_RANK_RULE,
        "peak_window_rule": PEAK_PARITY_RULE,
    }


# --------------------------------------------------------------------------- #
# Per-chain discovery row                                                     #
# --------------------------------------------------------------------------- #


def chain_discovery_row(
    *,
    mask,
    chain: int,
    truth_surface: BindingSurface,
    predicted_surface: BindingSurface,
    peak_window: int = PEAK_WINDOW,
    min_peak_candidates: int = MIN_PEAK_CANDIDATES,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """Discovery diagnostics for one chain of one masked closure."""
    indicator = mask.indicator
    z, n = mask.point(chain=chain, coordinate=mask.closure)
    true_value = observable_value(indicator, truth_surface, z=z, n=n)
    predicted_value = observable_value(indicator, predicted_surface, z=z, n=n)

    true_window: dict[int, float] = {}
    predicted_window: dict[int, float] = {}
    for coordinate in mask.peak_candidates(window=peak_window):
        cz, cn = mask.point(chain=chain, coordinate=coordinate)
        true_candidate = observable_value(indicator, truth_surface, z=cz, n=cn)
        predicted_candidate = observable_value(indicator, predicted_surface, z=cz, n=cn)
        if true_candidate is not None and predicted_candidate is not None:
            true_window[coordinate] = true_candidate
            predicted_window[coordinate] = predicted_candidate

    error = (
        None
        if true_value is None or predicted_value is None
        else abs(float(predicted_value) - float(true_value))
    )
    evaluable = (
        true_value is not None
        and predicted_value is not None
        and len(predicted_window) >= int(min_peak_candidates)
        and mask.closure in predicted_window
    )
    reasons = []
    if true_value is None:
        reasons.append(f"true {indicator} is not computable for this chain")
    if predicted_value is None:
        reasons.append(f"predicted {indicator} is not computable for this chain")
    if len(predicted_window) < int(min_peak_candidates):
        reasons.append(
            f"{len(predicted_window)} comparable window positions; "
            f"MIN_PEAK_CANDIDATES is {int(min_peak_candidates)}"
        )
    elif mask.closure not in predicted_window:
        reasons.append("the closure itself has no comparable indicator value")

    row: dict[str, Any] = {
        "challenge_id": mask.challenge_id,
        "mask_id": mask.mask_id,
        "axis": mask.axis,
        "closure": mask.closure,
        "chain": int(chain),
        "chain_axis": mask.span_axis_label,
        "nuclide_id": f"Z{z}-N{n}",
        "Z": z,
        "N": n,
        "indicator": indicator,
        "status": STATUS_EVALUABLE if evaluable else STATUS_NOT_EVALUABLE,
        "reasons": reasons,
        f"true_{indicator}": true_value,
        f"predicted_{indicator}": predicted_value,
        f"absolute_{indicator}_error": error,
        "sign_recovered": sign_recovered(true_value, predicted_value),
        "true_sign": sign_of(true_value),
        "predicted_sign": sign_of(predicted_value),
        "derivation": derivation_record(indicator, predicted_surface, z=z, n=n),
        "truth_derivation": derivation_record(indicator, truth_surface, z=z, n=n),
        "derivation_composition_rule": DERIVATION_COMPOSITION_RULE,
        "derived": True,
        "independent_evidence": False,
    }
    if evaluable:
        predicted_rank = peak_ranking(predicted_window, closure=mask.closure, top_k=top_k)
        true_rank = peak_ranking(true_window, closure=mask.closure, top_k=top_k)
        row["predicted_peak"] = predicted_rank
        row["true_peak"] = true_rank
        row["local_peak_rank"] = predicted_rank["local_peak_rank"]
        row["local_peak_rank_by_magnitude"] = predicted_rank["local_peak_rank_by_magnitude"]
        row["rank_bucket"] = predicted_rank["rank_bucket"]
        row["in_top_k"] = predicted_rank["in_top_k"]
        row["n_peak_candidates"] = predicted_rank["n_candidates"]
        row["true_local_peak_rank"] = true_rank["local_peak_rank"]
    else:
        row["predicted_peak"] = None
        row["true_peak"] = None
        row["local_peak_rank"] = None
        row["local_peak_rank_by_magnitude"] = None
        row["rank_bucket"] = None
        row["in_top_k"] = None
        row["n_peak_candidates"] = len(predicted_window)
        row["true_local_peak_rank"] = None
    return row


def _fraction(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def closure_discovery_metrics(
    rows: Sequence[Mapping[str, Any]],
    *,
    mask,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """Aggregate one closure's chain rows without dropping the unevaluable ones."""
    indicator = mask.indicator
    scored = [r for r in rows if r["status"] == STATUS_EVALUABLE]
    n = len(scored)
    signs = [bool(r["sign_recovered"]) for r in scored]
    ranks = [int(r["local_peak_rank"]) for r in scored]
    errors = [float(r[f"absolute_{indicator}_error"]) for r in scored]
    buckets = {bucket: sum(1 for r in scored if r["rank_bucket"] == bucket) for bucket in PEAK_RANK_BUCKETS}
    return {
        "challenge_id": mask.challenge_id,
        "mask_id": mask.mask_id,
        "axis": mask.axis,
        "closure": mask.closure,
        "indicator": indicator,
        "discovery_metrics_policy_id": DISCOVERY_METRICS_POLICY_ID,
        "n_chains": len(rows),
        "n_evaluable_chains": n,
        "n_not_evaluable_chains": len(rows) - n,
        "not_evaluable_chains": [
            {"chain": r["chain"], "reasons": list(r["reasons"])}
            for r in rows
            if r["status"] != STATUS_EVALUABLE
        ],
        "sign_recovered_count": sum(1 for s in signs if s),
        "sign_recovered_fraction": _fraction(sum(1 for s in signs if s), n),
        "rank_1_count": buckets[RANK_1],
        "rank_1_fraction": _fraction(buckets[RANK_1], n),
        "top_k_count": sum(1 for r in ranks if r <= top_k),
        "top_k_fraction": _fraction(sum(1 for r in ranks if r <= top_k), n),
        "outside_top_k_count": buckets[OUTSIDE_TOP_3],
        "rank_buckets": buckets,
        "mean_absolute_indicator_error_MeV": (sum(errors) / n) if n else None,
        "max_absolute_indicator_error_MeV": max(errors) if errors else None,
        "median_true_indicator_MeV": _median([float(r[f"true_{indicator}"]) for r in scored]),
        "median_predicted_indicator_MeV": _median(
            [float(r[f"predicted_{indicator}"]) for r in scored]
        ),
        "top_k": int(top_k),
        "chains": list(rows),
        "derived": True,
        "independent_evidence": False,
        "derivation_rule": DERIVED_OBSERVABLE_RULE,
        "derivation_composition_rule": DERIVATION_COMPOSITION_RULE,
        "shell_indicator_caveat": SHELL_INDICATOR_CAVEAT,
    }


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    import statistics

    return float(statistics.median(values))


def aggregate_discovery(
    closures: Sequence[Mapping[str, Any]],
    *,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """Pool the chain rows of every evaluable closure of one model."""
    chains = [chain for closure in closures for chain in closure["chains"]]
    scored = [c for c in chains if c["status"] == STATUS_EVALUABLE]
    n = len(scored)
    sign_hits = sum(1 for c in scored if bool(c["sign_recovered"]))
    rank_1 = sum(1 for c in scored if int(c["local_peak_rank"]) == 1)
    top = sum(1 for c in scored if int(c["local_peak_rank"]) <= top_k)
    return {
        "discovery_metrics_policy_id": DISCOVERY_METRICS_POLICY_ID,
        "n_closures": len(closures),
        "n_chains": len(chains),
        "n_evaluable_chains": n,
        "sign_recovered_count": sign_hits,
        "sign_recovered_fraction": _fraction(sign_hits, n),
        "rank_1_count": rank_1,
        "rank_1_fraction": _fraction(rank_1, n),
        "top_k_count": top,
        "top_k_fraction": _fraction(top, n),
        "top_k": int(top_k),
        "per_closure": [
            {
                "challenge_id": closure["challenge_id"],
                "mask_id": closure["mask_id"],
                "indicator": closure["indicator"],
                "n_evaluable_chains": closure["n_evaluable_chains"],
                "sign_recovered_fraction": closure["sign_recovered_fraction"],
                "rank_1_fraction": closure["rank_1_fraction"],
                "top_k_fraction": closure["top_k_fraction"],
                "mean_absolute_indicator_error_MeV": closure[
                    "mean_absolute_indicator_error_MeV"
                ],
            }
            for closure in sorted(closures, key=lambda c: c["challenge_id"])
        ],
        "derived": True,
        "independent_evidence": False,
        "derivation_rule": DERIVED_OBSERVABLE_RULE,
        "shell_indicator_caveat": SHELL_INDICATOR_CAVEAT,
    }


# --------------------------------------------------------------------------- #
# H0 / H1 bookkeeping                                                         #
# --------------------------------------------------------------------------- #
# WO-10 section 10. Two competing structures per masked closure, distinguished
# by one preregistered observable. This is bookkeeping: which structure a surface
# supports, and by what rule. It is not a magic-number claim.

HYPOTHESIS_H0 = "H0"
HYPOTHESIS_H1 = "H1"
HYPOTHESIS_LABELS: tuple[str, ...] = (HYPOTHESIS_H0, HYPOTHESIS_H1)

# A surface selects a hypothesis only with a strict majority of the closure's
# evaluable chains. A single chain is an anecdote about one isotopic chain.
HYPOTHESIS_MAJORITY = 0.5

SURFACE_PREDICTION = "prediction"
SURFACE_TRUTH = "truth"
SURFACES: tuple[str, ...] = (SURFACE_PREDICTION, SURFACE_TRUTH)

HYPOTHESIS_DECISION_RULE = (
    "ez-b003-hypothesis-decision-v1: for one masked closure and one surface, a "
    "chain supports H1 when the shell-gap indicator at the withheld closure is "
    "positive and ranks first inside the preregistered window, and supports H0 "
    "when the indicator is not positive. H1 is SELECTED_REPRESENTATIVE for that "
    "surface when a strict majority of the closure's evaluable chains support it, "
    "H0 is SELECTED_REPRESENTATIVE when a strict majority support H0, and both "
    "stay ACTIVE otherwise. Two resolutions are recorded per closure: one from "
    "snapshot truth, which restates what the known chart contains, and one from "
    "the sealed reconstruction, which is the benchmark question. Neither promotes "
    "a local maximum to a magic number."
)


def hypothesis_statements(*, indicator: str, closure_label: str) -> dict[str, str]:
    """The two statements the benchmark is asked to distinguish."""
    return {
        HYPOTHESIS_H0: (
            f"H0: no local shell discontinuity at {closure_label}. The reconstructed "
            f"{indicator} there is not a positive local excess inside the "
            "preregistered search window."
        ),
        HYPOTHESIS_H1: (
            f"H1: a local shell discontinuity at {closure_label}. The reconstructed "
            f"{indicator} there is a positive local excess and ranks first inside "
            "the preregistered search window."
        ),
    }


def hypothesis_resolution(
    rows: Sequence[Mapping[str, Any]],
    *,
    indicator: str,
    surface: str = SURFACE_PREDICTION,
    epsilon: float = SIGN_EPSILON_MeV,
) -> dict[str, Any]:
    """Which hypothesis one surface supports for one closure (see the rule)."""
    if surface not in SURFACES:
        raise SchemaError(f"unsupported surface {surface!r}; supported are {list(SURFACES)}")
    value_key = f"true_{indicator}" if surface == SURFACE_TRUTH else f"predicted_{indicator}"
    rank_key = "true_local_peak_rank" if surface == SURFACE_TRUTH else "local_peak_rank"
    scored = [r for r in rows if r["status"] == STATUS_EVALUABLE]
    n = len(scored)
    supports_h1 = [
        r
        for r in scored
        if r[value_key] is not None
        and float(r[value_key]) > float(epsilon)
        and r[rank_key] is not None
        and int(r[rank_key]) == 1
    ]
    supports_h0 = [
        r
        for r in scored
        if r[value_key] is not None and float(r[value_key]) <= float(epsilon)
    ]
    fraction_h1 = _fraction(len(supports_h1), n)
    fraction_h0 = _fraction(len(supports_h0), n)
    selected: str | None = None
    if fraction_h1 is not None and fraction_h1 > HYPOTHESIS_MAJORITY:
        selected = HYPOTHESIS_H1
    elif fraction_h0 is not None and fraction_h0 > HYPOTHESIS_MAJORITY:
        selected = HYPOTHESIS_H0
    return {
        "surface": surface,
        "indicator": indicator,
        "selected_label": selected,
        "n_evaluable_chains": n,
        "n_supporting_H1": len(supports_h1),
        "n_supporting_H0": len(supports_h0),
        "fraction_supporting_H1": fraction_h1,
        "fraction_supporting_H0": fraction_h0,
        "majority_threshold": HYPOTHESIS_MAJORITY,
        "decision_rule": HYPOTHESIS_DECISION_RULE,
        "scope_rule": CRITERION_SCOPE_RULE,
    }


# --------------------------------------------------------------------------- #
# Criterion evaluation                                                        #
# --------------------------------------------------------------------------- #


def evaluate_criterion(
    aggregate: Mapping[str, Any],
    *,
    calibration_error_90: float | None,
    scope: str,
    criterion: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the frozen criterion to one model's pooled discovery metrics.

    ``scope`` names what was scored (for example ``synthetic`` or ``AME2020``).
    The verdict is recorded next to the scope so a synthetic mechanics result can
    never be read as a statement about evaluated mass tables.
    """
    frozen = dict(criterion or rediscovery_criterion())
    if frozen["criterion_id"] != REDISCOVERY_CRITERION_ID:
        raise ProtocolError(
            f"criterion {frozen['criterion_id']!r} is not the frozen "
            f"{REDISCOVERY_CRITERION_ID!r}; a threshold change needs a protocol bump"
        )
    if not scope:
        raise SchemaError("a criterion verdict must record the scope it was applied to")
    checks = {
        "sign_fraction": {
            "observed": aggregate["sign_recovered_fraction"],
            "threshold": frozen["min_sign_fraction"],
            "comparison": ">=",
        },
        "top_k_fraction": {
            "observed": aggregate["top_k_fraction"],
            "threshold": frozen["min_top_k_fraction"],
            "comparison": ">=",
        },
        "rank_1_fraction": {
            "observed": aggregate["rank_1_fraction"],
            "threshold": frozen["min_rank_1_fraction"],
            "comparison": ">=",
        },
        "calibration_error_90": {
            "observed": calibration_error_90,
            "threshold": frozen["max_calibration_error_90"],
            "comparison": "<=",
        },
    }
    for check in checks.values():
        observed, threshold = check["observed"], check["threshold"]
        if observed is None:
            check["met"] = None
        elif check["comparison"] == ">=":
            check["met"] = float(observed) >= float(threshold)
        else:
            check["met"] = float(observed) <= float(threshold)
    met = [c["met"] for c in checks.values()]
    if any(m is None for m in met):
        verdict = VERDICT_NOT_YET_SCORED
    else:
        verdict = VERDICT_MET if all(met) else VERDICT_NOT_MET
    return {
        "criterion": frozen,
        "scope": scope,
        "checks": checks,
        "verdict": verdict,
        "n_evaluable_chains": aggregate["n_evaluable_chains"],
        "n_closures": aggregate["n_closures"],
        "scope_rule": CRITERION_SCOPE_RULE,
    }
