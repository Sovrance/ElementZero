"""Sigma provenance as a first-class record (WO-15B v0.5.2 §3).

WO-15 reported a single sigma per prediction, and the covariant family
showed what that costs: every one of its larger-basis probes failed, the
numerical component was silently recorded as zero, and the resulting
1 keV floor was read as a calibration measurement. A number with no
account of where it came from cannot be audited.

So each component now carries its own status, and the composed total
carries an explicit ``valid_for_calibration_scoring`` flag. A row whose
uncertainty is a floor or a failed probe still has a point prediction
worth scoring; it simply cannot contribute to a calibration statistic,
and the two facts are kept apart rather than averaged together.
"""

from __future__ import annotations

import math
from typing import Any

from elementzero.evidence.hashing import sha256_hex

# The complete status vocabulary, fixed by the spec.
MEASURED = "MEASURED"
PROPAGATED = "PROPAGATED"
POSTERIOR = "POSTERIOR"
NOT_APPLICABLE = "NOT_APPLICABLE"
INVALID_PROBE = "INVALID_PROBE"
UNAVAILABLE = "UNAVAILABLE"
FLOOR_ONLY = "FLOOR_ONLY"

COMPONENT_STATUSES = (
    MEASURED,
    PROPAGATED,
    POSTERIOR,
    NOT_APPLICABLE,
    INVALID_PROBE,
    UNAVAILABLE,
    FLOOR_ONLY,
)

# Probe-record statuses are a narrower vocabulary.
PROBE_MEASURED = "MEASURED"
PROBE_INVALID = "PROBE_INVALID"
PROBE_UNAVAILABLE = "UNAVAILABLE"

SIGMA_FLOOR_KEV = 1.0

COMPOSITION_POLICY = (
    "ez-wo15b-sigma-composition-v1: total predictive sigma is the quadrature "
    "sum of the components that carry a real measurement — numerical, "
    "parameter, discrepancy posterior and emulator. A component that is "
    "INVALID_PROBE or UNAVAILABLE contributes nothing and disqualifies the "
    "row from calibration scoring; it is never silently read as zero. "
    "NOT_APPLICABLE is a declared absence and does not disqualify. A total "
    "that falls back to the floor is FLOOR_ONLY and never valid for "
    "calibration"
)

# A component in one of these states means the row's sigma is not a
# measurement of this family's uncertainty.
DISQUALIFYING = (INVALID_PROBE, UNAVAILABLE, FLOOR_ONLY)


def probe_record(
    *,
    family_id: str,
    nuclide_id: str,
    variant: str,
    converged: bool,
    energy_valid: bool,
    workdir_id: str,
    output_hash: str | None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One probe's evidence, schema-exact and content-addressed."""
    if converged and energy_valid:
        status = PROBE_MEASURED
    elif output_hash is None:
        status = PROBE_UNAVAILABLE
    else:
        status = PROBE_INVALID
    record = {
        "family_id": family_id,
        "nuclide_id": nuclide_id,
        "variant": variant,
        "converged": bool(converged),
        "energy_valid": bool(energy_valid),
        "status": status,
        "workdir_id": workdir_id,
        "output_hash": output_hash,
        "detail": detail or {},
    }
    record["probe_id"] = (
        f"probe-{family_id}-{nuclide_id}-{variant}-"
        f"{sha256_hex(record)[:12]}"
    )
    return record


def component(
    *,
    status: str,
    value_keV: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """One uncertainty component with its status and evidence."""
    if status not in COMPONENT_STATUSES:
        raise ValueError(f"unknown sigma component status {status!r}")
    return {"status": status, "value_keV": value_keV, **extra}


def compose(
    *,
    nuclide_id: str,
    family_id: str,
    numerical: dict[str, Any],
    parameter: dict[str, Any],
    discrepancy: dict[str, Any] | None = None,
    emulator: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose the total predictive sigma and say whether it is usable."""
    components = {
        "numerical": numerical,
        "parameter": parameter,
        "discrepancy": discrepancy
        or component(status=NOT_APPLICABLE),
        "emulator": emulator or component(status=NOT_APPLICABLE),
    }

    contributing = []
    disqualified: list[str] = []
    for name, comp in components.items():
        if comp["status"] in DISQUALIFYING:
            disqualified.append(name)
            continue
        if comp["status"] == NOT_APPLICABLE:
            continue
        value = comp.get("value_keV")
        if value is None:
            disqualified.append(name)
            continue
        contributing.append(float(value))

    total = math.sqrt(sum(v**2 for v in contributing)) if contributing else 0.0
    floored = total < SIGMA_FLOOR_KEV
    value = max(total, SIGMA_FLOOR_KEV)
    valid = not disqualified and not floored and bool(contributing)

    record = {
        "nuclide_id": nuclide_id,
        "family_id": family_id,
        "components": components,
        "total_predictive": {
            "value_keV": value,
            "composition_policy": COMPOSITION_POLICY,
            "valid_for_calibration_scoring": valid,
            "status": FLOOR_ONLY if floored else MEASURED,
            "n_contributing_components": len(contributing),
            "disqualifying_components": sorted(disqualified),
        },
    }
    return record


def family_sigma_summary(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """What fraction of a family's rows can carry a calibration claim."""
    n = len(records)
    valid = [
        r for r in records
        if r["total_predictive"]["valid_for_calibration_scoring"]
    ]
    fraction = len(valid) / n if n else 0.0
    reasons: dict[str, int] = {}
    for record in records:
        for name in record["total_predictive"]["disqualifying_components"]:
            status = record["components"][name]["status"]
            key = f"{name}:{status}"
            reasons[key] = reasons.get(key, 0) + 1
    return {
        "n_rows": n,
        "n_sigma_valid": len(valid),
        "sigma_valid_fraction": fraction,
        "disqualification_reasons": dict(sorted(reasons.items())),
        "composition_policy": COMPOSITION_POLICY,
    }


__all__ = [
    "COMPONENT_STATUSES",
    "COMPOSITION_POLICY",
    "DISQUALIFYING",
    "FLOOR_ONLY",
    "INVALID_PROBE",
    "MEASURED",
    "NOT_APPLICABLE",
    "POSTERIOR",
    "PROBE_INVALID",
    "PROBE_MEASURED",
    "PROBE_UNAVAILABLE",
    "PROPAGATED",
    "SIGMA_FLOOR_KEV",
    "UNAVAILABLE",
    "compose",
    "component",
    "family_sigma_summary",
    "probe_record",
]
