"""WO-13 pipeline: eligibility bundle, real preregistrations, gate status.

Two entry points:

    run_wo13(commit_artifacts=True)
        Full build. Requires the pinned AME snapshots under data/amdc
        (stage A: chronology + real target selection), then derives every
        eligibility artifact (stage B) and writes the committed bundle
        under reports/eligibility/wo13 and the four real experiment
        preregistrations.

    rebuild_wo13(out_dir)
        Stage B only, from the committed stage-A inputs. Fully
        deterministic without any raw table — the CI reproducibility job
        byte-compares its output against the committed bundle.

WO-13 never scores real truth: selections and eligibility work on
identities and hashed snapshots; the scoring acts are WO-14's, behind the
gates preregistered here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.eligibility import REPORTS_RELPATH, WO13_ID
from elementzero.eligibility.claim_manifest import (
    CLAIM_SECTION_RULE,
    RECON_NOT_REDISCOVERY_RULE,
    THRESHOLD_INHERITANCE_RULE,
    TRACK_BLIND,
    TRACK_RECONSTRUCTION,
    b002_improvement_flags,
    b003_improvement_flags,
    build_claim_manifest,
    claim_section,
)
from elementzero.eligibility.historical_sources import (
    SourceChronology,
    build_chronology,
    snapshot_path,
    snapshots_available,
)
from elementzero.eligibility.model_training_provenance import audit_models
from elementzero.eligibility.subfederation import (
    NOT_EVALUABLE,
    TIER_CONTROL,
    TIER_FEDERATED,
    TIER_PHYSICS,
    build_manifest,
)
from elementzero.eligibility.target_eligibility import build_matrix
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import read_json

WO13_CREATED_AT = "2026-08-16T15:00:00Z"
REPORT_MARKDOWN = "WO13_Real_Data_Blindness_Report.md"

B002_BLIND_ID = "EZ-B002-v2-real-blind"
B002_RECON_ID = "EZ-B002-v2-real-recon"
B003_BLIND_ID = "EZ-B003-v2-real-blind"
B003_RECON_ID = "EZ-B003-v2-real-recon"

TRUTH_EDITION = "AME2020"

_TIER_ORDER = (NOT_EVALUABLE, TIER_CONTROL, TIER_PHYSICS, TIER_FEDERATED)


# --------------------------------------------------------------------------- #
# Input baseline (immutability of WO-12 and v1)                                #
# --------------------------------------------------------------------------- #


def build_input_baseline(*, repo_root: Path) -> dict[str, Any]:
    from elementzero.adjudication.artifact_audit import (
        assert_v1_evidence_unchanged,
        build_artifact_inventory,
    )
    from elementzero.experiments.wo12_qualification import (
        B002_V2_GATE,
        B003_V2_CRITERION,
    )

    inventory = build_artifact_inventory()
    assert_v1_evidence_unchanged(inventory)

    frozen = {}
    for experiment_id, constant in (
        ("EZ-B002-v2", B002_V2_GATE),
        ("EZ-B003-v2", B003_V2_CRITERION),
    ):
        protocol_path = repo_root / "experiments" / experiment_id / "PROTOCOL.json"
        protocol = read_json(protocol_path)
        committed = protocol["frozen_thresholds"]
        expected = json.loads(canonical_json(constant))
        if committed != expected:
            raise ProtocolError(
                f"{experiment_id} frozen thresholds changed; WO-13 must stop"
            )
        frozen[experiment_id] = {
            "protocol_sha256": sha256_file(protocol_path),
            "protocol_hash": protocol["protocol_hash"],
            "frozen_thresholds": committed,
            "state": protocol["state"],
        }
    manifest = read_json(
        repo_root / "reports" / "model_federation" / "wo12" / "federation_manifest.json"
    )
    qualification_path = (
        repo_root
        / "reports"
        / "model_federation"
        / "wo12"
        / "synthetic_qualification.json"
    )
    return {
        "work_order": WO13_ID,
        "v1_inventory_unchanged": True,
        "wo12_registry_hash": manifest["registry_hash"],
        "wo12_qualification_sha256": sha256_file(qualification_path),
        "frozen_protocols": frozen,
        "threshold_inheritance_rule": THRESHOLD_INHERITANCE_RULE,
        "immutability_rule": (
            "WO-13 modifies no v1 artifact, no WO-12 qualification artifact, "
            "no frozen threshold, and no registry hash; it only adds "
            "eligibility evidence and claim-aware preregistrations"
        ),
    }


# --------------------------------------------------------------------------- #
# Stage A — source-dependent inputs                                            #
# --------------------------------------------------------------------------- #


def build_real_selections(*, repo_root: Path, workspace: Path) -> dict[str, Any]:
    """Region/challenge selection on the real AME2020 snapshot (identities)."""
    from elementzero.benchmark.b002_prepare import prepare_geographic_split
    from elementzero.benchmark.b003_prepare import prepare_shell_split
    from elementzero.experiments.b002_runner import (
        read_regions,
        select_regions_for_source,
    )
    from elementzero.experiments.b003_runner import (
        read_challenges,
        select_challenges_for_source,
    )

    source = snapshot_path("AME2020", repo_root=repo_root)
    workspace.mkdir(parents=True, exist_ok=True)
    regions_path = workspace / "regions.json"
    select_regions_for_source(
        source=source,
        edition_id=TRUTH_EDITION,
        output=regions_path,
        candidates_output=workspace / "region_candidates.json",
        source_relpath=snapshot_path("AME2020", repo_root=repo_root).name,
    )
    regions = read_regions(regions_path)
    region_targets: dict[str, list[str]] = {}
    for region in regions["regions"]:
        split = prepare_geographic_split(
            source=source,
            edition_id=TRUTH_EDITION,
            region=region,
            region_manifest_hash=regions["region_manifest_hash"],
            out_dir=None,
        )
        region_targets[region.region_id] = list(
            split["split_manifest"]["target_nuclide_ids"]
        )

    challenges_path = workspace / "challenges.json"
    select_challenges_for_source(
        source=source,
        edition_id=TRUTH_EDITION,
        output=challenges_path,
        source_relpath=snapshot_path("AME2020", repo_root=repo_root).name,
    )
    challenges = read_challenges(challenges_path)
    challenge_targets: dict[str, list[str]] = {}
    for challenge in challenges["challenges"]:
        if challenge["status"] != "EVALUABLE":
            continue
        mask = challenges["masks"][challenge["challenge_id"]]
        split = prepare_shell_split(
            source=source,
            edition_id=TRUTH_EDITION,
            mask=mask,
            challenge_manifest_hash=challenges["challenge_manifest_hash"],
            out_dir=None,
        )
        challenge_targets[challenge["challenge_id"]] = list(
            split["split_manifest"]["target_nuclide_ids"]
        )
    return {
        "regions_payload": regions["payload"],
        "region_targets": region_targets,
        "challenges_payload": challenges["payload"],
        "challenge_targets": challenge_targets,
    }


# --------------------------------------------------------------------------- #
# Stage B — pure derivations                                                   #
# --------------------------------------------------------------------------- #


def _blind_status(manifest: dict[str, Any]) -> str:
    return manifest["benchmark_blind_status"]["status"]


def build_gate_status(
    *,
    b002_manifest: dict[str, Any],
    b003_manifest: dict[str, Any],
) -> dict[str, Any]:
    """The machine-readable WO-13 gate status (schema-exact fields only)."""
    b002 = _blind_status(b002_manifest)
    b003 = _blind_status(b003_manifest)
    best = max((b002, b003), key=_TIER_ORDER.index)
    physics_groups = sorted(
        {
            group
            for manifest in (b002_manifest, b003_manifest)
            for target in manifest["targets"]
            for group in target["eligible_physics_independence_groups"]
        }
    )
    if best in (TIER_PHYSICS, TIER_FEDERATED, TIER_CONTROL):
        next_gate = (
            "WO-14 — Execute Evaluated-Data v2 Validation with separate "
            "REAL-BLIND and REAL-RECON result tracks"
        )
        if len(physics_groups) < 2:
            next_gate += (
                "; fewer than two blind physics families remain, so frontier "
                "physics claims additionally require Refittable Physics "
                "Backends / Historical Physics Model Builds — the blind "
                "definition is not weakened to compensate"
            )
    else:
        next_gate = (
            "Refittable Physics Backends / Historical Physics Model Builds — "
            "no blind contributor survives on any preregistered target and "
            "the blind definition is not weakened"
        )
    return {
        "work_order": WO13_ID,
        "status": best,
        "b002_blind_status": b002,
        "b003_blind_status": b003,
        "blind_physics_independence_groups": physics_groups,
        "next_gate": next_gate,
    }


# --------------------------------------------------------------------------- #
# Atlas eligibility / claim lineage (spec section 23)                          #
# --------------------------------------------------------------------------- #

PROVENANCE_FACT_KIND = "eligibility_model_training_provenance"
ELIGIBILITY_FACT_KIND = "eligibility_target_matrix"
EXCLUSION_FACT_KIND = "eligibility_exclusion"
SUBFEDERATION_FACT_KIND = "eligibility_blind_subfederation"
CLAIM_FACT_KIND = "eligibility_claim_validation"

ELIGIBILITY_WARNING = (
    "Eligibility bookkeeping: statements about model fit provenance and "
    "claim integrity, conditioned on hashed snapshots and published fit "
    "descriptions. Not experimental evidence about nuclei."
)


def build_atlas_lineage(
    *,
    provenance: dict[str, Any],
    matrices: dict[str, dict[str, Any]],
    manifests: dict[str, dict[str, Any]],
    claim_manifests: dict[str, dict[str, Any]],
    out_dir: Path,
) -> dict[str, str]:
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

    adapter = AtlasEvidenceAdapter(created_at=WO13_CREATED_AT)
    facts: list[Fact] = []
    provenance_records: list[Any] = []

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
            created_at=WO13_CREATED_AT,
            assumptions=assumptions,
            measurement_interface=(NUCLEAR_MASS_INTERFACE,),
            warnings=(
                Warning_(
                    location=f"eligibility:{content.get('model_id', content['kind'])}",
                    message=ELIGIBILITY_WARNING,
                ),
            ),
        )
        adapter.append_fact(fact)
        facts.append(fact)
        provenance_records.append(
            adapter.append_provenance(
                entity=fact.fact_id,
                activity_type="ANALYZE",
                used=tuple(
                    a.split("fact:", 1)[1]
                    for a in assumptions
                    if a.startswith("fact:")
                ),
                generated=(fact.fact_id,),
            )
        )
        return fact

    provenance_facts: dict[str, Fact] = {}
    for model_id, record in sorted(provenance["records"].items()):
        provenance_facts[model_id] = _fact(
            {
                "kind": PROVENANCE_FACT_KIND,
                "model_id": model_id,
                "independence_group": record["independence_group"],
                "fit_source_editions": record["fit_source_editions"],
                "exact_fit_membership_available": record[
                    "exact_fit_membership_available"
                ],
                "provenance_confidence": record["provenance_confidence"],
                "default_blind_use_policy": record["default_blind_use_policy"],
                "warning": ELIGIBILITY_WARNING,
            },
            (f"model:{model_id}",),
        )

    for experiment_id, matrix in sorted(matrices.items()):
        matrix_hash = sha256_hex(matrix)
        eligibility_facts: dict[str, Fact] = {}
        for model_id in matrix["model_ids"]:
            model_records = [
                r for r in matrix["records"] if r["model_id"] == model_id
            ]
            counts: dict[str, int] = {}
            for record in model_records:
                counts[record["claim_type"]] = counts.get(record["claim_type"], 0) + 1
            eligibility_facts[model_id] = _fact(
                {
                    "kind": ELIGIBILITY_FACT_KIND,
                    "experiment_id": experiment_id,
                    "model_id": model_id,
                    "n_targets": len(model_records),
                    "claim_type_counts": dict(sorted(counts.items())),
                    "eligibility_manifest_hash": matrix_hash,
                    "warning": ELIGIBILITY_WARNING,
                },
                (f"fact:{provenance_facts[model_id].fact_id}",),
            )
            excluded = sum(
                n
                for claim, n in counts.items()
                if claim not in ("STRICT_BLIND", "HISTORICAL_BLIND")
            )
            if excluded:
                _fact(
                    {
                        "kind": EXCLUSION_FACT_KIND,
                        "experiment_id": experiment_id,
                        "model_id": model_id,
                        "n_excluded_targets": excluded,
                        "eligibility_manifest_hash": matrix_hash,
                        "warning": ELIGIBILITY_WARNING,
                    },
                    (f"fact:{eligibility_facts[model_id].fact_id}",),
                )
        manifest = manifests[experiment_id]
        subfederation_fact = _fact(
            {
                "kind": SUBFEDERATION_FACT_KIND,
                "experiment_id": experiment_id,
                "benchmark_blind_status": manifest["benchmark_blind_status"],
                "subfederation_manifest_hash": sha256_hex(manifest),
                "warning": ELIGIBILITY_WARNING,
            },
            tuple(
                f"fact:{eligibility_facts[m].fact_id}"
                for m in sorted(eligibility_facts)
            ),
        )
        for track_id, claim_manifest in sorted(claim_manifests.items()):
            if not track_id.startswith(experiment_id.rsplit("-", 1)[0]):
                continue
            # Contributors are derived from the TRACK's own allowed claim
            # types. The strict-blind subfederation is the authority for the
            # BLIND track; the RECONSTRUCTION track filters the eligibility
            # matrix instead — a STRICT_BLIND control has no admissible row
            # label there, while the nonblind BSkG3 reference does.
            #
            # A model's eligibility can differ per target (FRDM95 is blind
            # on the post-1995 targets only), so the three contributor
            # buckets are DISJOINT: eligible on every target, excluded on
            # every target, or partial with explicit per-target counts —
            # never one model in two flat lists.
            if claim_manifest["claim_track"] == TRACK_BLIND:
                eligible_by_target = {
                    target["target_id"]: set(target["eligible_models"])
                    for target in manifest["targets"]
                }
            else:
                allowed = set(claim_manifest["allowed_claim_types"])
                eligible_by_target = {}
                for record in matrix["records"]:
                    bucket = eligible_by_target.setdefault(
                        record["nuclide_id"], set()
                    )
                    if record["claim_type"] in allowed:
                        bucket.add(record["model_id"])
            n_targets = len(eligible_by_target)
            eligible = []
            excluded_models = []
            partial: dict[str, dict[str, int]] = {}
            for model_id in matrix["model_ids"]:
                n_eligible = sum(
                    1
                    for models in eligible_by_target.values()
                    if model_id in models
                )
                if n_eligible == n_targets:
                    eligible.append(model_id)
                elif n_eligible == 0:
                    excluded_models.append(model_id)
                else:
                    partial[model_id] = {
                        "n_eligible_targets": n_eligible,
                        "n_excluded_targets": n_targets - n_eligible,
                    }
            _fact(
                {
                    "kind": CLAIM_FACT_KIND,
                    "experiment_id": claim_manifest["experiment_id"],
                    "claim_track": claim_manifest["claim_track"],
                    "claim_type": claim_manifest["allowed_claim_types"],
                    "n_targets": n_targets,
                    "eligible_contributors": eligible,
                    "excluded_contributors": excluded_models,
                    "partially_eligible_contributors": partial,
                    "contributor_bucket_rule": (
                        "buckets are disjoint: eligible on every target, "
                        "excluded on every target, or partial with explicit "
                        "per-target counts"
                    ),
                    "eligibility_manifest_hash": claim_manifest[
                        "eligibility_manifest_hash"
                    ],
                    "warning": ELIGIBILITY_WARNING,
                },
                (f"fact:{subfederation_fact.fact_id}",),
            )

    return write_atlas_bundle(
        out_dir,
        stage="predict",
        facts=facts,
        provenance=provenance_records,
        artifacts=(),
        events=(),
    )


# --------------------------------------------------------------------------- #
# Visual claim-firewall events (spec section 22)                               #
# --------------------------------------------------------------------------- #


def _write_eligibility_events(
    out: Path, *, manifests: dict[str, dict[str, Any]], gate_status: dict[str, Any]
) -> None:
    from elementzero.data.identity import parse_nuclide_id
    from elementzero.visuals.event_types import (
        ProgressEvent,
        make_event_id,
        validate_event,
    )

    gate_hash = sha256_hex(gate_status)
    events: list[ProgressEvent] = []

    def _emit(event_type: str, z: int, payload: dict[str, Any]) -> None:
        event = ProgressEvent(
            event_id=make_event_id(
                event_type=event_type,
                source_hash=gate_hash,
                element_Z=z,
                benchmark_id=payload.get("experiment_id"),
                extra=payload.get("extra", ""),
            ),
            event_type=event_type,
            event_time=WO13_CREATED_AT,
            project_version="wo13-eligibility-v1",
            source_kind="wo13_eligibility",
            source_path=f"{REPORTS_RELPATH}/wo13_gate_status.json",
            source_hash=gate_hash,
            element_Z=z,
            status="info",
            benchmark_id=payload.get("experiment_id"),
            payload=payload,
        )
        validate_event(event.to_dict())
        events.append(event)

    for experiment_id, manifest in sorted(manifests.items()):
        eligible_zs: set[int] = set()
        ineligible_zs: set[int] = set()
        for target in manifest["targets"]:
            z, _n = parse_nuclide_id(target["target_id"])
            if not 1 <= z <= 200:
                continue
            (eligible_zs if target["gate_evaluable"] else ineligible_zs).add(z)
        for z in sorted(eligible_zs):
            _emit(
                "REAL_BLIND_TARGET_ELIGIBLE",
                z,
                {"experiment_id": experiment_id},
            )
        for z in sorted(ineligible_zs - eligible_zs):
            _emit(
                "REAL_BLIND_TARGET_INELIGIBLE",
                z,
                {"experiment_id": experiment_id},
            )
        status = manifest["benchmark_blind_status"]["status"]
        anchor_z = min(eligible_zs | ineligible_zs, default=1)
        if status == TIER_FEDERATED:
            _emit(
                "FEDERATED_BLIND_GATE_EVALUABLE",
                anchor_z,
                {"experiment_id": experiment_id, "tier": status},
            )
        elif status == NOT_EVALUABLE:
            _emit(
                "BLIND_GATE_NOT_EVALUABLE",
                anchor_z,
                {
                    "experiment_id": experiment_id,
                    "tier": status,
                    "extra": "honest-and-acceptable-outcome",
                },
            )
    lines = [json.dumps(e.to_dict(), sort_keys=True) for e in events]
    (out / "eligibility_progress_events.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# Preregistrations (spec sections 16-17)                                       #
# --------------------------------------------------------------------------- #


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _preregistration_markdown(
    *, experiment_id: str, track: str, claim_manifest: dict[str, Any], note: str
) -> str:
    allowed = ", ".join(claim_manifest["allowed_claim_types"])
    return (
        f"# {experiment_id} — preregistration\n\n"
        f"Claim track: **{track}**\n\n"
        f"Allowed claim types: {allowed}\n\n"
        f"Strict blind gate: {claim_manifest['strict_gate']}\n\n"
        f"Threshold manifest hash: `{claim_manifest['threshold_manifest_hash']}`\n\n"
        f"Eligibility manifest hash: `{claim_manifest['eligibility_manifest_hash']}`\n\n"
        f"{note}\n\n"
        f"{THRESHOLD_INHERITANCE_RULE}\n\n"
        "No real truth is scored by WO-13. Scoring is a WO-14 act behind "
        "this preregistration, and REAL_BLIND_GATE_NOT_EVALUABLE remains a "
        "valid outcome.\n"
    )


def write_preregistrations(
    *,
    repo_root: Path,
    selections: dict[str, Any],
    threshold_manifests: dict[str, dict[str, Any]],
    claim_manifests: dict[str, dict[str, Any]],
) -> None:
    blind_note = (
        "REAL-BLIND: only target/model combinations proven blind by the "
        "committed eligibility matrix enter this track, through the "
        "target-specific strict-blind subfederation. Scoring tables keep "
        "blind controls, blind physics, and blind federation separate."
    )
    recon_note = (
        RECON_NOT_REDISCOVERY_RULE
        + ". Every row is labeled NONBLIND_REFERENCE, RECONSTRUCTION_"
        "REFERENCE, or PARTIALLY_BLIND, and this track never grants blind "
        "extrapolation status or a validated tile stage."
    )
    plans = (
        (B002_BLIND_ID, TRACK_BLIND, "EZ-B002-v2", blind_note),
        (B002_RECON_ID, TRACK_RECONSTRUCTION, "EZ-B002-v2", recon_note),
        (B003_BLIND_ID, TRACK_BLIND, "EZ-B003-v2", blind_note),
        (B003_RECON_ID, TRACK_RECONSTRUCTION, "EZ-B003-v2", recon_note),
    )
    for experiment_id, track, benchmark_key, note in plans:
        directory = repo_root / "experiments" / experiment_id
        directory.mkdir(parents=True, exist_ok=True)
        claim_manifest = claim_manifests[experiment_id]
        _write(directory / "claim_manifest.json", claim_manifest)
        _write(
            directory / "threshold_manifest.json",
            threshold_manifests[benchmark_key],
        )
        if benchmark_key == "EZ-B002-v2":
            _write(directory / "regions.json", selections["regions_payload"])
            _write(
                directory / "region_targets.json",
                {
                    "experiment_id": experiment_id,
                    "identity_only_rule": (
                        "target identities only; no mass value appears here"
                    ),
                    "targets": selections["region_targets"],
                },
            )
        else:
            _write(directory / "challenges.json", selections["challenges_payload"])
            _write(
                directory / "challenge_targets.json",
                {
                    "experiment_id": experiment_id,
                    "identity_only_rule": (
                        "target identities only; no mass value appears here"
                    ),
                    "targets": selections["challenge_targets"],
                },
            )
        (directory / "PREREGISTRATION.md").write_text(
            _preregistration_markdown(
                experiment_id=experiment_id,
                track=track,
                claim_manifest=claim_manifest,
                note=note,
            ),
            encoding="utf-8",
        )


# --------------------------------------------------------------------------- #
# Markdown report                                                              #
# --------------------------------------------------------------------------- #


def render_report(
    *,
    input_baseline: dict[str, Any],
    matrices: dict[str, dict[str, Any]],
    manifests: dict[str, dict[str, Any]],
    gate_status: dict[str, Any],
    b002_flags: dict[str, Any],
    b003_flags: dict[str, Any],
) -> str:
    lines = [
        "# WO-13 — Real-Data Blindness, Eligibility, and Claim Integrity",
        "",
        f"Status: **{gate_status['status']}**",
        f"B002 blind status: **{gate_status['b002_blind_status']}**",
        f"B003 blind status: **{gate_status['b003_blind_status']}**",
        (
            "Blind physics independence groups: "
            f"{', '.join(gate_status['blind_physics_independence_groups']) or 'none'}"
        ),
        "",
        "Core rule: a target hidden from ElementZero is not automatically "
        "blind to an imported physics table.",
        "",
        "## 1. Immutable inputs",
        "",
        f"WO-12 registry hash: `{input_baseline['wo12_registry_hash']}`",
        "",
        "Frozen v2 thresholds re-hashed and asserted unchanged; v1 "
        "inventory re-verified. " + THRESHOLD_INHERITANCE_RULE,
        "",
        "## 2. Three separate facts",
        "",
        f"- protocol_qualified (B002): {b002_flags['protocol_qualified']}",
        (
            "- federation_improved_over_baseline (B002): "
            f"{b002_flags['federation_improved_over_baseline']} — best "
            f"baseline {b002_flags['best_baseline_model']['model_id']} at "
            f"{b002_flags['best_baseline_model']['MAE_keV']:.1f} keV, best "
            f"physics {b002_flags['best_physics_model']['model_id']} at "
            f"{b002_flags['best_physics_model']['MAE_keV']:.1f} keV, best "
            f"combined {b002_flags['best_combined_model']['model_id']} at "
            f"{b002_flags['best_combined_model']['MAE_keV']:.1f} keV"
        ),
        (
            "- B003: structure_localization_improved="
            f"{b003_flags['structure_localization_improved']}, "
            f"calibration_improved={b003_flags['calibration_improved']}, "
            f"federation_criterion_met={b003_flags['federation_criterion_met']}, "
            f"blind_claim_eligible={b003_flags['blind_claim_eligible']}"
        ),
        "",
        "Protocol PASS is not the same as frontier-model improvement, and "
        "reconstruction is not rediscovery.",
        "",
        "## 3. Claim-aware sections (never one mixed leaderboard)",
        "",
        CLAIM_SECTION_RULE,
        "",
    ]
    for experiment_id, matrix in sorted(matrices.items()):
        lines += [f"### {experiment_id}", ""]
        section_counts: dict[str, dict[str, int]] = {}
        for record in matrix["records"]:
            section = claim_section(record["claim_type"])
            per_model = section_counts.setdefault(section, {})
            per_model[record["model_id"]] = per_model.get(record["model_id"], 0) + 1
        for section in sorted(section_counts):
            lines.append(f"- **{section}**")
            for model_id, count in sorted(section_counts[section].items()):
                lines.append(f"  - {model_id}: {count} targets")
        manifest = manifests[experiment_id]
        summary = manifest["benchmark_blind_status"]
        lines += [
            "",
            (
                f"Blind gate: **{summary['status']}** over "
                f"{summary['n_targets']} targets "
                f"({summary['targets_by_tier']})."
            ),
            "",
        ]
    lines += [
        "## 4. Honest boundaries",
        "",
        "- BSkG3 against AME2020 defaults NONBLIND_REFERENCE; a blind GP "
        "residual cannot repair a nonblind base into blindness.",
        "- FRDM95 fit membership is unknown for every target already known "
        "by AME1995: INELIGIBLE_UNKNOWN_PROVENANCE, never assumed blind.",
        "- Combiners inherit their worst contributor; nonblind evidence is "
        "excluded from strict-blind subfederations, never reweighted away.",
        "- Residual variants are not independent physics families; Tier 2 "
        "is not faked with wrappers.",
        "- REAL_BLIND_GATE_NOT_EVALUABLE is an acceptable, honest result.",
        "",
        "## 5. Next gate",
        "",
        gate_status["next_gate"],
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Pipeline                                                                     #
# --------------------------------------------------------------------------- #


def _stage_b(
    *,
    root: Path,
    out: Path,
    chronology_payload: dict[str, Any],
    selections: dict[str, Any],
    commit_artifacts: bool,
) -> dict[str, Any]:
    from elementzero.experiments.wo12_qualification import (
        B002_V2_GATE,
        B003_V2_CRITERION,
    )
    from elementzero.models.federation.registry import build_default_federation

    out.mkdir(parents=True, exist_ok=True)

    input_baseline = build_input_baseline(repo_root=root)
    _write(out / "input_baseline.json", input_baseline)

    _write(out / "historical_source_chronology.json", chronology_payload)
    chronology = SourceChronology(chronology_payload)

    try:
        registry_manifest = build_default_federation(repo_root=root).manifest()
    except Exception:
        # The raw physics tables may be absent (CI); the committed WO-12
        # manifest is the frozen roster either way.
        registry_manifest = read_json(
            root / "reports" / "model_federation" / "wo12" / "federation_manifest.json"
        )
    if registry_manifest["registry_hash"] != input_baseline["wo12_registry_hash"]:
        raise ProtocolError("federation registry hash changed; WO-13 must stop")
    provenance = audit_models(registry_manifest=registry_manifest)
    _write(out / "model_training_provenance.json", provenance)

    b002_targets = sorted(
        {t for ids in selections["region_targets"].values() for t in ids}
    )
    b003_targets = sorted(
        {t for ids in selections["challenge_targets"].values() for t in ids}
    )
    matrices = {
        B002_BLIND_ID: build_matrix(
            benchmark_id="EZ-B002",
            experiment_id=B002_BLIND_ID,
            target_ids=b002_targets,
            target_truth_edition=TRUTH_EDITION,
            chronology=chronology,
        ),
        B003_BLIND_ID: build_matrix(
            benchmark_id="EZ-B003",
            experiment_id=B003_BLIND_ID,
            target_ids=b003_targets,
            target_truth_edition=TRUTH_EDITION,
            chronology=chronology,
        ),
    }
    _write(out / "target_eligibility_matrix.json", matrices)

    manifests = {
        experiment_id: build_manifest(experiment_id=experiment_id, matrix=matrix)
        for experiment_id, matrix in matrices.items()
    }
    _write(
        out / "subfederation_summary.json",
        {
            "work_order": WO13_ID,
            "manifests": manifests,
        },
    )

    qualification = read_json(
        root
        / "reports"
        / "model_federation"
        / "wo12"
        / "synthetic_qualification.json"
    )
    gate_status = build_gate_status(
        b002_manifest=manifests[B002_BLIND_ID],
        b003_manifest=manifests[B003_BLIND_ID],
    )
    b002_flags = b002_improvement_flags(qualification)
    b003_flags = b003_improvement_flags(
        qualification,
        blind_gate_eligible=gate_status["b003_blind_status"] != NOT_EVALUABLE,
    )

    threshold_manifests = {
        "EZ-B002-v2": {
            "benchmark_id": "EZ-B002",
            "inherited_from": "EZ-B002-v2",
            "frozen_thresholds": json.loads(canonical_json(B002_V2_GATE)),
            "rule": THRESHOLD_INHERITANCE_RULE,
        },
        "EZ-B003-v2": {
            "benchmark_id": "EZ-B003",
            "inherited_from": "EZ-B003-v2",
            "frozen_thresholds": json.loads(canonical_json(B003_V2_CRITERION)),
            "rule": THRESHOLD_INHERITANCE_RULE,
        },
    }
    claim_manifests = {}
    for experiment_id, track, benchmark_key, blind_experiment in (
        (B002_BLIND_ID, TRACK_BLIND, "EZ-B002-v2", B002_BLIND_ID),
        (B002_RECON_ID, TRACK_RECONSTRUCTION, "EZ-B002-v2", B002_BLIND_ID),
        (B003_BLIND_ID, TRACK_BLIND, "EZ-B003-v2", B003_BLIND_ID),
        (B003_RECON_ID, TRACK_RECONSTRUCTION, "EZ-B003-v2", B003_BLIND_ID),
    ):
        eligibility_hash = (
            sha256_hex(manifests[blind_experiment])
            if track == TRACK_BLIND
            else sha256_hex(matrices[blind_experiment])
        )
        claim_manifests[experiment_id] = build_claim_manifest(
            experiment_id=experiment_id,
            claim_track=track,
            threshold_manifest=threshold_manifests[benchmark_key],
            eligibility_manifest_hash=eligibility_hash,
            protocol_qualified=(
                b002_flags["protocol_qualified"]
                if benchmark_key == "EZ-B002-v2"
                else b003_flags["federation_criterion_met"]
            ),
        )

    _write(
        out / "b002_real_claim_plan.json",
        {
            "work_order": WO13_ID,
            "blind": claim_manifests[B002_BLIND_ID],
            "reconstruction": claim_manifests[B002_RECON_ID],
            "improvement_flags": b002_flags,
            "region_targets": selections["region_targets"],
            "threshold_manifest": threshold_manifests["EZ-B002-v2"],
        },
    )
    _write(
        out / "b003_real_claim_plan.json",
        {
            "work_order": WO13_ID,
            "blind": claim_manifests[B003_BLIND_ID],
            "reconstruction": claim_manifests[B003_RECON_ID],
            "improvement_flags": b003_flags,
            "challenge_targets": selections["challenge_targets"],
            "threshold_manifest": threshold_manifests["EZ-B003-v2"],
        },
    )
    _write(out / "wo13_gate_status.json", gate_status)

    atlas_hashes = build_atlas_lineage(
        provenance=provenance,
        matrices=matrices,
        manifests=manifests,
        claim_manifests=claim_manifests,
        out_dir=out,
    )
    _write(out / "atlas_bundle_hashes.json", {"atlas": atlas_hashes})

    _write_eligibility_events(out, manifests=manifests, gate_status=gate_status)

    (out / REPORT_MARKDOWN).write_text(
        render_report(
            input_baseline=input_baseline,
            matrices=matrices,
            manifests=manifests,
            gate_status=gate_status,
            b002_flags=b002_flags,
            b003_flags=b003_flags,
        ),
        encoding="utf-8",
    )

    from elementzero.experiments.runner import write_sha256sums

    write_sha256sums(out)

    if commit_artifacts:
        write_preregistrations(
            repo_root=root,
            selections=selections,
            threshold_manifests=threshold_manifests,
            claim_manifests=claim_manifests,
        )
    return {
        "out_dir": str(out),
        "status": gate_status["status"],
        "b002_blind_status": gate_status["b002_blind_status"],
        "b003_blind_status": gate_status["b003_blind_status"],
        "blind_physics_independence_groups": gate_status[
            "blind_physics_independence_groups"
        ],
        "next_gate": gate_status["next_gate"],
    }


def run_wo13(
    *,
    repo_root: str | Path | None = None,
    out_dir: str | Path | None = None,
    workspace_dir: str | Path | None = None,
    commit_artifacts: bool = True,
) -> dict[str, Any]:
    """Full WO-13 build (stage A from raw snapshots, then stage B)."""
    import tempfile

    root = Path(repo_root or REPO_ROOT)
    out = Path(out_dir) if out_dir is not None else root / REPORTS_RELPATH
    if not snapshots_available(repo_root=root):
        raise ProtocolError(
            "historical AME snapshots are missing; run tools/fetch_ame_sources.py"
        )
    chronology_payload = build_chronology(repo_root=root)
    if workspace_dir is None:
        with tempfile.TemporaryDirectory(prefix="wo13-workspace-") as tmp:
            selections = build_real_selections(
                repo_root=root, workspace=Path(tmp)
            )
    else:
        selections = build_real_selections(
            repo_root=root, workspace=Path(workspace_dir)
        )
    return _stage_b(
        root=root,
        out=out,
        chronology_payload=chronology_payload,
        selections=selections,
        commit_artifacts=commit_artifacts,
    )


def rebuild_wo13(
    *,
    out_dir: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Stage B from the committed stage-A inputs (no raw tables needed)."""
    root = Path(repo_root or REPO_ROOT)
    committed = root / REPORTS_RELPATH
    chronology_payload = read_json(committed / "historical_source_chronology.json")
    selections = {
        "regions_payload": read_json(
            root / "experiments" / B002_BLIND_ID / "regions.json"
        ),
        "region_targets": read_json(
            root / "experiments" / B002_BLIND_ID / "region_targets.json"
        )["targets"],
        "challenges_payload": read_json(
            root / "experiments" / B003_BLIND_ID / "challenges.json"
        ),
        "challenge_targets": read_json(
            root / "experiments" / B003_BLIND_ID / "challenge_targets.json"
        )["targets"],
    }
    return _stage_b(
        root=root,
        out=Path(out_dir),
        chronology_payload=chronology_payload,
        selections=selections,
        commit_artifacts=False,
    )
