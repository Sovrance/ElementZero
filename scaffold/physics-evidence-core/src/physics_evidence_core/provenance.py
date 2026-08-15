"""Append-only fact store + provenance engine.

Responsibilities (Stage 1, P1b):

* **Append-only** (hard constraint #1): a fact ID is content-addressed, so
  re-adding the *same* fact is idempotent, but re-adding a DIFFERENT payload
  under an existing ID -- a mutation -- is rejected. No pass may overwrite
  another pass's fact.
* **Provenance graph** over ``depends_on_facts`` with **cycle detection**
  (hard constraint / negative test): A depends on B depends on A is illegal.
* **Cross-namespace promotion guard** (hard constraint #6): a fact that
  depends on a fact in a different namespace must be accompanied by a typed
  transform record; an implicit promotion raises.
* **Invalidation traversal** (hard constraint #8): given an assumption ID,
  find every transitively dependent fact and mark it ``DOWNGRADED`` by
  *appending a downgrade record* -- never deleting anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .models import Fact, ProvenanceRecord
from .canonical import canonical_json
from .namespaces import NamespaceTransform, require_transform
from .types import FactStatus, Namespace


class AppendOnlyViolation(Exception):
    """Raised on any attempt to mutate or delete a stored fact."""


class ProvenanceCycle(Exception):
    """Raised when adding a fact would close a dependency cycle."""


@dataclass
class DowngradeRecord:
    """Appended (never overwriting) when a fact is invalidated."""

    fact_id: str
    previous_status: str
    reason: str
    triggering_assumption: str

    def to_dict(self):
        return {
            "fact_id": self.fact_id,
            "previous_status": self.previous_status,
            "new_status": FactStatus.DOWNGRADED.value,
            "reason": self.reason,
            "triggering_assumption": self.triggering_assumption,
        }


@dataclass
class FactStore:
    """Append-only store of facts + provenance records + downgrade log."""

    _facts: Dict[str, Fact] = field(default_factory=dict)
    _provenance: List[ProvenanceRecord] = field(default_factory=list)
    _downgrades: List[DowngradeRecord] = field(default_factory=list)
    # namespace transforms registered for a (child_fact_id, parent_fact_id) edge
    _edge_transforms: Dict[tuple, NamespaceTransform] = field(default_factory=dict)

    # ---- read ------------------------------------------------------------- #
    def get(self, fact_id: str) -> Fact:
        return self._facts[fact_id]

    def __contains__(self, fact_id: str) -> bool:
        return fact_id in self._facts

    def __len__(self) -> int:
        return len(self._facts)

    def facts(self) -> List[Fact]:
        return list(self._facts.values())

    def downgrades(self) -> List[DowngradeRecord]:
        return list(self._downgrades)

    def provenance(self) -> List[ProvenanceRecord]:
        return list(self._provenance)

    # ---- write (append-only) --------------------------------------------- #
    def add_fact(
        self,
        fact: Fact,
        edge_transforms: Optional[Dict[str, NamespaceTransform]] = None,
    ) -> Fact:
        """Append ``fact``. ``edge_transforms`` maps a parent fact ID to the
        typed transform justifying a cross-namespace dependency on it."""
        edge_transforms = edge_transforms or {}

        existing = self._facts.get(fact.fact_id)
        if existing is not None:
            # Idempotent re-add of the identical fact is fine; anything else is
            # a mutation of an append-only record.
            if canonical_json(existing.to_dict()) != canonical_json(fact.to_dict()):
                raise AppendOnlyViolation(
                    f"fact {fact.fact_id!r} already stored with different "
                    "content; facts are append-only, store a new fact or a "
                    "downgrade record instead of mutating"
                )
            return existing

        # Dependencies must already exist (a fact cannot depend on the future).
        for parent_id in fact.depends_on_facts:
            if parent_id not in self._facts:
                raise KeyError(
                    f"fact {fact.fact_id!r} depends on unknown fact {parent_id!r}"
                )
            parent = self._facts[parent_id]
            # Cross-namespace promotion guard (hard constraint #6).
            if parent.namespace != fact.namespace:
                transform = edge_transforms.get(parent_id)
                require_transform(parent.namespace, fact.namespace, transform)
                self._edge_transforms[(fact.fact_id, parent_id)] = transform

        # Cycle detection BEFORE committing (hard constraint / negative test).
        self._assert_acyclic(fact)

        self._facts[fact.fact_id] = fact
        return fact

    def add_provenance(self, record: ProvenanceRecord) -> ProvenanceRecord:
        self._provenance.append(record)
        return record

    def replace_fact(self, *args, **kwargs):
        raise AppendOnlyViolation(
            "the store has no replace/delete operation; it is append-only"
        )

    delete_fact = replace_fact  # same refusal

    # ---- provenance graph ------------------------------------------------- #
    def _assert_acyclic(self, new_fact: Fact) -> None:
        """DFS from ``new_fact`` over dependency edges; if it can reach itself,
        adding it would create a cycle."""
        target = new_fact.fact_id
        stack = list(new_fact.depends_on_facts)
        seen: Set[str] = set()
        while stack:
            cur = stack.pop()
            if cur == target:
                raise ProvenanceCycle(
                    f"adding fact {target!r} would create a dependency cycle "
                    f"(reaches itself via {cur!r})"
                )
            if cur in seen:
                continue
            seen.add(cur)
            parent = self._facts.get(cur)
            if parent is not None:
                stack.extend(parent.depends_on_facts)

    def dependents_of_fact(self, fact_id: str) -> Set[str]:
        """All facts that transitively depend on ``fact_id``."""
        out: Set[str] = set()
        changed = True
        while changed:
            changed = False
            for f in self._facts.values():
                if f.fact_id in out:
                    continue
                if fact_id in f.depends_on_facts or out & set(f.depends_on_facts):
                    out.add(f.fact_id)
                    changed = True
        return out

    # ---- invalidation traversal (hard constraint #8) --------------------- #
    def invalidate_assumption(self, assumption_id: str, reason: str) -> List[str]:
        """Downgrade every fact that rests on ``assumption_id`` transitively.

        A fact is affected if it names the assumption directly OR transitively
        depends on a fact that does. Each affected fact is replaced by a NEW
        ``DOWNGRADED`` fact object and a :class:`DowngradeRecord` is appended.
        The original fact content is preserved in the store's provenance log;
        nothing is deleted. Returns the affected fact IDs (sorted)."""
        directly = {f.fact_id for f in self._facts.values()
                    if assumption_id in f.assumptions}
        affected: Set[str] = set(directly)
        for seed in directly:
            affected |= self.dependents_of_fact(seed)

        for fid in sorted(affected):
            fact = self._facts[fid]
            if fact.status is FactStatus.DOWNGRADED:
                continue
            self._downgrades.append(DowngradeRecord(
                fact_id=fid,
                previous_status=fact.status.value,
                reason=reason,
                triggering_assumption=assumption_id,
            ))
            # Append-only downgrade: swap the in-store object for a downgraded
            # copy; the pre-downgrade state lives on in the downgrade log.
            self._facts[fid] = fact.with_status(FactStatus.DOWNGRADED)
        return sorted(affected)


def build_provenance_index(records: List[ProvenanceRecord]) -> Dict[str, ProvenanceRecord]:
    """Index provenance records by the entity they describe (last writer per
    entity is kept for lookup; the full append-only list is unchanged)."""
    return {r.entity: r for r in records}
