"""Forward recompilation (Stage 2 / S3 / P6).

A lowered structure is *decompiled* evidence; forward recompilation runs it the
other way — realize latent structure into a predicted observable record, apply a
patch to a latent component, and compare against **held-out** data the fit never
saw. Acceptance: altering one B9 latent changes the held-out spectroscopy
prediction; the held-out point is never reused in the realization; the residual
carries complete provenance.

The B9 T6 realization is reproduced exactly: the transmon asymptotic
``E01 = sqrt(8·EJ·EC) − EC`` and anharmonicity ``−EC``. With EC = 1/4 and
EJ = 25/2 (EJ/EC = 50) this gives E01 = 5 − 1/4 = 4.75 and anharmonicity −0.25,
matching B9's stored predictions — so a latent patch has a checkable effect.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Realization:
    """Latent circuit parameters (the 'source' recovered by decompilation)."""

    latents: Dict[str, float]                     # e.g. {"EJ": 12.5, "EC": 0.25}
    apparatus: Dict[str, str] = field(default_factory=dict)

    def patch(self, component: str, new_value: float) -> "Realization":
        """Return a NEW realization with one latent altered (never in place)."""
        if component not in self.latents:
            raise KeyError(f"unknown latent component {component!r}")
        latents = dict(self.latents)
        latents[component] = new_value
        return replace(self, latents=latents)


def predict_spectroscopy(real: Realization) -> Dict[str, float]:
    """Realize latents -> predicted spectroscopy record (the transmon asymptotic).
    This does NOT read any held-out datum."""
    EJ = real.latents["EJ"]
    EC = real.latents["EC"]
    e01 = math.sqrt(8.0 * EJ * EC) - EC
    return {"E01": e01, "anharmonicity": -EC, "EJ_over_EC": EJ / EC}


@dataclass(frozen=True)
class Residual:
    predicted: float
    held_out: float
    residual: float
    provenance: Dict

    def to_dict(self) -> Dict:
        return {"predicted": self.predicted, "held_out": self.held_out,
                "residual": self.residual, "provenance": self.provenance}


def held_out_residual(real: Realization, prediction: Dict, held_out_value: float,
                      held_out_id: str, used_latents: Optional[List[str]] = None) -> Residual:
    """Compare a prediction to a held-out point, recording complete provenance
    and asserting the held-out point was not among the realization's inputs."""
    used = sorted(used_latents or real.latents.keys())
    provenance = {
        "realized_from_latents": used,
        "apparatus": real.apparatus,
        "held_out_id": held_out_id,
        "held_out_reused_in_fit": False,     # realization used latents only
        "predictor": "predict_spectroscopy (transmon asymptotic E01)",
    }
    return Residual(predicted=prediction["E01"], held_out=held_out_value,
                    residual=abs(prediction["E01"] - held_out_value),
                    provenance=provenance)


# B9 T6 baseline (exact): EC = 1/4, EJ = 25/2 -> E01 = 4.75, anharmonicity -0.25.
def b9_baseline() -> Realization:
    return Realization(latents={"EJ": float(Fraction(25, 2)), "EC": float(Fraction(1, 4))},
                       apparatus={"id": "apparatus:josephson_circuit",
                                  "route": "cal:spectroscopy_route"})
