"""WO-206 / EZ-B007 — the prospective sealed forecast.

WHY THIS IS THE FIRST SCORED WORK ORDER OF v2
---------------------------------------------
Every other benchmark on the ladder is retrospective, and WO-13 showed how hard
retrospective blindness is to establish: a target hidden from ElementZero is not
automatically blind to an imported physics table, and fit-set membership is
often unknowable. EZ-B007 sidesteps all of it by construction. No component of a
prediction can have been fitted to a measurement that does not exist yet.

It also cannot be manufactured later. AME/NUBASE is issued every four to five
years, AME2020 is still current, and the moment the next edition appears the
opportunity to have predicted it is gone forever. That is why the charter says
to file this first even though the dependency graph places it after WO-202.

WHAT IS SEALED
--------------
AME2020 marks estimated (non-experimental) values with ``#``. Those are the
AMDC's own extrapolations: nuclides whose masses are *not measured today*, and
therefore exactly the pool from which the next edition's new measurements will
be drawn. We predict all of them, with calibrated intervals, and commit the
hash before the answers exist.

All 1008 are predicted rather than a "most likely" subset. A selection rule
would be one more thing to argue about after the fact, and excluding a target is
indistinguishable, later, from having predicted it badly. Each target instead
carries its preregistered L1 distance bucket, so the report can stratify by how
far into extrapolation the prediction reached without any target being dropped.

TRAINING AND THE GROUND-TRUTH POLICY
------------------------------------
Training uses AME2020 measured (non-estimated) values only, per
``ez-gt-policy-v1``. An AMDC extrapolation is never trained on and never scored
as truth. The extrapolations are recorded separately, as a labelled reference
baseline, so that when the edition lands the report can answer the question that
actually matters — did the model beat the evaluators' own extrapolation? — while
keeping the target manifest identity-only, as the leakage firewall requires.

CALIBRATION IS QUALIFIED WHERE IT WILL BE USED
----------------------------------------------
Doctrine 7 gates scoring on EZ-B004. A random holdout of measured nuclides would
qualify sigma in the interpolation regime, which is not the regime this forecast
operates in: every target sits off the edge of the measured chart. So the gate is
evaluated on two preregistered splits and BOTH verdicts are sealed:

    random_holdout    seeded random measured subset   interpolation calibration
    frontier_holdout  sparsest-neighbourhood measured  extrapolation calibration

The frontier verdict is the one that governs claim eligibility, because it is
the one that resembles the task. Reporting only the flattering split is the
error EZ-B004 exists to prevent.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from elementzero.benchmark.distance import distance_bucket, l1_distance
from elementzero.data.observations import MassObservation
from elementzero.evidence.hashing import canonical_json, sha256_hex
from elementzero.models.blindness import (
    TIER_A,
    BackboneProvenance,
    combine_tiers,
    resolve_tier,
)
from elementzero.models.gp_calibrated import (
    DEFAULT_HYPERPARAMETER_SUBSAMPLE,
    CallableBackbone,
    GPResidualV2,
)
from elementzero.physics.semf import fit_semf, mass_excess_keV, semf_manifest
from elementzero.uq.calibration import (
    CalibrationReport,
    ConformalSigmaScaler,
    calibration_report,
)

EXPERIMENT_ID = "EZ-B007-v2"
BENCHMARK_ID = "EZ-B007"
FORECAST_POLICY_ID = "ez-b007-prospective-v1"
MODULE_VERSION = "ez-b007-v2.0.0"
SEAL_HASH_RULE = "ez-b007-seal-hash-v1"

# Preregistered calibration splits. Changing either requires a protocol version
# bump, exactly as with the EZ-B004 thresholds themselves.
RANDOM_HOLDOUT_FRACTION = 0.20
RANDOM_HOLDOUT_SEED = 0
FRONTIER_HOLDOUT_FRACTION = 0.20
FRONTIER_NEIGHBOURHOOD_L1 = 2

# The split whose verdict governs claim eligibility. The forecast predicts off
# the edge of the measured chart, so the frontier split is the one that
# resembles the task.
GOVERNING_SPLIT = "frontier_holdout"


def is_measured(obs: MassObservation) -> bool:
    """True when AME recorded an experimental value, not an extrapolation."""
    return not (obs.estimated_mass or obs.estimated_uncertainty)


def split_by_measurement_status(
    observations: Iterable[MassObservation],
) -> tuple[list[MassObservation], list[MassObservation]]:
    """Partition one edition into (measured, extrapolated).

    The extrapolated side is the EZ-B007 candidate pool: not measured today,
    therefore the pool the next edition's new measurements come from.
    """
    measured: list[MassObservation] = []
    extrapolated: list[MassObservation] = []
    for obs in observations:
        (measured if is_measured(obs) else extrapolated).append(obs)
    measured.sort(key=lambda o: (o.Z, o.N))
    extrapolated.sort(key=lambda o: (o.Z, o.N))
    return measured, extrapolated


def _neighbour_counts(
    lattice: Sequence[tuple[int, int]], radius: int = FRONTIER_NEIGHBOURHOOD_L1
) -> dict[tuple[int, int], int]:
    """How many other lattice sites lie within L1 `radius` of each site."""
    present = set(lattice)
    offsets = [
        (dz, dn)
        for dz in range(-radius, radius + 1)
        for dn in range(-radius, radius + 1)
        if (dz, dn) != (0, 0) and abs(dz) + abs(dn) <= radius
    ]
    return {
        site: sum(1 for dz, dn in offsets if (site[0] + dz, site[1] + dn) in present)
        for site in lattice
    }


def frontier_holdout_ids(
    measured: Sequence[MassObservation], fraction: float = FRONTIER_HOLDOUT_FRACTION
) -> tuple[str, ...]:
    """The sparsest-neighbourhood measured nuclides: the chart's own edge.

    Predicting these from the rest is the closest thing the measured data offers
    to the task EZ-B007 actually performs, which is predicting off the edge.
    Deterministic and seed-free: ranked by neighbour count ascending, ties broken
    by nuclide id.
    """
    lattice = [(o.Z, o.N) for o in measured]
    counts = _neighbour_counts(lattice)
    ranked = sorted(measured, key=lambda o: (counts[(o.Z, o.N)], o.nuclide_id))
    n_hold = max(1, int(round(fraction * len(ranked))))
    return tuple(sorted(o.nuclide_id for o in ranked[:n_hold]))


def random_holdout_ids(
    measured: Sequence[MassObservation],
    fraction: float = RANDOM_HOLDOUT_FRACTION,
    seed: int = RANDOM_HOLDOUT_SEED,
) -> tuple[str, ...]:
    """A seeded random measured subset: the interpolation-regime control."""
    ids = sorted(o.nuclide_id for o in measured)
    rng = np.random.default_rng(seed)
    n_hold = max(1, int(round(fraction * len(ids))))
    picked = rng.choice(len(ids), size=n_hold, replace=False)
    return tuple(sorted(ids[int(i)] for i in picked))


@dataclass(frozen=True)
class ForecastModel:
    """A SEMF-backed, learned-kernel GP residual, fitted to measured data only.

    The backbone is SEMF, which protocol v2.0.0 demotes to a permanent control:
    five parameters, roughly the 2.5 MeV class, no shell term. That is a real
    limitation and it is recorded rather than hidden. It is not a reason to delay
    the seal, because the evidential value of EZ-B007 comes from the forecast
    being prospective, not from the backbone being the best available. When a
    table-backed backbone lands under WO-202 it can be sealed as an additional
    prospective entrant against the same target set, and the two compared.
    """

    gp: GPResidualV2
    semf_coefficients: Any
    training_ids: tuple[str, ...]
    model_id: str

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "backbone_class": "T0_control",
            "backbone_note": (
                "SEMF is a permanent control under protocol v2.0.0 (five parameters, "
                "~2.5 MeV class, no shell term). Recorded, not hidden: the evidential "
                "value of a prospective seal is its blindness, not its backbone."
            ),
            "semf": semf_manifest(self.semf_coefficients),
            "residual": self.gp.manifest(),
            "n_training": len(self.training_ids),
        }


def fit_forecast_model(
    training: Sequence[MassObservation],
    model_id: str = "EZ-SEMF-GP-RESIDUAL-v2",
    hyperparameter_subsample: int | None = DEFAULT_HYPERPARAMETER_SUBSAMPLE,
) -> ForecastModel:
    """Fit SEMF, then the learned-kernel GP on its residuals. Measured data only.

    The full measured chart is ~2550 nuclides, where a direct hyperparameter
    optimization costs roughly twenty minutes per fit, and this work order needs
    three. The two-stage path in `GPResidualV2.fit` keeps theta learned from data
    while making that tractable; both sample sizes land in the manifest.
    """
    for obs in training:
        if not is_measured(obs):
            raise ValueError(
                f"{obs.nuclide_id} is an AME extrapolation; ez-gt-policy-v1 forbids "
                "training on estimated values"
            )
    coeffs = fit_semf(list(training))
    backbone = CallableBackbone(
        backbone_id="SEMF-LS",
        fn=lambda z, n: np.array(
            [mass_excess_keV(int(zz), int(nn), coeffs) for zz, nn in zip(z, n)],
            dtype=float,
        ),
        blindness_tier=TIER_A,
        independence_group="semf_control",
        fit_data_cutoff="AME2020",
    )
    gp = GPResidualV2(backbone=backbone, model_id=model_id).fit(
        [o.Z for o in training],
        [o.N for o in training],
        [o.mass_excess_keV for o in training],
        nuclide_ids=[o.nuclide_id for o in training],
        hyperparameter_subsample=hyperparameter_subsample,
    )
    return ForecastModel(
        gp=gp,
        semf_coefficients=coeffs,
        training_ids=tuple(sorted(o.nuclide_id for o in training)),
        model_id=model_id,
    )


def qualify_calibration(
    measured: Sequence[MassObservation], holdout_ids: Iterable[str]
) -> tuple[CalibrationReport, dict[str, Any]]:
    """Run EZ-B004 on one preregistered split, refitting on the complement.

    The model is refit without the holdout so the qualification is honest; the
    sealed forecast model is fitted separately on all measured data.
    """
    held = set(holdout_ids)
    train = [o for o in measured if o.nuclide_id not in held]
    test = [o for o in measured if o.nuclide_id in held]
    if not test:
        raise ValueError("empty calibration holdout")

    model = fit_forecast_model(train, model_id="EZ-B004-QUALIFICATION")
    predicted, sigma = model.gp.predict([o.Z for o in test], [o.N for o in test])
    truth = np.array([o.mass_excess_keV for o in test], dtype=float)
    report = calibration_report(truth, predicted, sigma)

    residual = truth - predicted
    detail = {
        "n_train": len(train),
        "n_holdout": len(test),
        "median_abs_error_keV": float(np.median(np.abs(residual))),
        "mae_keV": float(np.mean(np.abs(residual))),
        "rmse_keV": float(np.sqrt(np.mean(residual**2))),
        "median_sigma_keV": float(np.median(sigma)),
        "calibration": report.to_dict(),
    }
    return report, detail


def build_target_manifest(
    extrapolated: Sequence[MassObservation], measured: Sequence[MassObservation]
) -> list[dict[str, Any]]:
    """Identity-only target records, plus the preregistered distance bucket.

    Deliberately carries no mass value of any kind. `ALLOWED_TARGET_FIELDS`
    permits identity only, and the AMDC's own extrapolation for each target is
    recorded in a separate reference file so that it can never reach a feature
    vector by accident.
    """
    lattice = [(o.Z, o.N) for o in measured]
    rows: list[dict[str, Any]] = []
    for obs in extrapolated:
        d = min(l1_distance(obs.Z, obs.N, z, n) for z, n in lattice)
        rows.append(
            {
                "nuclide_id": obs.nuclide_id,
                "Z": obs.Z,
                "N": obs.N,
                "A": obs.A,
                "l1_distance_to_measured": int(d),
                "distance_bucket": distance_bucket(int(d)),
            }
        )
    rows.sort(key=lambda r: (r["Z"], r["N"]))
    return rows


def build_reference_extrapolations(
    extrapolated: Sequence[MassObservation],
) -> list[dict[str, Any]]:
    """The AMDC's own extrapolated values — a baseline, never a truth.

    Recorded so the future report can answer the question that decides whether
    this program adds anything: did the model beat the evaluators' extrapolation?
    Marked estimated on every row so no downstream reader can mistake it for a
    measurement, and kept out of the target manifest so it cannot be fed to a
    model as a feature.
    """
    return [
        {
            "nuclide_id": o.nuclide_id,
            "amdc_extrapolated_mass_excess_keV": o.mass_excess_keV,
            "amdc_extrapolated_uncertainty_keV": o.uncertainty_keV,
            "is_measurement": False,
            "record_status": o.source_record_status,
        }
        for o in sorted(extrapolated, key=lambda o: (o.Z, o.N))
    ]


def predict_targets(
    model: ForecastModel, targets: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The sealed predictions: mass excess and calibrated sigma per target."""
    z = [int(t["Z"]) for t in targets]
    n = [int(t["N"]) for t in targets]
    predicted, sigma = model.gp.predict(z, n)
    return [
        {
            "nuclide_id": t["nuclide_id"],
            "Z": t["Z"],
            "N": t["N"],
            "A": t["A"],
            "predicted_mass_excess_keV": float(p),
            "predictive_sigma_keV": float(s),
            "distance_bucket": t["distance_bucket"],
        }
        for t, p, s in zip(targets, predicted, sigma)
    ]


