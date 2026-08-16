"""Geographic regions of the known nuclear chart (EZ-B002, WO-09).

EZ-B001 asks whether the models could predict later historical knowledge.
EZ-B002 asks whether they can reconstruct a region of the *known* chart when
every truth value inside that region is withheld. A region is therefore a
purely geometric object over identities (Z, N); it never carries a mass.

Supported region types (WO-09 section 2)::

    rectangle   z_min <= Z <= z_max  and  n_min <= N <= n_max
    isotopic    Z fixed,             n_min <= N <= n_max
    isotonic    N fixed,             z_min <= Z <= z_max

All three are stored in one normalized rectangle form: an isotopic segment is a
rectangle with ``z_min == z_max`` and an isotonic segment is a rectangle with
``n_min == n_max``. Membership is inclusive on every bound.

Region generation (WO-09 section 3) must not be hand-picked, so the candidate
generator is deterministic:

1. every eligible nucleus is used as the lower-left corner of one fixed-size
   ``z_span x n_span`` window,
2. windows with fewer than ``min_targets`` eligible nuclei are dropped,
3. windows with training support on fewer than ``min_supported_sides`` of their
   four faces are dropped,
4. survivors are sorted by ``(Z band, -n_targets, region_id)``, which depends
   only on the source table and never on model performance,
5. a preregistered number per Z band is selected, spanning light/medium/heavy Z.

The selected manifest is frozen (``experiments/EZ-B002-v1/regions.json``) before
any model is scored, and its hash enters the KnowledgeFreeze and the
ModelFitFact so a region set cannot be swapped after the fact.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from elementzero.benchmark.distance import REGION_BOUNDS, l1_distance, region_for_z
from elementzero.errors import ProtocolError, SchemaError
from elementzero.evidence.hashing import sha256_hex

REGION_TYPE_RECTANGLE = "rectangle"
REGION_TYPE_ISOTOPIC = "isotopic"
REGION_TYPE_ISOTONIC = "isotonic"
REGION_TYPES: tuple[str, ...] = (
    REGION_TYPE_RECTANGLE,
    REGION_TYPE_ISOTOPIC,
    REGION_TYPE_ISOTONIC,
)

REGION_POLICY_ID = "ez-b002-region-types-v1"
CANDIDATE_POLICY_ID = "ez-b002-rectangle-window-candidates-v1"
SELECTION_POLICY_ID = "ez-b002-z-band-selection-v1"

REGION_MANIFEST_HASH_RULE = (
    "ez-b002-region-manifest-hash-v1: sha256 of canonical JSON of "
    '{"hash_rule", "region_policy_id", "regions": [region.to_dict() sorted by '
    "(region_type, z_min, z_max, n_min, n_max)]}. Region order in the file and "
    "any generator metadata cannot change the digest; a bound, a type, or a "
    "membership change always does."
)

# Preregistered candidate-generator settings (WO-09 section 3). The window is
# deliberately larger than one lattice step in both directions so a selected
# region contains points at several extrapolation depths, not only a rim.
DEFAULT_Z_SPAN = 4
DEFAULT_N_SPAN = 5
DEFAULT_MIN_TARGETS = 8
DEFAULT_MIN_SUPPORTED_SIDES = 2
DEFAULT_REGIONS_PER_BAND = 1

# The first production benchmark uses rectangles spanning three Z bands. The
# bands themselves are the EZ-B001 Z bands (src/elementzero/benchmark/distance.py),
# so B001 and B002 diagnostics stay comparable.
SELECTION_Z_BANDS: tuple[str, ...] = ("light", "medium", "heavy")

SIDE_Z_LOW = "z_low"
SIDE_Z_HIGH = "z_high"
SIDE_N_LOW = "n_low"
SIDE_N_HIGH = "n_high"
SIDE_IDS: tuple[str, ...] = (SIDE_N_HIGH, SIDE_N_LOW, SIDE_Z_HIGH, SIDE_Z_LOW)

Point = tuple[int, int]

_RECTANGLE_KEYS = frozenset({"type", "z_min", "z_max", "n_min", "n_max"})
_ISOTOPIC_KEYS = frozenset({"type", "Z", "n_min", "n_max"})
_ISOTONIC_KEYS = frozenset({"type", "N", "z_min", "z_max"})
_OPTIONAL_KEYS = frozenset({"region_id", "z_band"})


@dataclass(frozen=True)
class Region:
    """One contiguous block of the (Z, N) lattice, stored in rectangle form."""

    region_type: str
    z_min: int
    z_max: int
    n_min: int
    n_max: int

    def __post_init__(self) -> None:
        if self.region_type not in REGION_TYPES:
            raise SchemaError(
                f"unsupported region type {self.region_type!r}; supported types are {list(REGION_TYPES)}"
            )
        for name in ("z_min", "z_max", "n_min", "n_max"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise SchemaError(f"region {name} must be an int, got {value!r}")
            if value < 0:
                raise SchemaError(f"region {name} must be non-negative, got {value}")
        if self.z_min > self.z_max:
            raise SchemaError(f"region z_min {self.z_min} exceeds z_max {self.z_max}")
        if self.n_min > self.n_max:
            raise SchemaError(f"region n_min {self.n_min} exceeds n_max {self.n_max}")
        if self.region_type == REGION_TYPE_ISOTOPIC and self.z_min != self.z_max:
            raise SchemaError(
                f"isotopic region spans Z {self.z_min}..{self.z_max}; an isotopic segment fixes one Z"
            )
        if self.region_type == REGION_TYPE_ISOTONIC and self.n_min != self.n_max:
            raise SchemaError(
                f"isotonic region spans N {self.n_min}..{self.n_max}; an isotonic segment fixes one N"
            )

    # -- identity ---------------------------------------------------------- #

    @property
    def region_id(self) -> str:
        """Deterministic, human-readable identity derived from the bounds."""
        if self.region_type == REGION_TYPE_ISOTOPIC:
            return f"isotopic-Z{self.z_min}-N{self.n_min}-{self.n_max}"
        if self.region_type == REGION_TYPE_ISOTONIC:
            return f"isotonic-N{self.n_min}-Z{self.z_min}-{self.z_max}"
        return f"rect-Z{self.z_min}-{self.z_max}-N{self.n_min}-{self.n_max}"

    @property
    def sort_key(self) -> tuple[str, int, int, int, int]:
        return (self.region_type, self.z_min, self.z_max, self.n_min, self.n_max)

    @property
    def z_band(self) -> str:
        """Preregistered Z band of the region, taken at its lowest Z."""
        return region_for_z(self.z_min)

    @property
    def lattice_sites(self) -> int:
        return (self.z_max - self.z_min + 1) * (self.n_max - self.n_min + 1)

    # -- membership -------------------------------------------------------- #

    def contains(self, z: int, n: int) -> bool:
        """Inclusive membership test on both axes."""
        return self.z_min <= int(z) <= self.z_max and self.n_min <= int(n) <= self.n_max

    def contains_id(self, nuclide_id: str) -> bool:
        from elementzero.data.identity import parse_nuclide_id

        z, n = parse_nuclide_id(nuclide_id)
        return self.contains(z, n)

    def members(self, points: Iterable[Point]) -> list[Point]:
        return sorted({(int(z), int(n)) for z, n in points if self.contains(z, n)})

    def outside(self, points: Iterable[Point]) -> list[Point]:
        return sorted({(int(z), int(n)) for z, n in points if not self.contains(z, n)})

    # -- serialization ----------------------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        """Only the keys the declared type owns, plus the derived region_id."""
        if self.region_type == REGION_TYPE_ISOTOPIC:
            payload: dict[str, Any] = {
                "type": self.region_type,
                "Z": self.z_min,
                "n_min": self.n_min,
                "n_max": self.n_max,
            }
        elif self.region_type == REGION_TYPE_ISOTONIC:
            payload = {
                "type": self.region_type,
                "N": self.n_min,
                "z_min": self.z_min,
                "z_max": self.z_max,
            }
        else:
            payload = {
                "type": self.region_type,
                "z_min": self.z_min,
                "z_max": self.z_max,
                "n_min": self.n_min,
                "n_max": self.n_max,
            }
        payload["region_id"] = self.region_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Region:
        if not isinstance(payload, dict):
            raise SchemaError(f"region must be an object, got {type(payload).__name__}")
        region_type = payload.get("type")
        if region_type not in REGION_TYPES:
            raise SchemaError(
                f"unsupported region type {region_type!r}; supported types are {list(REGION_TYPES)}"
            )
        required = {
            REGION_TYPE_RECTANGLE: _RECTANGLE_KEYS,
            REGION_TYPE_ISOTOPIC: _ISOTOPIC_KEYS,
            REGION_TYPE_ISOTONIC: _ISOTONIC_KEYS,
        }[region_type]
        missing = sorted(required - set(payload))
        if missing:
            raise SchemaError(f"{region_type} region is missing fields: {missing}")
        unknown = sorted(set(payload) - required - _OPTIONAL_KEYS)
        if unknown:
            raise SchemaError(f"{region_type} region has unsupported fields: {unknown}")
        if region_type == REGION_TYPE_ISOTOPIC:
            region = isotopic_region(payload["Z"], payload["n_min"], payload["n_max"])
        elif region_type == REGION_TYPE_ISOTONIC:
            region = isotonic_region(payload["N"], payload["z_min"], payload["z_max"])
        else:
            region = rectangle_region(
                payload["z_min"], payload["z_max"], payload["n_min"], payload["n_max"]
            )
        declared = payload.get("region_id")
        if declared is not None and declared != region.region_id:
            raise SchemaError(
                f"region_id {declared!r} does not match the bounds ({region.region_id!r})"
            )
        return region


def _as_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"region {name} must be an int, got {value!r}")
    return int(value)


def rectangle_region(z_min: int, z_max: int, n_min: int, n_max: int) -> Region:
    return Region(
        region_type=REGION_TYPE_RECTANGLE,
        z_min=_as_int(z_min, "z_min"),
        z_max=_as_int(z_max, "z_max"),
        n_min=_as_int(n_min, "n_min"),
        n_max=_as_int(n_max, "n_max"),
    )


def isotopic_region(z: int, n_min: int, n_max: int) -> Region:
    value = _as_int(z, "Z")
    return Region(
        region_type=REGION_TYPE_ISOTOPIC,
        z_min=value,
        z_max=value,
        n_min=_as_int(n_min, "n_min"),
        n_max=_as_int(n_max, "n_max"),
    )


def isotonic_region(n: int, z_min: int, z_max: int) -> Region:
    value = _as_int(n, "N")
    return Region(
        region_type=REGION_TYPE_ISOTONIC,
        z_min=_as_int(z_min, "z_min"),
        z_max=_as_int(z_max, "z_max"),
        n_min=value,
        n_max=value,
    )


# --------------------------------------------------------------------------- #
# Splitting and support                                                       #
# --------------------------------------------------------------------------- #


def normalize_points(points: Iterable[Point]) -> list[Point]:
    """Deduplicated, sorted (Z, N) lattice points."""
    return sorted({(int(z), int(n)) for z, n in points})


def split_points(points: Iterable[Point], region: Region) -> dict[str, list[Point]]:
    """Geographic split: targets inside the region, training outside it."""
    ordered = normalize_points(points)
    return {
        "targets": [p for p in ordered if region.contains(*p)],
        "training": [p for p in ordered if not region.contains(*p)],
    }


def assert_region_populated(region: Region, points: Iterable[Point], *, min_targets: int = 1) -> int:
    """An empty region is a protocol error, never a zero-target run."""
    count = len(region.members(points))
    if count < max(1, int(min_targets)):
        raise ProtocolError(
            f"region {region.region_id} holds {count} eligible nuclei; "
            f"at least {max(1, int(min_targets))} are required"
        )
    return count


def supported_sides(region: Region, points: Iterable[Point]) -> tuple[str, ...]:
    """Faces of the region that have an adjacent training nucleus.

    A face counts as supported when at least one nucleus one lattice step
    outside it, and within the span of the opposite axis, stays in training.
    """
    ordered = set(normalize_points(points))
    sides = []
    if region.z_min > 0 and any(
        (region.z_min - 1, n) in ordered for n in range(region.n_min, region.n_max + 1)
    ):
        sides.append(SIDE_Z_LOW)
    if any((region.z_max + 1, n) in ordered for n in range(region.n_min, region.n_max + 1)):
        sides.append(SIDE_Z_HIGH)
    if region.n_min > 0 and any(
        (z, region.n_min - 1) in ordered for z in range(region.z_min, region.z_max + 1)
    ):
        sides.append(SIDE_N_LOW)
    if any((z, region.n_max + 1) in ordered for z in range(region.z_min, region.z_max + 1)):
        sides.append(SIDE_N_HIGH)
    return tuple(sorted(sides))


def nearest_training_l1(*, z: int, n: int, training: Iterable[Point]) -> int:
    """min over training nuclei of abs(Z_t - Z_r) + abs(N_t - N_r)."""
    ordered = normalize_points(training)
    if not ordered:
        raise ValueError("training point set is empty")
    return min(l1_distance(z, n, z_r, n_r) for z_r, n_r in ordered)


def region_depth_profile(region: Region, points: Iterable[Point]) -> list[dict[str, Any]]:
    """Per-target extrapolation depth inside one region.

    Depth is the L1 distance to the nearest training nucleus of the same split,
    which is the primary extrapolation-depth coordinate of WO-09 section 5.
    """
    split = split_points(points, region)
    training = split["training"]
    rows = []
    for z, n in split["targets"]:
        rows.append(
            {
                "nuclide_id": f"Z{z}-N{n}",
                "Z": z,
                "N": n,
                "A": z + n,
                "nearest_training_L1": nearest_training_l1(z=z, n=n, training=training),
            }
        )
    return sorted(rows, key=lambda row: (row["nearest_training_L1"], row["nuclide_id"]))


# --------------------------------------------------------------------------- #
# Deterministic candidate generation and selection                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegionCandidate:
    """One generated window with the counts that decide its retention."""

    region: Region
    n_targets: int
    n_training_adjacent: int
    supported_sides: tuple[str, ...]

    @property
    def z_band(self) -> str:
        return self.region.z_band

    @property
    def order_key(self) -> tuple[int, int, str]:
        """Deterministic order: band first, then denser windows, then id.

        The key uses only the source table (counts and identities). No metric,
        no model, and no error enters it, which is what keeps region selection
        independent of performance.
        """
        band = self.z_band
        band_index = SELECTION_Z_BANDS.index(band) if band in SELECTION_Z_BANDS else len(SELECTION_Z_BANDS)
        return (band_index, -self.n_targets, self.region.region_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region.to_dict(),
            "region_id": self.region.region_id,
            "z_band": self.z_band,
            "n_targets": self.n_targets,
            "n_training_adjacent": self.n_training_adjacent,
            "supported_sides": list(self.supported_sides),
        }


def candidate_windows(
    points: Iterable[Point],
    *,
    z_span: int = DEFAULT_Z_SPAN,
    n_span: int = DEFAULT_N_SPAN,
) -> list[Region]:
    """Fixed-size windows anchored at every eligible nucleus, deduplicated."""
    if z_span < 1 or n_span < 1:
        raise ValueError("z_span and n_span must be positive")
    windows: dict[str, Region] = {}
    for z, n in normalize_points(points):
        region = rectangle_region(z, z + z_span - 1, n, n + n_span - 1)
        windows[region.region_id] = region
    return [windows[key] for key in sorted(windows, key=lambda k: windows[k].sort_key)]


def region_candidates(
    points: Iterable[Point],
    *,
    z_span: int = DEFAULT_Z_SPAN,
    n_span: int = DEFAULT_N_SPAN,
    min_targets: int = DEFAULT_MIN_TARGETS,
    min_supported_sides: int = DEFAULT_MIN_SUPPORTED_SIDES,
) -> list[RegionCandidate]:
    """Retained candidates in deterministic order (WO-09 section 3 steps 1-4)."""
    ordered = normalize_points(points)
    candidates = []
    for region in candidate_windows(ordered, z_span=z_span, n_span=n_span):
        targets = region.members(ordered)
        if len(targets) < int(min_targets):
            continue
        sides = supported_sides(region, ordered)
        if len(sides) < int(min_supported_sides):
            continue
        candidates.append(
            RegionCandidate(
                region=region,
                n_targets=len(targets),
                n_training_adjacent=len(ordered) - len(targets),
                supported_sides=sides,
            )
        )
    return sorted(candidates, key=lambda c: c.order_key)


def select_regions(
    candidates: Sequence[RegionCandidate],
    *,
    per_band: int = DEFAULT_REGIONS_PER_BAND,
    bands: Sequence[str] = SELECTION_Z_BANDS,
    allow_missing_bands: bool = False,
) -> list[Region]:
    """Take the first ``per_band`` candidates of each declared Z band.

    Regions are selected before any model runs, and a band that cannot supply a
    candidate is reported loudly instead of being quietly dropped.
    """
    if per_band < 1:
        raise ValueError("per_band must be positive")
    ordered = sorted(candidates, key=lambda c: c.order_key)
    selected: list[Region] = []
    empty = []
    for band in bands:
        in_band = [c for c in ordered if c.z_band == band]
        if len(in_band) < per_band:
            empty.append(band)
        selected.extend(c.region for c in in_band[:per_band])
    if empty and not allow_missing_bands:
        raise ProtocolError(
            f"Z bands {empty} supplied fewer than {per_band} candidate regions; widen the "
            "source, relax the preregistered generator settings, or declare fewer bands - "
            "do not silently report a partial band set"
        )
    return selected


def generator_settings(
    *,
    z_span: int = DEFAULT_Z_SPAN,
    n_span: int = DEFAULT_N_SPAN,
    min_targets: int = DEFAULT_MIN_TARGETS,
    min_supported_sides: int = DEFAULT_MIN_SUPPORTED_SIDES,
    per_band: int = DEFAULT_REGIONS_PER_BAND,
    bands: Sequence[str] = SELECTION_Z_BANDS,
) -> dict[str, Any]:
    return {
        "candidate_policy_id": CANDIDATE_POLICY_ID,
        "selection_policy_id": SELECTION_POLICY_ID,
        "z_span": int(z_span),
        "n_span": int(n_span),
        "min_targets": int(min_targets),
        "min_supported_sides": int(min_supported_sides),
        "regions_per_band": int(per_band),
        "z_bands": list(bands),
        "z_band_bounds": {band: list(REGION_BOUNDS[band]) for band in bands},
        "candidate_order": (
            "sorted by (Z band index, -n_targets, region_id); source counts and "
            "identities only, never a metric or an error"
        ),
    }


def generate_regions(
    points: Iterable[Point],
    *,
    z_span: int = DEFAULT_Z_SPAN,
    n_span: int = DEFAULT_N_SPAN,
    min_targets: int = DEFAULT_MIN_TARGETS,
    min_supported_sides: int = DEFAULT_MIN_SUPPORTED_SIDES,
    per_band: int = DEFAULT_REGIONS_PER_BAND,
    bands: Sequence[str] = SELECTION_Z_BANDS,
    allow_missing_bands: bool = False,
) -> dict[str, Any]:
    """Candidates and the selected regions for one eligible point set."""
    ordered = normalize_points(points)
    candidates = region_candidates(
        ordered,
        z_span=z_span,
        n_span=n_span,
        min_targets=min_targets,
        min_supported_sides=min_supported_sides,
    )
    selected = select_regions(
        candidates,
        per_band=per_band,
        bands=bands,
        allow_missing_bands=allow_missing_bands,
    )
    return {
        "settings": generator_settings(
            z_span=z_span,
            n_span=n_span,
            min_targets=min_targets,
            min_supported_sides=min_supported_sides,
            per_band=per_band,
            bands=bands,
        ),
        "n_eligible_points": len(ordered),
        "n_candidates": len(candidates),
        "candidates": [c.to_dict() for c in candidates],
        "selected": selected,
    }


# --------------------------------------------------------------------------- #
# Region manifest                                                             #
# --------------------------------------------------------------------------- #


def region_manifest_hash(regions: Iterable[Region] | dict[str, Any]) -> str:
    """Stable digest of a region set.

    The digest covers the region geometry only, in canonical sort order, so
    reordering the file or adding generator provenance cannot change it while a
    changed bound or type always does.
    """
    payload = {
        "hash_rule": REGION_MANIFEST_HASH_RULE,
        "region_policy_id": REGION_POLICY_ID,
        "regions": [r.to_dict() for r in _as_regions(regions)],
    }
    return sha256_hex(payload)


def _as_regions(regions: Iterable[Region] | dict[str, Any]) -> list[Region]:
    if isinstance(regions, dict):
        items = [Region.from_dict(r) for r in regions.get("regions", [])]
    else:
        items = []
        for item in regions:
            items.append(item if isinstance(item, Region) else Region.from_dict(item))
    if not items:
        raise ProtocolError("a region manifest must declare at least one region")
    ids = [r.region_id for r in items]
    duplicates = sorted({rid for rid in ids if ids.count(rid) > 1})
    if duplicates:
        raise SchemaError(f"region manifest repeats regions: {duplicates}")
    return sorted(items, key=lambda r: r.sort_key)


def region_manifest(
    regions: Sequence[Region],
    *,
    benchmark_id: str,
    protocol_version: str,
    source: dict[str, Any] | None = None,
    generator: dict[str, Any] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """The preregistered region manifest written to ``regions.json``."""
    ordered = _as_regions(regions)
    payload: dict[str, Any] = {
        "benchmark_id": benchmark_id,
        "protocol_version": protocol_version,
        "region_policy_id": REGION_POLICY_ID,
        "region_manifest_hash_rule": REGION_MANIFEST_HASH_RULE,
        "n_regions": len(ordered),
        "regions": [r.to_dict() for r in ordered],
        "region_ids": [r.region_id for r in ordered],
        "z_bands": [r.z_band for r in ordered],
        "region_manifest_hash": region_manifest_hash(ordered),
    }
    if source is not None:
        payload["source"] = dict(source)
    if generator is not None:
        payload["generator"] = dict(generator)
    if notes:
        payload["notes"] = notes
    return payload


def load_region_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse and verify a region manifest payload."""
    regions = _as_regions(payload)
    expected = region_manifest_hash(regions)
    recorded = payload.get("region_manifest_hash")
    if recorded is not None and recorded != expected:
        raise ProtocolError(
            f"region manifest hash {recorded!r} does not match the declared regions ({expected!r})"
        )
    declared_ids = payload.get("region_ids")
    if declared_ids is not None and sorted(declared_ids) != sorted(r.region_id for r in regions):
        raise ProtocolError("region manifest region_ids disagree with the declared regions")
    return {
        "regions": regions,
        "region_manifest_hash": expected,
        "benchmark_id": payload.get("benchmark_id"),
        "protocol_version": payload.get("protocol_version"),
        "source": payload.get("source"),
        "generator": payload.get("generator"),
    }
