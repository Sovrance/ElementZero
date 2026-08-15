"""Intervention search / optimal experiment design (Stage 2 / S3 / P7).

Given competing hypotheses and an admissible-intervention space, score each
intervention by how well it would discriminate the hypotheses, filter by
feasibility, and propose the best. Every proposal is HEURISTIC-tagged and states
its assumptions (it predicts, it does not certify). Acceptance: the known
discriminator is recovered on a synthetic benchmark; a negative control where no
intervention separates anything emits NONIDENTIFIABLE.

Objectives (all computed from the hypotheses' predicted outcomes under each
intervention):

* **candidate_disagreement** — fraction of hypothesis pairs the intervention
  splits (different predicted outcome);
* **expected_information_gain** — Shannon entropy of the induced outcome
  partition (bits), a proxy for how evenly it divides the candidates;
* **d_identifiable_reduction** — (#distinct outcome classes − 1), how many
  degrees of non-identifiability it removes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class AdmissibleIntervention:
    id: str
    kind: str
    cost: float
    # predicted outcome label per hypothesis id under this intervention
    predicted_outcomes: Dict[str, str] = field(default_factory=dict)
    feasibility: str = "routine"
    assumptions: tuple = ()


def _objectives(iv: AdmissibleIntervention, hyp_ids: List[str]) -> Dict[str, float]:
    outcomes = [iv.predicted_outcomes.get(h) for h in hyp_ids]
    pairs = list(combinations(range(len(hyp_ids)), 2))
    split = sum(1 for i, j in pairs if outcomes[i] != outcomes[j])
    disagreement = (split / len(pairs)) if pairs else 0.0
    # entropy over the outcome partition
    counts: Dict[str, int] = {}
    for o in outcomes:
        counts[o] = counts.get(o, 0) + 1
    n = len(outcomes)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values()) if n else 0.0
    d_ident = len(set(outcomes)) - 1
    return {"candidate_disagreement": round(disagreement, 6),
            "expected_information_gain": round(entropy, 6),
            "d_identifiable_reduction": float(d_ident)}


@dataclass
class Proposal:
    intervention_id: str
    scores: Dict[str, float]
    cost: float
    assumptions: List[str]
    verdict: str                       # the intervention's discriminating status

    def to_dict(self):
        return {"intervention_id": self.intervention_id, "scores": self.scores,
                "cost": self.cost, "assumptions": self.assumptions,
                "verdict": self.verdict, "tag": "HEURISTIC"}


def search(interventions: List[AdmissibleIntervention], hyp_ids: List[str],
           feasibility_filter: Optional[Callable[[AdmissibleIntervention], bool]] = None
           ) -> Dict:
    """Rank feasible interventions by discrimination. Returns
    {best, ranked, verdict}. ``verdict`` is NONIDENTIFIABLE when no feasible
    intervention splits any hypothesis pair, else the best proposal stands."""
    feasible = [iv for iv in interventions
                if feasibility_filter is None or feasibility_filter(iv)]
    scored: List[Proposal] = []
    for iv in feasible:
        obj = _objectives(iv, hyp_ids)
        discriminates = obj["candidate_disagreement"] > 0
        scored.append(Proposal(
            intervention_id=iv.id, scores=obj, cost=iv.cost,
            assumptions=list(iv.assumptions),
            verdict=("DISCRIMINATING" if discriminates else "NON_SEPARATING")))
    # deterministic ranking: disagreement desc, info-gain desc, cost asc, id asc
    scored.sort(key=lambda p: (-p.scores["candidate_disagreement"],
                               -p.scores["expected_information_gain"],
                               p.cost, p.intervention_id))
    if not scored or all(p.verdict == "NON_SEPARATING" for p in scored):
        return {"verdict": "NONIDENTIFIABLE", "cause": "no admissible intervention "
                "separates the candidates", "ranked": [p.to_dict() for p in scored],
                "best": None}
    return {"verdict": "DISCRIMINATOR_FOUND", "best": scored[0].to_dict(),
            "ranked": [p.to_dict() for p in scored]}


def least_cost_discriminator(interventions: List[AdmissibleIntervention],
                             hyp_ids: List[str]) -> Optional[str]:
    """Cheapest intervention that still discriminates (for cross-domain diff)."""
    disc = [iv for iv in interventions
            if _objectives(iv, hyp_ids)["candidate_disagreement"] > 0]
    if not disc:
        return None
    return min(disc, key=lambda iv: (iv.cost, iv.id)).id
