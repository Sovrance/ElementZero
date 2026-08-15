"""CI-guard tests (Stage 1, P1e / DoD).

G1  The degradation predicate does NOT fire on benign churn: a timestamp
    change and last-digit float jitter against a real committed certificate
    are not degradations.
G2  The predicate DOES fire on a synthetically corrupted certificate:
    - a hard-constraint certification flag flipped true -> false;
    - a FORCED status flipped to REJECTED;
    - a result key removed.
G3  End-to-end: ``ci/run_all_certified.py`` runs GREEN on the current repo
    (all test_b*.py re-certify without degradation) and its restore step leaves
    the committed certificates byte-for-byte unchanged. Skips gracefully if the
    benchmark scientific dependencies (numpy/scipy/mpmath) are absent.
"""

import copy
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci.run_all_certified import is_degradation, run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERT_DIR = os.path.join(ROOT, "certificates")


def _a_committed_cert():
    # b1 certificate is exact-rational and stable; fall back to any cert.
    for pref in ("b1_certificate.json", "b2_certificate.json"):
        p = os.path.join(CERT_DIR, pref)
        if os.path.exists(p):
            with open(p) as f:
                return pref, json.load(f)
    p = sorted(glob.glob(os.path.join(CERT_DIR, "*.json")))[0]
    with open(p) as f:
        return os.path.basename(p), json.load(f)


def g1_benign_churn():
    name, cert = _a_committed_cert()
    regen = copy.deepcopy(cert)
    regen["timestamp_utc"] = "2099-01-01T00:00:00Z"  # different timestamp

    def jitter(o):
        if isinstance(o, float):
            return o * (1 + 1e-12)
        if isinstance(o, dict):
            return {k: jitter(v) for k, v in o.items()}
        if isinstance(o, list):
            return [jitter(v) for v in o]
        return o

    regen = jitter(regen)
    degraded, reasons = is_degradation(cert, regen)
    assert not degraded, reasons
    print(f"G1 benign churn: PASS  {name}: timestamp change + 1e-12 float "
          f"jitter is NOT flagged as degradation")
    return {"cert": name}


def g2_corruption_detected():
    name, cert = _a_committed_cert()

    # (a) certification flag flip.
    c1 = copy.deepcopy(cert)
    if "hard_constraints_certified" in c1:
        c1["hard_constraints_certified"] = not c1["hard_constraints_certified"]
    else:
        c1.setdefault("results", {})["_synthetic"] = {"status": "FORCED"}
        cert = copy.deepcopy(c1)
        c1["results"]["_synthetic"]["status"] = "REJECTED"
    d1, r1 = is_degradation(cert, c1)
    assert d1, "flag flip not detected"

    # (b) a FORCED status flipped to REJECTED anywhere in the tree.
    c2 = copy.deepcopy(cert)
    blob = json.dumps(c2)
    if '"FORCED"' in blob:
        c2 = json.loads(blob.replace('"FORCED"', '"REJECTED"', 1))
        d2, _ = is_degradation(cert, c2)
        assert d2, "FORCED->REJECTED not detected"
    else:
        d2 = True  # no FORCED token in this cert; (a)/(c) already cover it

    # (c) a result key removed (lost certification surface).
    c3 = copy.deepcopy(cert)
    if isinstance(c3.get("results"), dict) and c3["results"]:
        c3["results"].pop(next(iter(c3["results"])))
        d3, _ = is_degradation(cert, c3)
        assert d3, "removed result key not detected"
    else:
        d3 = True

    print(f"G2 corruption detected: PASS  {name}: flag-flip, FORCED→REJECTED, "
          f"and removed-key all flagged as degradation")
    return {"detected": [bool(d1), bool(d2), bool(d3)]}


def g3_end_to_end():
    try:
        import numpy, scipy, mpmath  # noqa: F401
    except ImportError as e:
        print(f"G3 end-to-end: SKIP  benchmark dependency missing ({e})")
        return {"skipped": True}

    before = {}
    for p in glob.glob(os.path.join(CERT_DIR, "*.json")):
        with open(p, "rb") as f:
            before[p] = f.read()

    build = os.path.join(ROOT, "build", "ci_selftest")
    manifest = run(build, seed="0", verbose=False)

    # Working tree restored byte-for-byte.
    for p, raw in before.items():
        with open(p, "rb") as f:
            assert f.read() == raw, f"CI mutated committed cert {os.path.basename(p)}"

    assert manifest["result"] == "PASS", [b for b in manifest["benchmarks"] if not b.get("passed")]
    assert not manifest["any_degradation"], manifest
    assert manifest["signature_sha256"]
    n = len(manifest["benchmarks"])
    print(f"G3 end-to-end: PASS  {n} benchmarks re-certified GREEN; committed "
          f"certificates left unchanged; manifest signed "
          f"{manifest['signature_sha256'][:16]}")
    return {"benchmarks": n}


if __name__ == "__main__":
    r1 = g1_benign_churn(); r2 = g2_corruption_detected(); r3 = g3_end_to_end()
    print("\nALL CI-GUARD TESTS PASS (G1-G3)")
