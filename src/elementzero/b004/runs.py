"""B004 execution: predict, seal, commit, unlock, score.

The sealing discipline is WO-14's, reused deliberately: predictions and
their uncertainties are written and hashed while truth is still unread,
the seal hash is committed to git, and the unlock re-verifies every
governing hash before a single measured mass is loaded.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.b004 import B004_ID
from elementzero.b004.bind import assert_target_manifest_bound
from elementzero.b004.protocol import (
    MIN_COVERAGE_FRACTION,
    PAIRING_PROBE_DELTA,
    UNCERTAINTY_POLICY,
)
from elementzero.benchmark.metrics import calibration_error, coverage, mae_keV, medae_keV, nlpd, rmse_keV
from elementzero.data.amdc import load_edition
from elementzero.data.identity import NuclideIdentity, parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import read_json
from elementzero.physics.conversion import binding_energy_MeV, mass_excess_keV_from_binding
from elementzero.physics_backends import (
    BACKEND_COVARIANT,
    BACKEND_GOGNY,
    BACKEND_SKYRME,
)
from elementzero.physics_backends.adapters.hfbtho import (
    gogny_backend,
    skyrme_backend,
)
from elementzero.physics_backends.convergence import summarize
from elementzero.physics_backends.output_parser import parse_hfbtho
from elementzero.physics_backends.protocol import SOLVER_OK

SEALED_FILE = "SEALED_PREDICTIONS.json"
SEALED_HASH_FILE = "SEALED_PREDICTIONS_SHA256"
TRUTH_UNLOCK_FILE = "truth_unlock.json"
AME2020_RELPATH = "data/amdc/mass_1.mas20.txt"

SIGMA_FLOOR_KEV = 1.0
Z90, Z95, Z68 = 1.6448536269514722, 1.959963984540054, 0.9944578832097535

# An uncertainty probe is evidence only when it converged. A probe that
# stops at its iteration limit can still print a last-iterate energy, and
# folding that into sigma reports a measurement that was never made.
# A failed probe is recorded as failed; it is never read as zero spread.
PROBE_MEASURED = "MEASURED"
PROBE_NOT_APPLICABLE = "NOT_APPLICABLE"
PROBE_NONCONVERGED = "PROBE_NONCONVERGED"
PROBE_NO_ENERGY = "PROBE_NO_ENERGY"
PROBE_MISSING = "PROBE_MISSING"
SIGMA_MEASURED = "MEASURED"
SIGMA_INCOMPLETE = "INCOMPLETE_PROBE_FAILURE"
UNRECORDED_SIGMA_STATUS = "UNRECORDED_PRE_PROBE_POLICY"

# WO-15B v0.5.2 retrospective label: a family whose uncertainty probes
# were invalid has no calibration that could have failed.
NOT_EVALUABLE_FROM_INVALID_PROBE_SIGMA = (
    "NOT_EVALUABLE_FROM_INVALID_PROBE_SIGMA"
)

PROBE_POLICY = (
    "ez-wo15-probe-validity-v1: an uncertainty component is recorded only "
    "from a probe that classifies SOLVER_OK. A non-converged or energy-less "
    "probe yields a null component and marks the row "
    "INCOMPLETE_PROBE_FAILURE, so a failed probe can never be read as zero "
    "uncertainty"
)


def _probe_component(
    probe: dict[str, Any] | None,
    *,
    z: int,
    n: int,
    prediction: float,
    required: bool,
) -> tuple[float | None, str]:
    """The spread this probe measured, or why it measured nothing."""
    from elementzero.physics_backends.adapters.hfbtho import _classify

    if probe is None:
        return (None, PROBE_MISSING if required else PROBE_NOT_APPLICABLE)
    status, _ = _classify(probe)
    if status != SOLVER_OK:
        return None, PROBE_NONCONVERGED
    if probe.get("energy_MeV") is None:
        return None, PROBE_NO_ENERGY
    spread = abs(
        mass_excess_keV_from_binding(z=z, n=n, binding_MeV=-probe["energy_MeV"])
        - prediction
    )
    return spread, PROBE_MEASURED


def _backend(backend_id: str, functional: str, repo_root):
    if backend_id == BACKEND_SKYRME:
        return skyrme_backend(functional=functional, repo_root=repo_root)
    if backend_id == BACKEND_GOGNY:
        return gogny_backend(functional=functional, repo_root=repo_root)
    if backend_id == BACKEND_COVARIANT:
        from elementzero.physics_backends.adapters.dirhb import dirhb_backend

        return dirhb_backend(force=functional, repo_root=repo_root)
    raise ProtocolError(f"unknown B004 backend {backend_id}")


def _probe(args) -> tuple[str, str, dict[str, Any]]:
    """One (nuclide, variant) solve, run in its own directory.

    The backend supplies both the solve and the parser, so a family's
    output format never has to be guessed by the caller.
    """
    backend, nuclide_id, variant, work_dir, vpair_n, vpair_p, shells = args
    z, n = parse_nuclide_id(nuclide_id)
    solved = backend.solve_one(
        NuclideIdentity.from_zn(z, n),
        work_dir=work_dir,
        vpair_n=vpair_n,
        vpair_p=vpair_p,
        shells=shells,
    )
    parser = getattr(backend, "parse_run", None)
    parsed = parser(work_dir) if parser is not None else parse_hfbtho(work_dir)
    return nuclide_id, variant, {**parsed, **{
        k: v for k, v in solved.items() if k in ("timed_out", "returncode")
    }}


def predict_family(
    *,
    backend_id: str,
    functional: str,
    artifact: dict[str, Any],
    target_ids: list[str],
    work_root: str | Path,
    max_workers: int = 4,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Predictions plus their declared uncertainty components.

    Three solves per target: the prediction itself, a larger-basis probe
    for numerical uncertainty, and a perturbed-pairing probe for
    parameter uncertainty. All are preregistered; none consults truth.
    """
    backend = _backend(backend_id, functional, repo_root)
    work_root = Path(work_root)
    params = dict(
        zip(artifact["parameter_names"], artifact["parameter_values"], strict=True)
    )
    vpair_n = params.get("vpair_n")
    vpair_p = params.get("vpair_p")
    if vpair_n is not None:
        vpair_n, vpair_p = float(vpair_n), float(vpair_p)

    jobs = []
    for nuclide_id in target_ids:
        z, n = parse_nuclide_id(nuclide_id)
        if not backend.supports(NuclideIdentity.from_zn(z, n)):
            continue
        jobs.append(
            (backend, nuclide_id, "base", work_root / nuclide_id / "base",
             vpair_n, vpair_p, backend.base_shells)
        )
        jobs.append(
            (backend, nuclide_id, "basis", work_root / nuclide_id / "basis",
             vpair_n, vpair_p, backend.probe_shells)
        )
        if vpair_n is not None:
            jobs.append(
                (backend, nuclide_id, "pairing", work_root / nuclide_id / "pairing",
                 vpair_n + PAIRING_PROBE_DELTA, vpair_p + PAIRING_PROBE_DELTA,
                 backend.base_shells)
            )

    solved: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for nuclide_id, variant, parsed in pool.map(_probe, jobs):
            solved.setdefault(nuclide_id, {})[variant] = parsed

    rows: dict[str, Any] = {}
    convergence_records: list[dict[str, Any]] = []
    from elementzero.physics_backends.adapters.hfbtho import _classify
    from elementzero.physics_backends.convergence import build_record

    # Each family labels its own numerical policy; the shared classifier
    # maps parsed output onto the common status vocabulary.
    basis_policy = backend.basis_policy

    for nuclide_id in target_ids:
        z, n = parse_nuclide_id(nuclide_id)
        entry = solved.get(nuclide_id, {})
        base = entry.get("base")
        if base is None:
            record = build_record(
                nuclide_id=nuclide_id,
                backend_id=backend_id,
                parameter_artifact_id=artifact["artifact_id"],
                converged=False,
                iterations=0,
                basis_policy=basis_policy,
                retry_count=0,
                failure_class="UNSUPPORTED_NUCLIDE",
                output_hash=sha256_hex({"unsupported": nuclide_id}),
            )
            convergence_records.append(record)
            rows[nuclide_id] = {
                "nuclide_id": nuclide_id,
                "solver_status": "UNSUPPORTED_NUCLIDE",
                "prediction_keV": None,
                "sigma_keV": None,
                "convergence_record_id": record["convergence_record_id"],
            }
            continue

        status, failure = _classify(base)
        converged = status == SOLVER_OK
        record = build_record(
            nuclide_id=nuclide_id,
            backend_id=backend_id,
            parameter_artifact_id=artifact["artifact_id"],
            converged=converged,
            iterations=int(base.get("iterations") or 0),
            basis_policy=basis_policy,
            retry_count=0,
            failure_class=failure,
            output_hash=base["output_hash"],
            detail={"functional": functional},
        )
        convergence_records.append(record)

        if not converged:
            rows[nuclide_id] = {
                "nuclide_id": nuclide_id,
                "solver_status": status,
                "prediction_keV": None,
                "sigma_keV": None,
                "convergence_record_id": record["convergence_record_id"],
            }
            continue

        prediction = mass_excess_keV_from_binding(
            z=z, n=n, binding_MeV=-base["energy_MeV"]
        )
        numerical, numerical_status = _probe_component(
            entry.get("basis"), z=z, n=n, prediction=prediction, required=True
        )
        parameter, parameter_status = _probe_component(
            entry.get("pairing"),
            z=z,
            n=n,
            prediction=prediction,
            required=vpair_n is not None,
        )
        measured = [c for c in (numerical, parameter) if c is not None]
        sigma = max(
            sum(c**2 for c in measured) ** 0.5, SIGMA_FLOOR_KEV
        )
        sigma_status = (
            SIGMA_MEASURED
            if numerical_status == PROBE_MEASURED
            and parameter_status in (PROBE_MEASURED, PROBE_NOT_APPLICABLE)
            else SIGMA_INCOMPLETE
        )
        rows[nuclide_id] = {
            "nuclide_id": nuclide_id,
            "solver_status": status,
            "prediction_keV": prediction,
            "binding_MeV": -base["energy_MeV"],
            "sigma_keV": sigma,
            "sigma_status": sigma_status,
            "numerical_sigma_keV": numerical,
            "numerical_probe_status": numerical_status,
            "parameter_sigma_keV": parameter,
            "parameter_probe_status": parameter_status,
            "iterations": int(base.get("iterations") or 0),
            "convergence_record_id": record["convergence_record_id"],
        }

    return {
        "backend_id": backend_id,
        "functional": functional,
        "parameter_artifact_id": artifact["artifact_id"],
        "physics_family": artifact["physics_family"],
        "provenance_class": artifact["provenance_class"],
        "predictions": dict(sorted(rows.items())),
        "convergence_records": convergence_records,
        "convergence_summary": summarize(convergence_records),
        "uncertainty_policy": UNCERTAINTY_POLICY,
    }


