# ElementZero — Initial Research Baseline v0.1

**Status:** Initial canonical research baseline  
**Date:** 2026-08-15  
**Project:** ElementZero  
**Related upstream project:** [Sovrance/Atlas](https://github.com/Sovrance/Atlas)  
**Purpose:** Preserve the research basis, external project landscape, validation philosophy, and Atlas integration rationale that led to the ElementZero v0.2 engineering direction.

---

## 0. Executive Summary

ElementZero is a validation-first computational science project for predicting nuclear and, later, atomic properties beyond experimentally known regions.

The program did not begin with a machine-learning objective. It began with a physics question: whether theoretically predicted regions of enhanced stability in the superheavy and hyperheavy nuclear landscape — especially the region around proton number `Z ~ 154–156` and neutron number `N ~ 308–310` — could eventually be investigated computationally with enough credibility to justify future experimental attention.

The research led to a strong change in strategy:

> ElementZero should not begin by predicting unknown nuclei. It should first prove that its models, uncertainty estimates, and scientific workflow can predict measurements that are already known to us but deliberately hidden from the system.

This produces a staged program:

```text
known nuclear data
    |
    v
physics baselines
    |
    v
AI / statistical correction
    |
    v
blind historical validation
    |
    v
regional extrapolation tests
    |
    v
hidden-shell rediscovery
    |
    v
multi-observable validation
    |
    v
superheavy blind validation
    |
    v
unknown nuclear landscape
    |
    v
hyperheavy targets such as Z ~ 154–156
```

The research also showed that ElementZero should **not** independently re-create every scientific-inference primitive. The Sovrance Atlas repository already contains a Physics Intermediate Representation (PIR), append-only provenance, typed evidence levels, pass-honesty rules, forward recompilation, hypothesis/intervention abstractions, and optimal-intervention search. Atlas therefore becomes the upstream evidence substrate for ElementZero rather than a codebase to fork.

The recommended conceptual separation is:

```text
Atlas
  = evidence, provenance, falsification,
    intervention logic, certified inference substrate

ElementZero
  = nuclear data, physics models, AI emulation,
    blind benchmarks, extrapolation, prediction ledger
```

This document records the scientific and engineering research that supports that conclusion.

---

# 1. Original Scientific Motivation: Why Z ~ 154–156 Became Interesting

The currently recognized periodic table ends at element 118, oganesson. IUPAC formally approved the names and symbols of elements 113, 115, 117, and 118 in 2016 and described the seventh row as completed while noting that searches beyond it continue.

Source:

- IUPAC, “IUPAC Announces the Names of the Elements 113, 115, 117, and 118”  
  https://iupac.org/iupac-announces-the-names-of-the-elements-113-115-117-and-118/

Above the known table, nuclear theory predicts regions of **enhanced stability**, not necessarily absolutely stable nuclei.

The distinction is essential:

```text
chemical element stability != infinite nuclear lifetime

enhanced nuclear stability =
    longer survival relative to neighboring nuclei
    because of shell effects and deformation barriers
```

## 1.1 Superheavy shell closures

Self-consistent calculations have long disagreed over the strongest proton shell closure in the superheavy region.

Important candidate proton numbers include:

```text
Z = 114
Z = 120
Z = 124
Z = 126
```

A comparatively persistent neutron closure is:

```text
N = 184
```

Kruppa et al. found strong shell stabilization at `Z = 124` and `126`, `N = 184` for many Skyrme interactions, while relativistic models favored `Z = 120`, `N = 172`.

Source:

- A. T. Kruppa et al., “Shell Corrections of Superheavy Nuclei in Self-Consistent Calculations”  
  https://arxiv.org/abs/nucl-th/9910046

A broad modern review of heaviest-nuclide experiments also summarizes the model dependence: many energy-density-functional calculations favor `Z = 120`, while alternatives give `Z = 114` or `126`; `N = 184` is more consistently predicted.

Source:

- “Recent progress in experiments on the heaviest nuclides at SHIP”  
  https://doi.org/10.1007/s40766-022-00030-5

## 1.2 Hyperheavy islands

The strongest motivation for ElementZero's eventual far-extrapolation program came from covariant density functional theory (CDFT).

Afanasjev, Agbemava, and Gyawali predicted three localized regions of spherical hyperheavy nuclei centered approximately at:

```text
(Z ~ 138, N ~ 230)
(Z ~ 156, N ~ 310)
(Z ~ 174, N ~ 410)
```

The calculations indicated that spontaneous fission, deformation, and triaxiality become decisive constraints in the hyperheavy regime.

Sources:

- A. V. Afanasjev, S. E. Agbemava, A. Gyawali, “Hyperheavy nuclei: existence and stability”  
  https://arxiv.org/abs/1804.06395
- Published version, Physics Letters B 782 (2018)  
  https://doi.org/10.1016/j.physletb.2018.05.070

A follow-up landscape study found neutron shell gaps near:

```text
N = 228
N = 308
N = 406
```

and reported a particularly large proton gap near:

```text
Z = 154
```

This made the `Z ~ 154–156`, `N ~ 308–310` region especially interesting.

Sources:

- S. E. Agbemava et al., “Extension of nuclear landscape to hyperheavy nuclei”  
  https://arxiv.org/abs/1902.10108

A later shell-structure study using a broad set of covariant energy-density functionals found substantial proton shell gaps at:

```text
Z = 154
Z = 186
```

and neutron gaps at:

```text
N = 228
N = 308
N = 406
```

It also investigated the transition toward toroidal nuclear shapes at very high proton number.

Sources:

- S. E. Agbemava, A. V. Afanasjev, “Hyperheavy spherical and toroidal nuclei: The role of shell structure”  
  https://arxiv.org/abs/2012.13799
- Physical Review C 103, 034323 (2021)  
  https://doi.org/10.1103/PhysRevC.103.034323

## 1.3 Why these results are hypotheses, not facts

These calculations involve extreme extrapolation. Different energy-density functionals can produce materially different shell closures, deformation landscapes, and fission barriers.

ElementZero must therefore never encode:

```text
"Z = 154 is stable"
```

as a premise.

The correct scientific question is:

```text
Given models that successfully predict known nuclei,
where do independent model families predict future
regions of enhanced stability, and how uncertain are
those predictions?
```

That distinction became a foundational ElementZero design rule.

---

# 2. Why a Validation-First Program Is Necessary

A model can achieve low error on a random train/test split while still being poor at extrapolation.

This problem is especially severe on the nuclear chart because neighboring nuclei are highly correlated. A random holdout may place a target nucleus next to nearly identical training nuclei.

Therefore:

```text
random interpolation accuracy
    is not equivalent to
discovery-grade extrapolation ability
```

ElementZero's central methodological decision is to require progressively harder validation.

---

# 3. The Time-Machine Benchmark

The strongest precedent we found for ElementZero's proposed historical benchmark is Neufcourt et al. (2018).

The authors trained statistical corrections using nuclei whose masses were known before 2003 and evaluated predictions against exotic nuclei measured afterward.

They used:

- Bayesian Gaussian processes,
- Bayesian neural networks,
- residual correction of global nuclear models,
- predictive credibility intervals,
- empirical coverage probability.

The study found Gaussian processes to be comparatively stable and showed that statistical residual correction could materially improve global nuclear-model predictions.

Sources:

- L. Neufcourt, Y. Cao, W. Nazarewicz, F. Viens, “Bayesian approach to model-based extrapolation of nuclear observables”  
  https://doi.org/10.1103/PhysRevC.98.034318
- Preprint  
  https://arxiv.org/abs/1806.00552

This is almost exactly the scientific philosophy we independently arrived at.

ElementZero should generalize the idea into repeated historical freezes:

```text
AME2003 -> predict later measurements

AME2012 -> predict later measurements

AME2016 -> predict later measurements

AME2020 -> future measurements as they arrive
```

The objective is not merely retrospective fitting. It is a reproducible simulation of what the system would have predicted before later measurements were known.

---

# 4. Historical Data Infrastructure

## 4.1 Atomic Mass Data Center

The Atomic Mass Data Center (AMDC) maintains the Atomic Mass Evaluation (AME) lineage and historical mass-evaluation resources.

Primary portal:

- IAEA / Atomic Mass Data Center  
  https://www-nds.iaea.org/amdc/web/amdc_en.html

IAEA catalogue description:

- https://nucleus-qa.iaea.org/Pages/amdc.aspx

Historical editions are crucial because they allow chronological knowledge freezes rather than synthetic random splits.

## 4.2 NUBASE

NUBASE provides evaluated nuclear ground-state and isomeric properties and complements mass evaluations.

ElementZero should treat AME and NUBASE as versioned evidence snapshots, not as one timeless dataset.

## 4.3 ENSDF / NNDC

The Evaluated Nuclear Structure Data File contains critically evaluated nuclear-structure and decay information.

Primary source:

- Brookhaven National Laboratory, National Nuclear Data Center  
  https://www.nndc.bnl.gov/ensdf/

ENSDF includes evaluated:

- level energies,
- half-lives,
- spin/parity,
- decay modes,
- gamma-ray properties,
- radiation data.

Archive description:

- https://www.nndc.bnl.gov/ensdfarchivals/

ElementZero should eventually use ENSDF when moving beyond mass prediction into decay and spectroscopy.

---

# 5. Benchmark Hierarchy

The research supports a benchmark ladder rather than one score.

## Level 1 — Random blind holdout

Purpose:

```text
interpolation sanity check
```

Useful but insufficient.

## Level 2 — Isotopic-chain holdout

Hide an entire chain or meaningful segment.

Purpose:

```text
local extrapolation
```

## Level 3 — Geographic nuclear-chart holdout

Remove a contiguous region of `(Z, N)`.

Purpose:

```text
regional extrapolation
```

## Level 4 — Historical Time-Machine holdout

Train only on information available before a historical cutoff.

Purpose:

```text
simulate real scientific prediction
```

## Level 5 — Hidden Shell / Hidden Island Challenge

Remove known shell-stabilized regions and ask whether the model rediscovers them.

Targets can include neighborhoods around known shell closures.

The question becomes:

```text
If the system is not told where a known stability
feature is located, does it reconstruct the feature
from physics plus surrounding evidence?
```

This is more relevant to eventual hyperheavy prediction than random RMSE alone.

---

# 6. Why Uncertainty Must Be a First-Class Output

The project cannot treat uncertainty as a cosmetic confidence bar.

Nuclear extrapolation combines several sources:

```text
experimental uncertainty
parameter uncertainty
emulator uncertainty
model discrepancy
model-family disagreement
extrapolation distance
dataset/evaluation uncertainty
```

Important foundational UQ work includes:

- J. D. McDonnell et al., “Uncertainty Quantification for Nuclear Density Functional Theory and Information Content of New Measurements”  
  https://arxiv.org/abs/1501.03572

The work demonstrates Bayesian calibration, Gaussian-process emulation, uncertainty propagation, and evaluation of how new measurements constrain nuclear DFT.

Another useful statistical survey is:

- V. Kejzlar, L. Neufcourt, W. Nazarewicz, P.-G. Reinhard, “Statistical aspects of nuclear mass models”  
  https://arxiv.org/abs/2002.04151

It discusses:

- Bayesian calibration,
- model averaging,
- empirical coverage,
- parameter reduction,
- model uncertainty.

---

# 7. Physics + AI Is Preferable to AI Alone

The research consistently favored hybrid architectures.

A strong generic form is:

```text
physics_prediction = P(Z, N, ...)
residual = experiment - physics_prediction

AI learns residual
```

Then:

```text
final_prediction =
    physics_prediction
    + learned_residual
```

Why this is attractive:

1. The physics model supplies asymptotic structure.
2. AI learns systematic deficiencies.
3. Extrapolation is not left entirely to a black-box network.
4. Model disagreement can be preserved instead of collapsed.
5. Each theoretical model can maintain its own residual model.

This approach is directly supported by the 2018 Bayesian extrapolation work and later model-mixing literature.

---

# 8. Bayesian Model Mixing and Combination

No single nuclear model should be assumed correct in the unknown regime.

Important work includes local Bayesian model mixing:

- V. Kejzlar, L. Neufcourt, W. Nazarewicz, “Local Bayesian Dirichlet mixing of imperfect models”  
  https://arxiv.org/abs/2311.01596

The work argues that local/global mixtures of imperfect models can improve both predictive accuracy and uncertainty calibration.

A very recent 2026 development is particularly relevant to ElementZero:

- B. Knight et al., “Beyond Constant Error: Heteroscedastic Bayesian Model Combination for Modeling Unmeasured Nuclei”  
  https://arxiv.org/abs/2607.14039

The paper explicitly addresses uncertainty that grows with extrapolation and uses model ensembles for unmeasured nuclei.

ElementZero should follow the same conceptual direction:

```text
uncertainty should be allowed to increase
as the model moves away from known evidence
```

rather than assuming constant residual variance.

---

# 9. Bayesian Mass Mining and BMEX

## 9.1 Bayesian Mass Mining

Kyle Godbey and collaborators have an active program described publicly as a Bayesian framework for mining evaluated nuclear mass data.

WANDA 2025 listing:

- https://conferences.lbl.gov/event/1816/

WANDA 2026 listing:

- https://conferences.lbl.gov/event/2179/?print=1

The program is directly relevant because it combines:

- evaluated nuclear mass data,
- theoretical models,
- Bayesian statistical methods,
- model mixing,
- extrapolation.

ElementZero should treat Bayesian Mass Mining as one of the closest scientific programs to its initial mass-prediction phase.

## 9.2 Bayesian Mass Explorer (BMEX)

Public software:

- GitHub: https://github.com/massexplorer/bmex-masses
- Public explorer: https://bmex.dev/
- Zenodo release: https://zenodo.org/records/15851911

BMEX is valuable as a reference for:

- exposing theoretical mass predictions,
- comparing models,
- communicating uncertainty,
- organizing mass-model datasets.

ElementZero should not clone BMEX's role; it should learn from its public model registry and presentation model.

---

# 10. BAND: Bayesian Analysis of Nuclear Dynamics

BAND is a major public software ecosystem for Bayesian nuclear analysis.

Repository:

- https://github.com/bandframework/bandframework

Project materials:

- https://bandframework.github.io/

BAND ecosystem topics include:

- Gaussian-process emulation,
- Bayesian model mixing,
- experimental design,
- uncertainty quantification,
- model calibration.

ElementZero should strongly prefer adapters to mature BAND components over independently rebuilding equivalent statistical infrastructure.

---

# 11. BUQEYE and Reduced-Order Nuclear Emulation

The BUQEYE collaboration develops Bayesian UQ and reduced-order emulators for nuclear physics.

Project:

- https://buqeye.github.io/

Software page:

- https://buqeye.github.io/software/

A central reference is:

- C. Drischler et al., “BUQEYE Guide to Projection-Based Emulators in Nuclear Physics”  
  https://arxiv.org/abs/2212.04912

Published guide:

- https://doi.org/10.3389/fphy.2022.1092931

Important concept:

```text
high-fidelity quantum solver
        |
        v
low-dimensional reduced basis
        |
        v
fast emulator
```

This provides an important independent path alongside neural surrogates and Gaussian processes.

---

# 12. Eigenvector Continuation

Eigenvector continuation (EC) is particularly attractive because it is based on a reduced quantum subspace rather than only statistical interpolation.

Reference:

- S. König et al., “Eigenvector Continuation as an Efficient and Accurate Emulator for Uncertainty Quantification”  
  https://arxiv.org/abs/1909.08446

ElementZero should eventually compare:

```text
data-driven emulator
    vs
projection/reduced-basis emulator
```

Disagreement between those two is scientifically meaningful.

Recent frontier work continues this direction. A 2026 example combines neural-network variational Monte Carlo with eigenvector continuation:

- M. Li, Y. Yang, P. Zhao, “Efficient emulation of nuclear ground states with neural-network variational Monte Carlo and eigenvector continuation”  
  https://arxiv.org/abs/2606.12998

---

# 13. BANNANE / Global Nuclear Emulation

A particularly relevant frontier project is the hierarchical Bayesian framework for simultaneous emulation across isotopic chains.

Paper:

- A. Belley, J. M. Munoz, R. F. Garcia Ruiz, “Global Framework for Simultaneous Emulation Across the Nuclear Landscape”  
  https://arxiv.org/abs/2502.20363

Public reproduction repository:

- https://github.com/munozariasjm/paper_o_bannane

The approach couples ab initio calculations to Bayesian neural emulation and jointly predicts properties such as:

- ground-state energies,
- charge radii,
- multiple isotopes.

This supports ElementZero's decision to evolve from single-target prediction into multi-observable, multi-isotope latent modeling.

---

# 14. Multi-Task Gaussian Processes

A 2025/2026 line of work jointly models nuclear masses and charge radii.

Reference:

- W. Ye, N. Wan, “Simultaneous improvements in accuracy and generalization of nuclear mass and charge radius predictions using multi-task Gaussian process approaches”  
  https://arxiv.org/abs/2507.17357

Reported values in the work include approximately:

```text
mass RMS      ~ 0.136 MeV
radius RMS    ~ 0.007 fm
```

The broader lesson is more important than the headline error:

> Related observables can constrain a shared latent nuclear representation.

ElementZero should therefore eventually model jointly:

```text
mass
binding energy
charge radius
separation energy
deformation
decay observables
```

rather than treating every property as completely independent.

---

# 15. Physically Interpretable Machine Learning

Mumpower et al. developed physically interpretable machine learning for nuclear masses.

Sources:

- M. R. Mumpower et al., “Physically Interpretable Machine Learning for nuclear masses”  
  https://arxiv.org/abs/2203.10594
- Physical Review C 106, L021301  
  https://doi.org/10.1103/PhysRevC.106.L021301

The model uses:

- physically motivated features,
- probabilistic prediction,
- soft physics constraints,
- feature importance.

ElementZero should include at least one physics-informed neural competitor, but not rely on neural methods as the sole prediction architecture.

A newer 2026 architecture embeds physical structure directly into the network design and tests prediction against nuclei newly measured after AME2016:

- P. Zai, W. Cheng, F.-S. Zhang, “Architecture as physical prior: cooperative neural network for nuclear masses”  
  https://arxiv.org/abs/2603.09747

This is especially relevant to ElementZero's Hidden Shell benchmark because the authors report learned features associated with shell effects and odd-even staggering.

---

# 16. Symbolic Regression and Scientific Discovery

ElementZero should not stop at black-box prediction.

One research branch should ask:

```text
Can the system discover compact equations
that explain recurring residual structure?
```

The strongest nuclear-specific example found is:

- J. M. Munoz, S. M. Udrescu, R. F. Garcia Ruiz, “Discovering nuclear models from symbolic machine learning,” Communications Physics (2025)  
  https://www.nature.com/articles/s42005-025-02023-2

Public code:

- https://github.com/munozariasjm/nuclear-misr

The work develops multi-objective iterated symbolic regression and applies it to:

- binding energies,
- charge radii,
- separation energies,
- stability limits.

This directly supports an ElementZero “theory discovery” branch.

---

# 17. Nuclear DNA

Public repository:

- https://github.com/strifinopoulos/Nuclear_DNA

The project is relevant to interpretable representations of nuclear structure.

ElementZero should study techniques that expose what an ML model has learned about:

- shell structure,
- proton/neutron relationships,
- regional behavior,

rather than treating model weights as scientifically meaningless internals.

---

# 18. Fission Is Essential for Hyperheavy Predictions

For a very heavy nucleus, mass prediction alone is insufficient.

Eventually ElementZero must model survival against competing decay channels, especially spontaneous fission.

## 18.1 Neural emulation of fission

Reference:

- D. Lay et al., “Neural Network Emulation of Spontaneous Fission”  
  https://arxiv.org/abs/2310.01608

The work emulates Hartree-Fock-Bogoliubov potential-energy surfaces and collective inertia with neural networks.

The reported potential-energy-surface error was on the order of hundreds of keV, demonstrating that expensive fission calculations can be emulated well enough to explore larger regions.

## 18.2 PyNEB

Project:

- https://pyneb.dev/

Paper:

- E. Flynn et al., “Nudged elastic band approach to nuclear fission pathways”  
  https://arxiv.org/abs/2203.01975

The nudged elastic band method is useful for determining fission paths through high-dimensional deformation landscapes.

ElementZero should defer this layer until its mass and structural benchmarks are mature.

---

# 19. Public High-Fidelity Nuclear Physics Tooling

The project should avoid pretending that AI replaces nuclear many-body theory.

## 19.1 NUCLEI SciDAC

The Nuclear Computational Low Energy Initiative (NUCLEI) develops high-performance computational nuclear theory with strong emphasis on uncertainty quantification.

Project:

- https://nuclei.mps.ohio-state.edu/

Project description:

- https://nuclei.mps.ohio-state.edu/content/what_is.php

SciDAC page:

- https://www.scidac.gov/projects/2022/nuclear-physics/project_2022_003.html

NUCLEI is relevant as the model for ElementZero's **high-fidelity physics tier**.

## 19.2 NuclearToolkit.jl

Repository:

- https://github.com/SotaYoshida/NuclearToolkit.jl

Potential role:

- independent many-body calculations,
- benchmark anchors,
- medium-mass nuclear calculations.

## 19.3 imsrg++

Repository:

- https://github.com/ragnarstroberg/imsrg

Potential role:

- in-medium similarity renormalization group calculations,
- independent high-fidelity reference calculations.

## 19.4 NuHamil

Repository:

- https://github.com/Takayuki-Miyagi/NuHamil-public

Potential role:

- generation of nuclear Hamiltonian matrix elements for many-body workflows.

## 19.5 nucleardatapy

Repository:

- https://github.com/jeromemargueron/nucleardatapy

Potential role:

- normalized programmatic access to nuclear information,
- research data abstraction.

ElementZero should inspect compatibility before reimplementing data ingestion from scratch.

---

# 20. FRIB and AI-Enabled Nuclear Science

The Facility for Rare Isotope Beams (FRIB) is an important external reference for where AI-enabled nuclear science is going.

FRIB describes AI/ML use in:

- particle identification,
- theoretical nuclear calculations,
- emulators,
- accelerator tuning,
- physics-informed digital twins,
- rare-isotope research.

Sources:

- FRIB AI overview  
  https://frib.msu.edu/what-we-do/artificial-intelligence
- “Artificial intelligence and machine learning advance research and accelerator performance at FRIB”  
  https://frib.msu.edu/news-center/news/artificial-intelligence-and-machine-learning-advance-research-and-accelerator
- STREAMLINE2 collaboration symposium  
  https://frib.msu.edu/news-center/news/streamline2-symposium-connects-students-and-researchers-advance-artificial
- FRIB-led Genesis Mission digital-twin award  
  https://frib.msu.edu/news-center/news/frib-led-collaboration-named-us-genesis-mission-awardee-ai-powered-accelerator

The relevant ElementZero lesson is:

```text
physics-informed digital model
    +
AI acceleration
    +
real measurements
    +
adaptive model update
```

is becoming a serious scientific-computing pattern.

---

# 21. Active Learning and Experiment Selection

ElementZero's later stages should not only ask:

```text
"What nucleus is interesting?"
```

They should ask:

```text
"What next measurement would most reduce uncertainty
or discriminate among competing models?"
```

BUQEYE has published work on Bayesian optimal experimental design.

See BUQEYE publication list:

- https://buqeye.github.io/publications/

McDonnell et al. also explicitly studied the information content of new nuclear measurements:

- https://arxiv.org/abs/1501.03572

This connects directly to Atlas's intervention-search abstraction.

---

# 22. Atomic Physics Layer

Nuclear existence does not by itself determine chemical behavior.

If ElementZero eventually predicts a nucleus that survives long enough to support an atom, a second computational tier is required.

At very high `Z`, relativistic effects are dominant.

## 22.1 NIST Atomic Spectra Database

Primary database:

- https://www.nist.gov/pml/atomic-spectra-database
- https://physics.nist.gov/PhysRefData/ASD/ionEnergy.html

The database includes critically evaluated:

- ground states,
- ionization energies,
- energy levels,
- spectral lines,
- transition probabilities.

ElementZero can use known atoms as blind validation targets for a future atomic solver layer.

## 22.2 GRASP

GRASP2018 performs multiconfiguration Dirac-Hartree-Fock atomic calculations.

Paper:

- C. Froese Fischer et al., “GRASP2018 — A Fortran 95 version of the General Relativistic Atomic Structure Package”  
  https://doi.org/10.1016/j.cpc.2018.10.032

Public code:

- https://github.com/compas/grasp
- https://github.com/jongrumer/grasp2018

## 22.3 Relativistic element-119 calculations

A useful example of the level of theory required beyond the current periodic table is:

- A. R. Saetgaraev et al., “Ionization potential and electron affinity of superheavy element 119: relativistic high-order coupled cluster study with QED corrections”  
  https://arxiv.org/abs/2509.05509

This illustrates why ElementZero's atomic tier must account for:

- relativistic electronic structure,
- high-order electron correlation,
- QED corrections.

Atomic calculations should remain downstream of nuclear-survival predictions.

---

# 23. Chemistry Validation Layer

A later chemistry layer can be validated against NIST benchmark data.

## NIST Computational Chemistry Comparison and Benchmark Database

Primary source:

- https://cccbdb.nist.gov/

The CCCBDB contains experimental and calculated data for small molecules and is explicitly designed for benchmarking computational chemistry methods.

Potential ElementZero validation targets include:

- bond lengths,
- thermochemistry,
- vibrational frequencies,
- ionization properties,
- rotational constants,
- polarizability.

The chemistry layer is intentionally out of scope for the first ElementZero releases.

---

# 24. High-Level Formation / Synthesis Research

The session also considered whether hypothetical hyperheavy nuclei could ever be produced.

This document deliberately preserves only the scientific conclusion, not operational synthesis instructions.

Current superheavy-element research relies on rare nuclear-reaction events, and production difficulty increases sharply toward larger proton number.

A broad review of extending the chart of nuclides discusses:

- fusion approaches,
- multinucleon transfer,
- rare-isotope beams,
- production limits.

Source:

- “How to extend the chart of nuclides?”  
  https://doi.org/10.1140/EPJA/S10050-020-00046-7

Astrophysical rapid-neutron-capture environments are also relevant to theoretical studies of very neutron-rich heavy nuclei.

Review:

- “Nucleosynthesis and observation of the heaviest elements”  
  https://doi.org/10.1140/epja/s10050-023-00927-7

ElementZero is a computational prediction project, not a synthesis-control system. Practical target preparation, accelerator recipes, beam parameters, or other operational production procedures are outside this research baseline.

---

# 25. Atlas Research Review

The former Global Variables research program now lives in:

- https://github.com/Sovrance/Atlas

Repository state inspected during this research:

```text
repository: Sovrance/Atlas
branch:     main
reviewed commit:
31d76d094f1206e64a6920da4775d0a684618357
```

Atlas describes itself as an observational decompilation / physics-AI program that attempts to recover structural rules under certified constraints.

The strongest ElementZero synergy is not Atlas's speculative physical conjecture.

It is the **scientific evidence substrate** already implemented in `pir/`.

---

# 26. Atlas PIR: Physics Intermediate Representation

Important current modules include:

```text
pir/models.py
pir/types.py
pir/provenance.py
pir/forward.py
pir/intervention_search.py
pir/passes.py
pir/namespaces.py
pir/canonical.py
pir/analyzers.py
```

Repository paths:

- https://github.com/Sovrance/Atlas/tree/main/pir
- https://github.com/Sovrance/Atlas/blob/main/pir/models.py
- https://github.com/Sovrance/Atlas/blob/main/pir/types.py
- https://github.com/Sovrance/Atlas/blob/main/pir/provenance.py
- https://github.com/Sovrance/Atlas/blob/main/pir/forward.py
- https://github.com/Sovrance/Atlas/blob/main/pir/intervention_search.py

Atlas PIR separates two important axes:

```text
representation level
    L0-L3

evidence/warrant level
    E0-E4
```

These are explicitly independent.

That is useful for ElementZero because:

```text
raw AME file
evaluated mass
DFT prediction
GP surrogate output
future measured value
```

should not all be treated as the same epistemic object.

---

# 27. Atlas Evidence Levels

Atlas currently defines approximately:

```text
E0  exact theorem / exact arithmetic
E1  interval-certified
E2  statistical with stated coverage
E3  simulation-conditioned
E4  proxy / indirect
```

ElementZero can use this structure to distinguish:

```text
experimental/evaluated evidence
    from
simulation/model prediction
```

This prevents an especially dangerous scientific error:

> allowing model-generated values to silently re-enter the training corpus as if they were measurements.

---

# 28. Atlas Append-Only Provenance

Atlas `pir/provenance.py` provides a FactStore with protections including:

- content-addressed facts,
- append-only semantics,
- dependency validation,
- provenance-cycle detection,
- cross-namespace transformation requirements,
- assumption invalidation,
- downstream downgrade traversal.

This is highly relevant to ElementZero's prediction ledger.

A historical prediction should never be silently overwritten after truth becomes known.

Preferred pattern:

```text
PredictionCertificate
        |
        v
immutable record
        |
later measurement appears
        |
        v
new ValidationRecord
```

not:

```text
old prediction
    silently replaced
by retrained prediction
```

---

# 29. Atlas Forward Recompilation

Atlas `pir/forward.py` implements a general pattern:

```text
recover/freeze latent structure
        |
        v
forward prediction
        |
        v
held-out comparison
```

and explicitly records that the held-out point was not reused during fitting.

This maps naturally to ElementZero's Time-Machine benchmark.

ElementZero generalization:

```text
AME2003
   |
fit
   |
freeze
   |
predict target identities
   |
finalize ledger
   |
unlock post-2003 measurements
   |
score
```

This was one of the strongest architectural synergies found in the session.

---

# 30. Atlas Intervention Search

Atlas `pir/intervention_search.py` ranks interventions using criteria including:

```text
candidate disagreement
expected information gain
identifiability reduction
cost
feasibility
```

The current implementation is heuristic-tagged and explicitly does not claim proof.

That is an excellent fit for a future ElementZero function:

```text
Given competing nuclear models,
which unmeasured nucleus would be
most informative to measure next?
```

This can later be compared against BAND/BUQEYE optimal-experimental-design methods.

---

# 31. Measurement Interfaces

Atlas also contains measurement-provenance logic that distinguishes the physical system from the apparatus and calibration route.

This is important because nuclear databases can contain:

- directly measured quantities,
- values inferred through models,
- evaluator-adopted values,
- extrapolated estimates,
- correlations,
- adjusted values.

ElementZero should preserve those distinctions.

A future normalized observation record should include enough provenance to answer:

```text
Was this measured directly?
Was it evaluator-adjusted?
Was it extrapolated?
What source edition introduced it?
What uncertainty was reported?
What assumptions entered the evaluation?
```

---

# 32. Scientific Firewall Between Atlas and ElementZero

Atlas's research conjectures must not automatically become ElementZero priors.

The correct architecture is:

```text
                   shared infrastructure
                         |
        +----------------+----------------+
        |                                 |
        v                                 v
      Atlas                           ElementZero
physics decompilation            nuclear prediction
research conjectures             validated nuclear theory
```

ElementZero may import:

- PIR data models,
- evidence levels,
- provenance,
- forward-validation abstractions,
- intervention ranking,
- pass honesty,
- canonical IDs.

It should **not** silently import:

- Atlas's global-constant conjectures,
- benchmark-specific physical conclusions,
- unrelated domain priors.

This preserves ElementZero as an independent falsifiable scientific program.

---

# 33. Why Atlas Should Be Upstream, Not Forked

The earlier project design proposed extracting a separate Physics Evidence Core from the old Global Variables codebase.

After reviewing the live Atlas repository, that plan should be superseded.

Atlas already contains the reusable PIR package.

Therefore:

```text
wrong long-term architecture:

Atlas PIR
   |
copy
   v
physics_evidence_core fork
   |
   v
ElementZero
```

Preferred:

```text
Sovrance/Atlas
     |
     | commit-pinned dependency
     v
ElementZero Atlas adapter
```

This avoids:

- code drift,
- incompatible evidence vocabularies,
- duplicated bug fixes,
- conflicting provenance semantics.

ElementZero should depend on an immutable Atlas commit or release rather than `main`.

---

# 34. Atlas Packaging Observation

At the reviewed commit, Atlas exposes `pir/` at repository root but did not present a conventional root `pyproject.toml` at the expected path during inspection.

The recommended integration step is therefore to make the reusable PIR distribution explicitly installable before ElementZero treats Atlas as a normal dependency.

Suggested distribution name:

```text
sovrance-atlas-pir
```

while preserving:

```python
import pir
```

for the Python namespace.

This is an engineering recommendation derived from the repository review, not a scientific claim.

---

# 35. Atlas Test-Discovery Observation

The current Atlas B4 production code exposes a function named:

```python
test_event(...)
```

and `tests/test_b4.py` imports it.

Because pytest discovers callables whose names begin with `test_`, that production symbol can be mistaken for a test under conventional collection.

Current files:

- https://github.com/Sovrance/Atlas/blob/main/b4_area_pipeline/pipeline.py
- https://github.com/Sovrance/Atlas/blob/main/tests/test_b4.py

Recommended upstream correction:

```python
evaluate_event(...)
```

with a temporary compatibility alias explicitly marked non-test if required.

This change is packaging/test hygiene only and must not change scientific behavior.

---

# 36. ElementZero's Initial Scientific Architecture

The research supports the following major layers.

```text
+----------------------------------------------------+
|                 Evidence / Atlas                   |
| PIR | provenance | assumptions | certificates     |
+----------------------------------------------------+
                         |
                         v
+----------------------------------------------------+
|                    Data Layer                      |
| AME | NUBASE | ENSDF | later NIST                 |
+----------------------------------------------------+
                         |
                         v
+----------------------------------------------------+
|                Physics Model Layer                 |
| SEMF | global mass models | DFT | ab initio       |
+----------------------------------------------------+
                         |
                         v
+----------------------------------------------------+
|                Statistical / AI Layer              |
| GP | residual GP | BNN | multitask | model mix    |
+----------------------------------------------------+
                         |
                         v
+----------------------------------------------------+
|                Validation Layer                    |
| Time Machine | region holdout | Hidden Shell      |
+----------------------------------------------------+
                         |
                         v
+----------------------------------------------------+
|               Immutable Prediction Ledger          |
+----------------------------------------------------+
                         |
                         v
+----------------------------------------------------+
|                 Unknown Landscape                  |
+----------------------------------------------------+
```

---

# 37. Initial Model Ladder

The first implementation should be intentionally simple enough to falsify.

## Model A — Semi-Empirical Mass Formula baseline

ASCII canonical form:

```text
A = Z + N

B(Z,N) =
    a_v*A
  - a_s*A^(2/3)
  - a_c*Z*(Z-1)/A^(1/3)
  - a_a*(N-Z)^2/A
  + a_p*pairing_sign/sqrt(A)
```

where:

```text
pairing_sign = +1  for even-even nuclei
pairing_sign = -1  for odd-odd nuclei
pairing_sign =  0  otherwise
```

This is not expected to be competitive with modern mass models.

Its purpose is:

- pipeline validation,
- unit testing,
- interpretable baseline behavior,
- residual-learning demonstration.

## Model B — Direct Gaussian process

Input initially:

```text
Z
N
A
isospin features
parity features
```

Purpose:

- statistical baseline,
- calibrated intervals,
- comparison with residual model.

## Model C — SEMF + GP residual

```text
residual =
    observed_mass
    - SEMF_mass
```

Then:

```text
predicted_mass =
    SEMF_mass
    + GP_predicted_residual
```

This should become the first serious ElementZero benchmark model.

---

# 38. Why Calibration Matters More Than a Single RMSE

ElementZero should report:

```text
MAE
RMSE
negative log predictive density
90% coverage
95% coverage
calibration error
error vs extrapolation distance
regional error
isotopic-chain error
```

A model that reports:

```text
RMSE = low
coverage = poor
```

must not be promoted as scientifically reliable.

Confidence that is systematically too narrow is a failure.

---

# 39. Hidden Shell Challenge

The project should eventually conceal known structural regions.

Example conceptual experiment:

```text
known nuclear chart
       |
remove region around shell closure
       |
train outside region
       |
predict hidden region
       |
compare with experiment
```

The discovery-oriented branch should have a stricter version in which explicit magic-number features are removed.

Two model classes should therefore coexist:

## Accuracy model

Allowed:

- known shell-distance features,
- physics-informed engineered descriptors.

## Discovery model

Restricted to more primitive inputs.

Purpose:

```text
Can shell behavior emerge rather than
being handed to the model?
```

The 2026 cooperative-network work and symbolic-regression studies support this direction.

---

# 40. Multi-Model Independence Is Important

ElementZero should not average identical variations of one theoretical family and call that consensus.

Long-term model ensemble should include independent families where feasible, such as:

```text
phenomenological mass model
Skyrme EDF
Gogny EDF
covariant/relativistic DFT
ab initio anchors where tractable
symbolic models
ML residual models
```

Model-family identity should be preserved in the prediction ledger.

Consensus is meaningful only if model diversity is real.

---

# 41. Progressive Right to Extrapolate

ElementZero should implement explicit gates.

Illustrative progression:

```text
Gate 0
pipeline integrity

Gate 1
historical mass benchmark

Gate 2
regional holdout

Gate 3
coverage/calibration

Gate 4
hidden shell rediscovery

Gate 5
multi-observable validation

Gate 6
decay/fission validation

Gate 7
blind superheavy validation

Gate 8
unknown-superheavy predictions

Gate 9
hyperheavy landscape exploration
```

A future `Z ~ 154–156` run should be impossible to label production-grade unless the earlier gates are satisfied.

---

# 42. Prediction Ledger

Every prediction should record at minimum:

```text
prediction_id
nuclide_id
observable
knowledge_cutoff
training_source_hashes
forbidden_source_hashes
physics_model
statistical_model
model_parameters
random_seed
code_commit
Atlas_commit
training_identity_digest
prediction
predictive_interval
OOD_score
model_disagreement
timestamp
```

When truth becomes available, append:

```text
truth_source
truth_value
truth_uncertainty
error
interval_hit
calibration_update
```

Never overwrite the original prediction.

---

# 43. EZ-B001

The first formal benchmark is:

```text
EZ-B001
Historical Nuclear Mass Prediction
```

Legacy name:

```text
ZME-B001
```

The benchmark should have four separated stages:

```text
1. prepare identity-only target manifest
2. freeze old knowledge and generate predictions
3. finalize immutable prediction ledger
4. unlock later truth and score
```

The prediction process must not receive the later truth file.

Target manifest contains only identity fields such as:

```text
nuclide_id
Z
N
A
```

No measured mass values may appear.

---

# 44. Why ElementZero Is Different From Existing Projects

This is an inference based on the public landscape reviewed in this session.

No single public project identified combines all of the following into one workflow:

```text
heterogeneous nuclear model ensemble
+
physics residual learning
+
chronological time-machine benchmark
+
regional nuclear-chart holdout
+
hidden-shell rediscovery
+
symbolic theory discovery
+
multi-observable emulation
+
measurement-aware evidence provenance
+
append-only prediction certificates
+
next-experiment selection
```

Individual programs already solve important pieces.

ElementZero's opportunity is integration with unusually strict scientific provenance and falsifiability.

This should not be marketed as novelty until a formal literature review is completed for publication, but it is a defensible engineering hypothesis for the project.

---

# 45. Public Project Landscape — Recommended Learning Order

## Tier 1 — Immediate

### 1. BAND
https://github.com/bandframework/bandframework

Learn:

- Bayesian infrastructure
- emulator abstractions
- model mixing
- experimental design

### 2. BMEX
https://github.com/massexplorer/bmex-masses

Learn:

- nuclear mass model registry
- uncertainty presentation
- data/model organization

### 3. Neufcourt historical extrapolation
https://doi.org/10.1103/PhysRevC.98.034318

Reproduce first.

### 4. BANNANE
https://github.com/munozariasjm/paper_o_bannane

Learn:

- hierarchical multi-isotope emulation
- Bayesian neural UQ

### 5. Nuclear MISR
https://github.com/munozariasjm/nuclear-misr

Learn:

- symbolic discovery
- multi-objective constraints
- interpretable equations

## Tier 2 — Next

### 6. BUQEYE
https://buqeye.github.io/

Learn:

- reduced-order emulation
- truncation uncertainty
- experimental design

### 7. NUCLEI SciDAC
https://nuclei.mps.ohio-state.edu/

Learn:

- high-fidelity physics
- HPC workflows
- UQ expectations

### 8. FRIB AI programs
https://frib.msu.edu/what-we-do/artificial-intelligence

Learn:

- experiment/AI integration
- digital twins
- active scientific workflows

## Tier 3 — Physics backends

### 9. NuclearToolkit.jl
https://github.com/SotaYoshida/NuclearToolkit.jl

### 10. imsrg++
https://github.com/ragnarstroberg/imsrg

### 11. NuHamil
https://github.com/Takayuki-Miyagi/NuHamil-public

### 12. nucleardatapy
https://github.com/jeromemargueron/nucleardatapy

### 13. PyNEB
https://pyneb.dev/

---

# 46. Research Risks

## Risk 1 — Leakage

The largest immediate scientific risk.

Future values can leak through:

- revised historical evaluations,
- features derived from future databases,
- target-selection logic,
- cached models,
- model pretraining,
- manually entered shell labels.

Mitigation:

```text
hash every source
freeze explicit editions
record identities
separate prediction and scoring processes
```

## Risk 2 — False confidence from interpolation

Mitigation:

```text
chronological and geographic holdouts
```

## Risk 3 — Model monoculture

Mitigation:

```text
preserve independent physics families
```

## Risk 4 — AI residual overfitting

Mitigation:

```text
historical validation
OOD scoring
coverage tests
simple baselines
```

## Risk 5 — Evaluation uncertainty treated as exact truth

Mitigation:

```text
Atlas measurement/provenance layer
source-level uncertainty
evaluation-status flags
```

## Risk 6 — Hyperheavy model disagreement

Mitigation:

```text
do not force consensus
report model-family spread
allow uncertainty to grow
```

## Risk 7 — Scientific claims outrunning evidence

Mitigation:

```text
Atlas evidence levels
prediction certificates
explicit gate status
```

---

# 47. Research Questions for the Next Phase

1. What is the cleanest reproducible parser for AME2003, 2012, 2016, and 2020?
2. Which records were experimentally measured versus extrapolated in each edition?
3. How should revisions to the same nuclide between editions be represented?
4. Which global mass-model tables are legally and technically straightforward to bundle?
5. Can the Neufcourt 2003 historical benchmark be reproduced within tolerance?
6. How should GP residual uncertainty increase with extrapolation distance?
7. Which regional holdout geometry best predicts true discovery behavior?
8. Can shell closures be rediscovered without explicit magic-number features?
9. Does multi-task mass + radius learning improve historical extrapolation?
10. Which independent DFT families should form the first serious model ensemble?
11. How should Atlas E2/E3/E4 evidence map to evaluated versus simulated nuclear properties?
12. Which intervention-search objective best approximates experimentally useful next-nuclide selection?
13. Can symbolic regression discover persistent residual structure across model families?
14. At what point should fission barriers become a mandatory gate for heavy-nucleus predictions?
15. What benchmark is sufficient before ElementZero is allowed to explore `Z > 118`?

---

# 48. Research Decisions Established in This Session

The following are project decisions, not external facts.

## Decision R-001 — Validation first

ElementZero must earn extrapolation capability on known evidence.

## Decision R-002 — Historical benchmarks are mandatory

Random holdout performance is not enough.

## Decision R-003 — Uncertainty is part of the prediction

No scalar prediction without an uncertainty model in production scientific output.

## Decision R-004 — Physics + AI

AI should augment and diagnose physics models rather than replace physics wholesale.

## Decision R-005 — Multiple independent model families

Consensus must not be manufactured from one family.

## Decision R-006 — Hidden Shell benchmark

The system must be tested on rediscovery of known structural features.

## Decision R-007 — Append-only prediction history

Predictions cannot be rewritten after truth is known.

## Decision R-008 — Atlas is upstream evidence infrastructure

ElementZero should consume Atlas PIR rather than fork it.

## Decision R-009 — Scientific firewall

Atlas conjectures do not automatically become ElementZero priors.

## Decision R-010 — Hyperheavy exploration is gated

`Z ~ 154–156` is a long-term scientific target, not an initial model objective.

---

# 49. Source Catalogue

The following catalog consolidates the sources consulted during the ElementZero session.

## A. Periodic table / superheavy / hyperheavy

1. IUPAC — Elements 113, 115, 117, 118  
   https://iupac.org/iupac-announces-the-names-of-the-elements-113-115-117-and-118/

2. Kruppa et al. — Shell Corrections of Superheavy Nuclei  
   https://arxiv.org/abs/nucl-th/9910046

3. Bender et al. — Shell structure of superheavy nuclei in self-consistent mean-field models  
   https://arxiv.org/abs/nucl-th/9906030

4. Afanasjev et al. — Hyperheavy nuclei: existence and stability  
   https://arxiv.org/abs/1804.06395

5. Published hyperheavy existence/stability paper  
   https://doi.org/10.1016/j.physletb.2018.05.070

6. Agbemava et al. — Extension of nuclear landscape to hyperheavy nuclei  
   https://arxiv.org/abs/1902.10108

7. Agbemava & Afanasjev — Hyperheavy spherical and toroidal nuclei  
   https://arxiv.org/abs/2012.13799

8. Physical Review C 103, 034323  
   https://doi.org/10.1103/PhysRevC.103.034323

9. How to extend the chart of nuclides?  
   https://doi.org/10.1140/EPJA/S10050-020-00046-7

10. Nucleosynthesis and observation of the heaviest elements  
    https://doi.org/10.1140/epja/s10050-023-00927-7

11. Recent progress in experiments on the heaviest nuclides at SHIP  
    https://doi.org/10.1007/s40766-022-00030-5

## B. Nuclear data

12. Atomic Mass Data Center  
    https://www-nds.iaea.org/amdc/web/amdc_en.html

13. IAEA AMDC catalogue  
    https://nucleus-qa.iaea.org/Pages/amdc.aspx

14. NNDC ENSDF  
    https://www.nndc.bnl.gov/ensdf/

15. ENSDF archives / description  
    https://www.nndc.bnl.gov/ensdfarchivals/

## C. Bayesian extrapolation and UQ

16. Neufcourt et al. 2018, Bayesian model-based extrapolation  
    https://doi.org/10.1103/PhysRevC.98.034318

17. Neufcourt preprint  
    https://arxiv.org/abs/1806.00552

18. McDonnell et al. — UQ for nuclear DFT and information content  
    https://arxiv.org/abs/1501.03572

19. Statistical aspects of nuclear mass models  
    https://arxiv.org/abs/2002.04151

20. Local Bayesian Dirichlet mixing of imperfect models  
    https://arxiv.org/abs/2311.01596

21. Heteroscedastic Bayesian Model Combination, 2026  
    https://arxiv.org/abs/2607.14039

22. WANDA 2025 Mass Mining program listing  
    https://conferences.lbl.gov/event/1816/

23. WANDA 2026 Mass Mining program listing  
    https://conferences.lbl.gov/event/2179/?print=1

## D. Public nuclear AI/UQ software

24. BAND Framework  
    https://github.com/bandframework/bandframework

25. BAND project materials  
    https://bandframework.github.io/

26. Bayesian Mass Explorer  
    https://github.com/massexplorer/bmex-masses

27. BMEX public site  
    https://bmex.dev/

28. BMEX Zenodo release  
    https://zenodo.org/records/15851911

29. BUQEYE  
    https://buqeye.github.io/

30. BUQEYE software  
    https://buqeye.github.io/software/

31. BUQEYE projection-based emulator guide  
    https://arxiv.org/abs/2212.04912

32. Eigenvector continuation UQ  
    https://arxiv.org/abs/1909.08446

33. Neural VMC + eigenvector continuation, 2026  
    https://arxiv.org/abs/2606.12998

34. BANNANE / global simultaneous nuclear emulation  
    https://arxiv.org/abs/2502.20363

35. BANNANE code  
    https://github.com/munozariasjm/paper_o_bannane

36. Multi-task GP for nuclear masses and radii  
    https://arxiv.org/abs/2507.17357

37. Physically interpretable ML for nuclear masses  
    https://arxiv.org/abs/2203.10594

38. Physical Review C PIML publication  
    https://doi.org/10.1103/PhysRevC.106.L021301

39. Cooperative neural architecture physical prior, 2026  
    https://arxiv.org/abs/2603.09747

40. Nuclear MISR / symbolic ML publication  
    https://www.nature.com/articles/s42005-025-02023-2

41. Nuclear MISR code  
    https://github.com/munozariasjm/nuclear-misr

42. Nuclear DNA  
    https://github.com/strifinopoulos/Nuclear_DNA

## E. Fission / nuclear landscape tooling

43. Neural Network Emulation of Spontaneous Fission  
    https://arxiv.org/abs/2310.01608

44. PyNEB  
    https://pyneb.dev/

45. Nudged elastic band nuclear fission paper  
    https://arxiv.org/abs/2203.01975

## F. Nuclear many-body / lab programs

46. NUCLEI SciDAC  
    https://nuclei.mps.ohio-state.edu/

47. NUCLEI project description  
    https://nuclei.mps.ohio-state.edu/content/what_is.php

48. SciDAC NUCLEI project page  
    https://www.scidac.gov/projects/2022/nuclear-physics/project_2022_003.html

49. NuclearToolkit.jl  
    https://github.com/SotaYoshida/NuclearToolkit.jl

50. imsrg++  
    https://github.com/ragnarstroberg/imsrg

51. NuHamil  
    https://github.com/Takayuki-Miyagi/NuHamil-public

52. nucleardatapy  
    https://github.com/jeromemargueron/nucleardatapy

53. FRIB AI overview  
    https://frib.msu.edu/what-we-do/artificial-intelligence

54. FRIB AI/ML research and accelerator article  
    https://frib.msu.edu/news-center/news/artificial-intelligence-and-machine-learning-advance-research-and-accelerator

55. FRIB STREAMLINE2  
    https://frib.msu.edu/news-center/news/streamline2-symposium-connects-students-and-researchers-advance-artificial

56. FRIB Genesis physics-informed digital twins  
    https://frib.msu.edu/news-center/news/frib-led-collaboration-named-us-genesis-mission-awardee-ai-powered-accelerator

## G. Atomic / chemistry validation

57. NIST Atomic Spectra Database  
    https://www.nist.gov/pml/atomic-spectra-database

58. NIST ionization energies  
    https://physics.nist.gov/PhysRefData/ASD/ionEnergy.html

59. GRASP2018 publication  
    https://doi.org/10.1016/j.cpc.2018.10.032

60. GRASP code  
    https://github.com/compas/grasp

61. GRASP2018 repository  
    https://github.com/jongrumer/grasp2018

62. Element 119 relativistic coupled-cluster + QED study  
    https://arxiv.org/abs/2509.05509

63. NIST CCCBDB  
    https://cccbdb.nist.gov/

## H. Sovrance Atlas

64. Sovrance Atlas repository  
    https://github.com/Sovrance/Atlas

65. Atlas PIR package  
    https://github.com/Sovrance/Atlas/tree/main/pir

66. Atlas PIR models  
    https://github.com/Sovrance/Atlas/blob/main/pir/models.py

67. Atlas evidence vocabularies  
    https://github.com/Sovrance/Atlas/blob/main/pir/types.py

68. Atlas provenance store  
    https://github.com/Sovrance/Atlas/blob/main/pir/provenance.py

69. Atlas forward recompilation  
    https://github.com/Sovrance/Atlas/blob/main/pir/forward.py

70. Atlas intervention search  
    https://github.com/Sovrance/Atlas/blob/main/pir/intervention_search.py

71. Atlas measurement analyzers  
    https://github.com/Sovrance/Atlas/blob/main/pir/analyzers.py

72. Atlas B4 pipeline  
    https://github.com/Sovrance/Atlas/blob/main/b4_area_pipeline/pipeline.py

73. Atlas B4 test file  
    https://github.com/Sovrance/Atlas/blob/main/tests/test_b4.py

---

# 50. Final Research Position

The research supports proceeding with ElementZero, but under a stricter definition than the original concept.

ElementZero should not be:

```text
an AI that predicts element 154
```

It should become:

```text
a falsifiable computational scientist
for nuclear prediction
```

The system must be able to answer:

```text
What did the system know at prediction time?

Which evidence was permitted?

Which information was forbidden?

Which physics model generated the baseline?

What statistical correction was applied?

How uncertain was the prediction?

How far outside training support was the target?

Did independent models agree?

Was the prediction frozen before truth was opened?

When truth arrived, did the uncertainty interval cover it?

Can the complete result be reproduced from source hashes,
repository commits, and seeds?
```

If ElementZero can answer those questions and repeatedly succeeds against historical blind measurements, then extrapolation into unknown nuclear territory becomes scientifically meaningful.

Only after that should the project attempt to answer the long-term question that motivated it:

```text
Does a genuinely enhanced-stability hyperheavy
region survive rigorous multi-model analysis
near Z ~ 154–156 and N ~ 308–310?
```

That is the research path established in this session.

---

## Suggested repository location

```text
docs/research/ElementZero_Initial_Research_Baseline_v0.1.md
```

## Document maintenance rule

Future research updates should:

1. preserve this file as the initial baseline;
2. create versioned successor research notes;
3. identify claims as `ESTABLISHED`, `FRONTIER`, `PROJECT_INFERENCE`, or `PROJECT_DECISION`;
4. add primary sources wherever possible;
5. never rewrite historical predictions after new evidence appears.

