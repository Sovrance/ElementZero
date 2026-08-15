"""PIR v0.1 controlled vocabularies (the locked enums).

Every vocabulary the substrate enforces lives here so there is exactly one
source of truth. The two coordinate axes are ORTHOGONAL by construction
(ADJUDICATION #4): ``PirLevel`` is representation abstraction, ``EvidenceLevel``
is warrant strength. Nothing in the models derives one from the other.

Verdict vocabulary is LOCKED to the program specification (docs/SPECIFICATION.md
§4/§6). ChatGPT's candidate-class labels are a hypothesis-store taxonomy
(``CandidateClass``) and are *never* emittable as a verdict — hard constraint
#3 of the work order, enforced in ``pir.models.Fact``.
"""

from __future__ import annotations

from enum import Enum


class PirLevel(str, Enum):
    """L axis — representation abstraction (architecture.yaml pir_levels)."""

    L0 = "L0"  # raw records
    L1 = "L1"  # operational acts
    L2 = "L2"  # structural facts
    L3 = "L3"  # candidate grammars


class EvidenceLevel(str, Enum):
    """E axis — warrant strength (SPEC §3). Orthogonal to :class:`PirLevel`."""

    E0 = "E0"  # exact theorem / exact arithmetic
    E1 = "E1"  # interval-certified
    E2 = "E2"  # statistical with stated coverage
    E3 = "E3"  # simulation-conditioned
    E4 = "E4"  # proxy / indirect


class Layer(str, Enum):
    """Mandatory three-layer separation (SPEC §2)."""

    UNIVERSAL = "UNIVERSAL"
    DOMAIN = "DOMAIN"
    MEASUREMENT = "MEASUREMENT"


class Namespace(str, Enum):
    """Provenance namespaces (architecture.yaml). Cross-namespace references
    require an explicit typed transform record (hard constraint #6)."""

    raw = "raw"
    apparatus = "apparatus"
    operational = "operational"
    domain = "domain"
    latent = "latent"
    gauge = "gauge"
    invariant = "invariant"
    global_ = "global"      # ``global`` is a Python keyword; value is "global"
    effective = "effective"
    analyst = "analyst"


class FactStatus(str, Enum):
    """Lifecycle status of an append-only fact. Downgrades append a record;
    nothing is ever deleted (hard constraint #8)."""

    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"
    DOWNGRADED = "DOWNGRADED"
    RETRACTED_BY_ERRATUM = "RETRACTED_BY_ERRATUM"


class Verdict(str, Enum):
    """LOCKED verdict vocabulary (SPEC §4/§6). These are the ONLY strings the
    ``verdict``/``outcome`` fields accept. Candidate-class labels are NOT here.

    The starter fact-schema draft listed seven; SPEC §4 additionally makes
    ``AMBIGUOUS`` a first-class verdict (classification tie, distinct from
    NONIDENTIFIABLE). We adopt the SPEC superset — see ADR-PIR-0001 — so the
    lock tracks the normative spec rather than the draft."""

    FORCED = "FORCED"
    PERMITTED = "PERMITTED"
    REJECTED = "REJECTED"
    NONIDENTIFIABLE = "NONIDENTIFIABLE"
    OBSERVATIONALLY_EQUIVALENT = "OBSERVATIONALLY_EQUIVALENT"
    APPARATUS_LIMITED = "APPARATUS_LIMITED"
    REPRESENTATION_DEPENDENT = "REPRESENTATION_DEPENDENT"
    AMBIGUOUS = "AMBIGUOUS"


class CandidateClass(str, Enum):
    """Hypothesis-store TAXONOMY only (ADJUDICATION #24). Emitting one of these
    as a fact verdict is a schema violation, enforced in :class:`pir.models.Fact`."""

    GLOBAL_CANDIDATE = "GLOBAL_CANDIDATE"
    TOPOLOGICAL_CANDIDATE = "TOPOLOGICAL_CANDIDATE"
    HIDDEN_COMMON_CAUSE_CANDIDATE = "HIDDEN_COMMON_CAUSE_CANDIDATE"
    REPRESENTATION_ARTIFACT = "REPRESENTATION_ARTIFACT"
    NOT_DETECTED = "NOT_DETECTED"


class PassTag(str, Enum):
    """SOUND vs HEURISTIC honesty tag (hard constraint #4, Ghidra rule)."""

    SOUND = "SOUND"
    HEURISTIC = "HEURISTIC"


class HypothesisStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ELIMINATED = "ELIMINATED"
    OBSERVATIONALLY_EQUIVALENT_MEMBER = "OBSERVATIONALLY_EQUIVALENT_MEMBER"
    SELECTED_REPRESENTATIVE = "SELECTED_REPRESENTATIVE"
    DOWNGRADED = "DOWNGRADED"


class AgentKind(str, Enum):
    ANALYZER = "ANALYZER"
    HUMAN = "HUMAN"
    AI_AGENT = "AI_AGENT"


class ActivityType(str, Enum):
    LOAD = "LOAD"
    LOWER = "LOWER"
    ANALYZE = "ANALYZE"
    TRANSFORM = "TRANSFORM"
    CERTIFY = "CERTIFY"
    DIFF = "DIFF"
    FINGERPRINT = "FINGERPRINT"
    RECOMPILE = "RECOMPILE"
    DOWNGRADE = "DOWNGRADE"
    ANNOTATE = "ANNOTATE"


# Op families (architecture.yaml). Kept as frozensets for cheap membership.
ACT_OPS = frozenset({
    "PREPARE", "INTERVENE", "EVOLVE", "COUPLE", "SPLIT", "RECOMBINE",
    "TRANSPORT", "PHASE_ACCUMULATE", "MEASURE", "RECORD", "CONDITION",
    "TRACE_OUT", "COARSE_GRAIN", "SYMMETRY_ACT", "COMPOSE", "PARALLEL",
})

VERIFIER_OPS = frozenset({
    "SCHUR_PIVOT_EXACT", "RANK_TEST", "FLAT_EXTENSION",
    "JACOBIAN_RANK_IDENTIFIABILITY", "CPTP_GATE", "SYMPLECTIC_GATE",
})

PORT_TYPES = frozenset({
    "State", "Effect", "Observable", "Process", "Coupling",
    "SymmetryParameter", "GaugeCoordinate", "Invariant", "NuisanceParameter",
    "ApparatusParameter", "BoundarySector", "GlobalCandidate",
    "ScaleDependentEffectiveParameter",
})


# Convenience string sets for schema-free callers / cross-checks.
VERDICTS = frozenset(v.value for v in Verdict)
CANDIDATE_CLASSES = frozenset(c.value for c in CandidateClass)
NAMESPACES = frozenset(n.value for n in Namespace)
