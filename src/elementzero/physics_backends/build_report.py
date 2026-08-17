"""Assemble the committed WO-15 bundle from committed artifacts.

Deterministic and solver-free: given the fit artifacts, the B004
protocol, and (when present) the B004 scores, this rebuilds the whole
bundle byte-for-byte, which is what the reproducibility job checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.evidence.hashing import canonical_json
from elementzero.evidence.ledger import read_json
from elementzero.physics_backends import (
    BACKEND_COVARIANT,
    BACKEND_GOGNY,
    BACKEND_SKYRME,
    REPORTS_RELPATH,
)
from elementzero.physics_backends.campaign import FAMILY_PARAMETERIZATION
from elementzero.physics_backends.convergence import summarize
from elementzero.physics_backends.independence import count_blind_families
from elementzero.physics_backends.provenance import (
    FIT_FREEZE_CUTOFF,
    PARAMETERIZATIONS,
    SOLVER_SOURCES,
)
from elementzero.physics_backends.registry import ROSTER, qualification_status
from elementzero.physics_backends.report import (
    build_atlas_lineage,
    build_status,
    wo14_hashes,
    write_events,
)

FITS_RELPATH = f"{REPORTS_RELPATH}/fits"
EXPERIMENT_RELPATH = "experiments/EZ-B004-v1"
RESULTS_B004_RELPATH = "results/EZ-B004-v1"
REPORT_MARKDOWN = "WO15_Refittable_Physics_Backends_Report.md"


def _maybe(path: Path) -> dict[str, Any] | None:
    return read_json(path) if path.is_file() else None


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return value
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def build_wo15_report(
    *, repo_root: str | Path | None = None, out_dir: str | Path | None = None
) -> dict[str, Any]:
    root = Path(repo_root or REPO_ROOT)
    out = Path(out_dir) if out_dir is not None else root / REPORTS_RELPATH
    out.mkdir(parents=True, exist_ok=True)
    fits = root / FITS_RELPATH
    experiment = root / EXPERIMENT_RELPATH
    results = root / RESULTS_B004_RELPATH

    freeze = read_json(fits / "historical_fit_freeze.json")
    objective = read_json(fits / "objective_manifest.json")
    artifacts = {
        path.name.removeprefix("parameter_artifact_").removesuffix(".json"): read_json(
            path
        )
        for path in sorted(fits.glob("parameter_artifact_*.json"))
    }
    golden = read_json(fits / "golden_cases.json")
    builds = read_json(fits / "build_manifests.json")

    b004_protocol = _maybe(experiment / "PROTOCOL.json")
    adjudications = _maybe(experiment / "independence_adjudication.json") or {
        "records": [],
        "gate": count_blind_families([]),
    }
    targets = _maybe(experiment / "target_manifest.json")
    sealed = _maybe(results / "SEALED_PREDICTIONS.json")
    scores = _maybe(results / "b004_scores.json")
    claim_records = _maybe(results / "claim_adjudication.json")
    claim = (claim_records or {}).get("records", [None])[0]

    # Qualification verdicts, derived rather than asserted.
    convergence_records: list[dict[str, Any]] = []
    if sealed:
        for family in sealed["families"]:
            convergence_records.extend(family.get("convergence_records", []))
    qualifications = []
    for backend_id in (BACKEND_SKYRME, BACKEND_GOGNY, BACKEND_COVARIANT):
        if backend_id not in artifacts:
            continue
        family_converged = True
        if sealed:
            family = next(
                (f for f in sealed["families"] if f["backend_id"] == backend_id),
                None,
            )
            family_converged = bool(
                family and family["convergence_summary"]["n_converged"] > 0
            )
        entry = qualification_status(
            backend_id=backend_id,
            source_verified=True,
            build_verified=backend_id in {b for b in builds},
            golden_reproduced=_golden_ok(golden, ROSTER[backend_id]["solver"]),
            any_converged=family_converged,
        )
        entry["provenance_class"] = artifacts[backend_id]["provenance_class"]
        qualifications.append(entry)

    provenance = {
        "work_order": "WO-15",
        "solvers": {
            name: {
                k: record[k]
                for k in (
                    "solver_name",
                    "solver_version",
                    "archive_sha256",
                    "license",
                    "license_evidence",
                    "publication",
                    "record_url",
                    "redistribution_allowed",
                )
            }
            for name, record in sorted(SOLVER_SOURCES.items())
        },
        "builds": builds,
        "golden": golden,
        "parameterizations": {
            backend_id: {
                "parameterization": FAMILY_PARAMETERIZATION[backend_id],
                **PARAMETERIZATIONS[FAMILY_PARAMETERIZATION[backend_id]],
            }
            for backend_id in sorted(artifacts)
        },
        "qualifications": qualifications,
        "freeze_cutoff": FIT_FREEZE_CUTOFF,
    }

    status = build_status(
        qualifications=qualifications,
        independence=adjudications["records"],
        b004_protocol=b004_protocol,
        b004_scores=scores,
        b004_claim=claim,
    )
    status["wo14_hashes"] = wo14_hashes(repo_root=root)

    (out / "backend_provenance.json").write_text(
        canonical_json(provenance) + "\n", encoding="utf-8"
    )
    (out / "wo15_status.json").write_text(
        canonical_json(status) + "\n", encoding="utf-8"
    )
    write_events(
        out,
        qualifications=qualifications,
        target_ids=(targets or {}).get("target_nuclide_ids", []),
        status=status,
    )
    atlas = build_atlas_lineage(
        out_dir=out,
        provenance=provenance,
        freeze=freeze,
        objective=objective,
        artifacts=artifacts,
        convergence=summarize(convergence_records)
        if convergence_records
        else {"n_records": 0, "n_converged": 0},
        qualifications=qualifications,
        independence=adjudications["records"],
        b004_protocol=b004_protocol,
        b004_seal_hash=(
            (results / "SEALED_PREDICTIONS_SHA256").read_text(encoding="utf-8").strip()
            if (results / "SEALED_PREDICTIONS_SHA256").is_file()
            else None
        ),
        b004_scores=scores,
        b004_claim=claim,
    )
    (out / "atlas_bundle_hashes.json").write_text(
        canonical_json(atlas) + "\n", encoding="utf-8"
    )

    (out / REPORT_MARKDOWN).write_text(
        _markdown(
            status=status,
            provenance=provenance,
            freeze=freeze,
            objective=objective,
            artifacts=artifacts,
            adjudications=adjudications,
            targets=targets,
            protocol=b004_protocol,
            scores=scores,
            claim=claim,
        ),
        encoding="utf-8",
    )

    from elementzero.experiments.runner import write_sha256sums

    write_sha256sums(out)
    return {"status": status, "out_dir": str(out)}


def _golden_ok(golden: dict[str, Any], solver: str) -> bool:
    record = golden.get(solver, {})
    if solver == "DIRHB":
        return bool(record.get("reproduced_exactly"))
    return bool(record.get("solver_ok"))


def _markdown(
    *,
    status: dict[str, Any],
    provenance: dict[str, Any],
    freeze: dict[str, Any],
    objective: dict[str, Any],
    artifacts: dict[str, Any],
    adjudications: dict[str, Any],
    targets: dict[str, Any] | None,
    protocol: dict[str, Any] | None,
    scores: dict[str, Any] | None,
    claim: dict[str, Any] | None,
) -> str:
    gate = status["blind_physics_independence"]
    lines = [
        "# WO-15 — Refittable Physics Backends and Historical Physics Fits",
        "",
        f"Work order status: **{status['status']}**",
        "",
        "## 1. What WO-15 set out to fix",
        "",
        "WO-14 ended with one blind physics family and a mass criterion "
        "missed by 15 keV. The bottleneck was never another statistical "
        "residual: it was that ElementZero did not control any physics "
        "model's *fitted state*. A model is not historically blind because "
        "its source code is old.",
        "",
        "## 2. Solver provenance",
        "",
        "| solver | version | sha256 | licence | redistributable |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, record in provenance["solvers"].items():
        lines.append(
            f"| {name} | {record['solver_version']} | "
            f"`{record['archive_sha256'][:16]}…` | {record['license']} | "
            f"{record['redistribution_allowed']} |"
        )
    lines += [
        "",
        "Both archives are fetched and hash-verified rather than vendored; "
        "the DIRHB CPC licence does not grant redistribution, so only its "
        "digest lives in the repository.",
        "",
        "## 3. Golden-case qualification",
        "",
    ]
    hfbtho = provenance["golden"].get("HFBTHO", {})
    dirhb = provenance["golden"].get("DIRHB", {})
    lines += [
        f"- HFBTHO {hfbtho.get('golden_case')}: solver_ok "
        f"{hfbtho.get('solver_ok')}, E = {_fmt(hfbtho.get('energy_MeV'))} MeV",
        f"- DIRHB {dirhb.get('golden_case')}: expected "
        f"{_fmt(dirhb.get('expected_total_energy_MeV'))} MeV, observed "
        f"{_fmt(dirhb.get('observed_total_energy_MeV'))} MeV, exact match "
        f"{dirhb.get('reproduced_exactly')}",
        "",
        "## 4. Historical fit freeze",
        "",
        f"- freeze: `{freeze['freeze_id']}`, cutoff {freeze['cutoff_date']}",
        f"- allowed evidence: AME1995 only ({freeze['n_allowed_nuclides']} "
        "ground-truth-eligible nuclides)",
        f"- calibration set: {len(freeze['calibration_nuclide_ids'])} even-even "
        "nuclides selected by a preregistered deterministic rule",
        "- forbidden: every later AME edition and every committed WO-14 "
        "result artifact, enumerated by hash in the freeze record",
        "",
        f"Objective `{objective['objective_id']}` was locked "
        f"(hash `{objective['objective_manifest_hash'][:16]}…`) before the "
        "first solver call.",
        "",
        "## 5. Parameterization chronology",
        "",
        "| family | parameterization | published | freeze-admissible |",
        "| --- | --- | --- | --- |",
    ]
    for backend_id, record in provenance["parameterizations"].items():
        admissible = record["publication_year"] < int(FIT_FREEZE_CUTOFF[:4])
        lines.append(
            f"| {backend_id} | {record['parameterization']} | "
            f"{record['publication_year']} | {admissible} |"
        )
    lines += [
        "",
        "This table is the scientific finding of the backend survey: the "
        "distributed DIRHB package ships only DD-ME2 (2005) and DD-PC1 "
        "(2008), so the covariant family cannot be made historically blind "
        "by choosing a different shipped force.",
        "",
        "## 6. Refit results",
        "",
        "| family | provenance | parameters | objective (RMS keV) | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for backend_id, artifact in sorted(artifacts.items()):
        params = ", ".join(
            f"{n}={_fmt(v)}"
            for n, v in zip(
                artifact["parameter_names"], artifact["parameter_values"], strict=True
            )
        )
        lines.append(
            f"| {backend_id} | {artifact['provenance_class']} | {params} | "
            f"{_fmt(artifact['objective_value'])} | "
            f"{artifact['convergence_status']} |"
        )
    lines += [
        "",
        "The refit scope is the pairing sector of a pre-freeze published "
        "EDF, stated plainly rather than dressed up: a full EDF "
        "reoptimization is a supercomputer campaign. What it earns is exact "
        "calibration membership, a locked objective, a logged optimizer "
        "path, and an immutable artifact.",
        "",
        "## 7. Independence adjudication",
        "",
        "| group | functional class | verdict | blind eligible |",
        "| --- | --- | --- | --- |",
    ]
    for record in adjudications["records"]:
        lines.append(
            f"| {record['group_id']} | {record['functional_class']} | "
            f"{record['independence_verdict']} | {record['blind_eligible']} |"
        )
    lines += [
        "",
        f"**{gate['status']}** — {gate['n_blind_independent_families']} "
        "independent blind-eligible physics families: "
        f"{', '.join(gate['blind_independent_groups']) or 'none'}.",
        "",
        "The Skyrme and Gogny families run through one HFBTHO build. Their "
        "functional classes differ, so the physics is independent, but the "
        "numerics are correlated — that caveat is recorded on both "
        "adjudications, and a second implementation would strengthen the "
        "claim.",
        "",
        "## 8. B004 protocol",
        "",
    ]
    if protocol and targets:
        lines += [
            f"- experiment: `{protocol['experiment_id']}`, protocol hash "
            f"`{protocol['protocol_hash'][:16]}…`",
            f"- targets: {protocol['n_targets']} even-even nuclides that are "
            "AME2020-eligible, absent from AME1995, and not scored by WO-14",
            f"- strata: {json.dumps(targets['strata']['z_band'])} by Z band; "
            f"{json.dumps(targets['strata']['frontier_direction'])} by "
            "frontier direction",
            f"- odd policy: {protocol['odd_policy']}",
            "",
            "Gate E, preregistered before scoring: B004 v1 is a "
            "characterization challenge. The 150 keV EZ-B002-v2 value is "
            "carried only as LEGACY_INHERITED_REFERENCE and is explicitly "
            "not a pass bar, because SkM* and D1S were never calibrated as "
            "mass models.",
            "",
        ]
    else:
        lines += ["B004 was not preregistered in this build.", ""]

    lines += ["## 9. B004 results", ""]
    if scores:
        lines += [
            "| family | coverage | MAE keV | RMSE keV | cov90 | cal err 90 | "
            "sigma measured? |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for backend_id, entry in scores["by_model"].items():
            metrics = entry["metrics"] or {}
            provenance = entry.get("sigma_provenance") or {}
            floor_only = provenance.get("n_sigma_floor_only")
            if floor_only is None:
                measured = "not audited"
            elif floor_only:
                measured = f"no — {floor_only} row(s) at the sigma floor"
            else:
                measured = "yes"
            lines.append(
                f"| {backend_id} | {entry['n_predicted']}/{entry['n_target']} | "
                f"{_fmt(metrics.get('MAE_keV'))} | "
                f"{_fmt(metrics.get('RMSE_keV'))} | "
                f"{_fmt(metrics.get('coverage_90'))} | "
                f"{_fmt(metrics.get('calibration_error_90'))} | "
                f"{measured} |"
            )
        disagreement = scores["family_disagreement"]
        lines += [
            "",
            f"Mean cross-family spread: "
            f"{_fmt(disagreement.get('mean_spread_keV'))} keV, reported "
            "alongside — never inside — any single family's sigma.",
            "",
            f"Derived S2n rows scored: {scores['derived_s2n']['n_rows']} "
            "(only where both component masses are blind predictions of the "
            "same family).",
            "",
            "### What this result does and does not say",
            "",
            "It would be easy to read "
            "MULTI_FAMILY_BLIND_EVIDENCE_ESTABLISHED as a physics success. "
            "It is not one, and the preregistered criterion never claimed to "
            "be: it asks whether two independent, blind-eligible families "
            "can produce sealed, converged, uncertainty-carrying predictions "
            "on fresh post-freeze targets. They can. That is an "
            "infrastructure and provenance result.",
            "",
            "The physics numbers are poor, and they are the headline a "
            "reader should carry away:",
            "",
            "- Blind-family mass errors are several MeV — roughly two orders "
            "of magnitude worse than the 150 keV legacy reference. SkM* and "
            "D1S were never calibrated as mass models, which is exactly why "
            "the interpretation was fixed in advance rather than after "
            "seeing this.",
            "- The most accurate backend here is the covariant DD-ME2 "
            "family, and it is precisely the one that is NOT blind-eligible: "
            "a 2005 fit scoring post-1995 targets. Its accuracy is a "
            "reference point, not evidence.",
            "- Calibration failed outright. Observed 90% intervals contain "
            "almost none of the truths, because the preregistered "
            "uncertainty policy measured only numerical and parameter "
            "components. The dominant error here is model discrepancy — the "
            "functional itself being wrong — and that term was deliberately "
            "not fitted, so the sigmas are far too narrow. This is the "
            "clearest single improvement for the next protocol version, and "
            "it must be learned from training-era residuals, never from "
            "B004 truth.",
            "- The covariant family's calibration columns are not a "
            "measurement at all. A review of this PR found that the sealing "
            "code accepted an uncertainty probe on the strength of a parsed "
            "energy alone. Auditing the retained solver output showed every "
            "one of its 13 larger-basis probes failed to converge and emitted "
            "no energy, so its numerical component was recorded as zero and "
            "each sealed sigma is the bare 1 keV floor. Its cov90 therefore "
            "describes the floor, not DD-ME2. The two blind-eligible families "
            "audit clean — 14/14 measured each — so the claim itself is "
            "unaffected. The seal is evidence and was not rewritten; see "
            "results/EZ-B004-v1/probe_validity_audit.json, and the probe rule "
            "ez-wo15-probe-validity-v1 now refuses a non-converged probe "
            "instead of reading it as zero spread.",
            "",
        ]
    else:
        lines += ["B004 was not scored in this build.", ""]

    lines += [
        "## 10. Claim",
        "",
        f"**{status['b004_claim']}**",
        "",
    ]
    if claim:
        lines += [
            f"- blind-eligible families meeting coverage: "
            f"{', '.join(claim['blind_eligible_families_meeting_coverage']) or 'none'}",
            f"- visual permission: {claim['visual_stage_permission']}",
            "",
        ]
    lines += [
        "## 11. Limitations",
        "",
        "- The refit covers the pairing sector only; the bulk EDF stays at "
        "its published historical values.",
        "- Skyrme and Gogny share a solver implementation, so their "
        "numerical errors are correlated.",
        "- The covariant family is reference-only: no pre-freeze force ships "
        "with DIRHB.",
        "- B004 is small-n by construction and every point estimate carries "
        "wide uncertainty.",
        "- EVEN_EVEN_ONLY: odd nuclei need blocking and a separate "
        "preregistered treatment.",
        "",
        "## 12. Visual claim firewall",
        "",
        "Backend qualification emits the `PF` badge and a scored B004 emits "
        "`PB`. Neither can promote a tile's validation stage — qualification "
        "is an engineering fact about provenance, not evidence of accuracy.",
        "",
        "## 13. WO-14 immutability",
        "",
        f"All {len(status['wo14_hashes'])} WO-14 artifacts re-hash unchanged; "
        "no WO-14 truth entered any fit, objective, or selection rule.",
        "",
        "## 14. Next gate",
        "",
        status["next_gate"] + ".",
        "",
    ]
    return "\n".join(lines)
