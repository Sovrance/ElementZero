"""WO-11.10 — frontier candidate registry and the machine-readable verdict.

The verdict is a pure function of the WO-11 evidence artifacts, applied in a
fixed precedence order (WO-11 section 16): infrastructure defects outrank
benchmark defects, which outrank any statement about models. Running it twice
on the same artifacts yields the same verdict.

The candidate registry records *research* candidates for WO-12. Nothing is
integrated, fit, or tuned here — WO-11 adds no frontier nuclear model — and no
candidate may ever be selected by leaderboard accuracy alone (section 15).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.adjudication import (
    ALLOWED_READINESS_VERDICTS,
    VERDICT_BENCHMARK_REPAIR_REQUIRED,
    VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED,
    VERDICT_JUSTIFIED,
    VERDICT_NOT_YET_JUSTIFIED,
)
from elementzero.errors import SchemaError
from elementzero.evidence.hashing import canonical_json

MODEL_READINESS_FILE = "model_readiness.json"
FRONTIER_CANDIDATES_FILE = "frontier_model_candidates.json"

# Failure classes that point at the models rather than the harness.
MODEL_ATTRIBUTABLE_CLASSES = frozenset(
    {
        "MODEL_BIAS",
        "MODEL_VARIANCE",
        "UNCERTAINTY_UNDERCOVERAGE",
        "UNCERTAINTY_OVERCOVERAGE",
        "EXTRAPOLATION_DEPTH",
        "FEATURE_INSUFFICIENCY",
        "HYPERPARAMETER_SENSITIVITY",
    }
)

DEFECT_CLASSES = frozenset({"IMPLEMENTATION_DEFECT", "INFRASTRUCTURE_FAILURE"})


def readiness_verdict(
    *,
    inventory: dict[str, Any],
    replay: dict[str, Any],
    controls: dict[str, Any],
    failure_records: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic verdict per the frozen decision rules of section 16."""
    reasons: list[str] = []
    records = failure_records["records"]
    b003_records = [r for r in records if r["benchmark_id"] == "EZ-B003"]

    if not inventory["all_unchanged"]:
        verdict = VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED
        reasons.append("a frozen v1 artifact hash moved")
    elif replay["replay_status"] != "PASS":
        verdict = VERDICT_INFRASTRUCTURE_REPAIR_REQUIRED
        reasons.append("the sealed v1 replay did not reproduce the frozen results")
    elif controls["benchmark_control_status"] == "FAIL":
        verdict = VERDICT_BENCHMARK_REPAIR_REQUIRED
        reasons.append("an exact or shell-aware oracle failed the frozen benchmark mechanics")
    elif controls["benchmark_control_status"] != "PASS":
        verdict = VERDICT_NOT_YET_JUSTIFIED
        reasons.append("benchmark validity is indeterminate (a weak control behaved unexpectedly)")
    elif any(r["primary_class"] in DEFECT_CLASSES for r in records):
        verdict = VERDICT_NOT_YET_JUSTIFIED
        reasons.append(
            "a failure is attributed to a protocol-neutral implementation defect; "
            "fix it before crediting any stronger model"
        )
    elif b003_records and all(
        r["primary_class"] in MODEL_ATTRIBUTABLE_CLASSES for r in b003_records
    ):
        verdict = VERDICT_JUSTIFIED
        reasons.extend(
            [
                "the v1 evidence is intact and the sealed replay reproduces it",
                "oracle controls pass and the weak control fails, so the frozen "
                "benchmark mechanics and criterion are sound",
                "every frozen-criterion failure is attributed with evidence to "
                "model capacity, inductive bias, or uncertainty quality",
            ]
        )
    else:
        verdict = VERDICT_NOT_YET_JUSTIFIED
        reasons.append(
            "the frozen-criterion failures are not clearly attributable to the "
            "models; the honest state is indeterminate"
        )
    if verdict not in ALLOWED_READINESS_VERDICTS:
        raise SchemaError(f"internal error: illegal verdict {verdict!r}")
    return {
        "model_readiness_verdict": verdict,
        "reasons": reasons,
        "inputs": {
            "v1_artifact_hashes_unchanged": inventory["all_unchanged"],
            "replay_status": replay["replay_status"],
            "benchmark_control_status": controls["benchmark_control_status"],
            "b003_primary_classes": sorted({r["primary_class"] for r in b003_records}),
            "n_failure_records": len(records),
        },
        "decision_rules": {
            "INFRASTRUCTURE_REPAIR_REQUIRED": (
                "sealed v1 replay not reproducible, or a leakage/integrity defect"
            ),
            "BENCHMARK_REPAIR_REQUIRED": (
                "exact or shell-aware synthetic oracle fails frozen benchmark mechanics"
            ),
            "FRONTIER_MODEL_RERUN_NOT_YET_JUSTIFIED": (
                "failure clearly fixable by a protocol-neutral implementation "
                "defect, or benchmark validity indeterminate"
            ),
            "FRONTIER_MODEL_RERUN_JUSTIFIED": (
                "infrastructure reproduces, oracle controls pass, weak controls "
                "fail as expected, baseline failures persist, and diagnostics "
                "identify model capacity / physics / features / extrapolation "
                "as plausible causes"
            ),
        },
    }


