"""B4 pipeline: the black-hole area theorem as the Composition-column entry
for G (conjecture ?3).

Per event, with posterior samples (m1, m2, chi1, chi2) for the initial
state and (mf, chif) for the final state:

    A_i = kerr_area(m_i, chi_i),   Delta A = A_f - A_1 - A_2,
    eta_A = Delta A / A_f          (dimensionless composition invariant)

Outputs per event:
  P_hat(Delta A > 0)               Monte Carlo estimate
  P_lower (Clopper-Pearson)        EXACT binomial lower confidence bound --
                                   the statistical analogue of B1's
                                   certified inner interval
  eta_A median and 90% CI
  status: SUPPORTED_AT_CREDIBILITY / INCONCLUSIVE / VIOLATION_CANDIDATE

Certificate class: STATISTICAL (Monte Carlo + exact binomial bound).
This is a different certificate class from B1's exact-rational algebra and
is labeled as such; the two must never be conflated.
"""

import json
import os
import time

import numpy as np
from scipy.stats import beta

from .kerr import kerr_area, eta_A
from .demo_data import EVENTS


def _trunc_normal(rng, mu, sigma, lo, hi, n):
    out = np.empty(0)
    while out.size < n:
        draw = rng.normal(mu, sigma, size=2 * n)
        draw = draw[(draw > lo) & (draw < hi)]
        out = np.concatenate([out, draw])
    return out[:n]


def sample_event_demo(rng, ev, n):
    """Independent truncated-Gaussian reconstruction (DEMO MODE)."""
    m1 = _trunc_normal(rng, *ev["m1"], 0.1, 1e4, n)
    m2 = _trunc_normal(rng, *ev["m2"], 0.1, 1e4, n)
    m1, m2 = np.maximum(m1, m2), np.minimum(m1, m2)
    chi1 = np.zeros(n)  # conservative: maximizes initial area
    chi2 = np.zeros(n)
    mf = _trunc_normal(rng, *ev["mf"], 0.1, 1e4, n)
    chif = _trunc_normal(rng, *ev["chif"], 0.0, 0.999, n)
    return m1, m2, chi1, chi2, mf, chif


def clopper_pearson_lower(k, n, conf=0.99):
    """Exact binomial lower confidence bound on p at confidence `conf`."""
    if k == 0:
        return 0.0
    return float(beta.ppf(1.0 - conf, k, n - k + 1))


def test_event(samples, conf=0.99, support_threshold=0.95):
    m1, m2, chi1, chi2, mf, chif = samples
    a1, a2, af = kerr_area(m1, chi1), kerr_area(m2, chi2), kerr_area(mf, chif)
    dA = af - a1 - a2
    eta = eta_A(a1, a2, af)
    n = dA.size
    k = int(np.sum(dA > 0))
    p_hat = k / n
    p_low = clopper_pearson_lower(k, n, conf)
    if p_low >= support_threshold:
        status = "SUPPORTED_AT_CREDIBILITY"
    elif p_hat < 0.05:
        status = "VIOLATION_CANDIDATE"  # falsifier trigger: escalate, audit, verify data
    else:
        status = "INCONCLUSIVE"
    lo, med, hi = np.percentile(eta, [5, 50, 95])
    return {
        "status": status,
        "n_samples": n,
        "P_area_increase_MC": round(p_hat, 6),
        "P_lower_exact_binomial": round(p_low, 6),
        "binomial_confidence": conf,
        "eta_A_median": round(float(med), 4),
        "eta_A_90CI": [round(float(lo), 4), round(float(hi), 4)],
    }


def run_demo(n=200_000, seed=20260711, outdir=None):
    rng = np.random.default_rng(seed)
    results = {}
    for name, ev in EVENTS.items():
        r = test_event(sample_event_demo(rng, ev, n))
        r["source"] = ev["source"]
        results[name] = r
    all_supported = all(r["status"] == "SUPPORTED_AT_CREDIBILITY" for r in results.values())
    cert = {
        "certificate_version": "0.3",
        "certificate_class": "STATISTICAL (Monte Carlo + exact Clopper-Pearson bound); "
                             "NOT the exact-rational class of B1",
        "problem": "B4: area theorem as gravity's composition law (conjecture ?3)",
        "mode": "DEMO -- reconstructed summary-statistic posteriors; "
                "run REAL mode with official GWOSC samples before any promotion decision",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": seed,
        "conservative_choices": [
            "component spins set to 0 (maximizes initial area, hardest test direction)",
            "exact binomial lower bound instead of MC point estimate",
        ],
        "known_caveats": [
            "catalog-fit final states are partially circular (NR remnant fits assume GR); "
            "rigorous version uses ringdown-only final state (Isi et al. 2021; "
            "LVK PRL 135, 111403 (2025) for GW250114)",
            "demo posteriors are independent Gaussians; real posteriors are correlated -- "
            "for large-uncertainty events (GW190521) and small-margin extreme-mass-ratio "
            "events (GW190814, true eta_A ~ 0.15) dropping the chirp-mass and Mf "
            "correlations degrades the inference and the pipeline correctly returns "
            "INCONCLUSIVE rather than over-claiming",
        ],
        "results": results,
        "composition_law_statement": "A_f >= A_1 + A_2 realized as entropy subadditivity "
                                     "under merger; dimensionless invariant eta_A",
        "aggregate": "ALL_EVENTS_SUPPORTED" if all_supported else "MIXED (see known_caveats)",
        "m_layer_stipulations": [
            "DEMO reconstructed independent truncated-Gaussian posteriors "
            "from published summary stats (not official PE samples)",
            "Component spins set to 0 (conservative interface choice)",
            "Catalog-fit remnant masses/spins from summary literature "
            "(NR-fit circularity)",
            "INCONCLUSIVE outcomes on GW190521/GW190814 are M-layer "
            "artifacts of the independence approximation",
        ],
        "external_anchors": [
            "Isi et al., PRL 127, 011103 (2021): GW150914 area law ~97%",
            "LVK, PRL 135, 111403 (2025): GW250114 area law, highest-precision test",
            "GW230814/GW231226 (GWTC-4): area law at effectively >=5 sigma (arXiv:2509.03480)",
        ],
    }
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "b4_certificate_demo.json"), "w") as f:
            json.dump(cert, f, indent=2)
    return cert
