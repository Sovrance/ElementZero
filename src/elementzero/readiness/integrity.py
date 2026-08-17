"""WO-15B step 1: prove nothing upstream moved, and fence off the truth.

Two jobs. First, re-hash every WO-15 and WO-14 artifact this work order
promises not to touch, so a later claim rests on an unchanged base.
Second, enumerate the artifacts that now contain revealed truth — B004's
scores and unlock among them — and digest them as forbidden inputs.

Enumerating forbidden files by hash is the same discipline WO-15 applied
to its fit freeze: a rule that says "do not use B004 truth" is a promise,
whereas a digested membership list is a check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.atlas_pin import REPO_ROOT
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.physics_backends.freeze import WO14_TRUTH_ARTIFACTS
from elementzero.physics_backends.report import WO14_IMMUTABLE_ARTIFACTS
from elementzero.readiness import TRUTH_FIREWALL_RULE, WO15B_ID

INPUT_COMMIT = "4f72b3825965f155479943f62ea57f27a5e21f9e"

# WO-15 outputs WO-15B consumes but must not modify. The parameter
# artifacts are inputs to the discrepancy fits; the B004 seal and
# protocol are the record that the earlier challenge was run honestly.
WO15_IMMUTABLE_ARTIFACTS = (
    "experiments/EZ-B004-v1/PROTOCOL.json",
    "experiments/EZ-B004-v1/independence_adjudication.json",
    "experiments/EZ-B004-v1/target_manifest.json",
    "reports/physics_backends/wo15/fits/historical_fit_freeze.json",
    "reports/physics_backends/wo15/fits/objective_manifest.json",
    "reports/physics_backends/wo15/fits/parameter_artifact_"
    "EZ-PHYS-COVARIANT-RHB-v1.json",
    "reports/physics_backends/wo15/fits/parameter_artifact_"
    "EZ-PHYS-GOGNY-HFB-v1.json",
    "reports/physics_backends/wo15/fits/parameter_artifact_"
    "EZ-PHYS-SKYRME-HFB-v1.json",
    "results/EZ-B004-v1/SEALED_PREDICTIONS.json",
    "results/EZ-B004-v1/SEALED_PREDICTIONS_SHA256",
)

# Revealed truth. Reading any of these into a fit is the one thing this
# work order cannot recover from, so they are named rather than implied.
B004_TRUTH_ARTIFACTS = (
    "results/EZ-B004-v1/b004_scores.json",
    "results/EZ-B004-v1/truth_unlock.json",
    "results/EZ-B004-v1/claim_adjudication.json",
    "results/EZ-B004-v1/probe_validity_audit.json",
)


def _hash_all(root: Path, relpaths: tuple[str, ...], *, required: bool) -> dict[str, str]:
    out: dict[str, str] = {}
    for relpath in relpaths:
        path = root / relpath
        if not path.is_file():
            if required:
                raise ProtocolError(
                    f"{WO15B_ID}: required input {relpath} is missing; the "
                    "integrity of the base cannot be established"
                )
            continue
        out[relpath] = sha256_file(path)
    return dict(sorted(out.items()))


def build_input_integrity(
    *, repo_root: str | Path | None = None
) -> dict[str, Any]:
    """Hash the untouchable base and the forbidden truth in one record."""
    root = Path(repo_root or REPO_ROOT)
    wo14_immutable = _hash_all(root, WO14_IMMUTABLE_ARTIFACTS, required=True)
    wo15_immutable = _hash_all(root, WO15_IMMUTABLE_ARTIFACTS, required=True)
    forbidden = {
        **_hash_all(root, WO14_TRUTH_ARTIFACTS, required=False),
        **_hash_all(root, B004_TRUTH_ARTIFACTS, required=False),
    }
    record = {
        "work_order": WO15B_ID,
        "input_commit": INPUT_COMMIT,
        "truth_firewall_rule": TRUTH_FIREWALL_RULE,
        "wo14_immutable_artifacts": wo14_immutable,
        "wo15_immutable_artifacts": wo15_immutable,
        "forbidden_truth_artifacts": dict(sorted(forbidden.items())),
        "n_immutable": len(wo14_immutable) + len(wo15_immutable),
        "n_forbidden": len(forbidden),
    }
    record["integrity_digest"] = sha256_hex(record)
    return record


def assert_base_unchanged(
    *, recorded: dict[str, Any], repo_root: str | Path | None = None
) -> None:
    """Re-hash the base and refuse if any promised-immutable byte moved."""
    root = Path(repo_root or REPO_ROOT)
    for key, relpaths in (
        ("wo14_immutable_artifacts", WO14_IMMUTABLE_ARTIFACTS),
        ("wo15_immutable_artifacts", WO15_IMMUTABLE_ARTIFACTS),
    ):
        current = _hash_all(root, relpaths, required=True)
        for relpath, digest in recorded[key].items():
            if current.get(relpath) != digest:
                raise ProtocolError(
                    f"WO15B_BASE_MUTATED: {relpath} now hashes "
                    f"{current.get(relpath)}, recorded {digest}. WO-15B may "
                    "not modify the evidence it builds on"
                )


def assert_not_forbidden(
    *, paths: list[str] | tuple[str, ...], stage: str
) -> None:
    """Refuse a fit stage that names a truth-bearing artifact as input."""
    forbidden = set(WO14_TRUTH_ARTIFACTS) | set(B004_TRUTH_ARTIFACTS)
    named = sorted(set(paths) & forbidden)
    if named:
        raise ProtocolError(
            f"WO15B_TRUTH_LEAK: {stage} names {named} as an input. "
            f"{TRUTH_FIREWALL_RULE}"
        )


def integrity_hash(record: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(record))


__all__ = [
    "B004_TRUTH_ARTIFACTS",
    "INPUT_COMMIT",
    "WO15_IMMUTABLE_ARTIFACTS",
    "assert_base_unchanged",
    "assert_not_forbidden",
    "build_input_integrity",
    "integrity_hash",
]