WO12_PREREQUISITES: tuple[str, ...] = (
    "Define EZ-B002-v2 and EZ-B003-v2 as new preregistered protocol versions; "
    "the v1 results stay frozen and are never relabeled or rerun.",
    "Keep EZ-SEMF-LS-v1, EZ-GP-DIRECT-v1, and EZ-SEMF-GP-RESIDUAL-v1 in every "
    "WO-12 run as controls; do not replace them.",
    "Integrate at least one physics-rich global mass model (Class A: BSkG4 or "
    "BSkG5 published tables) as the physics backbone.",
    "Add a second, scientifically independent global model family and a "
    "Bayesian/ensemble combination layer (Class B) so model-family "
    "disagreement becomes measurable.",
    "Add residual/ML models (Class C) in challenger roles only; no ML model "
    "may be the sole source of truth.",
    "Include the optimizer-enabled GP configuration from the WO-11 dev grid as "
    "a configuration control: the dev evidence shows the frozen fixed-kernel "
    "configuration understates the baseline family.",
    "Repair predictive-uncertainty calibration before v2 scoring: v1 GP sigmas "
    "are orders of magnitude too wide (std(z) near 0) and the SEMF-LS global "
    "sigma cannot absorb structured bias (mean(z) near -1.6).",
    "Freeze v2 thresholds on synthetic mechanics before any evaluated-table "
    "truth is read, exactly as B003 v1 did.",
    "Pin the runtime environment (interpreter minor version and library "
    "versions) in the v2 protocol so strict byte replay stays achievable.",
    "Complete license and availability review for every candidate before "
    "integration; a candidate without traceable publications and data/code "
    "stays out of WO-12.",
    "Never tune any frontier candidate on EZ-B002/EZ-B003 hidden truth; public "
    "training data only, verified through the existing leakage firewalls.",
)


# --------------------------------------------------------------------------- #
# Frontier candidate registry (WO-11 sections 13-15)                          #
# --------------------------------------------------------------------------- #

CANDIDATE_REQUIRED_FIELDS: tuple[str, ...] = (
    "candidate_id",
    "family",
    "physics_class",
    "implementation_mode",
    "source_type",
    "source_url",
    "publication",
    "publication_date",
    "data_or_code_available",
    "license_review_required",
    "supported_observables",
    "published_validation",
    "extrapolation_validation",
    "uncertainty_native",
    "computational_cost_class",
    "elementzero_adapter_effort",
    "scientific_independence_group",
    "recommended_role",
    "status",
)

ALLOWED_ROLES = (
    "PHYSICS_BACKBONE",
    "RESIDUAL_CHALLENGER",
    "MODEL_COMBINATION",
    "UQ_CHALLENGER",
    "CONTROL_ONLY",
)
ALLOWED_STATUS = ("RESEARCH", "CANDIDATE", "APPROVED_FOR_WO12", "REJECTED", "BLOCKED")
ALLOWED_COST = ("LOW", "MEDIUM", "HIGH", "VERY_HIGH", "UNKNOWN")
ALLOWED_EFFORT = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")


