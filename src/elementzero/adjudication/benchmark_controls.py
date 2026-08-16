"""WO-11.7 — benchmark difficulty controls (synthetic oracle families).

The v1 baselines failed EZ-B003 and looked weak on parts of EZ-B002. Before any
statement about models is allowed, the benchmarks themselves are put on trial
with controlled synthetic predictors run through the *frozen* seal/score
mechanics — same regions, same masks, same metrics, same criterion:

    Control A  exact oracle          predicts the synthetic surface exactly.
                                     If the frozen mechanics do not give it a
                                     clean pass, the benchmark or metric
                                     implementation is defective.

    Control B  noisy oracle          exact surface plus preregistered,
                                     deterministic noise. Documents how far a
                                     model may drift from the truth surface
                                     before the frozen criterion flips
                                     (threshold sensitivity).

    Control C  weak smooth model     a deliberately weak global quadratic
                                     surface. Expected to fail; a criterion a
                                     weak smooth model can pass is too weak.

    Control D  shell-aware oracle    Control A on the EZ-B003 shell chart. It
                                     may know the synthetic generating
                                     function: this is a BENCHMARK VALIDITY
                                     CONTROL, never a discovery-model result.

Oracles read the frozen synthetic snapshot itself — on a synthetic chart the
committed table *is* the generating function evaluated on the lattice. Every
control is labelled ``CONTROL_ONLY`` and none of them is, or may ever be quoted
as, a scientific model result.

No frozen module changes: control models are injected by swapping the
``build_model`` reference inside the predict modules for the duration of a
control run, then restoring it. The v1 replay tests prove the frozen path is
byte-identical when the injection is not active.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import statistics as _statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from elementzero.adjudication.artifact_audit import BASELINE_COMMIT
from elementzero.data.amdc import load_edition
from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.evidence.hashing import canonical_json
from elementzero.evidence.ledger import read_json
from elementzero.models.protocol import (
    MIN_PREDICTIVE_STD_KEV,
    Prediction,
    gaussian_intervals,
)

BENCHMARK_CONTROLS_FILE = "benchmark_controls.json"

CONTROL_EXACT_ORACLE = "EZ-CONTROL-EXACT-ORACLE-v1"
CONTROL_NOISY_ORACLE_SMALL = "EZ-CONTROL-NOISY-ORACLE-200KEV-v1"
CONTROL_NOISY_ORACLE_LARGE = "EZ-CONTROL-NOISY-ORACLE-2MEV-v1"
CONTROL_WEAK_SMOOTH = "EZ-CONTROL-WEAK-QUADRATIC-v1"
CONTROL_SHELL_AWARE_ORACLE = "EZ-CONTROL-SHELL-AWARE-ORACLE-v1"

CONTROL_ROLE = "CONTROL_ONLY"

# Preregistered noise scales (keV). Chosen once, before any control was run,
# from the injected feature sizes of the shell chart: the small scale is far
# below the +2.4/+3.0 MeV indicator spikes, the large scale is comparable to
# them. Neither may be tuned after seeing a control outcome.
NOISE_SMALL_KEV = 200.0
NOISE_LARGE_KEV = 2000.0
NOISE_SALT = "ez-wo11-noise-v1"

# Deterministic timestamp for control workspaces: controls are adjudication
# reruns of frozen mechanics, and their outputs must be byte-reproducible.
CONTROL_CREATED_AT = "2026-08-16T00:00:00Z"

EXACT_ORACLE_MAX_MAE_KEV = 1.0e-9

CONTROL_SCOPE_RULE = (
    "Synthetic benchmark validity controls only. An oracle here knows the "
    "synthetic generating function by construction; nothing it does is a "
    "model result, a discovery result, or evidence about real nuclei."
)


def _gaussian_from_id(nuclide_id: str, *, salt: str) -> float:
    """Deterministic standard-normal draw addressed by nuclide identity."""
    digest = hashlib.sha256(f"{salt}:{nuclide_id}".encode()).digest()
    u = (int.from_bytes(digest[:8], "big") + 0.5) / 2.0**64
    return _statistics.NormalDist().inv_cdf(u)


# --------------------------------------------------------------------------- #
# Control models                                                              #
# --------------------------------------------------------------------------- #


@dataclass
class SyntheticTruthOracle:
    """Controls A, B, and D: the frozen synthetic surface, optionally noisy."""

    model_id: str
    truth_keV: Mapping[str, float] = field(repr=False)
    noise_keV: float = 0.0
    control_class: str = "A_EXACT_ORACLE"
    uncertainty_method: str = "preregistered control sigma"
    _fitted_ids: tuple[str, ...] = ()

    def fit(self, observations: Sequence[MassObservation]) -> None:
        # A validity control does not learn; recording the training identities
        # keeps the frozen training-digest checks meaningful.
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))

    def _sigma(self) -> float:
        return max(self.noise_keV, 1.0, MIN_PREDICTIVE_STD_KEV)

    def predict(self, nuclide: NuclideIdentity) -> Prediction:
        mu = float(self.truth_keV[nuclide.nuclide_id])
        if self.noise_keV > 0.0:
            mu += self.noise_keV * _gaussian_from_id(nuclide.nuclide_id, salt=NOISE_SALT)
        sigma = self._sigma()
        return Prediction(
            nuclide=nuclide,
            mass_excess_keV=mu,
            intervals=gaussian_intervals(mu, sigma),
            model_id=self.model_id,
            std_keV=sigma,
            uncertainty_method=self.uncertainty_method,
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "features": ["Z", "N", "A"],
            "control_class": self.control_class,
            "control_role": CONTROL_ROLE,
            "control_scope_rule": CONTROL_SCOPE_RULE,
            "noise_keV": self.noise_keV,
            "noise_salt": NOISE_SALT if self.noise_keV > 0.0 else None,
            "predictive_distribution": "gaussian",
            "uncertainty_method": self.uncertainty_method,
            "fitted_nuclide_ids": list(self._fitted_ids),
        }


@dataclass
class WeakSmoothControlModel:
    """Control C: global quadratic surface in (Z, N), deliberately weak."""

    model_id: str = CONTROL_WEAK_SMOOTH
    coefficients: list[float] | None = None
    residual_std_keV: float = 1000.0
    uncertainty_method: str = "global training residual standard deviation"
    _fitted_ids: tuple[str, ...] = ()

    @staticmethod
    def _design(z: float, n: float) -> list[float]:
        return [1.0, z, n, z * z, n * n, z * n]

    def fit(self, observations: Sequence[MassObservation]) -> None:
        x = np.array([self._design(o.Z, o.N) for o in observations], dtype=float)
        y = np.array([o.mass_excess_keV for o in observations], dtype=float)
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        self.coefficients = [float(b) for b in beta]
        residuals = y - x @ beta
        self.residual_std_keV = max(float(np.std(residuals)), 1.0)
        self._fitted_ids = tuple(sorted(o.nuclide_id for o in observations))

    def predict(self, nuclide: NuclideIdentity) -> Prediction:
        if self.coefficients is None:
            raise RuntimeError("control model has not been fit")
        mu = float(
            np.dot(self._design(nuclide.Z, nuclide.N), np.array(self.coefficients))
        )
        sigma = max(self.residual_std_keV, MIN_PREDICTIVE_STD_KEV)
        return Prediction(
            nuclide=nuclide,
            mass_excess_keV=mu,
            intervals=gaussian_intervals(mu, sigma),
            model_id=self.model_id,
            std_keV=sigma,
            uncertainty_method=self.uncertainty_method,
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "features": ["Z", "N", "A"],
            "control_class": "C_WEAK_SMOOTH",
            "control_role": CONTROL_ROLE,
            "control_scope_rule": CONTROL_SCOPE_RULE,
            "coefficients": self.coefficients,
            "residual_std_keV": self.residual_std_keV,
            "predictive_distribution": "gaussian",
            "uncertainty_method": self.uncertainty_method,
            "fitted_nuclide_ids": list(self._fitted_ids),
        }


def load_truth_table(source: str | Path, edition_id: str) -> dict[str, float]:
    """Every ground-truth-eligible mass of the frozen synthetic snapshot."""
    return {
        obs.nuclide_id: obs.mass_excess_keV
        for obs in load_edition(edition_id, str(source))
        if obs.ground_truth_eligible
    }


# --------------------------------------------------------------------------- #
# Control-model injection                                                     #
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def control_model_registry(builders: Mapping[str, Callable[[], Any]]):
    """Swap the predict-stage model registry for the duration of a control run.

    The frozen ``build_model`` stays the fallback for the frozen ids, so a
    control suite could even mix baselines and controls. Restoration is
    unconditional; outside this context the frozen path is untouched.
    """
    from elementzero.benchmark import b002_predict, b003_predict
    from elementzero.models.gp_residual import build_model as frozen_build

    def _build(model_id: str):
        maker = builders.get(model_id)
        if maker is not None:
            return maker()
        return frozen_build(model_id)

    saved = (b002_predict.build_model, b003_predict.build_model)
    b002_predict.build_model = _build
    b003_predict.build_model = _build
    try:
        yield
    finally:
        b002_predict.build_model, b003_predict.build_model = saved


@contextlib.contextmanager
def _pinned_environment():
    """Pin the commit id so control freezes are deterministic across reruns."""
    saved = os.environ.get("ELEMENTZERO_COMMIT")
    os.environ["ELEMENTZERO_COMMIT"] = BASELINE_COMMIT
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("ELEMENTZERO_COMMIT", None)
        else:
            os.environ["ELEMENTZERO_COMMIT"] = saved


# --------------------------------------------------------------------------- #
# Control runs                                                                #
# --------------------------------------------------------------------------- #


def _b002_control_builders(truth: dict[str, float]) -> dict[str, Callable[[], Any]]:
    return {
        CONTROL_EXACT_ORACLE: lambda: SyntheticTruthOracle(
            model_id=CONTROL_EXACT_ORACLE, truth_keV=truth
        ),
        CONTROL_NOISY_ORACLE_SMALL: lambda: SyntheticTruthOracle(
            model_id=CONTROL_NOISY_ORACLE_SMALL,
            truth_keV=truth,
            noise_keV=NOISE_SMALL_KEV,
            control_class="B_NOISY_ORACLE",
        ),
        CONTROL_WEAK_SMOOTH: lambda: WeakSmoothControlModel(),
    }


def _b003_control_builders(truth: dict[str, float]) -> dict[str, Callable[[], Any]]:
    return {
        CONTROL_SHELL_AWARE_ORACLE: lambda: SyntheticTruthOracle(
            model_id=CONTROL_SHELL_AWARE_ORACLE,
            truth_keV=truth,
            control_class="D_SHELL_AWARE_ORACLE",
        ),
        CONTROL_NOISY_ORACLE_SMALL: lambda: SyntheticTruthOracle(
            model_id=CONTROL_NOISY_ORACLE_SMALL,
            truth_keV=truth,
            noise_keV=NOISE_SMALL_KEV,
            control_class="B_NOISY_ORACLE",
        ),
        CONTROL_NOISY_ORACLE_LARGE: lambda: SyntheticTruthOracle(
            model_id=CONTROL_NOISY_ORACLE_LARGE,
            truth_keV=truth,
            noise_keV=NOISE_LARGE_KEV,
            control_class="B_NOISY_ORACLE",
        ),
        CONTROL_WEAK_SMOOTH: lambda: WeakSmoothControlModel(),
    }


def run_b002_controls(
    *,
    snapshot: str | Path,
    regions_path: str | Path,
    workspace_dir: str | Path,
    edition_id: str = "AME2020",
) -> dict[str, Any]:
    """Controls A, B, C through the frozen EZ-B002 mechanics."""
    from elementzero.experiments.b002_runner import score_b002, seal_b002

    truth = load_truth_table(snapshot, edition_id)
    builders = _b002_control_builders(truth)
    with _pinned_environment(), control_model_registry(builders):
        seal_b002(
            source=snapshot,
            edition_id=edition_id,
            regions_path=regions_path,
            experiment_dir=workspace_dir,
            created_at=CONTROL_CREATED_AT,
            model_ids=tuple(builders),
        )
        score_b002(
            source=snapshot,
            edition_id=edition_id,
            experiment_dir=workspace_dir,
            created_at=CONTROL_CREATED_AT,
        )
    aggregate = read_json(Path(workspace_dir) / "region_aggregate.json")
    summary = {}
    for model_id, payload in aggregate["by_model"].items():
        pooled = payload["pooled"]
        summary[model_id] = {
            "MAE_keV": float(pooled["MAE_keV"]),
            "RMSE_keV": float(pooled["RMSE_keV"]),
            "coverage_90": float(pooled["coverage_90"]),
            "coverage_95": float(pooled["coverage_95"]),
            "NLPD": float(pooled["NLPD"]),
            "n": int(pooled["n"]),
        }
    exact = summary[CONTROL_EXACT_ORACLE]
    weak = summary[CONTROL_WEAK_SMOOTH]
    noisy = summary[CONTROL_NOISY_ORACLE_SMALL]
    checks = {
        "exact_oracle_reconstructs_masked_truth": {
            "observed_MAE_keV": exact["MAE_keV"],
            "max_MAE_keV": EXACT_ORACLE_MAX_MAE_KEV,
            "met": exact["MAE_keV"] <= EXACT_ORACLE_MAX_MAE_KEV,
        },
        "exact_oracle_coverage_saturates": {
            "observed_coverage_90": exact["coverage_90"],
            "met": exact["coverage_90"] == 1.0,
        },
        "noisy_oracle_coverage_near_nominal": {
            "observed_coverage_90": noisy["coverage_90"],
            "met": abs(noisy["coverage_90"] - 0.90) <= 0.15,
        },
        "weak_control_fails_as_expected": {
            "observed_MAE_keV": weak["MAE_keV"],
            "min_MAE_keV": 100.0 * max(exact["MAE_keV"], 1.0),
            "met": weak["MAE_keV"] > 100.0 * max(exact["MAE_keV"], 1.0),
        },
    }
    return {
        "benchmark_id": "EZ-B002",
        "note": (
            "EZ-B002 v1 froze no accuracy criterion, so its controls check the "
            "mechanics: a perfect predictor must come back perfect, a noisy one "
            "calibrated, a weak one visibly weak."
        ),
        "by_model": dict(sorted(summary.items())),
        "checks": checks,
        "status": "PASS" if all(c["met"] for c in checks.values()) else "FAIL",
    }


def run_b003_controls(
    *,
    snapshot: str | Path,
    challenges_path: str | Path,
    workspace_dir: str | Path,
    edition_id: str = "AME2020",
) -> dict[str, Any]:
    """Controls B, C, D through the frozen EZ-B003 mechanics and criterion."""
    from elementzero.experiments.b003_runner import score_b003, seal_b003

    truth = load_truth_table(snapshot, edition_id)
    builders = _b003_control_builders(truth)
    with _pinned_environment(), control_model_registry(builders):
        seal_b003(
            source=snapshot,
            edition_id=edition_id,
            challenges_path=challenges_path,
            experiment_dir=workspace_dir,
            created_at=CONTROL_CREATED_AT,
            model_ids=tuple(builders),
        )
        score_b003(
            source=snapshot,
            edition_id=edition_id,
            experiment_dir=workspace_dir,
            created_at=CONTROL_CREATED_AT,
        )
    aggregate = read_json(Path(workspace_dir) / "shell_aggregate.json")
    summary = {}
    for model_id, payload in aggregate["by_model"].items():
        checks = payload["criterion"]["checks"]
        summary[model_id] = {
            "verdict": payload["criterion"]["verdict"],
            "sign_fraction": float(checks["sign_fraction"]["observed"]),
            "top_k_fraction": float(checks["top_k_fraction"]["observed"]),
            "rank_1_fraction": float(checks["rank_1_fraction"]["observed"]),
            "calibration_error_90": float(checks["calibration_error_90"]["observed"]),
        }
    oracle = summary[CONTROL_SHELL_AWARE_ORACLE]
    weak = summary[CONTROL_WEAK_SMOOTH]
    checks = {
        "shell_aware_oracle_meets_frozen_criterion": {
            "observed_verdict": oracle["verdict"],
            "met": oracle["verdict"] == "CRITERION_MET",
        },
        "shell_aware_oracle_ranks_closure_first_everywhere": {
            "observed_rank_1_fraction": oracle["rank_1_fraction"],
            "met": oracle["rank_1_fraction"] == 1.0,
        },
        "weak_control_fails_frozen_criterion": {
            "observed_verdict": weak["verdict"],
            "met": weak["verdict"] == "CRITERION_NOT_MET",
        },
    }
    status = "PASS" if all(c["met"] for c in checks.values()) else "FAIL"
    if status == "PASS" and weak["verdict"] == "CRITERION_MET":
        status = "INDETERMINATE"  # a criterion a weak control passes is too weak
    return {
        "benchmark_id": "EZ-B003",
        "criterion_id": "ez-b003-rediscovery-criterion-v1",
        "by_model": dict(sorted(summary.items())),
        "checks": checks,
        "threshold_sensitivity": {
            "rule": (
                "Preregistered noise scales only; thresholds themselves never "
                "move. The small scale sits far below the injected indicator "
                "spikes, the large scale is comparable to them, so the pair "
                "probes how much unstructured mass error the frozen criterion "
                "tolerates."
            ),
            "noise_small_keV": NOISE_SMALL_KEV,
            "noise_small_verdict": summary[CONTROL_NOISY_ORACLE_SMALL]["verdict"],
            "noise_large_keV": NOISE_LARGE_KEV,
            "noise_large_verdict": summary[CONTROL_NOISY_ORACLE_LARGE]["verdict"],
        },
        "status": status,
    }


def run_benchmark_controls(
    *,
    workspace_root: str | Path,
    repo_root: str | Path,
) -> dict[str, Any]:
    """All controls; combined status feeds the readiness verdict."""
    root = Path(repo_root)
    workspace = Path(workspace_root)
    b002 = run_b002_controls(
        snapshot=root / "tests" / "fixtures" / "b002" / "synthetic_chart_v1.mas20",
        regions_path=root / "experiments" / "EZ-B002-v1" / "regions.json",
        workspace_dir=workspace / "b002-controls",
    )
    b003 = run_b003_controls(
        snapshot=root / "tests" / "fixtures" / "b003" / "synthetic_shell_chart_v1.mas20",
        challenges_path=root / "experiments" / "EZ-B003-v1" / "challenges.json",
        workspace_dir=workspace / "b003-controls",
    )
    statuses = {b002["status"], b003["status"]}
    if statuses == {"PASS"}:
        status = "PASS"
    elif "FAIL" in statuses:
        status = "FAIL"
    else:
        status = "INDETERMINATE"
    return {
        "work_order": "WO-11",
        "scope_rule": CONTROL_SCOPE_RULE,
        "control_role": CONTROL_ROLE,
        "benchmark_control_status": status,
        "EZ-B002": b002,
        "EZ-B003": b003,
    }


def write_benchmark_controls(
    *,
    out_dir: str | Path,
    workspace_root: str | Path,
    repo_root: str | Path,
) -> dict[str, Any]:
    payload = run_benchmark_controls(workspace_root=workspace_root, repo_root=repo_root)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / BENCHMARK_CONTROLS_FILE).write_text(
        canonical_json(payload) + "\n", encoding="utf-8"
    )
    return payload
