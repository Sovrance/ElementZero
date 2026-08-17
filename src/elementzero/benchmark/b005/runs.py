"""B005 execution: predict, seal, commit, unlock, score.

The sealing discipline is WO-14's and the binding discipline is the one
PR #17 introduced, reused rather than reimplemented. What is new here is
that every prediction carries a structured sigma provenance record, and
scoring keeps two populations apart: point metrics over every converged
row, calibration metrics over only the rows whose uncertainty was
actually measured. Mixing them is how WO-15 reported a floor as a
calibration result.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.benchmark.b005 import B005_ID
from elementzero.data.amdc import load_edition
from elementzero.data.identity import parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file
from elementzero.evidence.ledger import read_json
from elementzero.model_discrepancy import sigma_provenance as sp
from elementzero.model_discrepancy.coverage import calibration_metrics, z_band
from elementzero.physics.conversion import mass_excess_keV_from_binding
from elementzero.physics_backends.protocol import SOLVER_OK

SEALED_FILE = "SEALED_PREDICTIONS.json"
SEALED_HASH_FILE = "SEALED_PREDICTIONS_SHA256"
TRUTH_UNLOCK_FILE = "truth_unlock.json"
AME2020_RELPATH = "data/amdc/mass_1.mas20.txt"

BASIS_PROBE_DELTA_SHELLS = 2
PAIRING_PROBE_DELTA = 10.0


def _classify(parsed: dict[str, Any]) -> tuple[str, str]:
    from elementzero.physics_backends.adapters.hfbtho import _classify as c

    return c(parsed)


def predict_family(
    *,
    family_id: str,
    backend_id: str,
    solve: Any,
    target_ids: list[str],
    work_root: str | Path,
    discrepancy: dict[str, Any] | None = None,
    training_set: dict[str, Any] | None = None,
    max_workers: int = 4,
) -> dict[str, Any]:
    """Raw solves, uncertainty probes, and the calibrated prediction.

    ``solve`` is a callable (nuclide_id, variant, work_dir) -> parsed
    output, so the caller owns the backend and this function owns the
    protocol.
    """
    work_root = Path(work_root)
    jobs = [
        (nuclide_id, variant)
        for nuclide_id in target_ids
        for variant in ("base", "basis")
    ]
    solved: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                solve, nuclide_id, variant, work_root / nuclide_id / variant
            ): (nuclide_id, variant)
            for nuclide_id, variant in jobs
        }
        for future in concurrent.futures.as_completed(futures):
            nuclide_id, variant = futures[future]
            solved.setdefault(nuclide_id, {})[variant] = future.result()

    model = None
    if discrepancy and training_set:
        from elementzero.model_discrepancy.calibration import rebuild_model

        model = rebuild_model(discrepancy, training_set)

    rows: list[dict[str, Any]] = []
    probe_records: list[dict[str, Any]] = []
    for nuclide_id in target_ids:
        entry = solved.get(nuclide_id, {})
        base = entry.get("base")
        z, n = parse_nuclide_id(nuclide_id)
        if base is None:
            rows.append(
                {
                    "nuclide_id": nuclide_id,
                    "solver_status": "UNSUPPORTED_NUCLIDE",
                    "prediction_keV": None,
                }
            )
            continue
        status, _ = _classify(base)
        if status != SOLVER_OK or base.get("energy_MeV") is None:
            rows.append(
                {
                    "nuclide_id": nuclide_id,
                    "solver_status": status,
                    "prediction_keV": None,
                }
            )
            continue

        raw = mass_excess_keV_from_binding(
            z=z, n=n, binding_MeV=-base["energy_MeV"]
        )

        probe = entry.get("basis")
        probe_status, probe_value = sp.UNAVAILABLE, None
        if probe is not None:
            pstatus, _ = _classify(probe)
            converged = pstatus == SOLVER_OK
            energy_ok = probe.get("energy_MeV") is not None
            record = sp.probe_record(
                family_id=family_id,
                nuclide_id=nuclide_id,
                variant="basis",
                converged=converged,
                energy_valid=energy_ok,
                workdir_id=str(work_root / nuclide_id / "basis"),
                output_hash=probe.get("output_hash"),
            )
            probe_records.append(record)
            if converged and energy_ok:
                probe_status = sp.MEASURED
                probe_value = abs(
                    mass_excess_keV_from_binding(
                        z=z, n=n, binding_MeV=-probe["energy_MeV"]
                    )
                    - raw
                )
            else:
                probe_status = sp.INVALID_PROBE

        numerical = sp.component(
            status=probe_status,
            value_keV=probe_value,
            n_requested=1,
            n_valid=1 if probe_status == sp.MEASURED else 0,
        )
        # The parameter component is propagated from the frozen artifact
        # rather than re-probed: the fit's own optimizer path is the
        # evidence, and re-probing after the freeze would be a new fit.
        parameter = sp.component(status=sp.NOT_APPLICABLE)

        discrepancy_component = sp.component(status=sp.NOT_APPLICABLE)
        prediction = raw
        if model is not None:
            from elementzero.model_discrepancy.calibration import calibrate_rows

            calibrated = calibrate_rows(
                model=model,
                artifact=discrepancy,
                rows=[{"nuclide_id": nuclide_id, "prediction_keV": raw}],
            )[0]
            prediction = calibrated["prediction_keV"]
            discrepancy_component = sp.component(
                status=sp.POSTERIOR,
                value_keV=calibrated["discrepancy_sigma_keV"],
                model_artifact_hash=discrepancy["artifact_hash"],
            )

        provenance = sp.compose(
            nuclide_id=nuclide_id,
            family_id=family_id,
            numerical=numerical,
            parameter=parameter,
            discrepancy=discrepancy_component,
        )
        rows.append(
            {
                "nuclide_id": nuclide_id,
                "solver_status": status,
                "raw_prediction_keV": raw,
                "prediction_keV": prediction,
                "sigma_keV": provenance["total_predictive"]["value_keV"],
                "sigma_provenance": provenance,
                "z_band": z_band(z),
            }
        )

    summary = sp.family_sigma_summary(
        [r["sigma_provenance"] for r in rows if "sigma_provenance" in r]
    )
    return {
        "family_id": family_id,
        "backend_id": backend_id,
        "predictions": {r["nuclide_id"]: r for r in rows},
        "probe_records": probe_records,
        "sigma_summary": summary,
        "n_predicted": sum(1 for r in rows if r["prediction_keV"] is not None),
        "n_target": len(target_ids),
    }


def seal_predictions(
    *,
    dest: str | Path,
    protocol: dict[str, Any],
    target_manifest: dict[str, Any],
    families: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Write the sealed predictions. No truth is present."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": B005_ID,
        "protocol_hash": protocol["protocol_hash"],
        "target_identity_digest": target_manifest["target_identity_digest"],
        "target_nuclide_ids": target_manifest["target_nuclide_ids"],
        "artifacts": {k: v for k, v in sorted(artifacts.items())},
        "families": families,
        "state": "PREDICTIONS_SEALED_TARGET_TRUTH_UNREAD",
    }
    seal_path = dest / SEALED_FILE
    seal_path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    digest = sha256_file(seal_path)
    (dest / SEALED_HASH_FILE).write_text(digest + "\n", encoding="utf-8")
    return {"seal_hash": digest, "path": str(seal_path)}


def score_b005(
    *,
    dest: str | Path,
    protocol: dict[str, Any],
    target_manifest: dict[str, Any],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Point metrics over converged rows; calibration over valid-sigma rows."""
    from elementzero.b004.bind import assert_target_manifest_bound

    dest = Path(dest)
    root = Path(repo_root or REPO_ROOT)
    sealed = read_json(dest / SEALED_FILE)
    assert_target_manifest_bound(
        target_manifest=target_manifest, protocol=protocol, sealed=sealed
    )
    truth = {
        o.nuclide_id: o.mass_excess_keV
        for o in load_edition("AME2020", str(root / AME2020_RELPATH))
        if o.ground_truth_eligible
    }

    by_family: dict[str, Any] = {}
    for family in sealed["families"]:
        point_rows, calib_rows = [], []
        for nuclide_id, row in family["predictions"].items():
            if row.get("prediction_keV") is None:
                continue
            if nuclide_id not in truth:
                raise ProtocolError(
                    f"B005_TRUTH_MISSING: {nuclide_id} has no AME2020 "
                    "ground-truth-eligible mass but was sealed as a target"
                )
            scored = {
                **row,
                "truth_keV": truth[nuclide_id],
                "error_keV": float(row["prediction_keV"]) - truth[nuclide_id],
            }
            point_rows.append(scored)
            provenance = row.get("sigma_provenance") or {}
            if provenance.get("total_predictive", {}).get(
                "valid_for_calibration_scoring"
            ):
                calib_rows.append(scored)

        n_target = len(target_manifest["target_nuclide_ids"])
        by_family[family["family_id"]] = {
            "family_id": family["family_id"],
            "backend_id": family["backend_id"],
            "n_target": n_target,
            "n_predicted": len(point_rows),
            "coverage_fraction": len(point_rows) / n_target if n_target else 0.0,
            "point_metrics": calibration_metrics(point_rows),
            "calibration_metrics": calibration_metrics(calib_rows),
            "n_sigma_valid": len(calib_rows),
            "sigma_valid_fraction": (
                len(calib_rows) / len(point_rows) if point_rows else 0.0
            ),
            "sigma_summary": family["sigma_summary"],
        }
    return {
        "experiment_id": B005_ID,
        "protocol_hash": protocol["protocol_hash"],
        "truth_edition": "AME2020",
        "by_family": dict(sorted(by_family.items())),
        "scoring_policy": (
            "point metrics use every converged row; calibration metrics use "
            "only rows whose sigma provenance is valid. A row with a real "
            "prediction and an unusable sigma contributes to accuracy and "
            "not to coverage"
        ),
    }


__all__ = [
    "AME2020_RELPATH",
    "SEALED_FILE",
    "SEALED_HASH_FILE",
    "TRUTH_UNLOCK_FILE",
    "predict_family",
    "score_b005",
    "seal_predictions",
]
