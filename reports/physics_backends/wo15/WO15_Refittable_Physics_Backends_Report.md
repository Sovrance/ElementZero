# WO-15 — Refittable Physics Backends and Historical Physics Fits

Work order status: **ENGINEERING_PASS_B004_PASS**

## 1. What WO-15 set out to fix

WO-14 ended with one blind physics family and a mass criterion missed by 15 keV. The bottleneck was never another statistical residual: it was that ElementZero did not control any physics model's *fitted state*. A model is not historically blind because its source code is old.

## 2. Solver provenance

| solver | version | sha256 | licence | redistributable |
| --- | --- | --- | --- | --- |
| DIRHB | DIRHB package (revised), Mendeley cx55fkbjy6 v1 | `04e3657e68a8dcd1…` | CPC non-profit use licence | False |
| HFBTHO | HFBTHO-AD (Zenodo 16249941) | `89818ef33b1f504c…` | GPL-3.0-or-later | True |

Both archives are fetched and hash-verified rather than vendored; the DIRHB CPC licence does not grant redistribution, so only its digest lives in the repository.

## 3. Golden-case qualification

- HFBTHO UNEDF0_Z20_N20_sphGS: solver_ok True, E = -338.532 MeV
- DIRHB 78Kr_DD-ME2: expected -670.937 MeV, observed -670.937 MeV, exact match True

## 4. Historical fit freeze

- freeze: `ez-wo15-historical-fit-freeze-v1`, cutoff 1995-12-01
- allowed evidence: AME1995 only (1844 ground-truth-eligible nuclides)
- calibration set: 12 even-even nuclides selected by a preregistered deterministic rule
- forbidden: every later AME edition and every committed WO-14 result artifact, enumerated by hash in the freeze record

Objective `ez-wo15-mass-objective-v1` was locked (hash `701da9dbaf2207ba…`) before the first solver call.

## 5. Parameterization chronology

| family | parameterization | published | freeze-admissible |
| --- | --- | --- | --- |
| EZ-PHYS-COVARIANT-RHB-v1 | DD-ME2 | 2005 | False |
| EZ-PHYS-GOGNY-HFB-v1 | D1S | 1984 | True |
| EZ-PHYS-SKYRME-HFB-v1 | SKM* | 1982 | True |

This table is the scientific finding of the backend survey: the distributed DIRHB package ships only DD-ME2 (2005) and DD-PC1 (2008), so the covariant family cannot be made historically blind by choosing a different shipped force.

## 6. Refit results

| family | provenance | parameters | objective (RMS keV) | status |
| --- | --- | --- | --- | --- |
| EZ-PHYS-COVARIANT-RHB-v1 | MODERN_REFERENCE | force=0 | n/a | PUBLISHED_PARAMETERIZATION |
| EZ-PHYS-GOGNY-HFB-v1 | HISTORICAL_FROZEN_PARTIAL | functional=0 | n/a | PUBLISHED_PARAMETERIZATION |
| EZ-PHYS-SKYRME-HFB-v1 | REFIT_STRICT | vpair_n=-325, vpair_p=-140 | 3100.97 | FIT_BUDGET_EXHAUSTED |

The refit scope is the pairing sector of a pre-freeze published EDF, stated plainly rather than dressed up: a full EDF reoptimization is a supercomputer campaign. What it earns is exact calibration membership, a locked objective, a logged optimizer path, and an immutable artifact.

## 7. Independence adjudication

| group | functional class | verdict | blind eligible |
| --- | --- | --- | --- |
| covariant_rhb_edf | covariant_meson_exchange | INDEPENDENT | False |
| gogny_finite_range_hfb | gogny_finite_range | INDEPENDENT | True |
| skyrme_hfb_edf | skyrme_zero_range_edf | INDEPENDENT | True |

**TWO_BLIND_PHYSICS_FAMILIES** — 2 independent blind-eligible physics families: gogny_finite_range_hfb, skyrme_hfb_edf.

The Skyrme and Gogny families run through one HFBTHO build. Their functional classes differ, so the physics is independent, but the numerics are correlated — that caveat is recorded on both adjudications, and a second implementation would strengthen the claim.

## 8. B004 protocol

- experiment: `EZ-B004-v1`, protocol hash `6655e8f2d8d6e420…`
- targets: 14 even-even nuclides that are AME2020-eligible, absent from AME1995, and not scored by WO-14
- strata: {"heavy": 2, "light": 1, "medium": 3, "very_heavy": 8} by Z band; {"neutron_rich_frontier": 4, "proton_rich_frontier": 10} by frontier direction
- odd policy: EVEN_EVEN_ONLY