def resolve_forecast_tier(
    fit_edition: str = "AME2020", fit_year: int = 2020, next_edition_year: int = 2025
) -> tuple[str, dict[str, Any]]:
    """Blindness tier of a prospective forecast, derived rather than asserted.

    Every contributor was fitted to AME2020 measured values. The targets are, by
    construction, nuclides AME2020 did not measure, so `target_in_fit_set` is
    False as a fact about the data rather than an assumption. The truth edition
    does not exist yet, so its year strictly exceeds every fit cutoff.

    `next_edition_year` is a lower bound used only to resolve the tier; the seal
    does not claim to know when the edition lands. Any real release year is
    later than the fit year, so the tier is insensitive to the exact value.
    """
    semf = BackboneProvenance(
        backbone_id="SEMF-LS",
        independence_group="semf_control",
        fit_edition=fit_edition,
        fit_year=fit_year,
        fit_set_known=True,
    )
    residual = BackboneProvenance(
        backbone_id="GP-ARD-v2",
        independence_group="semf_control",
        fit_edition=fit_edition,
        fit_year=fit_year,
        fit_set_known=True,
    )
    tiers = [
        resolve_tier(p, truth_edition="AME_NEXT", truth_year=next_edition_year, target_in_fit_set=False)
        for p in (semf, residual)
    ]
    combined = combine_tiers(tiers)
    return combined, {
        "contributors": [p.to_dict() for p in (semf, residual)],
        "contributor_tiers": tiers,
        "combined_tier": combined,
        "rule": "combination inherits the worst contributor",
        "why_blind": (
            "no component can have been fitted to a measurement that does not exist "
            "yet; target_in_fit_set is False as a fact about AME2020, not an assumption"
        ),
    }


