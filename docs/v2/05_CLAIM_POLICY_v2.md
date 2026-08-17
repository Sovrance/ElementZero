# ElementZero v2 — Claim Policy

Doctrine 8: claim ceilings are declared before scoring and cannot be raised by a
good result. A better-than-expected number licenses a new preregistration, not a
larger claim under the old one.

## 1. Ceilings by state

| State | May say | May NOT say |
| --- | --- | --- |
| Model fails EZ-B004 | nothing quantitative | any point metric presented without its sigma; "conservative intervals" |
| G0 passed only | "calibrated on development data" | anything about real nuclei |
| G0 + G1, tier C/D | "reconstructs withheld values to X keV" | "predicts", "blind", "validated" |
| G0 + G1, tier A | "predicted, blind, X keV with calibrated intervals, on this target set" | any extrapolation beyond the scored set |
| G3 passed | "localized a withheld known closure at rank 1 in X% of chains" | "discovered a magic number"; anything about an unknown closure |
| G2 not passed | "one blind physics family available" | any model-form uncertainty statement; any frontier physics claim |
| G4 not passed | nothing about superheavy or hyperheavy | existence, stability, island of stability, Z~154 |

## 2. Standing prohibitions

These hold regardless of any result, in every document in the repository:

- A met criterion in EZ-B003 is rediscovery of KNOWN structure under masking. It
  is not proof of a new magic number and not evidence for a predicted Z = 154
  shell gap or an island of stability. (Carried unchanged from v1, which had
  this right.)
- Synthetic-chart results are software evidence. They are never described as
  evidence about real nuclei.
- Prediction-only runs are never displayed as validated, including in the visual
  element table.
- Elements 119-200 in the visual layout are project placeholders, not IUPAC
  placement.
- No best-model label, and no single-metric ranking, ever.

## 3. The hyperheavy sentence

Wherever the motivation is stated, it is stated in this form and no stronger:

    Hyperheavy regions such as Z ~ 154-156 are the long-term motivation for
    this program. They are not a deliverable of it. Mass prediction cannot
    determine whether such nuclei exist, because in that region the boundary
    of nuclear existence is set by spontaneous fission rather than particle
    emission. Any statement about them requires capabilities gated behind
    EZ-B008, which this program has not built.
