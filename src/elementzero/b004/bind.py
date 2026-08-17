"""Bind the B004 scoring step to its preregistration (WO-15 review round).

Sealing predictions is only half of a blind protocol. The other half is
proving, at scoring time, that the files the scorer reads are the ones
that were preregistered and sealed — not edited copies sitting next to
them on disk. Three bindings are enforced here:

* the seal hash is resolved from the *committed* bytes at a reachable
  seal commit, so regenerating ``SEALED_PREDICTIONS.json`` and its
  companion hash file after truth is known no longer passes;
* the target manifest is re-derived and re-digested, so its target list
  (and therefore the coverage denominator) cannot be edited after the
  fact while the stored digest is kept;
* the independence adjudication is recomputed from the parameter
  artifacts, so ``blind_eligible`` and ``independence_verdict`` cannot be
  flipped after scores are visible.

Each check reads only preregistration-side evidence. None of them
consults truth.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json

SEAL_BINDING_RULE = (
    "ez-wo15-b004-seal-binding-v1: the expected prediction seal hash is the "
    "sha256 of the sealed-predictions blob as committed at the recorded seal "
    "commit, which must be a real commit reachable from HEAD. The on-disk "
    "seal and its companion hash file are compared against that value, never "
    "against each other"
)

PREREG_BINDING_RULE = (
    "ez-wo15-b004-prereg-binding-v1: before truth is unlocked, the target "
    "manifest and the independence adjudication are re-derived from their "
    "own deterministic inputs and compared to the committed files. Scoring "
    "inputs that no longer reproduce their preregistration are refused"
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=False, capture_output=True
    )


def seal_hash_from_commit(
    root: str | Path, *, commit: str, relpath: str
) -> str:
    """The sha256 of ``relpath`` as committed at ``commit``.

    The commit must exist and be an ancestor of HEAD: a seal that is not
    in the published history is not a seal, it is a claim about one.
    """
    root = Path(root)
    if not commit:
        raise ProtocolError(
            "B004_SEAL_COMMIT_MISSING: scoring requires the commit that "
            f"carries the sealed predictions. {SEAL_BINDING_RULE}"
        )
    if _git(root, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        raise ProtocolError(
            f"B004_SEAL_COMMIT_INVALID: {commit} is not a commit in this "
            "repository; a seal commit must be a real, reachable commit"
        )
    if _git(root, "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        raise ProtocolError(
            f"B004_SEAL_COMMIT_INVALID: {commit} is not an ancestor of HEAD; "
            "the seal commit must be part of the published history"
        )
    shown = _git(root, "show", f"{commit}:{relpath}")
    if shown.returncode != 0:
        raise ProtocolError(
            f"B004_SEAL_COMMIT_INVALID: {commit} does not contain {relpath}; "
            "the seal commit must carry the sealed predictions"
        )
    return hashlib.sha256(shown.stdout).hexdigest()


def assert_target_manifest_bound(
    *,
    target_manifest: dict[str, Any],
    protocol: dict[str, Any],
    sealed: dict[str, Any],
    recomputed: dict[str, Any] | None = None,
) -> dict[str, str]:
    """The manifest the scorer holds is the one that was preregistered.

    Includes the self-consistency check that catches the subtle edit:
    shortening ``target_nuclide_ids`` (and with it the coverage
    denominator) while leaving the rows and the stored digest intact.
    """
    ids = list(target_manifest["target_nuclide_ids"])
    checks: dict[str, tuple[Any, Any]] = {
        "manifest_identity_digest": (
            identity_digest(ids),
            target_manifest["target_identity_digest"],
        ),
        "protocol_identity_digest": (
            target_manifest["target_identity_digest"],
            protocol["target_identity_digest"],
        ),
        "sealed_identity_digest": (
            target_manifest["target_identity_digest"],
            sealed["target_identity_digest"],
        ),
        "sealed_target_list": (ids, list(sealed["target_nuclide_ids"])),
        "manifest_row_identity": (
            sorted(t["nuclide_id"] for t in target_manifest["targets"]),
            sorted(ids),
        ),
        "manifest_n_targets": (int(target_manifest["n_targets"]), len(ids)),
        "protocol_n_targets": (int(protocol["n_targets"]), len(ids)),
        "target_rule_hash": (
            target_manifest["target_rule_hash"],
            protocol["target_rule_hash"],
        ),
    }
    if recomputed is not None:
        checks["target_rule_reproduces_manifest"] = (
            canonical_json(recomputed),
            canonical_json(target_manifest),
        )
    _refuse(checks, code="B004_TARGET_MANIFEST_UNBOUND", rule=PREREG_BINDING_RULE)
    return {
        "target_identity_digest": target_manifest["target_identity_digest"],
        "n_targets": str(len(ids)),
    }


def assert_adjudication_bound(
    *,
    adjudication: dict[str, Any],
    protocol: dict[str, Any],
    recomputed_records: list[dict[str, Any]],
) -> dict[str, str]:
    """Blind eligibility is a preregistered derivation, not a late edit.

    The records are a deterministic function of the parameter artifacts,
    the backend roster and the freeze year, so recomputing them and
    comparing is a complete check: flipping ``blind_eligible`` or
    ``independence_verdict`` in the committed file cannot survive it.
    """
    committed = list(adjudication["records"])
    checks: dict[str, tuple[Any, Any]] = {
        "adjudication_records_reproduce": (
            canonical_json(committed),
            canonical_json(recomputed_records),
        ),
        "independence_groups": (
            sorted({r["group_id"] for r in committed}),
            sorted(protocol["independence_groups"]),
        ),
    }
    _refuse(checks, code="B004_ADJUDICATION_UNBOUND", rule=PREREG_BINDING_RULE)
    return {
        "adjudication_digest": hashlib.sha256(
            canonical_json({"records": committed}).encode("utf-8")
        ).hexdigest(),
        "blind_eligible_groups": ",".join(
            sorted(
                {
                    r["group_id"]
                    for r in committed
                    if r["blind_eligible"]
                    and r["independence_verdict"] == "INDEPENDENT"
                }
            )
        ),
    }


def _refuse(checks: dict[str, tuple[Any, Any]], *, code: str, rule: str) -> None:
    for name, (got, want) in checks.items():
        if got != want:
            raise ProtocolError(
                f"{code}: {name} does not match its preregistration "
                f"(got {got!r}, expected {want!r}); scoring is refused. {rule}"
            )


__all__ = [
    "PREREG_BINDING_RULE",
    "SEAL_BINDING_RULE",
    "assert_adjudication_bound",
    "assert_target_manifest_bound",
    "seal_hash_from_commit",
]