def seal_digest(payload: dict[str, Any]) -> str:
    """Content hash over the sealed forecast, excluding its own digest field."""
    body = {k: v for k, v in payload.items() if k != "seal_sha256"}
    return sha256_hex(canonical_json({"hash_rule": SEAL_HASH_RULE, "seal": body}))


def attempt_conformal_repair(
    measured: Sequence[MassObservation], holdout_ids: Iterable[str]
) -> dict[str, Any]:
    """Declare, attempt, and record a conformal sigma repair before sealing.

    Architecture section 5 permits a conformal repair provided it is declared
    pre-seal, fitted only on blind-eligible non-target data, and folded into
    model identity. This runs that attempt honestly:

      - the scaler is fitted on HALF the holdout and qualified on the other
        half, because fitting and qualifying on the same targets would be
        circular;
      - both the before and after verdicts are recorded;
      - the repair is ADOPTED only if it actually produces CALIBRATION_PASS.

    A repair that improves one diagnostic while breaking another is not a
    repair. A single multiplier can rescale a sigma; it cannot reshape a
    heavy-tailed error distribution, and matching the 90th percentile of |z|
    when the tail is heavy over-inflates sigma for the bulk, pushing the PIT
    further from uniform. That outcome is a finding about the model, and it is
    recorded rather than hidden behind the better-looking of the two numbers.
    """
    held = set(holdout_ids)
    train = [o for o in measured if o.nuclide_id not in held]
    test = [o for o in measured if o.nuclide_id in held]
    model = fit_forecast_model(train, model_id="EZ-B007-CONFORMAL-PROBE")
    predicted, sigma = model.gp.predict([o.Z for o in test], [o.N for o in test])
    truth = np.array([o.mass_excess_keV for o in test], dtype=float)

    order = sorted(range(len(test)), key=lambda i: test[i].nuclide_id)
    half = len(order) // 2
    fit_idx, qual_idx = order[:half], order[half:]
    if not fit_idx or not qual_idx:
        raise ValueError("holdout too small to split for a non-circular repair")

    scaler = ConformalSigmaScaler(level=0.90).fit(
        truth[fit_idx], predicted[fit_idx], sigma[fit_idx]
    )
    before = calibration_report(truth[qual_idx], predicted[qual_idx], sigma[qual_idx])
    result: dict[str, Any] = {
        "declared_pre_seal": True,
        "n_repair_fit": len(fit_idx),
        "n_repair_qualification": len(qual_idx),
        "disjoint": True,
        "scaler": scaler.manifest(),
        "before": before.to_dict(),
        "after": None,
        "adopted": False,
        "reason": "",
    }
    if not scaler.fitted:
        result["reason"] = scaler.refused_reason or "scaler refused to fit"
        return result

    after = calibration_report(
        truth[qual_idx], predicted[qual_idx], scaler.apply(sigma[qual_idx])
    )
    result["after"] = after.to_dict()
    if after.verdict == "CALIBRATION_PASS":
        result["adopted"] = True
        result["reason"] = "conformal repair achieved CALIBRATION_PASS on a disjoint split"
    else:
        result["adopted"] = False
        result["reason"] = (
            f"repair rescaled dispersion (std_z {before.std_z:.3f} -> {after.std_z:.3f}) "
            f"but the split still fails ({'; '.join(after.failures)}). A multiplier "
            "cannot reshape a heavy-tailed error distribution, so the repair is "
            "recorded and NOT applied; the sealed sigmas are the raw model's."
        )
    return result
