# ElementZero v2 — Blindness Ledger

The WO-13 finding was correct and is the most original epistemic contribution
this project has made. In v1 it lived in report prose. In v2 it is enforced code
(`elementzero.models.blindness`) and a required field on every prediction.

## 1. The rule

    A target hidden from ElementZero is not automatically blind to an
    imported physics table.

A published global mass model was fitted to an atomic mass evaluation. If a
target lies inside that fit set, the model has already seen the answer. Wrapping
it in a blind residual learner does not restore blindness; it launders it.

This is temporal leakage, and it is under-recognized in the published
literature: most mass-model extrapolation studies evaluate present-day tables
against present-day holdouts without addressing whether the table's parameters
already encode the held-out values. The project should say so explicitly when it
publishes, because it is a defensible methodological claim of its own.

## 2. Tiers

    A_STRICT_BLIND         fit cutoff strictly precedes the truth edition AND
                           the target was not in the fit set
    B_PARTIAL_BLIND        some targets blind, some not — scored separately,
                           never averaged into one number
    C_NONBLIND_REFERENCE   the model saw the truth; a legitimate reference
                           point, never a blind claim
    D_RECONSTRUCTION       reconstruction of withheld-but-known values, where
                           blindness is not claimed at all
    E_INELIGIBLE_UNKNOWN   fit-set membership unknown; never assumed blind

`E` is not a failure state. FRDM1995 against nuclei already known in AME1995 is
`E` because its fit membership cannot be enumerated, and recording that honestly
is worth more than a guess in either direction.

## 3. Inheritance

    combined_tier = worst(contributor tiers)

An ensemble containing one non-blind member is not blind. It may not be
reweighted into blindness, and a residual wrapper is not an independent physics
family. Both rules are enforced by `combine_tiers` rather than by convention.

## 4. Independence groups

The gate counts distinct physics-independence groups at tier A, not distinct
model ids. BSkG3, BSkG4 and BSkG5 are one group. A Skyrme-EDF backbone and a
Skyrme-EDF backbone with a different residual learner are one group.

    required by Gate G2 : 2
    available per WO-13 : 1   (macroscopic_microscopic_frdm)

The gap is closed by building blind physics (WO-205), never by widening the
definition of blind. If WO-205 does not land, the correct v2 output is the
finding "fewer than two blind physics families exist" and no frontier claim.

## 5. Reporting rule

Metrics may be identical across tiers. Claims may not. A table that mixes tiers
in one ranking is a protocol error, not a formatting preference — because the
whole point of the ledger is that a 400 keV non-blind number and a 400 keV blind
number are different scientific objects.
