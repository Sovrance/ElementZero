"""Identity of the source files that define an EZ-B001 protocol version.

WO-06 forbids a run whose code differs from the preregistered code without a
protocol bump. A repository commit SHA is a poor gate for that rule: adding a
report generator or a new test changes HEAD without changing a single parser,
model, metric, or leakage control.

So the enforced gate is a digest over the files that actually define the
protocol:

    protocol_code_digest =
        sha256(canonical_json({
            "policy_id": PROTOCOL_CODE_POLICY_ID,
            "files": [{"path": p, "sha256": sha256(bytes(p))}, ... sorted by path]
        }))

The ElementZero commit SHA is still recorded for lineage; it is reported, not
used as the equality test. Any edit to a listed file changes the digest, which
makes every downstream run refuse to execute under the old preregistration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.evidence.hashing import sha256_file, sha256_hex

PROTOCOL_CODE_POLICY_ID = "ez-b001-protocol-code-v1"

# Parsing, normalization, physics, models, metrics, evidence, and leakage
# controls. Reporting and orchestration code is deliberately excluded: it moves
# artifacts around but cannot change a prediction or a metric definition.
PROTOCOL_CODE_FILES: tuple[str, ...] = (
    "src/elementzero/benchmark/b001_finalize.py",
    "src/elementzero/benchmark/b001_freeze.py",
    "src/elementzero/benchmark/b001_predict.py",
    "src/elementzero/benchmark/b001_prepare.py",
    "src/elementzero/benchmark/b001_score.py",
    "src/elementzero/benchmark/distance.py",
    "src/elementzero/benchmark/metrics.py",
    "src/elementzero/benchmark/model_suite.py",
    "src/elementzero/data/amdc/ame2003.py",
    "src/elementzero/data/amdc/ame2012.py",
    "src/elementzero/data/amdc/ame2016.py",
    "src/elementzero/data/amdc/ame2020.py",
    "src/elementzero/data/amdc/common.py",
    "src/elementzero/data/identity.py",
    "src/elementzero/data/observations.py",
    "src/elementzero/evidence/certificates.py",
    "src/elementzero/evidence/freezes.py",
    "src/elementzero/evidence/hashing.py",
    "src/elementzero/evidence/ledger.py",
    "src/elementzero/models/gp_residual.py",
    "src/elementzero/models/model_manifest.py",
    "src/elementzero/models/protocol.py",
    "src/elementzero/physics/constants.py",
    "src/elementzero/physics/conversion.py",
    "src/elementzero/physics/semf.py",
)


def protocol_code_files(root: str | Path | None = None) -> list[dict[str, str]]:
    base = Path(root or REPO_ROOT)
    entries = []
    for relpath in sorted(PROTOCOL_CODE_FILES):
        path = base / relpath
        if not path.is_file():
            raise FileNotFoundError(f"protocol source file is missing: {relpath}")
        entries.append({"path": relpath, "sha256": sha256_file(path)})
    return entries


def protocol_code_identity(root: str | Path | None = None) -> dict[str, Any]:
    files = protocol_code_files(root)
    payload = {"policy_id": PROTOCOL_CODE_POLICY_ID, "files": files}
    return {
        "policy_id": PROTOCOL_CODE_POLICY_ID,
        "protocol_code_digest": sha256_hex(payload),
        "files": files,
    }


def protocol_code_digest(root: str | Path | None = None) -> str:
    return protocol_code_identity(root)["protocol_code_digest"]
