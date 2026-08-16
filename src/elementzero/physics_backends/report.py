"""WO-15 report bundle: qualification, independence, B004, and the gate.

Rebuilds deterministically from committed artifacts so CI can re-derive
the bundle byte-for-byte without a solver, a raw archive, or a network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.b004 import B004_ID
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.physics_backends import REPORTS_RELPATH, WO15_ID
from elementzero.physics_backends.independence import count_blind_families

WO15_CREATED_AT = "2026-08-16T20:00:00Z"

STATUS_ENGINEERING_PASS_B004_PASS = "ENGINEERING_PASS_B004_PASS"
STATUS_ENGINEERING_PASS_B004_MIXED = "ENGINEERING_PASS_B004_MIXED"
STATUS_ENGINEERING_PASS_B004_NOT_MET = "ENGINEERING_PASS_B004_NOT_MET"
STATUS_ENGINEERING_PASS_B004_NOT_EVALUABLE = "ENGINEERING_PASS_B004_NOT_EVALUABLE"

WO14_IMMUTABLE_ARTIFACTS = (
    "results/EZ-B002-v2-real-blind/SEALED_PREDICTIONS.json",
    "results/EZ-B002-v2-real-blind/aggregate.json",
    "results/EZ-B002-v2-real-recon/SEALED_PREDICTIONS.json",
    "results/EZ-B002-v2-real-recon/aggregate.json",
    "results/EZ-B003-v2-real-blind/SEALED_PREDICTIONS.json",
    "results/EZ-B003-v2-real-blind/mass_results.json",
    "results/EZ-B003-v2-real-blind/derived_results.json",
    "results/EZ-B003-v2-real-recon/SEALED_PREDICTIONS.json",
    "results/EZ-B003-v2-real-recon/closure_results.json",
    "reports/real_validation/wo14/wo14_status.json",
)


def wo14_hashes(*, repo_root: str | Path | None = None) -> dict[str, str]:
    """Digest every WO-14 artifact WO-15 promises not to touch."""
    from elementzero.evidence.hashing import sha256_file

    root = Path(repo_root or REPO_ROOT)
    out: dict[str, str] = {}
    for relpath in WO14_IMMUTABLE_ARTIFACTS:
        path = root / relpath
        if not path.is_file():
            raise ProtocolError(f"WO-14 artifact {relpath} is missing")
        out[relpath] = sha256_file(path)
    return dict(sorted(out.items()))


def build_status(
    *,
    qualifications: list[dict[str, Any]],
    independence: list[dict[str, Any]],
    b004_protocol: dict[str, Any] | None,
    b004_scores: dict[str, Any] | None,
    b004_claim: dict[str, Any] | None,
) -> dict[str, Any]:
    gate = count_blind_families(independence)
    if b004_scores is None or b004_protocol is None:
        top = STATUS_ENGINEERING_PASS_B004_NOT_EVALUABLE
    elif b004_claim and b004_claim["claim"] == "MULTI_FAMILY_BLIND_EVIDENCE_ESTABLISHED":
        top = STATUS_ENGINEERING_PASS_B004_PASS
    elif b004_claim and b004_claim["claim"] == "SINGLE_FAMILY_BLIND_EVIDENCE_ONLY":
        top = STATUS_ENGINEERING_PASS_B004_MIXED
    else:
        top = STATUS_ENGINEERING_PASS_B004_NOT_MET

    by_family = {
        q["backend_id"]: {
            "status": q["status"],
            "provenance_class": q.get("provenance_class"),
            "parameterization": q["parameterization"],
            "freeze_admissible": q["freeze_admissible_parameterization"],
            "refittable": q["refittable"],
        }
        for q in qualifications
    }
    return {
        "work_order": WO15_ID,
        "status": top,
        "families": dict(sorted(by_family.items())),
        "blind_physics_independence": gate,
        "b004_protocol_status": (
            "PREREGISTERED_AND_SCORED" if b004_scores else "NOT_EVALUABLE"
        ),
        "b004_claim": (b004_claim or {}).get("claim", "B004_NOT_EVALUABLE"),
        "next_gate": _next_gate(gate),
    }


def _next_gate(gate: dict[str, Any]) -> str:
    if gate["gate_met"]:
        return (
            "WO-16 Known-Superheavy Historical Challenge becomes available: "
            "two independent blind-eligible physics families now exist with "
            "reproducible fits. WO-16 remains a computational historical "
            "validation challenge and authorizes no experimental synthesis"
        )
    return (
        "remain at WO-15: fewer than two independent blind-eligible physics "
        "families qualified. Iterate backend physics and fits using "
        "training-era-only evidence under a new preregistered protocol "
        "version; do not open a frontier challenge"
    )


def build_atlas_lineage(
    *,
    out_dir: Path,
    provenance: dict[str, Any],
    freeze: dict[str, Any],
    objective: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    convergence: dict[str, Any],
    qualifications: list[dict[str, Any]],
    independence: list[dict[str, Any]],
    b004_protocol: dict[str, Any] | None,
    b004_seal_hash: str | None,
    b004_scores: dict[str, Any] | None,
    b004_claim: dict[str, Any] | None,
) -> dict[str, str]:
    """The 14-link WO-15 evidence chain (spec section 24)."""
    from elementzero.evidence.atlas_adapter import (
        NUCLEAR_MASS_INTERFACE,
        AtlasEvidenceAdapter,
        EvidenceLevel,
        Fact,
        FactStatus,
        Layer,
        Namespace,
        PirLevel,
        Warning_,
        _heuristic_analyzer,
        compute_fact_id,
        write_atlas_bundle,
    )

    adapter = AtlasEvidenceAdapter(created_at=WO15_CREATED_AT)
    facts: list[Fact] = []
    provenance_records: list[Any] = []
    warning = (
        "WO-15 physics backends: qualification is engineering provenance, "
        "not validated accuracy; blind eligibility follows the fit freeze, "
        "and a post-freeze parameterization is reference only"
    )

    def _fact(content: dict[str, Any], assumptions: tuple[str, ...]) -> Fact:
        analyzer = _heuristic_analyzer()
        fact = Fact(
            fact_id=compute_fact_id(content, analyzer, assumptions=assumptions),
            pir_level=PirLevel.L2,
            evidence_level=EvidenceLevel.E3,
            layer=Layer.MEASUREMENT,
            namespace=Namespace.analyst,
            status=FactStatus.SUPPORTED,
            analyzer=analyzer,
            content=content,
            created_at=WO15_CREATED_AT,
            assumptions=assumptions,
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=(
                Warning_(location=f"wo15:{content['kind']}", message=warning),
            ),
        )
        adapter.append_fact(fact)
        facts.append(fact)
        provenance_records.append(
            adapter.append_provenance(
                entity=fact.fact_id,
                activity_type="ANALYZE",
                used=tuple(
                    a.split("fact:", 1)[1] for a in assumptions if a.startswith("fact:")
                ),
                generated=(fact.fact_id,),
            )
        )
        return fact

    source_fact = _fact(
        {
            "kind": "PhysicsBackendSourceFact",
            "solvers": {
                name: {
                    "archive_sha256": rec["archive_sha256"],
                    "license": rec["license"],
                    "publication": rec["publication"],
                }
                for name, rec in sorted(provenance["solvers"].items())
            },
        },
        ("wo15:solver-archives",),
    )
    build_fact = _fact(
        {
            "kind": "PhysicsBuildFact",
            "builds": {
                b: m["build_manifest_hash"]
                for b, m in sorted(provenance["builds"].items())
            },
            "golden": provenance["golden"],
        },
        (f"fact:{source_fact.fact_id}",),
    )
    freeze_fact = _fact(
        {
            "kind": "PhysicsFitFreezeFact",
            "freeze_id": freeze["freeze_id"],
            "freeze_hash": freeze["freeze_hash"],
            "cutoff_date": freeze["cutoff_date"],
            "calibration_identity_digest": freeze["calibration_identity_digest"],
        },
        (f"fact:{build_fact.fact_id}",),
    )
    objective_fact = _fact(
        {
            "kind": "PhysicsObjectiveFact",
            "objective_id": objective["objective_id"],
            "objective_manifest_hash": objective["objective_manifest_hash"],
            "locked_before_fitting": objective["locked_before_fitting"],
        },
        (f"fact:{freeze_fact.fact_id}",),
    )
    artifact_facts = {}
    for backend_id, artifact in sorted(artifacts.items()):
        artifact_facts[backend_id] = _fact(
            {
                "kind": "PhysicsParameterArtifactFact",
                "backend_id": backend_id,
                "artifact_id": artifact["artifact_id"],
                "provenance_class": artifact["provenance_class"],
                "parameter_names": artifact["parameter_names"],
                "fit_log_hash": artifact["fit_log_hash"],
            },
            (f"fact:{objective_fact.fact_id}",),
        )
    convergence_fact = _fact(
        {"kind": "PhysicsConvergenceFact", **convergence},
        tuple(f"fact:{f.fact_id}" for f in artifact_facts.values()),
    )
    qualification_fact = _fact(
        {
            "kind": "PhysicsFamilyQualificationFact",
            "families": {
                q["backend_id"]: q["status"] for q in qualifications
            },
        },
        (f"fact:{convergence_fact.fact_id}",),
    )

    upstream = qualification_fact
    if b004_protocol is not None:
        protocol_fact = _fact(
            {
                "kind": "B004ProtocolFact",
                "experiment_id": B004_ID,
                "protocol_hash": b004_protocol["protocol_hash"],
                "target_rule_hash": b004_protocol["target_rule_hash"],
                "target_identity_digest": b004_protocol["target_identity_digest"],
                "truth_locked": b004_protocol["truth_locked"],
            },
            (f"fact:{qualification_fact.fact_id}",),
        )
        prediction_fact = _fact(
            {
                "kind": "B004PredictionSetFact",
                "prediction_seal_hash": b004_seal_hash,
            },
            (f"fact:{protocol_fact.fact_id}",),
        )
        finalization_fact = _fact(
            {
                "kind": "B004FinalizationFact",
                "seal_commit": (b004_claim or {}).get("seal_commit"),
            },
            (f"fact:{prediction_fact.fact_id}",),
        )
        unlock_fact = _fact(
            {
                "kind": "B004TruthUnlockFact",
                "truth_edition": "AME2020",
                "verified": bool(b004_scores),
            },
            (f"fact:{finalization_fact.fact_id}",),
        )
        upstream = _fact(
            {
                "kind": "B004ScoreFact",
                "by_model": {
                    m: {
                        "coverage_fraction": v["coverage_fraction"],
                        "MAE_keV": (v["metrics"] or {}).get("MAE_keV"),
                    }
                    for m, v in sorted((b004_scores or {}).get("by_model", {}).items())
                },
            },
            (f"fact:{unlock_fact.fact_id}",),
        )

    independence_fact = _fact(
        {
            "kind": "PhysicsIndependenceAdjudicationFact",
            "records": [
                {
                    "group_id": r["group_id"],
                    "independence_verdict": r["independence_verdict"],
                    "blind_eligible": r["blind_eligible"],
                    "adjudication_hash": r["adjudication_hash"],
                }
                for r in independence
            ],
            "gate": count_blind_families(independence),
        },
        (f"fact:{upstream.fact_id}",),
    )
    _fact(
        {
            "kind": "B004ClaimAdjudicationFact",
            "claim": (b004_claim or {}).get("claim", "B004_NOT_EVALUABLE"),
            "scientific_scope": (b004_claim or {}).get("scientific_scope"),
            "visual_stage_permission": (b004_claim or {}).get(
                "visual_stage_permission"
            ),
            "next_gate": (b004_claim or {}).get("next_gate"),
        },
        (f"fact:{independence_fact.fact_id}",),
    )

    return write_atlas_bundle(
        out_dir, stage="predict", facts=facts, provenance=provenance_records,
        artifacts=(), events=(),
    )


def write_events(
    out: Path,
    *,
    qualifications: list[dict[str, Any]],
    target_ids: list[str],
    status: dict[str, Any],
) -> None:
    """PF / PB events — badge-only by construction (spec section 23)."""
    from elementzero.visuals.event_types import (
        ProgressEvent,
        make_event_id,
        validate_event,
    )

    status_hash = sha256_hex(status)
    events: list[ProgressEvent] = []

    def _emit(event_type: str, z: int, payload: dict[str, Any]) -> None:
        event = ProgressEvent(
            event_id=make_event_id(
                event_type=event_type,
                source_hash=status_hash,
                element_Z=z,
                benchmark_id=payload.get("experiment_id", B004_ID),
                extra=payload.get("backend_id", ""),
            ),
            event_type=event_type,
            event_time=WO15_CREATED_AT,
            project_version="wo15-physics-backends-v1",
            source_kind="wo15_physics_backends",
            source_path=f"{REPORTS_RELPATH}/wo15_status.json",
            source_hash=status_hash,
            element_Z=z,
            status="info",
            benchmark_id=payload.get("experiment_id", B004_ID),
            payload=payload,
        )
        validate_event(event.to_dict())
        events.append(event)

    zs = sorted({parse_nuclide_id(i)[0] for i in target_ids if 1 <= parse_nuclide_id(i)[0] <= 200})
    for qualification in qualifications:
        if qualification["status"] != "PHYSICS_BACKEND_QUALIFIED":
            continue
        for z in zs:
            _emit(
                "PHYSICS_FAMILY_QUALIFIED",
                z,
                {
                    "backend_id": qualification["backend_id"],
                    "physics_family": qualification["physics_family"],
                    "experiment_id": B004_ID,
                    "stage_rule": (
                        "provenance-complete refittable physics family; "
                        "engineering qualification only, never a validation "
                        "stage"
                    ),
                },
            )
    for z in zs:
        _emit(
            "PHYSICS_BLIND_CHALLENGE_SCORED",
            z,
            {
                "experiment_id": B004_ID,
                "claim": status["b004_claim"],
                "stage_rule": (
                    "B004 result is badge-only; the claim record governs what "
                    "the evidence supports"
                ),
            },
        )
    lines = [json.dumps(e.to_dict(), sort_keys=True) for e in events]
    (out / "physics_progress_events.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def write_bundle(out: Path, payload: dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, content in payload.items():
        (out / name).write_text(canonical_json(content) + "\n", encoding="utf-8")
