"""Predictive-uncertainty calibration: diagnostics, gate, and repair.

ASCII-first:

    z_i    = (truth_i - prediction_i) / sigma_i
    PIT_i  = Phi(z_i)
    NLPD_i = 0.5*log(2*pi*sigma_i^2) + 0.5*z_i^2
    CRPS_i = sigma_i * ( z_i*(2*Phi(z_i) - 1) + 2*phi(z_i) - 1/sqrt(pi) )

A model is CALIBRATED when the realized z distribution is standard normal.
Three failure modes are named separately because they have different causes
and different repairs:

    std(z) << 1    UNCERTAINTY_OVERDISPERSED   sigma too wide, intervals vacuous
    std(z) >> 1    UNCERTAINTY_UNDERDISPERSED  sigma too narrow, intervals dishonest
    |mean(z)| > 0  MEAN_FUNCTION_BIASED        the mean is shifted; sigma is not the problem

This module reports; it never silently rescales a sealed prediction.
Conformal repair is an explicit, declared, pre-seal operation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

CALIBRATION_MODULE_VERSION = "ez-uq-v2.0.0"

# Gate thresholds. Mirrored in protocol/acceptance_matrix.json; changing them
# requires a protocol version bump, never an in-place edit.
GATE_STD_Z_MIN = 0.80
GATE_STD_Z_MAX = 1.25
GATE_ABS_MEAN_Z_MAX = 0.30
GATE_CAL_ERROR_90_MAX = 0.05
GATE_CAL_ERROR_95_MAX = 0.03
# The gate uses the KS *statistic* (an effect size), not the KS p-value.
# A p-value threshold tightens as n grows, so a larger, better benchmark would
# be punished for being larger. D is sample-size independent; p is reported as
# a diagnostic only.
GATE_PIT_KS_D_MAX = 0.10
GATE_PIT_KS_P_MIN_REPORTED = 0.05
GATE_MIN_N = 20

_SQRT2 = math.sqrt(2.0)
_SQRT_PI = math.sqrt(math.pi)


def _phi(x: np.ndarray) -> np.ndarray:
    """Standard normal pdf."""
    return np.exp(-0.5 * np.square(np.asarray(x, dtype=float))) / math.sqrt(2.0 * math.pi)


def _Phi(x: np.ndarray) -> np.ndarray:
    """Standard normal cdf via erf (no scipy dependency in the gate path)."""
    arr = np.asarray(x, dtype=float)
    return 0.5 * (1.0 + np.vectorize(math.erf)(arr / _SQRT2))


def _gaussian_two_sided_critical(level: float) -> float:
    """Central two-sided critical value for a nominal level, by bisection."""
    if not 0.0 < level < 1.0:
        raise ValueError("level must be in (0,1)")
    target = 0.5 * (1.0 + level)
    lo, hi = 0.0, 40.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if float(_Phi(np.array([mid]))[0]) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def z_scores(truth: np.ndarray, prediction: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    sigma = np.asarray(sigma, dtype=float)
    if np.any(sigma <= 0.0):
        raise ValueError("sigma must be strictly positive")
    return (np.asarray(truth, dtype=float) - np.asarray(prediction, dtype=float)) / sigma


def pit_values(z: np.ndarray) -> np.ndarray:
    return _Phi(z)


def nlpd_gaussian(z: np.ndarray, sigma: np.ndarray) -> float:
    sigma = np.asarray(sigma, dtype=float)
    return float(np.mean(0.5 * np.log(2.0 * math.pi * sigma**2) + 0.5 * np.square(z)))


def crps_gaussian(z: np.ndarray, sigma: np.ndarray) -> float:
    """Closed-form CRPS for a Gaussian predictive distribution (lower is better).

    CRPS is reported next to NLPD because NLPD is unbounded: one badly placed
    target can dominate it, which is part of why the v1 NLPD column was hard
    to read against the v1 coverage column.
    """
    z = np.asarray(z, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    return float(np.mean(sigma * (z * (2.0 * _Phi(z) - 1.0) + 2.0 * _phi(z) - 1.0 / _SQRT_PI)))


def empirical_coverage(z: np.ndarray, level: float) -> float:
    """Fraction of targets inside the central `level` Gaussian interval."""
    crit = _gaussian_two_sided_critical(level)
    return float(np.mean(np.abs(np.asarray(z, dtype=float)) <= crit))


def coverage_curve(z: np.ndarray, levels: tuple[float, ...] | None = None) -> list[dict[str, float]]:
    """Empirical-vs-nominal coverage across the whole range, not just 90/95.

    Reporting the curve is what makes an overdispersed model visibly useless
    rather than accidentally flattering: a model with sigma 1000x too wide
    scores coverage 1.000 at every nominal level, and the curve shows it.
    """
    if levels is None:
        levels = tuple(round(float(x), 2) for x in np.arange(0.05, 1.0, 0.05))
    return [
        {"nominal": float(level), "empirical": empirical_coverage(z, float(level))}
        for level in levels
    ]


def pit_ks(z: np.ndarray) -> tuple[float, float]:
    """One-sample KS statistic of PIT against Uniform(0,1), plus asymptotic p.

    The asymptotic p-value is adequate for n >= 20; below that the gate
    reports NOT_EVALUABLE rather than a number nobody should trust.
    """
    u = np.sort(pit_values(np.asarray(z, dtype=float)))
    n = u.size
    if n == 0:
        raise ValueError("empty sample")
    i = np.arange(1, n + 1, dtype=float)
    d_plus = float(np.max(i / n - u))
    d_minus = float(np.max(u - (i - 1.0) / n))
    d = max(d_plus, d_minus)
    lam = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * d
    p = 2.0 * sum((-1.0) ** (k - 1) * math.exp(-2.0 * k * k * lam * lam) for k in range(1, 101))
    return d, float(min(max(p, 0.0), 1.0))


def classify_dispersion(std_z: float, mean_z: float) -> str:
    if std_z < GATE_STD_Z_MIN:
        return "UNCERTAINTY_OVERDISPERSED"
    if std_z > GATE_STD_Z_MAX:
        return "UNCERTAINTY_UNDERDISPERSED"
    if abs(mean_z) > GATE_ABS_MEAN_Z_MAX:
        return "MEAN_FUNCTION_BIASED"
    return "CALIBRATED"


@dataclass(frozen=True)
class CalibrationReport:
    n: int
    mean_z: float
    std_z: float
    nlpd: float
    crps: float
    coverage_90: float
    coverage_95: float
    cal_error_90: float
    cal_error_95: float
    pit_ks_d: float
    pit_ks_p: float
    verdict: str
    failures: tuple[str, ...] = ()
    dispersion_class: str = ""
    module_version: str = CALIBRATION_MODULE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "mean_z": self.mean_z,
            "std_z": self.std_z,
            "NLPD": self.nlpd,
            "CRPS": self.crps,
            "coverage_90": self.coverage_90,
            "coverage_95": self.coverage_95,
            "cal_error_90": self.cal_error_90,
            "cal_error_95": self.cal_error_95,
            "pit_ks_d": self.pit_ks_d,
            "pit_ks_p": self.pit_ks_p,
            "verdict": self.verdict,
            "failures": list(self.failures),
            "dispersion_class": self.dispersion_class,
            "module_version": self.module_version,
        }


def calibration_report(
    truth: np.ndarray, prediction: np.ndarray, sigma: np.ndarray
) -> CalibrationReport:
    """Full calibration verdict for one model on one target set."""
    z = z_scores(truth, prediction, sigma)
    n = int(z.size)
    mean_z = float(np.mean(z))
    std_z = float(np.std(z))
    c90 = empirical_coverage(z, 0.90)
    c95 = empirical_coverage(z, 0.95)
    d, p = pit_ks(z)

    failures: list[str] = []
    if std_z < GATE_STD_Z_MIN:
        failures.append(f"std_z {std_z:.4f} < {GATE_STD_Z_MIN}")
    if std_z > GATE_STD_Z_MAX:
        failures.append(f"std_z {std_z:.4f} > {GATE_STD_Z_MAX}")
    if abs(mean_z) > GATE_ABS_MEAN_Z_MAX:
        failures.append(f"abs(mean_z) {abs(mean_z):.4f} > {GATE_ABS_MEAN_Z_MAX}")
    if abs(c90 - 0.90) > GATE_CAL_ERROR_90_MAX:
        failures.append(f"cal_error_90 {abs(c90 - 0.90):.4f} > {GATE_CAL_ERROR_90_MAX}")
    if abs(c95 - 0.95) > GATE_CAL_ERROR_95_MAX:
        failures.append(f"cal_error_95 {abs(c95 - 0.95):.4f} > {GATE_CAL_ERROR_95_MAX}")
    if n >= GATE_MIN_N and d > GATE_PIT_KS_D_MAX:
        failures.append(f"pit_ks_d {d:.4f} > {GATE_PIT_KS_D_MAX}")

    if n < GATE_MIN_N:
        verdict = "NOT_EVALUABLE"
        failures.append(f"n {n} < {GATE_MIN_N}: calibration gate not evaluable at this sample size")
    else:
        verdict = "CALIBRATION_PASS" if not failures else "CALIBRATION_FAIL"

    return CalibrationReport(
        n=n,
        mean_z=mean_z,
        std_z=std_z,
        nlpd=nlpd_gaussian(z, sigma),
        crps=crps_gaussian(z, sigma),
        coverage_90=c90,
        coverage_95=c95,
        cal_error_90=abs(c90 - 0.90),
        cal_error_95=abs(c95 - 0.95),
        pit_ks_d=d,
        pit_ks_p=p,
        verdict=verdict,
        failures=tuple(failures),
        dispersion_class=classify_dispersion(std_z, mean_z),
    )


@dataclass
class ConformalSigmaScaler:
    """Single-parameter conformal repair of predictive sigma.

    Learns one multiplier s such that the empirical |z| quantile on a
    calibration split matches the nominal Gaussian quantile:

        s = quantile(abs(z_cal), level) / Phi_inv((1+level)/2)

    Rules of use, enforced by the protocol and not by this class:
      - the calibration split MUST be blind-eligible under the same tier as
        the scored targets, and MUST NOT contain any scored target;
      - the scaler MUST be fit and declared before the seal;
      - a scaler is part of model identity: EZ-<MODEL>+CONF-v2.

    A conformal scaler repairs dispersion. It cannot repair a biased mean, and
    `fit` refuses rather than papering over one.
    """

    level: float = 0.90
    scale: float = 1.0
    fitted: bool = False
    n_calibration: int = 0
    refused_reason: str | None = None
    _meta: dict[str, Any] = field(default_factory=dict)

    def fit(
        self, truth: np.ndarray, prediction: np.ndarray, sigma: np.ndarray
    ) -> ConformalSigmaScaler:
        z = z_scores(truth, prediction, sigma)
        if z.size < GATE_MIN_N:
            raise ValueError(f"conformal calibration requires n >= {GATE_MIN_N}")
        mean_z = float(np.mean(z))
        std_z = float(np.std(z))
        if std_z > 0 and abs(mean_z) / std_z > 0.5:
            self.refused_reason = (
                f"calibration residuals are shifted (mean_z={mean_z:.3f}, std_z={std_z:.3f}); "
                "a sigma scaler cannot repair a biased mean function"
            )
            self.fitted = False
            return self
        crit = _gaussian_two_sided_critical(self.level)
        emp = float(np.quantile(np.abs(z), self.level))
        self.scale = float(emp / crit)
        self.fitted = True
        self.refused_reason = None
        self.n_calibration = int(z.size)
        self._meta = {
            "empirical_quantile": emp,
            "gaussian_critical": crit,
            "mean_z": mean_z,
            "std_z": std_z,
        }
        return self

    def apply(self, sigma: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError(f"scaler not fitted ({self.refused_reason or 'fit() not called'})")
        return np.asarray(sigma, dtype=float) * self.scale

    def manifest(self) -> dict[str, Any]:
        return {
            "method": "conformal_sigma_scaler_v2",
            "level": self.level,
            "scale": self.scale,
            "fitted": self.fitted,
            "n_calibration": self.n_calibration,
            "refused_reason": self.refused_reason,
            "diagnostics": dict(self._meta),
            "module_version": CALIBRATION_MODULE_VERSION,
        }
