#!/usr/bin/env python3
"""Audit the uncertainty probes behind the sealed EZ-B004 predictions.

Written for the WO-15 review round. EZ-B004-v1 was sealed under a probe
rule that accepted any probe energy that happened to parse; the rule now
requires the probe to converge. This tool does not touch the seal — it
reads the retained solver work directories and reports, per family, how
much of the sealed sigma was an actual measurement.

That distinction matters for reading the result: a family whose probes
all failed has a sigma equal to the floor, so its coverage and NLPD
describe the floor rather than the model's calibration.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elementzero.b004 import RESULTS_RELPATH  # noqa: E402
from elementzero.b004.runs import (  # noqa: E402
    PROBE_MEASURED,
    PROBE_NONCONVERGED,
    PROBE_NOT_APPLICABLE,
    PROBE_POLICY,
    SEALED_FILE,
    SIGMA_FLOOR_KEV,
    _probe_component,
)
from elementzero.data.identity import parse_nuclide_id  # noqa: E402
from elementzero.evidence.hashing import canonical_json  # noqa: E402
from elementzero.evidence.ledger import read_json  # noqa: E402
from elementzero.physics_backends.output_parser import (  # noqa: E402
    parse_dirhb,
    parse_hfbtho,
)

AUDIT_FILE = "probe_validity_audit.json"


def audit(work_root: Path, results: Path) -> dict:
    sealed = read_json(results / SEALED_FILE)
    families = []
    for family in sealed["families"]:
        backend_id = family["backend_id"]
        parse = parse_dirhb if "COVARIANT" in backend_id else parse_hfbtho
        backend_dir = work_root / backend_id
        rows = []
        for nuclide_id, row in sorted(family["predictions"].items()):
            if row["prediction_keV"] is None:
                continue
            z, n = parse_nuclide_id(nuclide_id)
            prediction = float(row["prediction_keV"])
            entry = {"nuclide_id": nuclide_id, "sealed_sigma_keV": row["sigma_keV"]}
            for variant, component, required in (
                ("basis", "numerical", True),
                ("pairing", "parameter", float(row["parameter_sigma_keV"]) != 0.0),
            ):
                probe_dir = backend_dir / nuclide_id / variant
                parsed = parse(probe_dir) if probe_dir.is_dir() else None
                value, status = _probe_component(
                    parsed, z=z, n=n, prediction=prediction, required=required
                )
                entry[f"{component}_probe_status"] = status
                entry[f"{component}_probe_keV"] = value
                entry[f"{component}_sealed_keV"] = row[f"{component}_sigma_keV"]
            rows.append(entry)
        measured = [
            r
            for r in rows
            if r["numerical_probe_status"] == PROBE_MEASURED
            and r["parameter_probe_status"]
            in (PROBE_MEASURED, PROBE_NOT_APPLICABLE)
        ]
        nonconverged = [
            r
            for r in rows
            if PROBE_NONCONVERGED
            in (r["numerical_probe_status"], r["parameter_probe_status"])
        ]
        floor_only = [
            r
            for r in rows
            if abs(float(r["sealed_sigma_keV"]) - SIGMA_FLOOR_KEV) < 1e-12
        ]
        families.append(
            {
                "backend_id": backend_id,
                "physics_family": family["physics_family"],
                "n_rows": len(rows),
                "n_fully_measured": len(measured),
                "n_with_nonconverged_probe": len(nonconverged),
                "n_sigma_floor_only": len(floor_only),
                "sealed_sigma_is_measurement": len(rows) > 0
                and len(measured) == len(rows)
                and not floor_only,
                "rows": rows,
            }
        )
    return {
        "audit_id": "ez-wo15-b004-probe-validity-audit-v1",
        "experiment_id": sealed["experiment_id"],
        "probe_policy": PROBE_POLICY,
        "seal_untouched": True,
        "note": (
            "EZ-B004-v1 was sealed before ez-wo15-probe-validity-v1 existed. "
            "The seal is evidence and is not rewritten; this audit records "
            "which sealed uncertainties were real measurements so the "
            "calibration statistics are read for what they are"
        ),
        "families": families,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", default="data/physics_backends/b004work")
    parser.add_argument("--results", default=RESULTS_RELPATH)
    args = parser.parse_args()
    work_root = Path(args.work)
    if not work_root.is_dir():
        print(f"{work_root} is absent; the probe outputs cannot be audited")
        return 1
    report = audit(work_root, Path(args.results))
    out = Path(args.results) / AUDIT_FILE
    out.write_text(canonical_json(report) + "\n", encoding="utf-8")
    for family in report["families"]:
        print(
            f"{family['backend_id']:28s} measured "
            f"{family['n_fully_measured']}/{family['n_rows']}  "
            f"nonconverged-probe {family['n_with_nonconverged_probe']}  "
            f"floor-only sigma {family['n_sigma_floor_only']}"
        )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
