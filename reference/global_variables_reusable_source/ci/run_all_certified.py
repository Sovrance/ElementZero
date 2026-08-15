#!/usr/bin/env python3
"""Headless CI entrypoint: re-certify the benchmark suite and fail on any
degradation (Stage 1, P1e; work-order hard constraint #11).

What it does
------------
1. Discovers ``tests/test_b*.py`` (the certified-benchmark suite).
2. Snapshots the committed ``certificates/*.json``.
3. Reruns each benchmark in a subprocess with a pinned hash seed. Each rerun
   regenerates its certificate(s) in place; we capture the regenerated copy to
   a build directory and then RESTORE the committed copy, so the working tree
   is left byte-for-byte unchanged.
4. Compares regenerated vs committed with a *degradation* predicate that is
   tolerant to timestamps and last-digit float jitter but strict about
   certification: a hard-constraint certification flipping to false, a
   FORCED/PERMITTED status or a SPEC verdict changing, or a result key
   disappearing, is a degradation.
5. Writes a signed run manifest (tool + library versions, pinned seed, content
   hashes of every test file and regenerated certificate, per-benchmark result)
   to the build directory.
6. Exits nonzero on any benchmark failure OR any certificate degradation.

The degradation predicate is importable (``is_degradation``) so
``tests/test_ci_guard.py`` can prove it fires on a synthetically corrupted
certificate without running the whole suite.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERT_DIR = os.path.join(ROOT, "certificates")
TESTS_DIR = os.path.join(ROOT, "tests")
B13_CERT_DIR = os.path.join(ROOT, "b13_cdl", "certificates")
B13_TEST = os.path.join(ROOT, "b13_cdl", "tests", "test_b13.py")

# Fields whose values must never silently regress. Compared as exact strings.
_CERTIFICATION_FLAGS = ("hard_constraints_certified", "score")
_STRING_STATUS_KEYS = ("status", "verdict", "outcome")

_FLOAT_RTOL = 1e-6
_FLOAT_ATOL = 1e-9
# Keys that are expected to change every run and are not degradations.
_VOLATILE_KEYS = frozenset({"timestamp_utc", "generated", "generated_at",
                            "wall_time_s", "created_at"})


# --------------------------------------------------------------------------- #
# degradation predicate                                                       #
# --------------------------------------------------------------------------- #
def _floats_close(a: float, b: float) -> bool:
    return abs(a - b) <= _FLOAT_ATOL + _FLOAT_RTOL * max(abs(a), abs(b))


def _as_number(s: str):
    """Parse a numeric-valued string to a complex, else None.

    Handles ints, floats, Python complex reprs (``-1.8+0j``), and exact
    rationals (``"7/1250"``). Status/verdict strings like ``"FORCED"`` return
    None and fall through to exact string comparison. This makes the predicate
    tolerant to numeric *representation* jitter (e.g. a real value serialized
    as ``-1.8`` vs ``-1.800000+0.000000j``) while staying strict about any
    non-numeric label change."""
    from fractions import Fraction
    t = s.strip()
    if not t:
        return None
    try:
        return complex(Fraction(t))  # "7/1250", "3"
    except (ValueError, ZeroDivisionError):
        pass
    try:
        return complex(t.replace("j", "j"))  # "-1.8", "-1.8+0.0j", "2e-6"
    except ValueError:
        return None


def _complex_close(a: complex, b: complex) -> bool:
    return (_floats_close(a.real, b.real) and _floats_close(a.imag, b.imag))


def _diff(committed: Any, regenerated: Any, path: str, out: List[str]) -> None:
    """Append human-readable degradation reasons to ``out``.

    Degradations (hard): a certification flag or status/verdict string changing
    value or type; a mapping key present in ``committed`` but absent in
    ``regenerated`` (lost certification surface); a non-float value changing.
    Non-degradations: timestamps, added keys, float jitter within tolerance.
    """
    key = path.rsplit(".", 1)[-1]
    if key in _VOLATILE_KEYS:
        return

    if isinstance(committed, dict) and isinstance(regenerated, dict):
        for k in committed:
            if k in _VOLATILE_KEYS:
                continue
            if k not in regenerated:
                out.append(f"{path}.{k}: key removed (certification surface lost)")
            else:
                _diff(committed[k], regenerated[k], f"{path}.{k}", out)
        return

    if isinstance(committed, list) and isinstance(regenerated, list):
        if len(committed) != len(regenerated):
            out.append(f"{path}: list length {len(committed)} -> {len(regenerated)}")
            return
        for i, (c, r) in enumerate(zip(committed, regenerated)):
            _diff(c, r, f"{path}[{i}]", out)
        return

    # scalars
    if isinstance(committed, bool) or isinstance(regenerated, bool):
        if committed != regenerated:
            out.append(f"{path}: {committed!r} -> {regenerated!r}")
        return
    if isinstance(committed, (int, float)) and isinstance(regenerated, (int, float)):
        if not _floats_close(float(committed), float(regenerated)):
            out.append(f"{path}: numeric {committed} -> {regenerated} (beyond tolerance)")
        return
    if isinstance(committed, str) and isinstance(regenerated, str) and committed != regenerated:
        # Compare numeric-valued strings by value (representation jitter), but
        # keep label/status strings under exact comparison.
        nc, nr = _as_number(committed), _as_number(regenerated)
        if nc is not None and nr is not None and _complex_close(nc, nr):
            return
        out.append(f"{path}: {committed!r} -> {regenerated!r}")
        return
    if committed != regenerated:
        # A changed certification flag or status string is always a degradation;
        # any other changed scalar is reported too (conservative).
        out.append(f"{path}: {committed!r} -> {regenerated!r}")


def is_degradation(committed: Dict, regenerated: Dict) -> Tuple[bool, List[str]]:
    """Return ``(degraded, reasons)`` comparing two certificate dicts."""
    reasons: List[str] = []
    _diff(committed, regenerated, "cert", reasons)
    return (len(reasons) > 0, reasons)


# --------------------------------------------------------------------------- #
# suite runner                                                                #
# --------------------------------------------------------------------------- #
def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _library_versions() -> Dict[str, str]:
    import importlib.metadata as im
    vers = {"python": sys.version.split()[0]}
    for mod in ("numpy", "scipy", "mpmath", "jsonschema"):
        try:
            vers[mod] = im.version(mod)
        except Exception:
            vers[mod] = "absent"
    return vers


def _snapshot_certs(cert_dir: str = CERT_DIR) -> Dict[str, str]:
    """Return {basename: raw-text} of every committed certificate in ``cert_dir``."""
    snap = {}
    for p in glob.glob(os.path.join(cert_dir, "*.json")):
        with open(p) as f:
            snap[os.path.basename(p)] = f.read()
    return snap


def _suites() -> List[Dict[str, Any]]:
    """The certified suites to re-run, each pinned to its own certificate zone.

    A suite = {name, cert_dir, tests}. B1-B12 write to certificates/; B13-CDL
    writes to b13_cdl/certificates/. Keeping the zones separate lets each be
    snapshotted, diffed, and restored independently."""
    suites = [{
        "name": "benchmarks",
        "cert_dir": CERT_DIR,
        "tests": sorted(glob.glob(os.path.join(TESTS_DIR, "test_b*.py"))),
    }]
    if os.path.exists(B13_TEST):
        suites.append({"name": "b13-cdl", "cert_dir": B13_CERT_DIR, "tests": [B13_TEST]})
    return suites


def run(build_dir: str, seed: str = "0", verbose: bool = True) -> Dict:
    os.makedirs(build_dir, exist_ok=True)
    regen_dir = os.path.join(build_dir, "regenerated")
    os.makedirs(regen_dir, exist_ok=True)

    env = dict(os.environ, PYTHONHASHSEED=seed, PIR_CI_SEED=seed)
    benchmarks: List[Dict] = []
    degraded_any = False
    failed_any = False
    all_tests: List[str] = []

    for suite in _suites():
        cert_dir = suite["cert_dir"]
        committed_snapshot = _snapshot_certs(cert_dir)
        for test_path in suite["tests"]:
            all_tests.append(test_path)
            name = os.path.basename(test_path)
            before = _snapshot_certs(cert_dir)
            proc = subprocess.run(
                [sys.executable, test_path], cwd=ROOT, env=env,
                capture_output=True, text=True,
            )
            ok = proc.returncode == 0
            entry: Dict[str, Any] = {"test": name, "suite": suite["name"],
                                     "passed": ok, "returncode": proc.returncode}
            if not ok:
                failed_any = True
                entry["stderr_tail"] = proc.stderr.strip().splitlines()[-3:]
                benchmarks.append(entry)
                if verbose:
                    print(f"[FAIL] {name} (exit {proc.returncode})")
                continue

            after = _snapshot_certs(cert_dir)
            touched = [b for b, txt in after.items() if before.get(b) != txt]
            entry["certificates"] = []
            for b in touched:
                regenerated = json.loads(after[b])
                with open(os.path.join(regen_dir, b), "w") as f:
                    json.dump(regenerated, f, indent=2, sort_keys=True)
                committed_txt = committed_snapshot.get(b)
                cert_result: Dict[str, Any] = {"name": b}
                if committed_txt is None:
                    cert_result["status"] = "NEW"
                else:
                    degraded, reasons = is_degradation(json.loads(committed_txt), regenerated)
                    cert_result["status"] = "DEGRADED" if degraded else "OK"
                    cert_result["reasons"] = reasons
                    if degraded:
                        degraded_any = True
                entry["certificates"].append(cert_result)
            benchmarks.append(entry)
            if verbose:
                tag = "OK" if all(c.get("status") in ("OK", "NEW") for c in entry["certificates"]) else "DEGRADED"
                print(f"[{tag}] {name}  ({len(touched)} cert(s))")

        # Restore this zone's committed certificates exactly.
        for b, txt in committed_snapshot.items():
            with open(os.path.join(cert_dir, b), "w") as f:
                f.write(txt)

    tests = all_tests

    manifest = {
        "tool": "ci/run_all_certified.py",
        "manifest_version": "0.1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pinned_seed": seed,
        "library_versions": _library_versions(),
        "test_file_hashes": {os.path.basename(t): _sha256_file(t) for t in tests},
        "regenerated_certificate_hashes": {
            b: _sha256_file(os.path.join(regen_dir, b))
            for b in os.listdir(regen_dir)
        },
        "benchmarks": benchmarks,
        "result": "FAIL" if (failed_any or degraded_any) else "PASS",
        "any_failure": failed_any,
        "any_degradation": degraded_any,
    }
    # "Signed": a self-hash over the canonical manifest body binds its contents.
    body = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    manifest["signature_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()

    with open(os.path.join(build_dir, "run_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Re-certify benchmarks; fail on degradation.")
    ap.add_argument("--build-dir", default=os.path.join(ROOT, "build", "ci"))
    ap.add_argument("--seed", default="0")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    manifest = run(args.build_dir, seed=args.seed, verbose=not args.quiet)
    print(f"\nCI result: {manifest['result']}  "
          f"(failures={manifest['any_failure']}, "
          f"degradations={manifest['any_degradation']})")
    print(f"Manifest: {os.path.join(args.build_dir, 'run_manifest.json')} "
          f"(sig {manifest['signature_sha256'][:16]})")
    return 0 if manifest["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
