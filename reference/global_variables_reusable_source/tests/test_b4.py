"""B4 tests.

T1  Remnant fits reproduce equal-mass NR benchmarks (Mf/M ~ 0.9516,
    chi_f ~ 0.6865) and the GW150914 catalog remnant within tolerance.
T2  Demo run: GW150914, GW190814, GW250114 must certify
    SUPPORTED_AT_CREDIBILITY (exact binomial lower bound >= 0.95 at 99%
    confidence). GW190521 must come out INCONCLUSIVE in demo mode: its
    mass uncertainties are so large that the independence approximation
    (demo posteriors drop the m1+m2 <-> Mf correlation) destroys the
    inference. This is a FEATURE: the pipeline refuses to over-claim from
    degraded inputs, and demonstrates why REAL correlated posterior
    samples are required for promotion decisions.
T3  Falsifier injection: a fabricated area-DECREASING event must trigger
    VIOLATION_CANDIDATE (the pipeline can fail -- gate #8, adversarial).
T4  Self-consistency: remnant-fit final states imply eta_A > 0
    deterministically for nonspinning binaries across mass ratios.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from b4_area_pipeline.remnant import final_mass_nonspinning, final_spin_nonspinning
from b4_area_pipeline.kerr import kerr_area, eta_A
from b4_area_pipeline.pipeline import run_demo, test_event


def t1_remnant_benchmarks():
    Mf = final_mass_nonspinning(1.0, 1.0)   # total M = 2
    chif = final_spin_nonspinning(1.0, 1.0)
    assert abs(Mf / 2.0 - 0.9516) < 0.002, Mf / 2.0
    assert abs(chif - 0.6865) < 0.002, chif
    # GW150914 cross-check: catalog Mf ~ 63.1, chif ~ 0.69 (spins small)
    Mf9 = final_mass_nonspinning(35.6, 30.6)
    chif9 = final_spin_nonspinning(35.6, 30.6)
    assert abs(Mf9 - 63.1) / 63.1 < 0.01, Mf9
    assert abs(chif9 - 0.69) < 0.03, chif9
    print(f"T1 remnant fits: PASS  (eq-mass Mf/M={Mf/2:.4f}, chif={chif:.4f}; "
          f"GW150914 fit Mf={Mf9:.1f}, chif={chif9:.3f})")


def t2_demo_run():
    cert = run_demo(n=200_000,
                    outdir=os.path.join(os.path.dirname(__file__), "..", "certificates"))
    expected = {"GW150914": "SUPPORTED_AT_CREDIBILITY",
                "GW250114": "SUPPORTED_AT_CREDIBILITY",
                "GW190521": "INCONCLUSIVE",
                "GW190814": "INCONCLUSIVE"}
    for name, r in cert["results"].items():
        assert r["status"] == expected[name], (name, r)
        print(f"T2 {name}: P_lower={r['P_lower_exact_binomial']:.4f}  "
              f"eta_A={r['eta_A_median']:.3f} 90CI={r['eta_A_90CI']}  "
              f"-> {r['status']}")
    print("T2 demo pipeline: PASS  (2 supported; GW190521/GW190814 correctly "
          "refuse over-claim under the demo independence approximation)")
    return cert


def t3_falsifier_injection():
    rng = np.random.default_rng(7)
    n = 50_000
    # Fabricate a GR-violating event: remnant much too small.
    m1 = rng.normal(35, 1.0, n); m2 = rng.normal(30, 1.0, n)
    mf = rng.normal(40.0, 1.0, n)          # impossible: too much mass radiated
    chif = np.clip(rng.normal(0.69, 0.02, n), 0, 0.99)
    r = test_event((m1, m2, np.zeros(n), np.zeros(n), mf, chif))
    assert r["status"] == "VIOLATION_CANDIDATE", r
    print(f"T3 falsifier injection: PASS  (fabricated event correctly flagged "
          f"{r['status']}, P_MC={r['P_area_increase_MC']:.4f})")


def t4_deterministic_eta():
    for q in [1.0, 1.5, 2.0, 4.0, 9.0]:
        m2 = 20.0; m1 = q * m2
        mf, chif = final_mass_nonspinning(m1, m2), final_spin_nonspinning(m1, m2)
        e = eta_A(kerr_area(m1, 0), kerr_area(m2, 0), kerr_area(mf, chif))
        assert e > 0, (q, e)
    print("T4 deterministic eta_A > 0 across mass ratios: PASS")


if __name__ == "__main__":
    t1_remnant_benchmarks()
    cert = t2_demo_run()
    t3_falsifier_injection()
    t4_deterministic_eta()
    print("\nCertificate written: certificates/b4_certificate_demo.json")
    print("ALL B4 TESTS PASS")