def validate_frontier_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Enforce schemas/frontier_model_candidate.schema.json in code."""
    missing = [f for f in CANDIDATE_REQUIRED_FIELDS if f not in candidate]
    if missing:
        raise SchemaError(f"frontier candidate is missing required fields: {missing}")
    extra = sorted(set(candidate) - set(CANDIDATE_REQUIRED_FIELDS))
    if extra:
        raise SchemaError(f"frontier candidate carries unknown fields: {extra}")
    # Stop condition (section 21): a candidate must be traceable to a
    # publication and a source.
    for field in ("candidate_id", "source_url", "publication", "publication_date"):
        if not isinstance(candidate[field], str) or not candidate[field].strip():
            raise SchemaError(f"frontier candidate {field} must be a non-empty string")
    if candidate["recommended_role"] not in ALLOWED_ROLES:
        raise SchemaError(f"unknown recommended_role {candidate['recommended_role']!r}")
    if candidate["status"] not in ALLOWED_STATUS:
        raise SchemaError(f"unknown status {candidate['status']!r}")
    if candidate["computational_cost_class"] not in ALLOWED_COST:
        raise SchemaError(
            f"unknown computational_cost_class {candidate['computational_cost_class']!r}"
        )
    if candidate["elementzero_adapter_effort"] not in ALLOWED_EFFORT:
        raise SchemaError(
            f"unknown elementzero_adapter_effort {candidate['elementzero_adapter_effort']!r}"
        )
    for field in ("data_or_code_available", "license_review_required", "uncertainty_native"):
        if not isinstance(candidate[field], bool):
            raise SchemaError(f"frontier candidate {field} must be a boolean")
    for field in ("supported_observables", "published_validation", "extrapolation_validation"):
        if not isinstance(candidate[field], list) or any(
            not isinstance(v, str) for v in candidate[field]
        ):
            raise SchemaError(f"frontier candidate {field} must be a list of strings")
    return candidate


def frontier_candidates() -> list[dict[str, Any]]:
    """Research registry assembled from the WO-11 source dossier (SOURCES.md)."""
    candidates = [
        {
            "candidate_id": "BSKG4",
            "family": "Skyrme-Hartree-Fock-Bogoliubov (BSkG series, 3D mesh)",
            "physics_class": "microscopic global EDF mass model",
            "implementation_mode": "published mass table + adapter",
            "source_type": "peer-reviewed publication with published tables",
            "source_url": "https://doi.org/10.1140/epja/s10050-025-01503-x",
            "publication": (
                "G. Grams et al., Skyrme-Hartree-Fock-Bogoliubov mass models on a "
                "3D mesh: IV. Improved description of the isospin dependence of "
                "pairing, Eur. Phys. J. A 61, 35 (2025)"
            ),
            "publication_date": "2025",
            "data_or_code_available": True,
            "license_review_required": True,
            "supported_observables": [
                "mass_excess",
                "binding_energy",
                "separation_energies",
                "deformation",
                "pairing",
            ],
            "published_validation": [
                "global AME2020 rms deviation reported in the publication",
                "isospin dependence of pairing improved over BSkG3",
            ],
            "extrapolation_validation": [
                "global fit across the known chart; drip-line behavior discussed "
                "in the BSkG series papers"
            ],
            "uncertainty_native": False,
            "computational_cost_class": "LOW",
            "elementzero_adapter_effort": "LOW",
            "scientific_independence_group": "brussels-skyrme-edf",
            "recommended_role": "PHYSICS_BACKBONE",
            "status": "CANDIDATE",
        },
        {
            "candidate_id": "BSKG5",
            "family": "Skyrme-Hartree-Fock-Bogoliubov (BSkG series, N2LO)",
            "physics_class": "microscopic global EDF mass model",
            "implementation_mode": "published mass table + adapter",
            "source_type": "peer-reviewed publication with published tables",
            "source_url": "https://doi.org/10.1016/j.physletb.2026.140590",
            "publication": (
                "G. Grams et al., Skyrme-Hartree-Fock-Bogoliubov mass models on a "
                "3D mesh: V. The N2LO extension of the Skyrme EDF, Phys. Lett. B "
                "(2026); preprint of series IV at arXiv:2411.08007"
            ),
            "publication_date": "2026",
            "data_or_code_available": True,
            "license_review_required": True,
            "supported_observables": [
                "mass_excess",
                "binding_energy",
                "separation_energies",
                "deformation",
                "pairing",
            ],
            "published_validation": ["global evaluated-table rms deviation reported"],
            "extrapolation_validation": [
                "global fit across the known chart; N2LO extension tested against "
                "the BSkG series baselines"
            ],
            "uncertainty_native": False,
            "computational_cost_class": "LOW",
            "elementzero_adapter_effort": "LOW",
            "scientific_independence_group": "brussels-skyrme-edf",
            "recommended_role": "PHYSICS_BACKBONE",
            "status": "RESEARCH",
        },
        {
            "candidate_id": "BAYES-GP-EXTRAP-2018",
            "family": "Bayesian GP residual correction on global mass models",
            "physics_class": "statistical residual correction with UQ",
            "implementation_mode": "reimplementation from publication",
            "source_type": "peer-reviewed publication",
            "source_url": "https://doi.org/10.1103/PhysRevC.98.034318",
            "publication": (
                "L. Neufcourt et al., Bayesian approach to model-based "
                "extrapolation of nuclear observables, Phys. Rev. C 98, 034318 "
                "(2018)"
            ),
            "publication_date": "2018",
            "data_or_code_available": True,
            "license_review_required": True,
            "supported_observables": ["mass_excess", "separation_energies"],
            "published_validation": [
                "historical AME2003 -> AME2016 blind-style validation of GP "
                "residual corrections"
            ],
            "extrapolation_validation": [
                "credibility-interval quality tested toward the neutron drip line"
            ],
            "uncertainty_native": True,
            "computational_cost_class": "MEDIUM",
            "elementzero_adapter_effort": "MEDIUM",
            "scientific_independence_group": "bayesian-mass-uq",
            "recommended_role": "UQ_CHALLENGER",
            "status": "CANDIDATE",
        },
        {
            "candidate_id": "EBMA-2024",
            "family": "ensemble Bayesian model averaging over global mass models",
            "physics_class": "multi-model combination with UQ",
            "implementation_mode": "reimplementation from publication",
            "source_type": "peer-reviewed publication",
            "source_url": "https://doi.org/10.1103/PhysRevC.109.054301",
            "publication": (
                "Y. Saito et al., Uncertainty quantification of mass models using "
                "ensemble Bayesian model averaging, Phys. Rev. C 109, 054301 (2024)"
            ),
            "publication_date": "2024",
            "data_or_code_available": True,
            "license_review_required": True,
            "supported_observables": ["mass_excess"],
            "published_validation": [
                "ensemble calibration against evaluated tables across model "
                "families"
            ],
            "extrapolation_validation": [
                "2026 follow-up validation against the newly measured 101Sn mass "
                "and proton drip line extrapolations (C. M. Ireland et al., Phys. "
                "Rev. C 113, L021302 (2026), https://doi.org/10.1103/vck7-1c4t)"
            ],
            "uncertainty_native": True,
            "computational_cost_class": "MEDIUM",
            "elementzero_adapter_effort": "MEDIUM",
            "scientific_independence_group": "bayesian-mass-uq",
            "recommended_role": "MODEL_COMBINATION",
            "status": "CANDIDATE",
        },
        {
            "candidate_id": "CNN-WS4",
            "family": "convolutional neural network correction on WS4",
            "physics_class": "ML residual model over a macroscopic-microscopic base",
            "implementation_mode": "reimplementation or published predictions",
            "source_type": "peer-reviewed publication",
            "source_url": "https://doi.org/10.1103/PhysRevC.111.014325",
            "publication": (
                "Y. Lu et al., Nuclear mass predictions based on a convolutional "
                "neural network, Phys. Rev. C 111, 014325 (2025)"
            ),
            "publication_date": "2025",
            "data_or_code_available": True,
            "license_review_required": True,
            "supported_observables": ["mass_excess"],
            "published_validation": ["evaluated-table rms deviation reported"],
            "extrapolation_validation": [
                "performance away from the training region discussed in the "
                "publication"
            ],
            "uncertainty_native": False,
            "computational_cost_class": "MEDIUM",
            "elementzero_adapter_effort": "MEDIUM",
            "scientific_independence_group": "ml-residual-networks",
            "recommended_role": "RESIDUAL_CHALLENGER",
            "status": "RESEARCH",
        },
        {
            "candidate_id": "GPR-NN-2025",
            "family": "neural network with additive GPR-optimized activations",
            "physics_class": "ML mass regression with GP components",
            "implementation_mode": "reimplementation from preprint",
            "source_type": "preprint",
            "source_url": "https://arxiv.org/abs/2509.08314",
            "publication": (
                "H. X. Liu, S. Manzhos, X. H. Wu, Nuclear Mass Predictions Using a "
                "Neural Network with Additive Gaussian Process Regression-"
                "Optimized Activation Functions, arXiv:2509.08314"
            ),
            "publication_date": "2025",
            "data_or_code_available": False,
            "license_review_required": True,
            "supported_observables": ["mass_excess"],
            "published_validation": ["preprint-reported deviations only"],
            "extrapolation_validation": [],
            "uncertainty_native": False,
            "computational_cost_class": "UNKNOWN",
            "elementzero_adapter_effort": "HIGH",
            "scientific_independence_group": "ml-residual-networks",
            "recommended_role": "RESIDUAL_CHALLENGER",
            "status": "RESEARCH",
        },
        {
            "candidate_id": "MTGP-2025",
            "family": "multi-task Gaussian process over masses and charge radii",
            "physics_class": "ML multi-observable regression with UQ",
            "implementation_mode": "reimplementation from preprint",
            "source_type": "preprint",
            "source_url": "https://arxiv.org/abs/2507.17357",
            "publication": (
                "W. Ye, N. Wan, Simultaneous improvements in accuracy and "
                "generalization of nuclear mass and charge radius predictions "
                "using multi-task Gaussian process approaches, arXiv:2507.17357; "
                "companion model-difference analysis in Phys. Rev. C 111, 044317 "
                "(2025), https://doi.org/10.1103/PhysRevC.111.044317"
            ),
            "publication_date": "2025",
            "data_or_code_available": False,
            "license_review_required": True,
            "supported_observables": ["mass_excess", "charge_radius"],
            "published_validation": ["preprint-reported deviations only"],
            "extrapolation_validation": [
                "generalization study across held-out regions reported in the "
                "preprint"
            ],
            "uncertainty_native": True,
            "computational_cost_class": "MEDIUM",
            "elementzero_adapter_effort": "HIGH",
            "scientific_independence_group": "ml-multitask-gp",
            "recommended_role": "RESIDUAL_CHALLENGER",
            "status": "RESEARCH",
        },
    ]
    return [validate_frontier_candidate(c) for c in candidates]


SELECTION_RULE = (
    "WO-12 must not choose by leaderboard accuracy alone. Selection weighs "
    "independent physics assumptions, global coverage, extrapolation evidence, "
    "uncertainty support, access to tables/code, reproducibility, "
    "deformation/fission extensibility, computational feasibility, and "
    "licensing. ElementZero needs physics diversity more than a monoculture "
    "of closely related regressors; note that BSkG4 and BSkG5 share one "
    "independence group and count once toward diversity."
)


def build_frontier_registry() -> dict[str, Any]:
    return {
        "work_order": "WO-11",
        "rule": (
            "Research registry only: WO-11 integrates no frontier model, fits "
            "none, and tunes none. WO-12 is the first work order allowed to "
            "add model families, under new benchmark protocol versions."
        ),
        "selection_rule": SELECTION_RULE,
        "candidates": frontier_candidates(),
    }


def build_model_readiness(
    *,
    inventory: dict[str, Any],
    replay: dict[str, Any],
    controls: dict[str, Any],
    failure_records: dict[str, Any],
) -> dict[str, Any]:
    verdict = readiness_verdict(
        inventory=inventory,
        replay=replay,
        controls=controls,
        failure_records=failure_records,
    )
    return {
        "work_order": "WO-11",
        **verdict,
        "wo12_prerequisites": list(WO12_PREREQUISITES),
        "next_work_order": (
            "WO-12 - Nuclear Model Federation v1"
            if verdict["model_readiness_verdict"] == VERDICT_JUSTIFIED
            else None
        ),
    }


def write_model_readiness(*, out_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
    payload = build_model_readiness(**kwargs)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / MODEL_READINESS_FILE).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return payload


def write_frontier_registry(*, out_dir: str | Path) -> dict[str, Any]:
    payload = build_frontier_registry()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / FRONTIER_CANDIDATES_FILE).write_text(
        canonical_json(payload) + "\n", encoding="utf-8"
    )
    return payload
