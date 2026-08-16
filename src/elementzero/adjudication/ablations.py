"""WO-11.8 / WO-11.9 — development-only ablations on NEW fixtures.

Nothing in this module touches EZ-B002-v1 or EZ-B003-v1: the frozen v1 scoring
truth may not be used to retune anything, so ablations run on two *new*
development fixtures with different surfaces, different withheld geometry, and
different injected shell structure:

    EZ-B002-dev   a fresh synthetic chart (new ripple phases, new SEMF-like
                  coefficients, new valley drift) with a rectangle holdout that
                  is not one of the v1 regions.

    EZ-B003-dev   a fresh synthetic shell chart with the injected closures
                  moved (N0 = 82, Z0 = 50 instead of the v1 N0 = 50, Z0 = 28)
                  and different gap sizes.

Two preregistered sweeps run on those fixtures:

    feature ablation (WO-11.8)    Z,N,A -> +parity -> +isospin asymmetry ->
                                  +simple local coordinate features. Shell dev
                                  runs stay behind the discovery firewall:
                                  magic-number labels, distances to known magic
                                  numbers, and explicit closure features remain
                                  forbidden.

    hyperparameter sensitivity    a fixed, one-at-a-time grid around the frozen
    (WO-11.9)                     GP configuration: kernel length scale, noise
                                  level, normalization, optimizer restarts, and
                                  residual-vs-direct formulation. No search
                                  beyond the preregistered grid.

Every result row is a development diagnostic. None of it is benchmark
evidence, and none of it may be quoted as a v1 outcome.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

from elementzero.benchmark.b003_prepare import (
    DISCOVERY_FEATURE_DENY_PATTERNS,
    DISCOVERY_FEATURE_DENYLIST,
    normalize_feature_name,
)
from elementzero.benchmark.regions import Region
from elementzero.benchmark.shell_metrics import peak_ranking, sign_of
from elementzero.data.amdc import load_edition
from elementzero.data.amdc.ame2020 import EDITION as AME2020_SPEC
from elementzero.data.amdc.common import format_ame_line
from elementzero.data.observations import MassObservation
from elementzero.errors import LeakageError
from elementzero.evidence.hashing import canonical_json, sha256_file
from elementzero.physics.conversion import (
    binding_energy_MeV,
    mass_excess_keV_from_binding,
)
from elementzero.physics.semf import fit_semf, mass_excess_keV, pairing_sign

ABLATION_MATRIX_FILE = "ablation_matrix.json"

EDITION_ID = "AME2020"

DEV_RULE = (
    "Development diagnostics only. These fixtures use different synthetic "
    "surfaces and different withheld geometry from EZ-B002-v1/EZ-B003-v1; no "
    "frozen v1 truth entered any fit, feature choice, or hyperparameter "
    "choice, and no row here may be quoted as a v1 benchmark result."
)

# --------------------------------------------------------------------------- #
# Dev fixture surfaces (deterministic; deliberately not the v1 surfaces)      #
# --------------------------------------------------------------------------- #

B002_DEV_FIXTURE_ID = "EZ-B002-dev"
B003_DEV_FIXTURE_ID = "EZ-B003-dev"

# Dev SEMF-like coefficients: same functional family as every synthetic chart,
# different values than the v1 fixtures on purpose.
DEV_COEFFS = {"a_v": 15.6, "a_s": 17.9, "a_c": 0.70, "a_a": 23.5, "a_p": 11.5}

B002_DEV_Z_MIN, B002_DEV_Z_MAX = 8, 50
B002_DEV_ESTIMATED_MODULUS = 43

# The dev holdout rectangle. Not one of the v1 regions (rect-Z14-17-N15-19,
# rect-Z33-36-N42-46, rect-Z50-53-N70-74).
B002_DEV_REGION = {"region_type": "rectangle", "z_min": 20, "z_max": 23, "n_min": 24, "n_max": 27}
B002_DEV_REGION_ID = "dev-rect-Z20-23-N24-27"

B003_DEV_Z_MIN, B003_DEV_Z_MAX = 40, 60
B003_DEV_N_MIN, B003_DEV_N_MAX = 70, 94
B003_DEV_ESTIMATED_MODULUS = 47

# Injected closures for the dev shell chart: moved off the v1 pair (N0 = 50,
# Z0 = 28) onto other members of the availability set, with new gap sizes.
B003_DEV_NEUTRON_CLOSURE = 82
B003_DEV_PROTON_CLOSURE = 50
B003_DEV_NEUTRON_GAP_MEV = 1.2
B003_DEV_PROTON_GAP_MEV = 1.0
B003_DEV_MASK_HALF_WIDTH = 1
B003_DEV_PEAK_WINDOW = 6
B003_DEV_CHALLENGE_ID = "dev-neutron-N82"


def _dev_ripple_MeV(z: int, n: int) -> float:
    """Smooth non-SEMF ripple with phases the v1 fixtures do not use."""
    return (
        0.55 * math.cos(0.47 * n + 1.30)
        + 0.40 * math.cos(0.33 * z + 0.70)
        + 0.30 * math.cos(0.13 * (n - z) + 0.35)
    )


def _dev_binding_MeV(z: int, n: int) -> float:
    a = float(z + n)
    return (
        DEV_COEFFS["a_v"] * a
        - DEV_COEFFS["a_s"] * a ** (2.0 / 3.0)
        - DEV_COEFFS["a_c"] * z * (z - 1) / a ** (1.0 / 3.0)
        - DEV_COEFFS["a_a"] * (n - z) ** 2 / a
        + DEV_COEFFS["a_p"] * pairing_sign(z, n) / a**0.5
    )


def _dev_shell_term_MeV(z: int, n: int) -> float:
    return -B003_DEV_NEUTRON_GAP_MEV * max(0, n - B003_DEV_NEUTRON_CLOSURE) - (
        B003_DEV_PROTON_GAP_MEV * max(0, z - B003_DEV_PROTON_CLOSURE)
    )


def _write_chart(path: Path, rows: list[tuple[int, int, float, float, bool]]) -> Path:
    lines = ["   AME synthetic development chart for ElementZero WO-11\n"]
    for z, n, mass_excess, unc, estimated in rows:
        lines.append(
            format_ame_line(
                n=n,
                z=z,
                a=z + n,
                el="X",
                mass_excess_keV=mass_excess,
                uncertainty_keV=unc,
                estimated=estimated,
                spec=AME2020_SPEC,
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_b002_dev_chart(path: str | Path) -> Path:
    rows = []
    for z in range(B002_DEV_Z_MIN, B002_DEV_Z_MAX + 1):
        center = round(z + 0.009 * z * z)
        half_width = 3 + z // 18
        for n in range(center - half_width, center + half_width + 1):
            if n < 1:
                continue
            binding = _dev_binding_MeV(z, n) + _dev_ripple_MeV(z, n)
            rows.append(
                (
                    z,
                    n,
                    mass_excess_keV_from_binding(z=z, n=n, binding_MeV=binding),
                    13.0 + (z % 3),
                    (z + n) % B002_DEV_ESTIMATED_MODULUS == 0,
                )
            )
    return _write_chart(Path(path), rows)


def write_b003_dev_chart(path: str | Path) -> Path:
    rows = []
    for z in range(B003_DEV_Z_MIN, B003_DEV_Z_MAX + 1):
        for n in range(B003_DEV_N_MIN, B003_DEV_N_MAX + 1):
            binding = _dev_binding_MeV(z, n) + _dev_ripple_MeV(z, n) + _dev_shell_term_MeV(z, n)
            rows.append(
                (
                    z,
                    n,
                    mass_excess_keV_from_binding(z=z, n=n, binding_MeV=binding),
                    12.0 + (z % 2),
                    (z + n) % B003_DEV_ESTIMATED_MODULUS == 0,
                )
            )
    return _write_chart(Path(path), rows)


# --------------------------------------------------------------------------- #
# Feature policies (WO-11.8)                                                  #
# --------------------------------------------------------------------------- #

# The discovery firewall keeps applying to every shell dev run: the extended
# sets below add primitive parity/coordinate features and nothing that names,
# labels, or measures distance to a known shell closure.
DEV_FEATURE_POLICIES: dict[str, tuple[str, ...]] = {
    "dev-zna-v1": ("Z", "N", "A"),
    "dev-zna-parity-v1": ("Z", "N", "A", "z_parity", "n_parity", "a_parity"),
    "dev-zna-parity-isospin-v1": (
        "Z",
        "N",
        "A",
        "z_parity",
        "n_parity",
        "a_parity",
        "isospin_asymmetry",
    ),
    "dev-zna-parity-isospin-local-v1": (
        "Z",
        "N",
        "A",
        "z_parity",
        "n_parity",
        "a_parity",
        "isospin_asymmetry",
        "n_minus_z",
        "sqrt_a",
        "inv_cbrt_a",
    ),
}

_FEATURE_BUILDERS = {
    "Z": lambda z, n: float(z),
    "N": lambda z, n: float(n),
    "A": lambda z, n: float(z + n),
    "z_parity": lambda z, n: float(z % 2),
    "n_parity": lambda z, n: float(n % 2),
    "a_parity": lambda z, n: float((z + n) % 2),
    "isospin_asymmetry": lambda z, n: (n - z) / (z + n),
    "n_minus_z": lambda z, n: float(n - z),
    "sqrt_a": lambda z, n: math.sqrt(z + n),
    "inv_cbrt_a": lambda z, n: (z + n) ** (-1.0 / 3.0),
}


def assert_dev_shell_features(features: tuple[str, ...]) -> None:
    """The dev firewall: the EZ-B003 denylist with a wider primitive whitelist.

    WO-11.8 widens the *allowed* primitives (parity, isospin, local
    coordinates) but the denylist is non-negotiable: magic-number labels,
    distances to known magic numbers, and explicit closure features stay
    forbidden. The allowed-set shortcut of the frozen firewall is therefore
    skipped and the denied tokens/patterns are applied to every name.
    """
    if not features:
        raise LeakageError("WO-11 dev shell feature set is empty")
    bad: dict[str, str] = {}
    for name in features:
        normalized = normalize_feature_name(name)
        for token in DISCOVERY_FEATURE_DENYLIST:
            if normalize_feature_name(token) in normalized:
                bad[name] = f"contains the denied token {token!r}"
                break
        else:
            for pattern, reason in DISCOVERY_FEATURE_DENY_PATTERNS:
                if re.search(pattern, normalized):
                    bad[name] = reason
                    break
    if bad:
        detail = "; ".join(f"{name!r} {reason}" for name, reason in sorted(bad.items()))
        raise LeakageError(f"WO-11 dev shell feature set violates the firewall: {detail}")


# --------------------------------------------------------------------------- #
# Hyperparameter grid (WO-11.9) — fixed, preregistered, one-at-a-time         #
# --------------------------------------------------------------------------- #

HP_BASELINE = "hp-baseline"

# Every variant changes exactly one knob relative to the frozen v1 GP
# configuration (RBF length_scale 8.0, white noise 1.0e4, normalize_y True,
# optimizer None, SEMF-residual formulation).
HYPERPARAMETER_GRID: dict[str, dict[str, Any]] = {
    HP_BASELINE: {},
    "hp-length-scale-2": {"length_scale": 2.0},
    "hp-length-scale-32": {"length_scale": 32.0},
    "hp-noise-1e2": {"noise_level": 1.0e2},
    "hp-noise-1e6": {"noise_level": 1.0e6},
    "hp-no-normalize-y": {"normalize_y": False},
    "hp-optimized-restarts-2": {"optimize": True, "n_restarts": 2},
    "hp-direct-formulation": {"formulation": "direct"},
}

GRID_RULE = (
    "ez-wo11-hp-grid-v1: fixed one-at-a-time grid around the frozen GP "
    "configuration. No wider search is run and no configuration is promoted; "
    "the grid only measures how fragile the family is to its own knobs."
)


@dataclass
class DevGPModel:
    """Development GP used for both sweeps. Never registered as a benchmark model."""

    model_id: str
    features: tuple[str, ...]
    length_scale: float = 8.0
    noise_level: float = 1.0e4
    normalize_y: bool = True
    optimize: bool = False
    n_restarts: int = 0
    formulation: str = "semf_residual"  # or "direct"

    def __post_init__(self) -> None:
        unknown = [f for f in self.features if f not in _FEATURE_BUILDERS]
        if unknown:
            raise ValueError(f"unknown dev features: {unknown}")
        self._coeffs = None
        self._gp = None
        self._mean = None
        self._scale = None

    def _raw_features(self, z: int, n: int) -> np.ndarray:
        return np.array([_FEATURE_BUILDERS[f](z, n) for f in self.features], dtype=float)

    def _design(self, pairs: list[tuple[int, int]]) -> np.ndarray:
        x = np.vstack([self._raw_features(z, n) for z, n in pairs])
        if self._mean is None:
            self._mean = x.mean(axis=0)
            scale = x.std(axis=0)
            scale[scale == 0.0] = 1.0
            self._scale = scale
        return (x - self._mean) / self._scale

    def fit(self, observations: list[MassObservation]) -> None:
        pairs = [(o.Z, o.N) for o in observations]
        y = np.array([o.mass_excess_keV for o in observations], dtype=float)
        if self.formulation == "semf_residual":
            self._coeffs = fit_semf(observations)
            physics = np.array([mass_excess_keV(z, n, self._coeffs) for z, n in pairs])
            y = y - physics
        if self.optimize:
            kernel = ConstantKernel(1.0e6) * RBF(length_scale=self.length_scale) + WhiteKernel(
                noise_level=self.noise_level
            )
            self._gp = GaussianProcessRegressor(
                kernel=kernel,
                n_restarts_optimizer=self.n_restarts,
                normalize_y=self.normalize_y,
                random_state=0,
            )
        else:
            kernel = ConstantKernel(1.0e6, constant_value_bounds="fixed") * RBF(
                length_scale=self.length_scale, length_scale_bounds="fixed"
            ) + WhiteKernel(noise_level=self.noise_level, noise_level_bounds="fixed")
            self._gp = GaussianProcessRegressor(
                kernel=kernel, optimizer=None, normalize_y=self.normalize_y, random_state=0
            )
        self._gp.fit(self._design(pairs), y)

    def predict(self, z: int, n: int) -> tuple[float, float]:
        x = (self._raw_features(z, n) - self._mean) / self._scale
        mean, std = self._gp.predict(x.reshape(1, -1), return_std=True)
        mu = float(mean[0])
        if self.formulation == "semf_residual":
            mu += mass_excess_keV(z, n, self._coeffs)
        return mu, max(float(std[0]), 1.0e-9)


# --------------------------------------------------------------------------- #
# Dev evaluation                                                              #
# --------------------------------------------------------------------------- #


def _eligible(source: Path) -> list[MassObservation]:
    return sorted(
        (o for o in load_edition(EDITION_ID, str(source)) if o.ground_truth_eligible),
        key=lambda o: o.nuclide_id,
    )


def _mass_metrics(rows: list[dict[str, float]]) -> dict[str, Any]:
    predictions = [r["prediction_keV"] for r in rows]
    truth = [r["truth_keV"] for r in rows]
    stds = [r["std_keV"] for r in rows]
    errors = [p - t for p, t in zip(predictions, truth)]
    z90, z95 = 1.6448536269514722, 1.959963984540054
    cov90 = sum(
        1 for p, t, s in zip(predictions, truth, stds) if abs(t - p) <= z90 * s
    ) / len(rows)
    cov95 = sum(
        1 for p, t, s in zip(predictions, truth, stds) if abs(t - p) <= z95 * s
    ) / len(rows)
    nlpd_terms = [
        0.5 * math.log(2.0 * math.pi * s * s) + 0.5 * ((t - p) / s) ** 2
        for p, t, s in zip(predictions, truth, stds)
    ]
    return {
        "n": len(rows),
        "MAE_keV": statistics.fmean(abs(e) for e in errors),
        "RMSE_keV": math.sqrt(statistics.fmean(e * e for e in errors)),
        "NLPD": statistics.fmean(nlpd_terms),
        "coverage_90": cov90,
        "coverage_95": cov95,
    }


def evaluate_b002_dev(model: DevGPModel, observations: list[MassObservation]) -> dict[str, Any]:
    """Fit outside the dev rectangle, score inside it. Dev-only mass metrics."""
    region = Region(**B002_DEV_REGION)
    training = [o for o in observations if not region.contains(o.Z, o.N)]
    targets = [o for o in observations if region.contains(o.Z, o.N)]
    model.fit(training)
    rows = []
    for o in targets:
        mu, sigma = model.predict(o.Z, o.N)
        rows.append({"prediction_keV": mu, "truth_keV": o.mass_excess_keV, "std_keV": sigma})
    return {**_mass_metrics(rows), "shell_metric": None, "n_training": len(training)}


def _hybrid_binding(
    z: int,
    coordinate: int,
    *,
    predictions: dict[tuple[int, int], float],
    truth: dict[tuple[int, int], float],
) -> float | None:
    """Binding energy from the sealed-style hybrid: prediction inside the mask,
    training truth outside it."""
    key = (z, coordinate)
    if key in predictions:
        mass = predictions[key]
    elif key in truth:
        mass = truth[key]
    else:
        return None
    return binding_energy_MeV(z=z, n=coordinate, mass_excess_keV=mass)


def evaluate_b003_dev(model: DevGPModel, observations: list[MassObservation]) -> dict[str, Any]:
    """Fit outside the dev neutron-closure mask, score masses and localization."""
    closure = B003_DEV_NEUTRON_CLOSURE
    half = B003_DEV_MASK_HALF_WIDTH
    masked = {
        (o.Z, o.N)
        for o in observations
        if abs(o.N - closure) <= half
    }
    training = [o for o in observations if (o.Z, o.N) not in masked]
    targets = [o for o in observations if (o.Z, o.N) in masked]
    model.fit(training)
    truth = {(o.Z, o.N): o.mass_excess_keV for o in observations}
    predictions: dict[tuple[int, int], float] = {}
    mass_rows = []
    for o in targets:
        mu, sigma = model.predict(o.Z, o.N)
        predictions[(o.Z, o.N)] = mu
        mass_rows.append({"prediction_keV": mu, "truth_keV": o.mass_excess_keV, "std_keV": sigma})

    def delta2n(z: int, coordinate: int, table: str) -> float | None:
        values = []
        for offset, weight in ((0, 2.0), (-2, -1.0), (2, -1.0)):
            n_val = coordinate + offset
            if table == "hybrid":
                binding = _hybrid_binding(z, n_val, predictions=predictions, truth=truth)
            else:
                mass = truth.get((z, n_val))
                binding = (
                    None
                    if mass is None
                    else binding_energy_MeV(z=z, n=n_val, mass_excess_keV=mass)
                )
            if binding is None:
                return None
            values.append(weight * binding)
        return sum(values)

    chains = sorted({o.Z for o in targets})
    n_chains = 0
    sign_hits = 0
    rank_1_hits = 0
    top_3_hits = 0
    for z in chains:
        candidates = {}
        true_candidates = {}
        for coordinate in range(closure - B003_DEV_PEAK_WINDOW, closure + B003_DEV_PEAK_WINDOW + 1):
            if (coordinate - closure) % 2 != 0:
                continue
            predicted = delta2n(z, coordinate, "hybrid")
            true_value = delta2n(z, coordinate, "truth")
            if predicted is not None and true_value is not None:
                candidates[coordinate] = predicted
                true_candidates[coordinate] = true_value
        if closure not in candidates or len(candidates) < 3:
            continue
        n_chains += 1
        ranking = peak_ranking(candidates, closure=closure)
        if ranking["local_peak_rank"] == 1:
            rank_1_hits += 1
        if ranking["in_top_k"]:
            top_3_hits += 1
        predicted_sign = sign_of(candidates[closure])
        true_sign = sign_of(true_candidates[closure])
        if predicted_sign is not None and predicted_sign == true_sign:
            sign_hits += 1
    return {
        **_mass_metrics(mass_rows),
        "shell_metric": rank_1_hits / n_chains if n_chains else None,
        "sign_recovered_fraction": sign_hits / n_chains if n_chains else None,
        "top_3_fraction": top_3_hits / n_chains if n_chains else None,
        "n_evaluated_chains": n_chains,
        "n_training": len(training),
    }


# --------------------------------------------------------------------------- #
# The ablation matrix                                                         #
# --------------------------------------------------------------------------- #

DEV_MODEL_ID = "EZ-DEV-GP-v1"


def _model_for(policy: tuple[str, ...], variant: dict[str, Any]) -> DevGPModel:
    return DevGPModel(model_id=DEV_MODEL_ID, features=policy, **variant)


def build_ablation_matrix(*, workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    b002_chart = write_b002_dev_chart(workspace / "ez-b002-dev-chart.mas20")
    b003_chart = write_b003_dev_chart(workspace / "ez-b003-dev-chart.mas20")
    b002_observations = _eligible(b002_chart)
    b003_observations = _eligible(b003_chart)

    fixtures = {
        B002_DEV_FIXTURE_ID: {
            "chart_sha256": sha256_file(b002_chart),
            "region_id": B002_DEV_REGION_ID,
            "region": dict(B002_DEV_REGION),
            "n_eligible": len(b002_observations),
            "differs_from_v1": (
                "new SEMF-like coefficients, new ripple phases, new valley "
                "drift, and a holdout rectangle that is not a v1 region"
            ),
        },
        B003_DEV_FIXTURE_ID: {
            "chart_sha256": sha256_file(b003_chart),
            "challenge_id": B003_DEV_CHALLENGE_ID,
            "neutron_closure": B003_DEV_NEUTRON_CLOSURE,
            "proton_closure": B003_DEV_PROTON_CLOSURE,
            "neutron_gap_MeV": B003_DEV_NEUTRON_GAP_MEV,
            "proton_gap_MeV": B003_DEV_PROTON_GAP_MEV,
            "n_eligible": len(b003_observations),
            "differs_from_v1": (
                "injected closures moved from (N0=50, Z0=28) to (N0=82, Z0=50) "
                "with different gap sizes on a different lattice window"
            ),
        },
    }

    rows: list[dict[str, Any]] = []

    def run_case(
        fixture_id: str,
        policy_id: str,
        variant_id: str,
        notes: str,
    ) -> None:
        policy = DEV_FEATURE_POLICIES[policy_id]
        if fixture_id == B003_DEV_FIXTURE_ID:
            assert_dev_shell_features(policy)
        model = _model_for(policy, HYPERPARAMETER_GRID[variant_id])
        if fixture_id == B002_DEV_FIXTURE_ID:
            outcome = evaluate_b002_dev(model, b002_observations)
        else:
            outcome = evaluate_b003_dev(model, b003_observations)
        rows.append(
            {
                "model_id": DEV_MODEL_ID,
                "dev_fixture_id": fixture_id,
                "feature_policy_id": policy_id,
                "hyperparameter_variant": variant_id,
                "MAE_keV": outcome["MAE_keV"],
                "RMSE_keV": outcome["RMSE_keV"],
                "NLPD": outcome["NLPD"],
                "coverage_90": outcome["coverage_90"],
                "shell_metric": outcome["shell_metric"],
                "sign_recovered_fraction": outcome.get("sign_recovered_fraction"),
                "top_3_fraction": outcome.get("top_3_fraction"),
                "n_evaluated_chains": outcome.get("n_evaluated_chains"),
                "n_targets": outcome["n"],
                "notes": notes,
            }
        )

    for fixture_id in (B002_DEV_FIXTURE_ID, B003_DEV_FIXTURE_ID):
        for policy_id in DEV_FEATURE_POLICIES:
            run_case(fixture_id, policy_id, HP_BASELINE, "feature ablation (WO-11.8)")
        for variant_id in HYPERPARAMETER_GRID:
            if variant_id == HP_BASELINE:
                continue  # already present as the feature-ablation baseline row
            run_case(
                fixture_id, "dev-zna-v1", variant_id, "hyperparameter sensitivity (WO-11.9)"
            )

    return {
        "work_order": "WO-11",
        "rule": DEV_RULE,
        "grid_rule": GRID_RULE,
        "fixtures": fixtures,
        "feature_policies": {k: list(v) for k, v in DEV_FEATURE_POLICIES.items()},
        "hyperparameter_grid": {k: dict(v) for k, v in HYPERPARAMETER_GRID.items()},
        "firewall_rule": (
            "Shell dev runs keep the ez-b003 discovery denylist: magic-number "
            "labels, distances to known magic numbers, and explicit closure "
            "features stay forbidden in every policy above."
        ),
        "rows": rows,
        "summary": summarize_matrix(rows),
    }


def summarize_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Computed readouts; descriptive only, nothing is promoted or tuned."""

    def rows_for(fixture: str, note_prefix: str) -> list[dict[str, Any]]:
        return [
            r
            for r in rows
            if r["dev_fixture_id"] == fixture and r["notes"].startswith(note_prefix)
        ]

    def baseline_for(fixture: str) -> dict[str, Any]:
        return next(
            r
            for r in rows
            if r["dev_fixture_id"] == fixture
            and r["feature_policy_id"] == "dev-zna-v1"
            and r["hyperparameter_variant"] == HP_BASELINE
        )

    summary: dict[str, Any] = {}
    for fixture in (B002_DEV_FIXTURE_ID, B003_DEV_FIXTURE_ID):
        base = baseline_for(fixture)
        features = rows_for(fixture, "feature ablation")
        hypers = rows_for(fixture, "hyperparameter sensitivity") + [base]
        feature_maes = {r["feature_policy_id"]: r["MAE_keV"] for r in features}
        hyper_maes = {r["hyperparameter_variant"]: r["MAE_keV"] for r in hypers}
        entry: dict[str, Any] = {
            "baseline_MAE_keV": base["MAE_keV"],
            "feature_policy_MAE_keV": feature_maes,
            "max_feature_MAE_change_fraction": max(
                abs(m - base["MAE_keV"]) / base["MAE_keV"] for m in feature_maes.values()
            ),
            "hyperparameter_MAE_keV": hyper_maes,
            "max_hyperparameter_MAE_change_fraction": max(
                abs(m - base["MAE_keV"]) / base["MAE_keV"] for m in hyper_maes.values()
            ),
        }
        if fixture == B003_DEV_FIXTURE_ID:
            entry["feature_policy_shell_metric"] = {
                r["feature_policy_id"]: r["shell_metric"] for r in features
            }
            entry["hyperparameter_shell_metric"] = {
                r["hyperparameter_variant"]: r["shell_metric"] for r in hypers
            }
        summary[fixture] = entry
    return summary


def write_ablation_matrix(*, out_dir: str | Path, workspace_dir: str | Path) -> dict[str, Any]:
    payload = build_ablation_matrix(workspace_dir=workspace_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / ABLATION_MATRIX_FILE).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return payload
