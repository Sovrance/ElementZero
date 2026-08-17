"""What a discrepancy model is allowed to be (WO-15B stream B).

A discrepancy model learns what a physics family gets wrong. That makes
it powerful and dangerous in equal measure: powerful because the missing
term in WO-15's uncertainty budget *was* model discrepancy, dangerous
because a model that can see blind truth would turn a blind challenge
into a fit.

Three rules follow, and they are enforced rather than documented:

* it trains on training-era residuals only;
* its features are identity and support metadata only — never a residual
  of another model, never an error table, never a measured mass outside
  the freeze;
* it is a *child* of its parent physics family and inherits that
  family's independence group, so correcting a family can never increase
  the count of independent blind families.
"""

from __future__ import annotations

from typing import Any

from elementzero.errors import ProtocolError

FEATURE_POLICY_ID = "ez-wo15b-discrepancy-features-v1"

# The complete allowed feature vocabulary. Anything outside this list is
# refused by name, so adding a feature is a deliberate, reviewable act.
ALLOWED_FEATURES = (
    "Z",
    "N",
    "A",
    "asymmetry",          # (N - Z) / A
    "Z_parity",           # 0 for even Z, 1 for odd Z
    "N_parity",
    "shell_distance_Z",   # |Z - nearest magic Z|, identity arithmetic only
    "shell_distance_N",
)

FEATURE_POLICY = (
    f"{FEATURE_POLICY_ID}: discrepancy features are derived from nuclide "
    "identity and support metadata alone — "
    f"{', '.join(ALLOWED_FEATURES)}. No feature may be a function of a "
    "measured mass outside the training freeze, of any model's residual on "
    "a blind target, or of any scored result"
)

MODEL_TYPE_GP = "GAUSSIAN_PROCESS_RBF_PLUS_NOISE"

FIT_METHOD = (
    "ez-wo15b-gp-fit-v1: zero-mean GP on standardized features with an RBF "
    "kernel plus a white-noise term. Hyperparameters are chosen by "
    "maximizing the training-era marginal log-likelihood over a fixed grid, "
    "then confirmed by k-fold cross-validation on the same training set. No "
    "blind truth participates in either step"
)

MAGIC_NUMBERS = (2, 8, 20, 28, 50, 82, 126, 184)


def features_for(z: int, n: int) -> dict[str, float]:
    """The allowed feature vector for one nuclide, from identity alone."""
    a = z + n
    return {
        "Z": float(z),
        "N": float(n),
        "A": float(a),
        "asymmetry": (n - z) / a if a else 0.0,
        "Z_parity": float(z % 2),
        "N_parity": float(n % 2),
        "shell_distance_Z": float(min(abs(z - m) for m in MAGIC_NUMBERS)),
        "shell_distance_N": float(min(abs(n - m) for m in MAGIC_NUMBERS)),
    }


def assert_features_allowed(names: list[str] | tuple[str, ...]) -> None:
    """Refuse a feature set that reaches outside the declared vocabulary."""
    unknown = sorted(set(names) - set(ALLOWED_FEATURES))
    if unknown:
        raise ProtocolError(
            f"DISCREPANCY_FEATURE_FORBIDDEN: {unknown} is not in the "
            f"declared feature policy. {FEATURE_POLICY}"
        )


def assert_child_of_family(
    *, discrepancy_record: dict[str, Any], parent_family: str
) -> None:
    """A discrepancy model never earns its own independence group."""
    from elementzero.readiness import CHILD_FAMILY_RULE

    group = discrepancy_record.get("independence_group")
    if group != parent_family:
        raise ProtocolError(
            f"DISCREPANCY_INDEPENDENCE_CLAIM: a discrepancy child declared "
            f"group {group!r} but its parent family is {parent_family!r}. "
            f"{CHILD_FAMILY_RULE}"
        )
    if discrepancy_record.get("counts_as_independent_family"):
        raise ProtocolError(
            "DISCREPANCY_INDEPENDENCE_CLAIM: a discrepancy child may not "
            f"count as an independent family. {CHILD_FAMILY_RULE}"
        )


__all__ = [
    "ALLOWED_FEATURES",
    "FEATURE_POLICY",
    "FEATURE_POLICY_ID",
    "FIT_METHOD",
    "MAGIC_NUMBERS",
    "MODEL_TYPE_GP",
    "assert_child_of_family",
    "assert_features_allowed",
    "features_for",
]