# --------------------------------------------------------------------------- #
# Seal and unlock                                                             #
# --------------------------------------------------------------------------- #


def seal_predictions(
    *,
    dest: str | Path,
    protocol: dict[str, Any],
    target_manifest: dict[str, Any],
    families: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Write SEALED_PREDICTIONS.json and its hash. No truth is present."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": B004_ID,
        "protocol_hash": protocol["protocol_hash"],
        "freeze_id": protocol["freeze_id"],
        "target_identity_digest": target_manifest["target_identity_digest"],
        "target_nuclide_ids": target_manifest["target_nuclide_ids"],
        "parameter_artifacts": {
            backend_id: artifact["artifact_id"]
            for backend_id, artifact in sorted(artifacts.items())
        },
        "families": families,
        "state": "PREDICTIONS_SEALED_TARGET_TRUTH_UNREAD",
        "uncertainty_policy": UNCERTAINTY_POLICY,
    }
    seal_path = dest / SEALED_FILE
    seal_path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    digest = sha256_file(seal_path)
    (dest / SEALED_HASH_FILE).write_text(digest + "\n", encoding="utf-8")
    return {"seal_hash": digest, "path": str(seal_path)}


def unlock_truth(
    *,
    dest: str | Path,
    expected_seal_hash: str,
    protocol: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Verify every governing hash before any measured mass is loaded."""
    dest = Path(dest)
    recorded = (dest / SEALED_HASH_FILE).read_text(encoding="utf-8").strip()
    actual = sha256_file(dest / SEALED_FILE)
    sealed = read_json(dest / SEALED_FILE)
    root = Path(repo_root or REPO_ROOT)

    def _assert(table: dict[str, tuple[str, str]]) -> None:
        for name, (got, want) in table.items():
            if got != want:
                raise ProtocolError(
                    f"B004_CLAIM_INTEGRITY_FAILURE: {name} is {got}, expected "
                    f"{want}; truth stays locked"
                )

    # Seal-side checks run first and the truth file is not so much as opened
    # while any of them is outstanding. Hashing it early would mean touching
    # the truth artifact on a run that is about to be refused.
    checks = {
        "prediction_seal_hash": (actual, expected_seal_hash),
        "recorded_seal_hash": (recorded, expected_seal_hash),
        "protocol_hash": (sealed["protocol_hash"], protocol["protocol_hash"]),
        "target_identity_digest": (
            sealed["target_identity_digest"],
            protocol["target_identity_digest"],
        ),
    }
    for backend_id, artifact in sorted(artifacts.items()):
        from elementzero.physics_backends.artifact import assert_artifact_unchanged

        assert_artifact_unchanged(artifact, expected_id=artifact["artifact_id"])
        checks[f"parameter_artifact:{backend_id}"] = (
            sealed["parameter_artifacts"][backend_id],
            artifact["artifact_id"],
        )
    _assert(checks)

    checks["truth_source_sha256"] = (
        sha256_file(root / AME2020_RELPATH),
        "e8599c6d7f724fac91934e59f1b9de8fb8f63e820f4b39456b790665ed2a3307",
    )
    _assert(checks)
    payload = {
        "truth_unlocked": True,
        "verified": {name: got for name, (got, _) in checks.items()},
    }
    (dest / TRUTH_UNLOCK_FILE).write_text(
        canonical_json(payload) + "\n", encoding="utf-8"
    )
    return payload


# --------------------------------------------------------------------------- #
# Scoring                                                                     #
# --------------------------------------------------------------------------- #


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    preds = [r["prediction_keV"] for r in rows]
    truth = [r["truth_keV"] for r in rows]
    stds = [r["sigma_keV"] for r in rows]
    p68 = [[p - Z68 * s, p + Z68 * s] for p, s in zip(preds, stds, strict=True)]
    p90 = [[p - Z90 * s, p + Z90 * s] for p, s in zip(preds, stds, strict=True)]
    p95 = [[p - Z95 * s, p + Z95 * s] for p, s in zip(preds, stds, strict=True)]
    cov90 = coverage(truth, p90)
    return {
        "n": len(rows),
        "MAE_keV": mae_keV(preds, truth),
        "MedAE_keV": medae_keV(preds, truth),
        "RMSE_keV": rmse_keV(preds, truth),
        "NLPD": nlpd(preds, truth, stds),
        "coverage_68": coverage(truth, p68),
        "coverage_90": cov90,
        "coverage_95": coverage(truth, p95),
        "calibration_error_90": calibration_error(cov90, 0.90),
    }


def _sigma_provenance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """How much of each family's sigma was actually measured.

    A row whose sigma is exactly the floor carries no measured spread at
    all, so any calibration statistic computed from it describes the
    floor rather than the model. Reporting the count keeps a coverage
    number from being read as a calibration result it is not.
    """
    floor_only = [
        r
        for r in rows
        if abs(float(r["sigma_keV"]) - SIGMA_FLOOR_KEV) < 1e-12
    ]
    statuses: dict[str, int] = {}
    for row in rows:
        # Runs sealed before ez-wo15-probe-validity-v1 carry no status.
        key = str(row.get("sigma_status", UNRECORDED_SIGMA_STATUS))
        statuses[key] = statuses.get(key, 0) + 1

    # Interpretability follows the recorded probe status, not the floor.
    # A row whose numerical probe failed while its parameter probe
    # measured something has a sigma above the floor and is still not a
    # measurement of this family's uncertainty; using the floor as a
    # proxy would report it as one.
    incomplete = statuses.get(SIGMA_INCOMPLETE, 0)
    unrecorded = statuses.get(UNRECORDED_SIGMA_STATUS, 0)

    # Three states, not two. A failed probe is known-bad; a run sealed
    # before the policy existed is unknown from the seal alone, and
    # saying "not interpretable" would overstate what the seal shows.
    if not rows or floor_only or incomplete:
        interpretable: bool | None = False
        basis = (
            "a probe failed or a sigma sits at the floor, so the "
            "calibration statistics describe the floor rather than the model"
        )
        # WO-15B v0.5.2 sections 0 and 9: a family whose probes were
        # invalid has no calibration to have failed. Its point
        # predictions remain valid reference results.
        calibration_status = NOT_EVALUABLE_FROM_INVALID_PROBE_SIGMA
    elif unrecorded:
        interpretable = None
        basis = (
            "sealed before ez-wo15-probe-validity-v1, so the seal records no "
            "probe status; probe_validity_audit.json is the authority for "
            "this run"
        )
        calibration_status = "EVALUABLE_BY_PROBE_AUDIT"
    else:
        interpretable = True
        basis = "every row reports sigma_status=MEASURED"
        calibration_status = "EVALUABLE"
    return {
        "calibration_status": calibration_status,
        "n_rows": len(rows),
        "n_sigma_floor_only": len(floor_only),
        "n_sigma_incomplete": incomplete,
        "n_sigma_status_unrecorded": unrecorded,
        "sigma_floor_keV": SIGMA_FLOOR_KEV,
        "sigma_status_counts": dict(sorted(statuses.items())),
        "calibration_interpretable": interpretable,
        "interpretability_basis": basis,
        "probe_policy": PROBE_POLICY,
    }


def score_b004(
    *,
    dest: str | Path,
    protocol: dict[str, Any],
    target_manifest: dict[str, Any],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Score the sealed predictions against AME2020; no threshold moves."""
    dest = Path(dest)
    root = Path(repo_root or REPO_ROOT)
    sealed = read_json(dest / SEALED_FILE)
    # The coverage denominator comes from this manifest, so it is bound to
    # the seal and the protocol before a single mass is read.
    assert_target_manifest_bound(
        target_manifest=target_manifest, protocol=protocol, sealed=sealed
    )
    truth = {
        o.nuclide_id: o.mass_excess_keV
        for o in load_edition("AME2020", str(root / AME2020_RELPATH))
        if o.ground_truth_eligible
    }
    strata_by_id = {t["nuclide_id"]: t for t in target_manifest["targets"]}

    by_model: dict[str, Any] = {}
    for family in sealed["families"]:
        scored_rows = []
        for nuclide_id, row in family["predictions"].items():
            if row["prediction_keV"] is None:
                continue
            scored_rows.append(
                {
                    **row,
                    "prediction_keV": float(row["prediction_keV"]),
                    "sigma_keV": float(row["sigma_keV"]),
                    "truth_keV": truth[nuclide_id],
                    "error_keV": float(row["prediction_keV"]) - truth[nuclide_id],
                    **{
                        k: strata_by_id[nuclide_id][k]
                        for k in (
                            "z_band",
                            "frontier_direction",
                            "shell_adjacent",
                            "nearest_freeze_distance_L1",
                        )
                    },
                }
            )
        n_target = len(target_manifest["target_nuclide_ids"])
        entry = {
            "backend_id": family["backend_id"],
            "physics_family": family["physics_family"],
            "provenance_class": family["provenance_class"],
            "parameter_artifact_id": family["parameter_artifact_id"],
            "n_target": n_target,
            "n_predicted": len(scored_rows),
            "coverage_fraction": len(scored_rows) / n_target if n_target else 0.0,
            "metrics": _metrics(scored_rows) if scored_rows else None,
            "sigma_provenance": _sigma_provenance(scored_rows),
            "by_stratum": _by_stratum(scored_rows),
            "per_target": sorted(
                (
                    {
                        "nuclide_id": r["nuclide_id"],
                        "prediction_keV": r["prediction_keV"],
                        "truth_keV": r["truth_keV"],
                        "error_keV": r["error_keV"],
                        "sigma_keV": r["sigma_keV"],
                    }
                    for r in scored_rows
                ),
                key=lambda r: r["nuclide_id"],
            ),
            "convergence_summary": family["convergence_summary"],
        }
        by_model[family["backend_id"]] = entry

    return {
        "experiment_id": B004_ID,
        "protocol_hash": protocol["protocol_hash"],
        "truth_edition": "AME2020",
        "by_model": dict(sorted(by_model.items())),
        "family_disagreement": _family_disagreement(sealed["families"]),
        "derived_s2n": _derived_s2n(sealed["families"], truth, target_manifest),
        "min_coverage_fraction": MIN_COVERAGE_FRACTION,
        "legacy_inherited_reference_keV": protocol["legacy_inherited_reference_keV"],
        "legacy_reference_status": "LEGACY_INHERITED_REFERENCE",
        "performance_interpretation": protocol["performance_interpretation"],
    }


def _by_stratum(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("z_band", "frontier_direction", "shell_adjacent",
                "nearest_freeze_distance_L1"):
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            buckets.setdefault(str(row[key]), []).append(row)
        out[key] = {
            name: _metrics(bucket) for name, bucket in sorted(buckets.items())
        }
    return out


def _family_disagreement(families: list[dict[str, Any]]) -> dict[str, Any]:
    """Spread across families, reported separately from any family sigma."""
    per_target: dict[str, list[float]] = {}
    for family in families:
        for nuclide_id, row in family["predictions"].items():
            if row["prediction_keV"] is not None:
                per_target.setdefault(nuclide_id, []).append(
                    float(row["prediction_keV"])
                )
    spread = {
        nuclide_id: max(values) - min(values)
        for nuclide_id, values in sorted(per_target.items())
        if len(values) > 1
    }
    return {
        "rule": (
            "max minus min predicted mass excess across families with a "
            "converged prediction; reported alongside, never inside, a "
            "single family's uncertainty"
        ),
        "per_target_spread_keV": spread,
        "mean_spread_keV": (sum(spread.values()) / len(spread)) if spread else None,
    }


def _derived_s2n(
    families: list[dict[str, Any]],
    truth: dict[str, float],
    target_manifest: dict[str, Any],
) -> dict[str, Any]:
    """S2n only where both component masses are blind predictions."""
    rows = []
    target_ids = set(target_manifest["target_nuclide_ids"])
    for family in families:
        predictions = family["predictions"]
        for nuclide_id in sorted(predictions):
            z, n = parse_nuclide_id(nuclide_id)
            partner = f"Z{z}-N{n - 2}"
            if partner not in target_ids:
                continue
            here, there = predictions.get(nuclide_id), predictions.get(partner)
            if not here or not there:
                continue
            if here["prediction_keV"] is None or there["prediction_keV"] is None:
                continue
            if nuclide_id not in truth or partner not in truth:
                continue
            b_here = binding_energy_MeV(
                z=z, n=n, mass_excess_keV=float(here["prediction_keV"])
            )
            b_there = binding_energy_MeV(
                z=z, n=n - 2, mass_excess_keV=float(there["prediction_keV"])
            )
            t_here = binding_energy_MeV(z=z, n=n, mass_excess_keV=truth[nuclide_id])
            t_there = binding_energy_MeV(
                z=z, n=n - 2, mass_excess_keV=truth[partner]
            )
            rows.append(
                {
                    "derived_observable_id": f"S2n:{nuclide_id}",
                    "backend_id": family["backend_id"],
                    "central_nuclide_id": nuclide_id,
                    "component_nuclide_ids": [partner, nuclide_id],
                    "predicted_MeV": b_here - b_there,
                    "truth_MeV": t_here - t_there,
                    "error_MeV": (b_here - b_there) - (t_here - t_there),
                    "all_components_blind_predictions": True,
                }
            )
    return {
        "rule": (
            "a derived S2n is scored only when both component masses are "
            "themselves blind predictions of the same family on the "
            "preregistered target set; shell-adjacent evidence is never "
            "shell rediscovery"
        ),
        "n_rows": len(rows),
        "rows": rows,
        "evaluable": bool(rows),
    }


def target_digest(target_ids: list[str]) -> str:
    return identity_digest(target_ids)