Gate E, preregistered before scoring: B004 v1 is a characterization challenge. The 150 keV EZ-B002-v2 value is carried only as LEGACY_INHERITED_REFERENCE and is explicitly not a pass bar, because SkM* and D1S were never calibrated as mass models.

## 9. B004 results

| family | coverage | MAE keV | RMSE keV | cov90 | cal err 90 | sigma measured? |
| --- | --- | --- | --- | --- | --- | --- |
| EZ-PHYS-COVARIANT-RHB-v1 | 13/14 | 3458.21 | 4083.37 | 0 | 0.9 | no — 13 row(s) at the sigma floor |
| EZ-PHYS-GOGNY-HFB-v1 | 14/14 | 7862.47 | 8686.73 | 0 | 0.9 | yes (by audit) |
| EZ-PHYS-SKYRME-HFB-v1 | 14/14 | 9618.69 | 10699.2 | 0.0714286 | 0.828571 | yes (by audit) |

Mean cross-family spread: 17501.5 keV, reported alongside — never inside — any single family's sigma.

Derived S2n rows scored: 9 (only where both component masses are blind predictions of the same family).

### What this result does and does not say

It would be easy to read MULTI_FAMILY_BLIND_EVIDENCE_ESTABLISHED as a physics success. It is not one, and the preregistered criterion never claimed to be: it asks whether two independent, blind-eligible families can produce sealed, converged, uncertainty-carrying predictions on fresh post-freeze targets. They can. That is an infrastructure and provenance result.

The physics numbers are poor, and they are the headline a reader should carry away:

- Blind-family mass errors are several MeV — roughly two orders of magnitude worse than the 150 keV legacy reference. SkM* and D1S were never calibrated as mass models, which is exactly why the interpretation was fixed in advance rather than after seeing this.
- The most accurate backend here is the covariant DD-ME2 family, and it is precisely the one that is NOT blind-eligible: a 2005 fit scoring post-1995 targets. Its accuracy is a reference point, not evidence.
- Calibration failed outright. Observed 90% intervals contain almost none of the truths, because the preregistered uncertainty policy measured only numerical and parameter components. The dominant error here is model discrepancy — the functional itself being wrong — and that term was deliberately not fitted, so the sigmas are far too narrow. This is the clearest single improvement for the next protocol version, and it must be learned from training-era residuals, never from B004 truth.
- The covariant family's calibration columns are not a measurement at all. A review of this PR found that the sealing code accepted an uncertainty probe on the strength of a parsed energy alone. Auditing the retained solver output showed every one of its 13 larger-basis probes failed to converge and emitted no energy, so its numerical component was recorded as zero and each sealed sigma is the bare 1 keV floor. Its cov90 therefore describes the floor, not DD-ME2. The two blind-eligible families audit clean — 14/14 measured each — so the claim itself is unaffected. The seal is evidence and was not rewritten; see results/EZ-B004-v1/probe_validity_audit.json, and the probe rule ez-wo15-probe-validity-v1 now refuses a non-converged probe instead of reading it as zero spread.

## 10. Claim

**MULTI_FAMILY_BLIND_EVIDENCE_ESTABLISHED**

- blind-eligible families meeting coverage: gogny_finite_range_hfb, skyrme_hfb_edf
- visual permission: BADGE_PB_ONLY_NO_STAGE_PROMOTION

## 11. Limitations

- The refit covers the pairing sector only; the bulk EDF stays at its published historical values.
- Skyrme and Gogny share a solver implementation, so their numerical errors are correlated.
- The covariant family is reference-only: no pre-freeze force ships with DIRHB.
- B004 is small-n by construction and every point estimate carries wide uncertainty.
- EVEN_EVEN_ONLY: odd nuclei need blocking and a separate preregistered treatment.

## 12. Visual claim firewall

Backend qualification emits the `PF` badge and a scored B004 emits `PB`. Neither can promote a tile's validation stage — qualification is an engineering fact about provenance, not evidence of accuracy.

## 13. WO-14 immutability

All 10 WO-14 artifacts re-hash unchanged; no WO-14 truth entered any fit, objective, or selection rule.

## 14. Next gate

WO-16 Known-Superheavy Historical Challenge becomes available: two independent blind-eligible physics families now exist with reproducible fits. WO-16 remains a computational historical validation challenge and authorizes no experimental synthesis.
