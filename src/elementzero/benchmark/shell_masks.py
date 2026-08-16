"""Hidden-shell neighborhood masks for EZ-B003 (WO-10).

EZ-B002 hides a rectangle of the chart and asks whether the models can
reconstruct the masses inside it. EZ-B003 hides the neighborhood of a *known*
shell closure and asks a harder question: after the closure region is withheld,
does the reconstructed mass surface still show the shell-gap structure that is
actually there?

A mask is geometry over identities (Z, N). It never carries a mass.

Mask geometry (WO-10 section 1), half-width one in v1::

    neutron closure N0:   N in {N0-1, N0, N0+1}, z_min <= Z <= z_max
    proton  closure Z0:   Z in {Z0-1, Z0, Z0+1}, n_min <= N <= n_max

Half-width one is the smallest mask that still makes the indicator at the
closure a prediction rather than a lookup, because ``delta2n(Z,N0)`` expands to
``2*B(Z,N0) - B(Z,N0-2) - B(Z,N0+2)``: the closure mass is withheld while its
two-step neighbors stay in training. Hiding one single point instead would leave
``N0-1`` and ``N0+1`` in training, and a model that interpolates two immediate
neighbors is not reconstructing shell structure.

Support rule (WO-10 section 2). A closure is only evaluable when enough
neighboring nuclei survive *outside* the mask to compute the requested derived
observables. The rule is preregistered, deterministic, and applied per chain
(one isotopic chain per Z for a neutron closure, one isotonic chain per N for a
proton closure)::

    chain is supported when
        it holds at least one eligible masked target,
        the indicator at the closure itself is computable, that is every one of
            its inputs (closure - 2, closure, closure + 2) is eligible,
        the two-step lower neighbor  (closure - 2) is eligible and outside the mask,
        the two-step upper neighbor  (closure + 2) is eligible and outside the mask,
        it holds at least MIN_CHAIN_LENGTH eligible nuclei outside the mask
            within the peak-search window,
        at least MIN_PEAK_CANDIDATES window positions have a computable indicator

    closure is EVALUABLE when
        at least MIN_EVALUABLE_CHAINS chains are supported
        and the mask holds at least MIN_TARGETS eligible targets

A closure that fails the rule is reported as ``NOT_EVALUABLE`` with its reasons.
It is never silently omitted, because a benchmark that quietly drops the
closures it cannot handle reports only the closures it can.

The Z (or N) span of a mask is itself derived from the support rule, before any
scoring: the span is the contiguous hull of every chain that holds an eligible
nucleus inside the closure neighborhood. Every chain in that hull is hidden,
including a chain the support rule refuses to score. The span is deliberately
*not* the hull of the supported chains only: a shell gap at N0 is a feature of
the closure coordinate, identical along every chain, so one unmasked chain still
carrying its own N0 neighborhood would hand the model the answer for all the
others. Support decides which chains are *scored*; the neighborhood is hidden
wherever it exists.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from elementzero.errors import ProtocolError, SchemaError
from elementzero.evidence.hashing import sha256_hex
from elementzero.physics.separation import (
    OBSERVABLE_DELTA2N,
    OBSERVABLE_DELTA2P,
    observable_inputs,
)

AXIS_NEUTRON = "neutron"
AXIS_PROTON = "proton"
AXES: tuple[str, ...] = (AXIS_NEUTRON, AXIS_PROTON)

# Availability set (WO-10 section "Candidate known closures"). These are the
# textbook closures the benchmark is allowed to ask about; which of them is
# actually produced is decided by the support rule below, never by how well a
# model happens to do on them.
KNOWN_NEUTRON_CLOSURES: tuple[int, ...] = (20, 28, 50, 82, 126)
KNOWN_PROTON_CLOSURES: tuple[int, ...] = (20, 28, 50, 82)

# Recommended production focus when the data support it (WO-10).
PRIMARY_NEUTRON_CLOSURES: tuple[int, ...] = (50, 82, 126)
PRIMARY_PROTON_CLOSURES: tuple[int, ...] = (28, 50, 82)

MASK_POLICY_ID = "ez-b003-neighborhood-mask-v1"
SUPPORT_POLICY_ID = "ez-b003-support-rule-v1"
CHALLENGE_POLICY_ID = "ez-b003-shell-challenge-v1"

STATUS_EVALUABLE = "EVALUABLE"
STATUS_NOT_EVALUABLE = "NOT_EVALUABLE"

# Preregistered support-rule and search-window settings.
DEFAULT_HALF_WIDTH = 1
MIN_CHAIN_LENGTH = 5
MIN_TARGETS = 6
MIN_EVALUABLE_CHAINS = 3
MIN_PEAK_CANDIDATES = 3
PEAK_WINDOW = 6

# Peak candidates share the parity of the closure. The two-nucleon difference
# cancels the pairing term only within one parity class, so mixing parities would
# rank a pairing artifact against a shell gap.
PEAK_PARITY_RULE = (
    "ez-b003-peak-window-v1: candidates are the positions c with "
    "abs(c - closure) <= PEAK_WINDOW and c congruent to closure modulo 2, whose "
    "indicator inputs are all present. Same parity only: the two-nucleon "
    "difference cancels the pairing term within one parity class, so a "
    "mixed-parity ranking would compare a pairing artifact with a shell gap."
)

CHALLENGE_MANIFEST_HASH_RULE = (
    "ez-b003-challenge-manifest-hash-v1: sha256 of canonical JSON of "
    '{"hash_rule", "challenge_policy_id", "mask_policy_id", "support_policy_id", '
    '"support_settings", "challenges": [{axis, closure, status, mask} sorted by '
    "(axis, closure)]}. Challenge order in the file and any generator metadata "
    "cannot change the digest; a mask bound, a closure, or an evaluability "
    "verdict always does."
)

MASK_HASH_RULE = (
    "ez-b003-mask-hash-v1: sha256 of canonical JSON of "
    '{"hash_rule", "mask_policy_id", "mask": mask.to_dict()}'
)

Point = tuple[int, int]

_NEUTRON_KEYS = frozenset({"axis", "closure_N", "half_width", "z_min", "z_max"})
_PROTON_KEYS = frozenset({"axis", "closure_Z", "half_width", "n_min", "n_max"})
_OPTIONAL_KEYS = frozenset({"mask_id", "hidden_N", "hidden_Z", "mask_policy_id"})


def normalize_points(points: Iterable[Point]) -> list[Point]:
    """Deduplicated, sorted (Z, N) lattice points."""
    return sorted({(int(z), int(n)) for z, n in points})


def _as_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"shell mask {name} must be an int, got {value!r}")
    return int(value)


# --------------------------------------------------------------------------- #
# The mask                                                                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ShellMask:
    """One hidden closure neighborhood, stored in one normalized form.

    ``closure`` is N0 for a neutron mask and Z0 for a proton mask. ``span_min``
    and ``span_max`` bound the orthogonal axis: Z for a neutron mask, N for a
    proton mask.
    """

    axis: str
    closure: int
    half_width: int
    span_min: int
    span_max: int

    def __post_init__(self) -> None:
        if self.axis not in AXES:
            raise SchemaError(f"unsupported mask axis {self.axis!r}; supported axes are {list(AXES)}")
        for name in ("closure", "half_width", "span_min", "span_max"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise SchemaError(f"shell mask {name} must be an int, got {value!r}")
        if self.half_width < 1:
            raise SchemaError(f"shell mask half_width must be at least 1, got {self.half_width}")
        if self.closure - self.half_width < 0:
            raise SchemaError(
                f"shell mask around {self.closure} with half width {self.half_width} "
                "would hide a negative nucleon number"
            )
        if self.span_min < 0:
            raise SchemaError(f"shell mask span_min must be non-negative, got {self.span_min}")
        if self.span_min > self.span_max:
            raise SchemaError(
                f"shell mask span_min {self.span_min} exceeds span_max {self.span_max}"
            )

    # -- identity ---------------------------------------------------------- #

    @property
    def hidden_values(self) -> tuple[int, ...]:
        """The withheld closure-axis values, e.g. (81, 82, 83) for N0 = 82."""
        return tuple(
            range(self.closure - self.half_width, self.closure + self.half_width + 1)
        )

    @property
    def closure_axis_label(self) -> str:
        return "N" if self.axis == AXIS_NEUTRON else "Z"

    @property
    def span_axis_label(self) -> str:
        return "Z" if self.axis == AXIS_NEUTRON else "N"

    @property
    def mask_id(self) -> str:
        """Deterministic, human-readable identity derived from the geometry."""
        return (
            f"shell-{self.closure_axis_label}{self.closure}"
            f"-w{self.half_width}"
            f"-{self.span_axis_label}{self.span_min}-{self.span_max}"
        )

    @property
    def challenge_id(self) -> str:
        """Identity of the closure being asked about, independent of the span."""
        return f"{self.axis}-{self.closure_axis_label}{self.closure}"

    @property
    def sort_key(self) -> tuple[str, int, int, int, int]:
        return (self.axis, self.closure, self.half_width, self.span_min, self.span_max)

    @property
    def lattice_sites(self) -> int:
        return len(self.hidden_values) * (self.span_max - self.span_min + 1)

    # -- membership -------------------------------------------------------- #

    def closure_coordinate(self, z: int, n: int) -> int:
        """The coordinate the mask hides: N for a neutron mask, Z for a proton one."""
        return int(n) if self.axis == AXIS_NEUTRON else int(z)

    def chain_key(self, z: int, n: int) -> int:
        """The chain a nucleus belongs to: Z for a neutron mask, N for a proton one."""
        return int(z) if self.axis == AXIS_NEUTRON else int(n)

    def point(self, *, chain: int, coordinate: int) -> Point:
        """The (Z, N) point of one chain at one closure-axis coordinate."""
        if self.axis == AXIS_NEUTRON:
            return (int(chain), int(coordinate))
        return (int(coordinate), int(chain))

    def contains(self, z: int, n: int) -> bool:
        return (
            self.closure_coordinate(z, n) in self.hidden_values
            and self.span_min <= self.chain_key(z, n) <= self.span_max
        )

    def contains_id(self, nuclide_id: str) -> bool:
        from elementzero.data.identity import parse_nuclide_id

        z, n = parse_nuclide_id(nuclide_id)
        return self.contains(z, n)

    def members(self, points: Iterable[Point]) -> list[Point]:
        return [p for p in normalize_points(points) if self.contains(*p)]

    def outside(self, points: Iterable[Point]) -> list[Point]:
        return [p for p in normalize_points(points) if not self.contains(*p)]

    def chains(self, points: Iterable[Point]) -> list[int]:
        """Chains that hold at least one masked nucleus, in ascending order."""
        return sorted({self.chain_key(*p) for p in self.members(points)})

    # -- derived observable ------------------------------------------------ #

    @property
    def indicator(self) -> str:
        return OBSERVABLE_DELTA2N if self.axis == AXIS_NEUTRON else OBSERVABLE_DELTA2P

    def indicator_inputs(self, *, chain: int, coordinate: int) -> tuple[Point, ...]:
        z, n = self.point(chain=chain, coordinate=coordinate)
        return observable_inputs(self.indicator, z=z, n=n)

    def peak_candidates(self, *, window: int = PEAK_WINDOW) -> tuple[int, ...]:
        """Preregistered search window, same parity as the closure."""
        if window < 0:
            raise ValueError("peak window must be non-negative")
        lo = max(0, self.closure - window)
        return tuple(
            c
            for c in range(lo, self.closure + window + 1)
            if (c - self.closure) % 2 == 0
        )

    # -- serialization ----------------------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        if self.axis == AXIS_NEUTRON:
            payload: dict[str, Any] = {
                "axis": self.axis,
                "closure_N": self.closure,
                "half_width": self.half_width,
                "hidden_N": list(self.hidden_values),
                "z_min": self.span_min,
                "z_max": self.span_max,
            }
        else:
            payload = {
                "axis": self.axis,
                "closure_Z": self.closure,
                "half_width": self.half_width,
                "hidden_Z": list(self.hidden_values),
                "n_min": self.span_min,
                "n_max": self.span_max,
            }
        payload["mask_id"] = self.mask_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ShellMask:
        if not isinstance(payload, dict):
            raise SchemaError(f"shell mask must be an object, got {type(payload).__name__}")
        axis = payload.get("axis")
        if axis not in AXES:
            raise SchemaError(f"unsupported mask axis {axis!r}; supported axes are {list(AXES)}")
        required = _NEUTRON_KEYS if axis == AXIS_NEUTRON else _PROTON_KEYS
        missing = sorted(required - set(payload))
        if missing:
            raise SchemaError(f"{axis} shell mask is missing fields: {missing}")
        unknown = sorted(set(payload) - required - _OPTIONAL_KEYS)
        if unknown:
            raise SchemaError(f"{axis} shell mask has unsupported fields: {unknown}")
        if axis == AXIS_NEUTRON:
            mask = neutron_mask(
                payload["closure_N"],
                z_min=payload["z_min"],
                z_max=payload["z_max"],
                half_width=payload["half_width"],
            )
            declared_hidden = payload.get("hidden_N")
        else:
            mask = proton_mask(
                payload["closure_Z"],
                n_min=payload["n_min"],
                n_max=payload["n_max"],
                half_width=payload["half_width"],
            )
            declared_hidden = payload.get("hidden_Z")
        if declared_hidden is not None and list(declared_hidden) != list(mask.hidden_values):
            raise SchemaError(
                f"declared hidden values {list(declared_hidden)} do not match the mask "
                f"geometry {list(mask.hidden_values)}"
            )
        declared_id = payload.get("mask_id")
        if declared_id is not None and declared_id != mask.mask_id:
            raise SchemaError(
                f"mask_id {declared_id!r} does not match the geometry ({mask.mask_id!r})"
            )
        return mask


def neutron_mask(
    closure_n: int, *, z_min: int, z_max: int, half_width: int = DEFAULT_HALF_WIDTH
) -> ShellMask:
    return ShellMask(
        axis=AXIS_NEUTRON,
        closure=_as_int(closure_n, "closure_N"),
        half_width=_as_int(half_width, "half_width"),
        span_min=_as_int(z_min, "z_min"),
        span_max=_as_int(z_max, "z_max"),
    )


def proton_mask(
    closure_z: int, *, n_min: int, n_max: int, half_width: int = DEFAULT_HALF_WIDTH
) -> ShellMask:
    return ShellMask(
        axis=AXIS_PROTON,
        closure=_as_int(closure_z, "closure_Z"),
        half_width=_as_int(half_width, "half_width"),
        span_min=_as_int(n_min, "n_min"),
        span_max=_as_int(n_max, "n_max"),
    )


def mask_hash(mask: ShellMask) -> str:
    return sha256_hex(
        {
            "hash_rule": MASK_HASH_RULE,
            "mask_policy_id": MASK_POLICY_ID,
            "mask": mask.to_dict(),
        }
    )


def split_points(points: Iterable[Point], mask: ShellMask) -> dict[str, list[Point]]:
    """Shell split: targets inside the masked neighborhood, training outside it."""
    ordered = normalize_points(points)
    return {
        "targets": [p for p in ordered if mask.contains(*p)],
        "training": [p for p in ordered if not mask.contains(*p)],
    }


# --------------------------------------------------------------------------- #
# Support rule                                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ChainSupport:
    """Whether one chain can supply the derived observables of a closure."""

    chain: int
    n_masked_targets: int
    n_window_training: int
    lower_support: bool
    upper_support: bool
    closure_computable: bool
    n_peak_candidates: int
    supported: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain": self.chain,
            "n_masked_targets": self.n_masked_targets,
            "n_window_training": self.n_window_training,
            "lower_support": self.lower_support,
            "upper_support": self.upper_support,
            "closure_computable": self.closure_computable,
            "n_peak_candidates": self.n_peak_candidates,
            "supported": self.supported,
            "reasons": list(self.reasons),
        }


def support_settings(
    *,
    half_width: int = DEFAULT_HALF_WIDTH,
    min_chain_length: int = MIN_CHAIN_LENGTH,
    min_targets: int = MIN_TARGETS,
    min_evaluable_chains: int = MIN_EVALUABLE_CHAINS,
    min_peak_candidates: int = MIN_PEAK_CANDIDATES,
    peak_window: int = PEAK_WINDOW,
) -> dict[str, Any]:
    """The frozen support-rule settings, as written into a manifest."""
    return {
        "support_policy_id": SUPPORT_POLICY_ID,
        "mask_policy_id": MASK_POLICY_ID,
        "half_width": int(half_width),
        "MIN_CHAIN_LENGTH": int(min_chain_length),
        "MIN_TARGETS": int(min_targets),
        "MIN_EVALUABLE_CHAINS": int(min_evaluable_chains),
        "MIN_PEAK_CANDIDATES": int(min_peak_candidates),
        "PEAK_WINDOW": int(peak_window),
        "peak_parity_rule": PEAK_PARITY_RULE,
        "chain_rule": (
            "a chain is supported when it holds a masked target, the indicator at "
            "the closure itself is computable, both two-step neighbors of the "
            "closure are eligible and outside the mask, it holds at least "
            "MIN_CHAIN_LENGTH eligible nuclei outside the mask inside the search "
            "window, and at least MIN_PEAK_CANDIDATES window positions have all "
            "indicator inputs present"
        ),
        "span_rule": (
            "the masked span is the contiguous hull of every chain holding an "
            "eligible nucleus inside the closure neighborhood, not the hull of the "
            "supported chains: the closure feature is identical along every chain, "
            "so an unmasked chain still carrying its own closure neighborhood would "
            "reveal it for all the others. Support decides which chains are scored"
        ),
        "closure_rule": (
            "a closure is EVALUABLE when at least MIN_EVALUABLE_CHAINS chains are "
            "supported and the mask holds at least MIN_TARGETS eligible targets; "
            "otherwise it is reported NOT_EVALUABLE, never omitted"
        ),
        "not_evaluable_rule": (
            "NOT_EVALUABLE closures are listed with their reasons and carry no "
            "discovery metrics; they are still part of the reported challenge set"
        ),
    }


def chain_support(
    mask: ShellMask,
    points: Iterable[Point],
    *,
    chain: int,
    min_chain_length: int = MIN_CHAIN_LENGTH,
    min_peak_candidates: int = MIN_PEAK_CANDIDATES,
    peak_window: int = PEAK_WINDOW,
) -> ChainSupport:
    """Support of one chain, computed from identities alone."""
    ordered = set(normalize_points(points))
    hidden = set(mask.hidden_values)

    def available(coordinate: int) -> bool:
        """Eligible and not withheld by the mask."""
        return (
            mask.point(chain=chain, coordinate=coordinate) in ordered
            and coordinate not in hidden
        )

    masked = [c for c in hidden if mask.point(chain=chain, coordinate=c) in ordered]
    window = [
        c
        for c in range(max(0, mask.closure - peak_window), mask.closure + peak_window + 1)
        if available(c)
    ]
    candidates = [
        c
        for c in mask.peak_candidates(window=peak_window)
        if all(
            point in ordered
            for point in mask.indicator_inputs(chain=chain, coordinate=c)
        )
    ]
    lower = available(mask.closure - 2)
    upper = available(mask.closure + 2)
    # The indicator at the closure is the question being asked. If one of its
    # inputs is missing -- most often because the closure nucleus itself is not
    # ground-truth eligible -- this chain can never answer it, no matter how many
    # other window positions it can compute.
    closure_computable = mask.closure in candidates

    reasons = []
    if not masked:
        reasons.append("chain holds no eligible masked target")
    if not closure_computable:
        missing = sorted(
            point
            for point in mask.indicator_inputs(chain=chain, coordinate=mask.closure)
            if point not in ordered
        )
        reasons.append(
            f"the indicator at the closure is not computable; missing eligible "
            f"inputs {missing}"
        )
    if not lower:
        reasons.append(f"two-step lower neighbor {mask.closure - 2} is not available outside the mask")
    if not upper:
        reasons.append(f"two-step upper neighbor {mask.closure + 2} is not available outside the mask")
    if len(window) < int(min_chain_length):
        reasons.append(
            f"chain has {len(window)} eligible nuclei outside the mask in the search "
            f"window; MIN_CHAIN_LENGTH is {int(min_chain_length)}"
        )
    if len(candidates) < int(min_peak_candidates):
        reasons.append(
            f"chain has {len(candidates)} computable indicator positions; "
            f"MIN_PEAK_CANDIDATES is {int(min_peak_candidates)}"
        )
    return ChainSupport(
        chain=int(chain),
        n_masked_targets=len(masked),
        n_window_training=len(window),
        lower_support=lower,
        upper_support=upper,
        closure_computable=closure_computable,
        n_peak_candidates=len(candidates),
        supported=not reasons,
        reasons=tuple(reasons),
    )


def candidate_chains(axis: str, points: Iterable[Point]) -> list[int]:
    """Every chain present in the snapshot, for the orthogonal axis of ``axis``."""
    if axis not in AXES:
        raise SchemaError(f"unsupported mask axis {axis!r}")
    ordered = normalize_points(points)
    if axis == AXIS_NEUTRON:
        return sorted({z for z, _ in ordered})
    return sorted({n for _, n in ordered})


def provisional_mask(
    axis: str,
    closure: int,
    points: Iterable[Point],
    *,
    half_width: int = DEFAULT_HALF_WIDTH,
) -> ShellMask:
    """A mask spanning every chain in the snapshot.

    Chain support does not depend on the span (both two-step neighbors and every
    window position are evaluated inside one chain), so support can be measured
    on this mask and the final span derived from the result.
    """
    chains = candidate_chains(axis, points)
    if not chains:
        raise ProtocolError("point set is empty; a shell mask needs a snapshot")
    if axis == AXIS_NEUTRON:
        return neutron_mask(closure, z_min=chains[0], z_max=chains[-1], half_width=half_width)
    return proton_mask(closure, n_min=chains[0], n_max=chains[-1], half_width=half_width)


@dataclass(frozen=True)
class ShellChallenge:
    """One closure, its mask if any, and the verdict of the support rule."""

    axis: str
    closure: int
    status: str
    mask: ShellMask | None
    chain_support: tuple[ChainSupport, ...]
    n_targets: int
    n_training: int
    reasons: tuple[str, ...]

    @property
    def challenge_id(self) -> str:
        label = "N" if self.axis == AXIS_NEUTRON else "Z"
        return f"{self.axis}-{label}{self.closure}"

    @property
    def evaluable(self) -> bool:
        return self.status == STATUS_EVALUABLE

    @property
    def supported_chains(self) -> tuple[int, ...]:
        return tuple(s.chain for s in self.chain_support if s.supported)

    @property
    def unsupported_chains(self) -> tuple[int, ...]:
        return tuple(s.chain for s in self.chain_support if not s.supported)

    @property
    def sort_key(self) -> tuple[str, int]:
        return (self.axis, self.closure)

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "axis": self.axis,
            "closure": self.closure,
            "status": self.status,
            "mask": self.mask.to_dict() if self.mask is not None else None,
            "mask_id": self.mask.mask_id if self.mask is not None else None,
            "indicator": self.mask.indicator if self.mask is not None else None,
            "n_targets": self.n_targets,
            "n_training": self.n_training,
            "n_supported_chains": len(self.supported_chains),
            "supported_chains": list(self.supported_chains),
            "unsupported_chains": list(self.unsupported_chains),
            "chain_support": [s.to_dict() for s in self.chain_support],
            "reasons": list(self.reasons),
        }


def evaluate_challenge(
    axis: str,
    closure: int,
    points: Iterable[Point],
    *,
    half_width: int = DEFAULT_HALF_WIDTH,
    min_chain_length: int = MIN_CHAIN_LENGTH,
    min_targets: int = MIN_TARGETS,
    min_evaluable_chains: int = MIN_EVALUABLE_CHAINS,
    min_peak_candidates: int = MIN_PEAK_CANDIDATES,
    peak_window: int = PEAK_WINDOW,
) -> ShellChallenge:
    """Apply the support rule to one closure and return its challenge record."""
    if axis not in AXES:
        raise SchemaError(f"unsupported mask axis {axis!r}; supported axes are {list(AXES)}")
    ordered = normalize_points(points)
    if not ordered:
        raise ProtocolError("point set is empty; a shell challenge needs a snapshot")

    try:
        probe = provisional_mask(axis, closure, ordered, half_width=half_width)
    except SchemaError as exc:
        return ShellChallenge(
            axis=axis,
            closure=int(closure),
            status=STATUS_NOT_EVALUABLE,
            mask=None,
            chain_support=(),
            n_targets=0,
            n_training=len(ordered),
            reasons=(str(exc),),
        )

    supports = [
        chain_support(
            probe,
            ordered,
            chain=chain,
            min_chain_length=min_chain_length,
            min_peak_candidates=min_peak_candidates,
            peak_window=peak_window,
        )
        for chain in candidate_chains(axis, ordered)
    ]
    supported = [s.chain for s in supports if s.supported]
    reasons = []
    if len(supported) < int(min_evaluable_chains):
        reasons.append(
            f"{len(supported)} chains satisfy the support rule; "
            f"MIN_EVALUABLE_CHAINS is {int(min_evaluable_chains)}"
        )
    # Every chain that holds an eligible nucleus inside the closure neighborhood.
    # These are the chains that carry the structure being hidden, whether or not
    # the support rule can score them.
    maskable = probe.chains(ordered)
    if not supported or not maskable:
        return ShellChallenge(
            axis=axis,
            closure=int(closure),
            status=STATUS_NOT_EVALUABLE,
            mask=None,
            chain_support=tuple(supports),
            n_targets=0,
            n_training=len(ordered),
            reasons=tuple(reasons),
        )

    # The span is the contiguous hull of the maskable chains; every chain inside
    # it is hidden, supported or not.
    if axis == AXIS_NEUTRON:
        mask = neutron_mask(
            closure, z_min=maskable[0], z_max=maskable[-1], half_width=half_width
        )
    else:
        mask = proton_mask(
            closure, n_min=maskable[0], n_max=maskable[-1], half_width=half_width
        )
    split = split_points(ordered, mask)
    in_span = [s for s in supports if mask.span_min <= s.chain <= mask.span_max]
    if len(split["targets"]) < int(min_targets):
        reasons.append(
            f"mask holds {len(split['targets'])} eligible targets; "
            f"MIN_TARGETS is {int(min_targets)}"
        )
    if not split["training"]:
        reasons.append("mask leaves no training nuclei outside it")
    return ShellChallenge(
        axis=axis,
        closure=int(closure),
        status=STATUS_NOT_EVALUABLE if reasons else STATUS_EVALUABLE,
        mask=mask,
        chain_support=tuple(in_span),
        n_targets=len(split["targets"]),
        n_training=len(split["training"]),
        reasons=tuple(reasons),
    )


def assert_mask_populated(
    mask: ShellMask, points: Iterable[Point], *, min_targets: int = 1
) -> int:
    """An empty mask is a protocol error, never a zero-target run."""
    count = len(mask.members(points))
    if count < max(1, int(min_targets)):
        raise ProtocolError(
            f"mask {mask.mask_id} holds {count} eligible nuclei; "
            f"at least {max(1, int(min_targets))} are required"
        )
    return count


def generate_challenges(
    points: Iterable[Point],
    *,
    neutron_closures: Sequence[int] = KNOWN_NEUTRON_CLOSURES,
    proton_closures: Sequence[int] = KNOWN_PROTON_CLOSURES,
    half_width: int = DEFAULT_HALF_WIDTH,
    min_chain_length: int = MIN_CHAIN_LENGTH,
    min_targets: int = MIN_TARGETS,
    min_evaluable_chains: int = MIN_EVALUABLE_CHAINS,
    min_peak_candidates: int = MIN_PEAK_CANDIDATES,
    peak_window: int = PEAK_WINDOW,
) -> dict[str, Any]:
    """Every declared closure of the availability set, evaluable or not."""
    ordered = normalize_points(points)
    challenges = [
        evaluate_challenge(
            axis,
            closure,
            ordered,
            half_width=half_width,
            min_chain_length=min_chain_length,
            min_targets=min_targets,
            min_evaluable_chains=min_evaluable_chains,
            min_peak_candidates=min_peak_candidates,
            peak_window=peak_window,
        )
        for axis, closures in (
            (AXIS_NEUTRON, neutron_closures),
            (AXIS_PROTON, proton_closures),
        )
        for closure in sorted(set(int(c) for c in closures))
    ]
    challenges.sort(key=lambda c: c.sort_key)
    return {
        "settings": {
            **support_settings(
                half_width=half_width,
                min_chain_length=min_chain_length,
                min_targets=min_targets,
                min_evaluable_chains=min_evaluable_chains,
                min_peak_candidates=min_peak_candidates,
                peak_window=peak_window,
            ),
            "availability_set": {
                AXIS_NEUTRON: [int(c) for c in sorted(set(neutron_closures))],
                AXIS_PROTON: [int(c) for c in sorted(set(proton_closures))],
            },
        },
        "n_eligible_points": len(ordered),
        "challenges": challenges,
        "evaluable": [c for c in challenges if c.evaluable],
        "not_evaluable": [c for c in challenges if not c.evaluable],
    }


# --------------------------------------------------------------------------- #
# Challenge manifest                                                          #
# --------------------------------------------------------------------------- #


def _challenge_digest_entry(challenge: dict[str, Any]) -> dict[str, Any]:
    return {
        "axis": challenge["axis"],
        "closure": challenge["closure"],
        "status": challenge["status"],
        "mask": challenge["mask"],
    }


def challenge_manifest_hash(challenges: Iterable[Any] | dict[str, Any]) -> str:
    """Stable digest of a challenge set.

    The digest covers the masks and the evaluability verdicts only, in canonical
    order, so reordering the file or adding generator provenance cannot change it
    while a changed bound, closure, or verdict always does.
    """
    payload = {
        "hash_rule": CHALLENGE_MANIFEST_HASH_RULE,
        "challenge_policy_id": CHALLENGE_POLICY_ID,
        "mask_policy_id": MASK_POLICY_ID,
        "support_policy_id": SUPPORT_POLICY_ID,
        "challenges": [_challenge_digest_entry(c) for c in _as_challenge_dicts(challenges)],
    }
    return sha256_hex(payload)


def _as_challenge_dicts(challenges: Iterable[Any] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(challenges, dict):
        items = list(challenges.get("challenges", []))
    else:
        items = list(challenges)
    payloads = []
    for item in items:
        payload = item.to_dict() if isinstance(item, ShellChallenge) else dict(item)
        if payload.get("axis") not in AXES:
            raise SchemaError(f"challenge has unsupported axis {payload.get('axis')!r}")
        if payload.get("status") not in (STATUS_EVALUABLE, STATUS_NOT_EVALUABLE):
            raise SchemaError(f"challenge has unsupported status {payload.get('status')!r}")
        if payload.get("mask") is not None:
            # Re-derive the mask so a hand-edited bound cannot survive a load.
            payload["mask"] = ShellMask.from_dict(payload["mask"]).to_dict()
        elif payload["status"] == STATUS_EVALUABLE:
            raise SchemaError(
                f"challenge {payload.get('challenge_id')!r} is EVALUABLE without a mask"
            )
        payloads.append(payload)
    if not payloads:
        raise ProtocolError("a challenge manifest must declare at least one closure")
    ids = [f"{p['axis']}-{p['closure']}" for p in payloads]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise SchemaError(f"challenge manifest repeats closures: {duplicates}")
    return sorted(payloads, key=lambda p: (p["axis"], p["closure"]))


def challenge_manifest(
    challenges: Sequence[Any],
    *,
    benchmark_id: str,
    protocol_version: str,
    settings: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """The preregistered challenge manifest written to ``challenges.json``."""
    ordered = _as_challenge_dicts(challenges)
    evaluable = [c for c in ordered if c["status"] == STATUS_EVALUABLE]
    payload: dict[str, Any] = {
        "benchmark_id": benchmark_id,
        "protocol_version": protocol_version,
        "challenge_policy_id": CHALLENGE_POLICY_ID,
        "mask_policy_id": MASK_POLICY_ID,
        "support_policy_id": SUPPORT_POLICY_ID,
        "challenge_manifest_hash_rule": CHALLENGE_MANIFEST_HASH_RULE,
        "n_challenges": len(ordered),
        "n_evaluable": len(evaluable),
        "n_not_evaluable": len(ordered) - len(evaluable),
        "challenges": ordered,
        "challenge_ids": [c["challenge_id"] for c in ordered],
        "evaluable_challenge_ids": [c["challenge_id"] for c in evaluable],
        "not_evaluable_challenge_ids": [
            c["challenge_id"] for c in ordered if c["status"] != STATUS_EVALUABLE
        ],
        "mask_ids": [c["mask_id"] for c in evaluable],
        "challenge_manifest_hash": challenge_manifest_hash(ordered),
    }
    payload["support_settings"] = dict(settings or support_settings())
    if source is not None:
        payload["source"] = dict(source)
    if notes:
        payload["notes"] = notes
    return payload


def load_challenge_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse and verify a challenge manifest payload."""
    ordered = _as_challenge_dicts(payload)
    expected = challenge_manifest_hash(ordered)
    recorded = payload.get("challenge_manifest_hash")
    if recorded is not None and recorded != expected:
        raise ProtocolError(
            f"challenge manifest hash {recorded!r} does not match the declared "
            f"challenges ({expected!r})"
        )
    declared_ids = payload.get("challenge_ids")
    if declared_ids is not None and sorted(declared_ids) != sorted(
        c["challenge_id"] for c in ordered
    ):
        raise ProtocolError("challenge manifest challenge_ids disagree with its challenges")
    masks = {
        c["challenge_id"]: ShellMask.from_dict(c["mask"])
        for c in ordered
        if c["mask"] is not None
    }
    evaluable = [c["challenge_id"] for c in ordered if c["status"] == STATUS_EVALUABLE]
    declared_evaluable = payload.get("evaluable_challenge_ids")
    if declared_evaluable is not None and sorted(declared_evaluable) != sorted(evaluable):
        raise ProtocolError(
            "challenge manifest evaluable_challenge_ids disagree with the recorded statuses"
        )
    return {
        "challenges": ordered,
        "masks": masks,
        "evaluable_challenge_ids": evaluable,
        "not_evaluable_challenge_ids": [
            c["challenge_id"] for c in ordered if c["status"] != STATUS_EVALUABLE
        ],
        "challenge_manifest_hash": expected,
        "benchmark_id": payload.get("benchmark_id"),
        "protocol_version": payload.get("protocol_version"),
        "support_settings": payload.get("support_settings"),
        "source": payload.get("source"),
    }


def mask_by_id(manifest: dict[str, Any], mask_id: str) -> ShellMask:
    for mask in manifest["masks"].values():
        if mask.mask_id == mask_id:
            return mask
    known = sorted(m.mask_id for m in manifest["masks"].values())
    raise ProtocolError(f"mask {mask_id!r} is not in the manifest; declared masks are {known}")
