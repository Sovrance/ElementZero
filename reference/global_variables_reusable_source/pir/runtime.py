"""Analyzer runtime: a dependency-resolved pass graph (Stage 2 / P3).

Builds on the Stage-1 pass registry. An :class:`AnalyzerPass` declares the pass
ids it depends on; the runtime topologically orders the graph (rejecting cycles),
runs each pass once with its dependencies' outputs, and appends emitted facts to
an append-only :class:`pir.provenance.FactStore`.

Guarantees (P3 acceptance):

* **Deterministic reruns** — passes run in a stable order (topological, ties
  broken by id), and the runtime reads store facts in id order, so two runs over
  the same inputs emit identical fact ids.
* **Conflicts retained** — the store is append-only; two passes asserting opposite
  claims about the same subject both persist, and :meth:`detect_conflicts`
  surfaces them without deleting anything.
* **Isolation** — a pass that raises is quarantined with its error; the store is
  not corrupted and the remaining passes still run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from .models import Fact
from .passes import PassRegistry, PassSpec
from .provenance import FactStore
from .types import PassTag


class PassGraphCycle(Exception):
    """Raised when the analyzer dependency graph contains a cycle."""


@dataclass(frozen=True)
class AnalyzerPass:
    """A pass in the analyzer graph. ``fn(store, ctx) -> List[Fact]`` where
    ``ctx`` maps each dependency pass id to the facts it emitted this run."""

    id: str
    version: str
    tag: PassTag
    fn: Callable[[FactStore, Dict[str, List[Fact]]], List[Fact]]
    depends_on: Tuple[str, ...] = ()
    description: str = ""

    def as_spec(self) -> PassSpec:
        return PassSpec(id=self.id, version=self.version, tag=self.tag,
                        fn=lambda *a, **k: [], description=self.description)


@dataclass
class RunReport:
    order: List[str]
    emitted: Dict[str, List[str]]          # pass id -> emitted fact ids
    quarantined: List[Dict]                # {pass, error}
    conflicts: List[Dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.quarantined


class AnalyzerRuntime:
    def __init__(self):
        self._passes: Dict[str, AnalyzerPass] = {}

    def register(self, p: AnalyzerPass) -> AnalyzerPass:
        if p.id in self._passes:
            raise ValueError(f"analyzer pass {p.id!r} already registered")
        self._passes[p.id] = p
        return p

    # ---- ordering -------------------------------------------------------- #
    def topological_order(self) -> List[str]:
        """Kahn's algorithm with id tie-breaking (deterministic). Raises on a
        cycle or an unknown dependency."""
        indeg = {pid: 0 for pid in self._passes}
        for p in self._passes.values():
            for dep in p.depends_on:
                if dep not in self._passes:
                    raise KeyError(f"pass {p.id!r} depends on unknown pass {dep!r}")
                indeg[p.id] += 1
        ready = sorted(pid for pid, d in indeg.items() if d == 0)
        order: List[str] = []
        while ready:
            cur = ready.pop(0)
            order.append(cur)
            for p in self._passes.values():
                if cur in p.depends_on:
                    indeg[p.id] -= 1
                    if indeg[p.id] == 0:
                        ready.append(p.id)
            ready.sort()
        if len(order) != len(self._passes):
            stuck = sorted(set(self._passes) - set(order))
            raise PassGraphCycle(f"cycle among analyzer passes: {stuck}")
        return order

    # ---- execution ------------------------------------------------------- #
    def run(self, store: FactStore) -> RunReport:
        order = self.topological_order()
        emitted: Dict[str, List[Fact]] = {}
        emitted_ids: Dict[str, List[str]] = {}
        quarantined: List[Dict] = []

        for pid in order:
            p = self._passes[pid]
            ctx = {dep: emitted.get(dep, []) for dep in p.depends_on}
            try:
                facts = p.fn(store, ctx)
                spec = p.as_spec()
                for f in facts:
                    PassRegistry.check_emission(spec, f)  # honesty gate
                # Commit only after all emitted facts pass the honesty gate, so a
                # bad fact cannot half-corrupt the store.
                for f in facts:
                    store.add_fact(f)
                emitted[pid] = facts
                emitted_ids[pid] = [f.fact_id for f in facts]
            except Exception as exc:  # noqa: BLE001 — isolate analyzer failure
                quarantined.append({"pass": pid, "error": f"{type(exc).__name__}: {exc}"})
                emitted[pid] = []
                emitted_ids[pid] = []

        report = RunReport(order=order, emitted=emitted_ids, quarantined=quarantined)
        report.conflicts = detect_conflicts(store)
        return report


def _subject(fact: Fact) -> str:
    """A coarse subject key for conflict detection: the claim/entry identity."""
    c = fact.content
    return str(c.get("claim") or c.get("entry_id") or c.get("subject")
               or fact.source_spans[0]["span"] if fact.source_spans else fact.fact_id)


def detect_conflicts(store: FactStore) -> List[Dict]:
    """Surface pairs of facts about the same subject with opposing status /
    verdict. Nothing is deleted; conflicts are reported (append-only)."""
    by_subject: Dict[str, List[Fact]] = {}
    for f in sorted(store.facts(), key=lambda x: x.fact_id):
        by_subject.setdefault(_subject(f), []).append(f)
    conflicts = []
    for subj, facts in by_subject.items():
        verdicts = {(f.verdict.value if f.verdict else None) for f in facts}
        opposed = {"REJECTED", "PERMITTED", "FORCED"} & verdicts
        if len(facts) > 1 and ("REJECTED" in verdicts and (opposed - {"REJECTED"})):
            conflicts.append({"subject": subj,
                              "fact_ids": sorted(f.fact_id for f in facts),
                              "verdicts": sorted(v for v in verdicts if v)})
    return conflicts
