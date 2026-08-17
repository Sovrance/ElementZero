#!/usr/bin/env python3
"""Verify solver archives, builds, and upstream golden cases.

Writes the two records the WO-15 bundle needs as evidence that each
backend is the code it claims to be and reproduces its own published
reference output.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elementzero.evidence.hashing import canonical_json  # noqa: E402
from elementzero.physics_backends.adapters.dirhb import dirhb_backend  # noqa: E402
from elementzero.physics_backends.adapters.hfbtho import (  # noqa: E402
    gogny_backend,
    skyrme_backend,
)
from elementzero.physics_backends.provenance import verify_archive  # noqa: E402

OUT = Path("reports/physics_backends/wo15/fits")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    skyrme = skyrme_backend(functional="SKM*", repo_root=".")
    gogny = gogny_backend(functional="D1S", repo_root=".")
    covariant = dirhb_backend(force="DD-ME2", repo_root=".")

    for solver in ("HFBTHO", "DIRHB"):
        record = verify_archive(solver, repo_root=".")
        print(f"{solver} archive verified: {record['archive_sha256'][:16]}…")

    builds = {
        skyrme.backend_id: skyrme.verify_build(),
        gogny.backend_id: gogny.verify_build(),
        covariant.backend_id: covariant.verify_build(),
    }
    (OUT / "build_manifests.json").write_text(
        canonical_json(builds) + "\n", encoding="utf-8"
    )
    for backend_id, manifest in builds.items():
        print(f"{backend_id}: build {manifest['build_manifest_hash'][:16]}…")

    golden = {
        "HFBTHO": skyrme.verify_golden_cases(),
        "DIRHB": covariant.verify_golden_cases(),
    }
    (OUT / "golden_cases.json").write_text(
        canonical_json(golden) + "\n", encoding="utf-8"
    )
    print(canonical_json(golden))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
