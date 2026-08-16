"""WO-11.3 — structured failure records for the frozen v1 outcomes.

Every failed frozen criterion produces one FailureRecord per failed check.
EZ-B002-v1 froze *no* accuracy criterion, so its records document observed
characterization weaknesses against the nominal coverage targets, with
``frozen_threshold`` honestly ``None`` and the notes saying so — nothing here
invents a criterion after the fact.

Classification discipline:

    - a class is only asserted when the WO-11 evidence (sealed diagnostics,
      oracle controls, dev ablations) supports it,
    - INDETERMINATE is used when it does not,
    - ``requires_protocol_change`` stays false for every record attributed to
      a model: the benchmarks behaved correctly under their oracle controls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.errors import SchemaError
from elementzero.evidence.hashing import canonical_json

FAILURE_RECORDS_FILE = "failure_records.json"

ALLOWED_PRIMARY_CLASSES: tuple[str, ...] = (
    "MODEL_BIAS",
    "MODEL_VARIANCE",
    "UNCERTAINTY_UNDERCOVERAGE",
    "UNCERTAINTY_OVERCOVERAGE",
    "EXTRAPOLATION_DEPTH",
    "FEATURE_INSUFFICIENCY",
    "HYPERPARAMETER_SENSITIVITY",
    "BENCHMARK_GEOMETRY",
    "TARGET_SUPPORT_SPARSITY",
    "METRIC_INSTABILITY",
    "IMPLEMENTATION_DEFECT",
    "INFRASTRUCTURE_FAILURE",
    "INDETERMINATE",
)

ALLOWED_CONFIDENCE = ("LOW", "MEDIUM", "HIGH")

REQUIRED_FIELDS: tuple[str, ...] = (
    "failure_id",
    "benchmark_id",
    "protocol_version",
    "model_id",
    "criterion_id",
    "observed_value",
    "frozen_threshold",
    "primary_class",
    "secondary_classes",
    "evidence",
    "confidence",
    "requires_protocol_change",
    "notes",
)


def validate_failure_record(record: dict[str, Any]) -> dict[str, Any]:
    """Enforce schemas/wo11_failure_record.schema.json in code."""
    missing = [f for f in REQUIRED_FIELDS if f not in record]
    if missing:
        raise SchemaError(f"failure record is missing required fields: {missing}")
    extra = sorted(set(record) - set(REQUIRED_FIELDS))
    if extra:
        raise SchemaError(f"failure record carries unknown fields: {extra}")
    if record["primary_class"] not in ALLOWED_PRIMARY_CLASSES:
        raise SchemaError(
            f"unknown primary failure class {record['primary_class']!r}; allowed: "
            f"{list(ALLOWED_PRIMARY_CLASSES)}"
        )
    if not isinstance(record["secondary_classes"], list) or any(
        not isinstance(c, str) for c in record["secondary_classes"]
    ):
        raise SchemaError("secondary_classes must be a list of strings")
    unknown_secondary = [
        c for c in record["secondary_classes"] if c not in ALLOWED_PRIMARY_CLASSES
    ]
    if unknown_secondary:
        raise SchemaError(f"unknown secondary failure classes: {unknown_secondary}")
    if not isinstance(record["evidence"], list) or any(
        not isinstance(e, dict) for e in record["evidence"]
    ):
        raise SchemaError("evidence must be a list of objects")
    if record["confidence"] not in ALLOWED_CONFIDENCE:
        raise SchemaError(
            f"unknown confidence {record['confidence']!r}; allowed: {list(ALLOWED_CONFIDENCE)}"
        )
    if not isinstance(record["requires_protocol_change"], bool):
        raise SchemaError("requires_protocol_change must be a boolean")
    for field in ("failure_id", "benchmark_id", "protocol_version", "model_id", "criterion_id"):
        if not isinstance(record[field], str) or not record[field]:
            raise SchemaError(f"{field} must be a non-empty string")
    if not isinstance(record["notes"], str):
        raise SchemaError("notes must be a string")
    return record


def _record(**kwargs: Any) -> dict[str, Any]:
    return validate_failure_record(kwargs)


def _ev(source: str, observation: str, value: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"source": source, "observation": observation}
    if value is not None:
        payload["value"] = value
    return payload


# --------------------------------------------------------------------------- #
# Record construction from the committed v1 evidence                          #
# --------------------------------------------------------------------------- #

B003_CRITERION_ID = "ez-b003-rediscovery-criterion-v1"
B002_CRITERION_ID = "ez-b002-v1-no-accuracy-threshold"

_SMEARING_NOTE = (
    "A squared-exponential GP has no inductive bias for a kink: training data "
    "below and above the closure differ in slope, but which lattice site the "
    "break occurred at survives only in the level offset, so a smooth "
    "interpolator smears the indicator spike across the search window instead "
    "of localizing it."
)


def _b003_failed_checks(inventory: dict[str, Any], b003_aggregate: dict[str, Any]):
    protocol = inventory["experiments"]["EZ-B003-v1"]["protocol_version"]
    for model_id, payload in sorted(b003_aggregate["by_model"].items()):
        for check_name, check in sorted(payload["criterion"]["checks"].items()):
            if check["met"] is False:
                yield model_id, protocol, check_name, check


def build_b003_records(
    *,
    inventory: dict[str, Any],
    b003_aggregate: dict[str, Any],
    diagnostics: dict[str, Any],
    controls: dict[str, Any],
    ablations: dict[str, Any],
) -> list[dict[str, Any]]:
    records = []
    control_ev = _ev(
        "benchmark_controls.json",
        "shell-aware oracle meets the frozen criterion and the weak smooth "
        "control fails it, so the mechanics and criterion separate a capable "
        "predictor from an incapable one",
        controls["EZ-B003"]["status"],
    )
    dev_summary = ablations["summary"]["EZ-B003-dev"]
    dev_ev = _ev(
        "ablation_matrix.json",
        "on the dev shell fixture the frozen fixed-kernel GP scores rank-1 "
        "fraction 0 while the optimizer-enabled variant reaches the highest "
        "dev localization; feature additions barely move it",
        dev_summary["hyperparameter_shell_metric"],
    )
    for model_id, protocol, check_name, check in _b003_failed_checks(
        inventory, b003_aggregate
    ):
        calibration = diagnostics["EZ-B003-v1"]["by_model"][model_id]["calibration"]
        if check_name == "calibration_error_90":
            primary = "UNCERTAINTY_UNDERCOVERAGE"
            secondary = ["MODEL_BIAS"]
            evidence = [
                _ev(
                    "uncertainty_diagnostics.json",
                    "standardized residuals are biased, not merely wide: the "
                    "mean is far from zero while the spread is near one, so "
                    "the missed intervals come from a shifted mean with a "
                    "global sigma that cannot absorb structured error",
                    {"mean_z": calibration["mean_z"], "std_z": calibration["std_z"]},
                ),
                control_ev,
            ]
            notes = (
                "SEMF-LS reports one global residual sigma; near a masked "
                "closure its systematic bias dominates and the nominal 90% "
                "interval covers far less."
            )
        else:
            primary = "MODEL_BIAS"
            secondary = ["HYPERPARAMETER_SENSITIVITY"] if model_id != "EZ-SEMF-LS-v1" else []
            evidence = [
                _ev(
                    "shell_aggregate.json",
                    f"frozen check {check_name} failed on the sealed run",
                    {"observed": check["observed"], "threshold": check["threshold"]},
                ),
                control_ev,
            ]
            if model_id == "EZ-SEMF-LS-v1":
                evidence.append(
                    _ev(
                        "shell_aggregate.json",
                        "plain SEMF has no term that can express a shell gap; "
                        "its reconstruction resolves H0 (no discontinuity) "
                        "while snapshot truth resolves H1",
                    )
                )
                notes = (
                    "A model family without any shell-capable term cannot "
                    "rediscover a shell gap; this is structural model bias, "
                    "not a benchmark defect."
                )
            else:
                evidence.append(dev_ev)
                notes = _SMEARING_NOTE
        records.append(
            _record(
                failure_id=f"WO11-F-B003-{model_id}-{check_name}",
                benchmark_id="EZ-B003",
                protocol_version=protocol,
                model_id=model_id,
                criterion_id=f"{B003_CRITERION_ID}:{check_name}",
                observed_value=float(check["observed"]),
                frozen_threshold=float(check["threshold"]),
                primary_class=primary,
                secondary_classes=secondary,
                evidence=evidence,
                confidence="HIGH",
                requires_protocol_change=False,
                notes=notes,
            )
        )
    return records


def build_b002_records(
    *,
    inventory: dict[str, Any],
    diagnostics: dict[str, Any],
    controls: dict[str, Any],
    ablations: dict[str, Any],
) -> list[dict[str, Any]]:
    """Characterization observations: EZ-B002-v1 froze no accuracy criterion."""
    protocol = inventory["experiments"]["EZ-B002-v1"]["protocol_version"]
    by_model = diagnostics["EZ-B002-v1"]["by_model"]
    no_criterion_note = (
        "EZ-B002 v1 is characterization: no accuracy pass/fail threshold was "
        "preregistered and none is invented here. The nominal 90% coverage of "
        "the reported interval is the reference point, not a frozen threshold."
    )
    control_ev = _ev(
        "benchmark_controls.json",
        "the exact oracle reconstructs the withheld regions with zero error "
        "and the noisy oracle comes back calibrated, so the split, masking, "
        "and metric mechanics are sound",
        controls["EZ-B002"]["status"],
    )
    records = []

    semf = by_model["EZ-SEMF-LS-v1"]
    records.append(
        _record(
            failure_id="WO11-F-B002-EZ-SEMF-LS-v1-undercoverage",
            benchmark_id="EZ-B002",
            protocol_version=protocol,
            model_id="EZ-SEMF-LS-v1",
            criterion_id=B002_CRITERION_ID,
            observed_value=semf["pooled"]["coverage_90"],
            frozen_threshold=None,
            primary_class="UNCERTAINTY_UNDERCOVERAGE",
            secondary_classes=["MODEL_BIAS"],
            evidence=[
                _ev(
                    "uncertainty_diagnostics.json",
                    "nominal 90% intervals covered less than half the withheld "
                    "truth; standardized residuals show a shifted mean rather "
                    "than a wide spread",
                    {
                        "coverage_90": semf["pooled"]["coverage_90"],
                        "mean_z": semf["calibration"]["mean_z"],
                        "std_z": semf["calibration"]["std_z"],
                    },
                ),
                control_ev,
            ],
            confidence="HIGH",
            requires_protocol_change=False,
            notes=no_criterion_note,
        )
    )

    gp = by_model["EZ-GP-DIRECT-v1"]
    residual = by_model["EZ-SEMF-GP-RESIDUAL-v1"]
    dev = ablations["summary"]["EZ-B002-dev"]
    records.append(
        _record(
            failure_id="WO11-F-B002-EZ-GP-DIRECT-v1-bias",
            benchmark_id="EZ-B002",
            protocol_version=protocol,
            model_id="EZ-GP-DIRECT-v1",
            criterion_id=B002_CRITERION_ID,
            observed_value=gp["pooled"]["MAE_keV"],
            frozen_threshold=None,
            primary_class="MODEL_BIAS",
            secondary_classes=["HYPERPARAMETER_SENSITIVITY"],
            evidence=[
                _ev(
                    "uncertainty_diagnostics.json",
                    "pooled MAE is roughly 40x the SEMF+GP residual model on "
                    "identical splits, so the physics-free mean function, not "
                    "the data or the split, is what fails",
                    {
                        "MAE_keV": gp["pooled"]["MAE_keV"],
                        "residual_model_MAE_keV": residual["pooled"]["MAE_keV"],
                    },
                ),
                _ev(
                    "ablation_matrix.json",
                    "on the dev fixture the same family drops from hundreds of "
                    "keV to under 10 keV when its kernel is optimized, so the "
                    "frozen fixed-kernel configuration understates the family",
                    dev["hyperparameter_MAE_keV"],
                ),
                control_ev,
            ],
            confidence="HIGH",
            requires_protocol_change=False,
            notes=no_criterion_note,
        )
    )

    for model_id, payload in (("EZ-GP-DIRECT-v1", gp), ("EZ-SEMF-GP-RESIDUAL-v1", residual)):
        records.append(
            _record(
                failure_id=f"WO11-F-B002-{model_id}-overcoverage",
                benchmark_id="EZ-B002",
                protocol_version=protocol,
                model_id=model_id,
                criterion_id=B002_CRITERION_ID,
                observed_value=payload["pooled"]["coverage_90"],
                frozen_threshold=None,
                primary_class="UNCERTAINTY_OVERCOVERAGE",
                secondary_classes=["HYPERPARAMETER_SENSITIVITY"],
                evidence=[
                    _ev(
                        "uncertainty_diagnostics.json",
                        "standardized residuals have a spread far below one: "
                        "the reported sigma is orders of magnitude wider than "
                        "the realized error, so intervals are uninformative",
                        {
                            "coverage_90": payload["pooled"]["coverage_90"],
                            "std_z": payload["calibration"]["std_z"],
                        },
                    ),
                    control_ev,
                ],
                confidence="HIGH",
                requires_protocol_change=False,
                notes=no_criterion_note,
            )
        )
    return records


def build_failure_records(
    *,
    inventory: dict[str, Any],
    b003_aggregate: dict[str, Any],
    diagnostics: dict[str, Any],
    controls: dict[str, Any],
    ablations: dict[str, Any],
) -> dict[str, Any]:
    b003 = build_b003_records(
        inventory=inventory,
        b003_aggregate=b003_aggregate,
        diagnostics=diagnostics,
        controls=controls,
        ablations=ablations,
    )
    b002 = build_b002_records(
        inventory=inventory,
        diagnostics=diagnostics,
        controls=controls,
        ablations=ablations,
    )
    records = b003 + b002
    return {
        "work_order": "WO-11",
        "allowed_primary_classes": list(ALLOWED_PRIMARY_CLASSES),
        "classification_rule": (
            "One record per failed frozen check; EZ-B002-v1 records are "
            "characterization observations because that protocol froze no "
            "accuracy criterion. A class is asserted only where the sealed "
            "diagnostics, oracle controls, or dev ablations support it."
        ),
        "records": records,
        "primary_classes_by_benchmark": {
            "EZ-B002": sorted({r["primary_class"] for r in b002}),
            "EZ-B003": sorted({r["primary_class"] for r in b003}),
        },
    }


def write_failure_records(*, out_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
    payload = build_failure_records(**kwargs)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / FAILURE_RECORDS_FILE).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return payload
