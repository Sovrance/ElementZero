# Zero-Mass Element
## Research Dossier and Scientific Adjudication
**Version:** 0.1  
**Date:** 15 August 2026  
**Status:** Canonical research baseline  
**Scope:** Validation-first computational prediction of nuclear and, later, atomic properties. Experimental synthesis procedures are outside this specification.

---

## Executive Summary

**Zero-Mass Element** is a computational science program whose long-term objective is to make defensible predictions about nuclei and elements beyond the present experimental frontier. The project begins from the opposite direction: it must first demonstrate that it can reconstruct and predict properties of known nuclei under test conditions that imitate genuine scientific discovery.

The core adjudication of this research is that a single end-to-end neural network is not scientifically adequate for this goal. The strongest current evidence supports a **hybrid physics + probabilistic machine-learning architecture** in which established nuclear models generate physically constrained predictions, AI learns residual structure and expensive-solver surrogates, Bayesian or probabilistic methods quantify uncertainty, and blind historical benchmarks determine whether extrapolation claims are credible. [R8-R18]

The project therefore adopts five scientific doctrines:

1. **Validation precedes extrapolation.** Zero-Mass Element cannot enter unknown-territory mode until it passes predefined blind benchmarks on known nuclei.
2. **Time is part of the benchmark.** Historical AME and NUBASE releases make it possible to train on what was known at one date and evaluate against measurements incorporated later. [R1-R3, R9]
3. **Physics remains in the loop.** AI primarily corrects, emulates, mixes, or interrogates physics models; it is not treated as a substitute for nuclear theory. [R9-R11, R16-R22]
4. **Uncertainty is an output, not an afterthought.** Every prediction must carry calibrated predictive uncertainty, model disagreement, and an extrapolation-risk score. [R9, R10, R24, R25]
5. **Discovery models are separated from production models.** A high-accuracy model may use known shell features; a separate restricted-feature model must be able to rediscover hidden shell structure without being handed the answer.

The initial product, **Zero-Mass Element v0.1: Nuclear Mass Oracle**, will ingest historical AME/NUBASE data, separate measured/evaluated facts from extrapolated estimates, fit conventional physics baselines, learn probabilistic residual corrections, and run four benchmark families: random blind, isotopic-chain blind, geographic-region blind, and historical time-machine blind. It will also calculate derived observables such as one- and two-nucleon separation energies from predicted masses.

The long-term progression is intentionally staged: masses -> charge radii -> deformation and shell diagnostics -> decay -> fission potential-energy surfaces -> superheavy blind challenge -> unknown nuclear landscape. Only after that does the program add relativistic atomic structure and chemistry, eventually permitting a principled investigation of predicted hyperheavy regions such as Z approximately 154-156 and N approximately 308-310. [R26-R28]

---

## 1. Scientific Problem

The nuclear chart is not a conventional tabular prediction problem. Neighboring nuclides share strong physical correlations, known experimental data are concentrated near stability, uncertainties are heterogeneous, and theoretical disagreement grows quickly as calculations move toward neutron-rich, proton-rich, superheavy, and hyperheavy regions. A model can appear excellent under random cross-validation while failing at the actual task of interest: extrapolation.

The target question is therefore not:

> Can an ML model fit known nuclear masses?

It is:

> Can a computational system predict measurements it has never been allowed to see, remain calibrated as it moves away from training data, and correctly signal when the extrapolation is no longer trustworthy?

That distinction determines the entire architecture.

### 1.1 What counts as success

Zero-Mass Element will treat predictive credibility as a conjunction of:

- accurate point predictions;
- calibrated probability intervals;
- stable performance under spatially structured holdouts;
- historical prediction of measurements that were unknown at the training cutoff;
- recovery of known shell signatures when those regions are hidden;
- controlled degradation with extrapolation distance;
- reproducibility from immutable data/model snapshots;
- agreement or explainable disagreement among independent physics/model families.

A low test RMSE alone is not sufficient.

---

## 2. Authoritative Data Foundations

### 2.1 AME and NUBASE

The IAEA-hosted Atomic Mass Data Center provides the critical foundation for a chronological benchmark because it exposes current and historical Atomic Mass Evaluation and NUBASE products. AME2020 is the current mass evaluation exposed by the AMDC as of this research date, and NUBASE2020 provides recommended basic properties for known ground states and isomers. [R1-R3]

The data layer must preserve the distinction between:

- direct or evaluated experimental information;
- values inferred through the AME evaluation network;
- extrapolated or estimated values;
- uncertainties and evaluation flags;
- edition/publication date.

A central no-leakage rule is that **estimated values cannot be silently promoted to experimental truth**. Every row must retain its source status.

### 2.2 ENSDF and NNDC

ENSDF provides critically evaluated nuclear structure and decay information, including levels, half-lives, decay modes, spin/parity and radiation data. It is maintained by the National Nuclear Data Center and updated through an international evaluation network. [R4, R5]

ENSDF becomes essential after the mass-only v0.1 phase, because the later system will validate predictions of:

- ground and excited-state structure;
- spin/parity;
- half-lives and decay modes;
- level energies;
- spectroscopic signatures.

### 2.3 NIST atomic data

The eventual atomic-physics layer should use NIST's Atomic Spectra Database as a truth source for ionization energies, ground states and atomic energy levels. [R6, R7]

This separation is important: **nuclear validation and atomic validation are distinct scientific tasks**. The chemistry of a hypothetical element should not be inferred until the nuclear system has established a plausible isotope and the atomic model has passed blind relativistic atomic benchmarks on known heavy elements.

---

## 3. Why Naive Machine Learning Is Not Enough

The nuclear chart contains local smoothness, pairing patterns, shell closures, deformation transitions and long-range systematics. Random train/test splits can leak this structure because a withheld nucleus may be surrounded by nearly identical neighbors in the training set.

The 2022 RMP review of machine learning in nuclear physics describes the rapidly expanding role of ML across nuclear theory and experiment, but the scientific problem for Zero-Mass Element is narrower: **reliable extrapolation with uncertainty**. [R8]

Neufcourt et al. provide one of the most directly relevant demonstrations. Their 2018 study learned residuals of multiple global mass models using Bayesian Gaussian processes and Bayesian neural networks, while explicitly using nuclei whose masses were known before 2003 as training data and later-determined exotic nuclei as a test. The work found that both statistical corrections improved predictions, while GP behavior was more stable and produced useful credibility intervals. [R9]

That paper establishes three principles adopted here:

1. learn **model discrepancy/residuals**, not only the observable itself;
2. test on **chronologically newer measurements**;
3. judge uncertainty using **empirical coverage**, not just nominal intervals.

---

## 4. Recommended Modeling Philosophy: Physics + Residual Learning

The default production architecture is:

```text
physics model prediction
        +
probabilistic residual model
        =
corrected predictive distribution
```

For a nuclear observable y at nuclide x=(Z,N):

```text
y_pred(x) = y_physics(x) + delta_AI(x)
```

where delta_AI is trained on the discrepancy between physics predictions and eligible experimental/evaluated measurements.

This preserves physical asymptotic structure better than asking a generic network to extrapolate indefinitely. It also permits model-specific residuals: one GP can learn where a Skyrme-HFB model is systematically biased while another learns the discrepancy of a phenomenological mass model.

The system should initially support three families:

- **direct data models** as controls;
- **physics-residual models** as the preferred production path;
- **model ensembles/mixers** for model-form uncertainty.

Physically interpretable ML for nuclear masses further supports the use of structured features and constraints when accuracy is the objective. [R11]

---

## 5. Gaussian Processes, Bayesian Models, and 2026 Frontier Methods

### 5.1 Gaussian processes as the initial probabilistic baseline

GPs are particularly attractive for v0.1 because they naturally return predictive distributions and have a strong record in nuclear residual correction and uncertainty quantification. [R9, R10]

They also provide a scientifically useful failure mode: uncertainty tends to rise as a prediction moves away from support in the training data, if the kernel and mean structure are selected appropriately.

Zero-Mass Element should begin with conventional stationary kernels, anisotropic kernels over physically meaningful coordinates, and a residual mean anchored to a physics model. Kernel methods specifically designed to avoid degrading baseline mass predictions are relevant comparators. [R33]

### 5.2 Multitask Gaussian processes

A major 2026 result jointly predicts nuclear masses and charge radii using multitask GPs and reports overall RMS deviations of 0.136 MeV for masses and 0.007 fm for radii. [R13]

The architectural implication is not that v0.1 should immediately become multitask. Rather, v0.1 should define interfaces so v0.2 can test whether correlated observables improve the learned latent representation and extrapolation.

### 5.3 Hybrid neural + GP structures

The 2026 GPR-NN work combines neural expressivity with GP-optimized activation structure and explicitly reports that interpolation and extrapolation prefer different hyperparameters. [R15]

Zero-Mass Element should therefore never tune models only on random interpolation folds and assume those settings are appropriate for frontier prediction. **Hyperparameter selection must include an extrapolation objective.**

### 5.4 Hierarchical Bayesian neural emulation

Belley, Munoz and Garcia Ruiz introduced a 2026 hierarchical Bayesian neural framework for emulating ab-initio many-body nuclear calculations across isotopic chains, with simultaneous ground-state energy and charge-radius predictions and uncertainty quantification. [R16]

This belongs in the research track for later versions because it shows a credible path from local expensive many-body calculations to global emulation. It should not replace the simpler v0.1 benchmark stack; it should be tested against it.

### 5.5 Physics-embedded Bayesian models

Physics-embedded BNN work on structured fission observables demonstrates another useful design pattern: incorporate physically motivated quantities as explicit inputs rather than forcing the network to rediscover all known structure. [R32]

This motivates the two-track design described later: a **production model** may use such knowledge; a **discovery model** must not receive target shell labels when the goal is rediscovery.

---

## 6. Multitask and Multi-Observable Learning

A nucleus is a coupled physical object; its mass, radius, separation energies, deformation, shell structure and decay behavior are not independent. The research frontier increasingly exploits this structure. [R13, R14]

The recommended progression is:

```text
v0.1: mass / mass excess
  -> derived S_n, S_2n, S_p, S_2p
v0.2: + charge radius
v0.3: + deformation and shell diagnostics
v0.4: + decay observables
v0.5: + fission surfaces and collective quantities
```

Derived separation energies should be calculated from predicted masses rather than independently learned in the first implementation, because this enables consistency tests. Later models may jointly learn them as auxiliary tasks and be penalized when outputs violate algebraic consistency.

A multitask latent state can be interpreted as a compressed representation of nuclear structure. However, Zero-Mass Element must verify that multitask learning improves **out-of-distribution performance**, not merely average interpolation accuracy.

---

## 7. Emulation of Expensive Physics Solvers

There are two separate places for AI:

1. **residual correction against experiment**;
2. **emulation of expensive theoretical solvers**.

These must remain separate in the codebase and evaluation reports.

### 7.1 Neural emulation of fission calculations

Lay et al. used constrained HFB calculations to generate potential-energy surfaces and collective inertia and trained neural networks to emulate these quantities. Their reported potential-energy RMS error was about 500 keV, and the resulting fission observables were sufficiently accurate to support large-scale exploration. [R17]

The lesson is that AI can turn a sparse set of expensive solver evaluations into a dense approximate physics surface, but the emulator must be validated **against the solver** before it is validated against experiment.

### 7.2 Reduced-basis and eigenvector-continuation emulators

Eigenvector continuation is an alternative to generic ML. It projects a parametric quantum problem into a low-dimensional subspace constructed from representative solutions. The 2024 RMP colloquium summarizes the theory, convergence behavior and nuclear applications. [R18]

Extended EC has also been demonstrated for generator-coordinate calculations. [R19]

Zero-Mass Element should therefore maintain an **emulator bake-off**:

- Gaussian-process surrogate;
- neural surrogate;
- eigenvector-continuation/reduced-basis surrogate where mathematically applicable.

A disagreement between emulator families is not noise to average away; it is a trigger for new high-fidelity calculations.

---

## 8. Differentiable Nuclear Physics

HFBTHO and HFODD are established EDF solvers that support large-scale nuclear-structure studies using Skyrme/Gogny/HFB frameworks. [R21, R22]

A frontier development relevant to Zero-Mass Element is HFBTHO-AD, which applies automatic differentiation to HFBTHO so derivatives of solver outputs with respect to EDF parameters can be computed. [R20]

This opens several future capabilities:

- gradient-based parameter inference;
- faster sensitivity analysis;
- Hamiltonian/functional calibration with modern optimizers;
- gradient-informed Bayesian inference;
- differentiable experiment-design loops.

The engineering recommendation is to define solver interfaces that can optionally expose Jacobians/gradients, even though v0.1 does not require them.

---

## 9. Symbolic Regression and Scientific Discovery

High prediction accuracy does not guarantee new understanding. Symbolic regression and interpretable architectures create a separate research path: can learned residual structure be compressed into an analytic relation?

The 2025 KAN study on nuclear binding energies reported competitive prediction and used symbolic regression to recover simplified analytic expressions that align with familiar liquid-drop/Bethe-Weizsaecker-like structure. [R23]

Zero-Mass Element should therefore periodically attempt to fit symbolic expressions to:

- residual mass surfaces;
- shell-gap indicators;
- deformation transition signatures;
- uncertainty growth versus extrapolation distance.

Any proposed equation must be evaluated on the same historical/geographic holdouts as the statistical model. It is not considered a scientific discovery merely because it fits the full known dataset.

---

## 10. Uncertainty Quantification: Non-Negotiable Architecture

Nuclear predictions beyond known data are dominated by several uncertainty sources:

```text
measurement / evaluation uncertainty
parameter uncertainty
emulator uncertainty
statistical residual uncertainty
model-form uncertainty
model-family disagreement
out-of-distribution / extrapolation risk
```

Bayesian nuclear DFT work demonstrates how GP emulators can support posterior inference and uncertainty propagation to masses, driplines and fission barriers. [R10]

Bayesian model averaging/ensemble approaches provide a route to mixing model families while representing model uncertainty. [R24]

The engineering system must therefore produce at least:

- posterior or predictive mean/median;
- 68%, 90% and 95% predictive intervals;
- empirical calibration report;
- continuous ranked probability score (CRPS) where practical;
- negative log predictive density/log score;
- model-family spread;
- out-of-distribution score;
- extrapolation-distance diagnostic.

A prediction may be accurate but scientifically unacceptable if its 90% intervals contain the truth only 50% of the time.

---

## 11. The Zero-Mass Element Benchmark Ladder

### 11.1 Random blind benchmark

Purpose: verify basic implementation and interpolation competence.

Use grouped splitting at the nuclide level. This benchmark has the lowest scientific weight because neighboring-data leakage can make it overly optimistic.

### 11.2 Isotopic-chain blind benchmark

Hold out complete isotope chains or contiguous segments. This tests whether the model can generalize across proton number without relying on immediate neighbors.

### 11.3 Geographic nuclear-chart blind benchmark

Remove contiguous rectangles/diamonds in (Z,N) space. Train outside the region and predict everything inside it.

This should include ordinary regions and known structure-transition regions.

### 11.4 Time-Machine benchmark

Freeze data at an historical AME/NUBASE edition and train only on information that existed at that cutoff. Predict nuclei/observables incorporated in later releases.

Canonical sequence:

```text
AME2003 -> score against later eligible measurements
AME2012 -> score against later eligible measurements
AME2016 -> score against AME2020-era additions/revisions
```

The exact benchmark generator must use provenance timestamps and status flags rather than assuming that every value in a later edition was first measured immediately after the earlier release.

### 11.5 Hidden Shell / Hidden Islands challenge

The discovery model is denied explicit magic-number features. Known shell-stabilized neighborhoods are masked from training. The system is then evaluated on whether predicted separation-energy discontinuities and local stability indicators correctly localize the hidden closure.

The benchmark should include several known closures before any superheavy challenge is permitted.

### 11.6 Superheavy blind challenge

Later, freeze the model below a selected Z boundary and predict known heavier nuclei. Repeat with progressively higher boundaries. This is the closest available analogue to the final task of moving beyond Z=118.

---

## 12. Production Track vs Discovery Track

### Production Track

Goal: best defensible predictive distribution.

May use:

- known shell-distance features;
- pairing/parity descriptors;
- deformation proxies;
- outputs of calibrated physics models;
- multitask features;
- model ensembles.

### Discovery Track

Goal: test whether structure emerges rather than being encoded.

Must begin with restricted descriptors such as:

- Z, N, A;
- asymmetry (N-Z)/A;
- parity/even-odd state only if the benchmark permits it;
- raw physics-solver outputs that do not explicitly include the hidden label.

When a shell region is hidden, features that directly encode its magic-number identity are forbidden.

This separation is essential to avoid confusing **prediction using known physics** with **rediscovery of physics**.

---

## 13. Model Adjudication

The recommended initial order is:

1. **Refit semi-empirical mass formula (SEMF) baseline** on each training snapshot.
2. **Direct GP** over physically simple coordinates as a control.
3. **SEMF + GP residual correction** as the default v0.1 probabilistic hybrid.
4. **Tree/kernel control models** to detect architecture-specific artifacts.
5. **Physics-informed neural model** with uncertainty only after the benchmark harness is stable.
6. **Published global-model residual adapters** where predictions/licensing are available.
7. **Bayesian model mixing** once multiple independent families are validated.

The SEMF baseline is deliberately simple. A sophisticated AI system that cannot consistently beat a refit liquid-drop-like baseline under honest historical holdouts has not earned complexity.

---

## 14. Hyperheavy Target: Why Z approximately 154-156 Is a Later Question

Covariant EDF calculations predict hyperheavy shell structures at proton numbers around Z=154 and neutron number N=308, with later work finding substantial shell gaps at Z=154 and 186 and N=228, 308 and 406 across a set of covariant functionals. [R26, R27]

This is scientifically compelling but highly model-dependent extrapolation. The project must therefore avoid target confirmation bias.

The correct future experiment is not:

> Confirm that Z=154, N=308 is stable.

It is:

> After the system passes known-region and superheavy validation, search the unknown landscape and report where independent model families place stability structures, including disagreements and calibrated extrapolation risk.

If the validated system converges on the published Z approximately 154/N approximately 308 region independently, confidence rises. If it does not, the disagreement is itself a research result.

The RMP review of superheavy elements underscores the coupled nuclear/atomic theoretical challenges at and beyond oganesson. [R28]

---

## 15. Future Atomic and Chemical Layers

After nuclear v1.0, Zero-Mass Element may add an atomic layer.

Candidate tools include GRASP for fully relativistic atomic structure and DIRAC for relativistic all-electron atomic/molecular calculations. [R30, R31]

Validation should proceed from known heavy atoms using NIST ASD truth data. [R6, R7]

The atomic benchmark ladder should hide:

- ionization energies;
- ground-state configurations;
- selected energy levels;
- relativistic splittings.

Only after blind validation should the system extrapolate to hypothetical atomic numbers.

A chemistry layer should be a separate project phase because an atomic electronic structure does not automatically determine condensed-phase or molecular behavior.

---

## 16. Frontier Research Tracks Worth Monitoring

The following methods are promising but should remain gated behind benchmark evidence:

- multitask GPs and multi-observable latent states [R13];
- hybrid GPR-neural architectures specialized for extrapolation [R15];
- hierarchical BNN emulators of ab-initio calculations [R16];
- physics-embedded BNNs [R32];
- neural HFB/fission emulation [R17];
- reduced-basis/eigenvector continuation [R18, R19];
- automatic differentiation of EDF solvers [R20];
- symbolic regression/KAN interpretability [R23];
- Bayesian model mixing [R24];
- quantified nuclear-landscape limits [R25].

These tracks should be adopted only when they improve at least one of: extrapolation accuracy, uncertainty calibration, compute efficiency, interpretability, or experimental value-of-information.

---

## 17. Scientific Failure Modes and Controls

### Leakage

**Risk:** a feature, later evaluation, global fit, or derived table leaks post-cutoff information.

**Control:** immutable snapshot manifests, source publication dates, feature lineage and strict historical eligibility rules.

### Neighbor interpolation masquerading as extrapolation

**Risk:** random splits produce excellent results with little relevance to unknown nuclei.

**Control:** geographic and chronological holdouts are primary release gates.

### Overconfident uncertainty

**Risk:** nominal 90% intervals cover far less than 90% out of distribution.

**Control:** empirical coverage curves, recalibration, distance-stratified coverage and rejection/abstention thresholds.

### Model monoculture

**Risk:** one EDF or AI architecture defines the entire unknown landscape.

**Control:** independent physics families and Bayesian/explicit model disagreement.

### Confirmation bias toward Z=154

**Risk:** features, hyperparameters or search objectives are tuned to reproduce a desired hyperheavy island.

**Control:** freeze the benchmark and unknown-search protocol before viewing final hyperheavy outputs; pre-register target metrics.

### AI hallucination in scientific reporting

**Risk:** language models invent numerical values or citations.

**Control:** LLMs never become sources of numerical truth. Reports are generated from structured ledger entries with source IDs and hashes.

---

## 18. Recommended Research Roadmap

| Phase | Scientific capability | Release gate |
|---|---|---|
| v0.1 | Nuclear masses + separation energies | Time-machine + regional + calibration gates |
| v0.2 | Charge radii + multitask models | Historical radius benchmark improves or remains calibrated |
| v0.3 | Deformation + shell diagnostics | Hidden Shell challenge |
| v0.4 | Decay properties | Held-out decay data + calibrated uncertainty |
| v0.5 | Fission/PES emulation | Solver-emulator fidelity + experimental cross-checks |
| v0.6 | Superheavy blind challenge | Predefined Z-boundary tests |
| v1.0 | Unknown Nuclear Landscape Explorer | All prior gates + model disagreement reporting |
| v1.x | Relativistic atomic structure | Blind NIST heavy-atom tests |
| v2.x | Hyperheavy nuclear + atomic coupled study | Independent model convergence and uncertainty discipline |

---

## 19. Final Adjudication

The most defensible Zero-Mass Element architecture is **not an AI-first element generator**. It is a falsifiable computational scientist composed of:

- authoritative historical data snapshots;
- multiple physics baselines;
- probabilistic residual learning;
- solver emulation;
- rigorous out-of-distribution benchmarks;
- calibrated uncertainty;
- model-family disagreement;
- immutable prediction provenance;
- separate production and discovery tracks.

The project should begin with a humble target: predict already-known masses as if the future data did not exist. If it cannot repeatedly predict the known future from the historical past, it has no scientific basis for claiming knowledge of the unknown future.

If it succeeds, the same infrastructure provides a disciplined route from well-measured nuclei to rare isotopes, superheavy nuclei, and eventually the hyperheavy regions that motivated the project.

---

# References

**[R1] IAEA Nuclear Data Services, Atomic Mass Data Center (AMDC).** Current and historical AME/NUBASE evaluations; authoritative data hub.  
https://www-nds.iaea.org/amdc/

**[R2] W. J. Huang et al., The AME 2020 atomic mass evaluation (I).** Chinese Physics C 45 (2021); methodology and evaluation of atomic masses.  
https://www-nds.iaea.org/amdc/ame2020/AME2020-a.pdf

**[R3] F. G. Kondev et al., The NUBASE2020 evaluation of nuclear physics properties.** Chinese Physics C 45 (2021) 030001; evaluated ground/isomer properties.  
https://www-nds.iaea.org/amdc/ame2020/NUBASE2020.pdf

**[R4] National Nuclear Data Center, Evaluated Nuclear Structure Data File (ENSDF).** Evaluated nuclear structure and decay data for known nuclides.  
https://www.nndc.bnl.gov/ensdf/

**[R5] National Nuclear Data Center, NNDC Databases.** Overview of ENSDF, NuDat, XUNDL, reaction and related nuclear databases.  
https://www.nndc.bnl.gov/databases/

**[R6] NIST Atomic Spectra Database: Ionization Energies.** Critically evaluated ground states and ionization energies of atoms and ions.  
https://physics.nist.gov/PhysRefData/ASD/ionEnergy.html

**[R7] NIST Atomic Spectra Database: Energy Levels.** Critically evaluated atomic energy levels.  
https://physics.nist.gov/PhysRefData/ASD/levels_form.html

**[R8] A. Boehnlein et al., Colloquium: Machine learning in nuclear physics.** Rev. Mod. Phys. 94, 031003 (2022); broad review of ML in nuclear physics.  
https://doi.org/10.1103/RevModPhys.94.031003

**[R9] L. Neufcourt et al., Bayesian approach to model-based extrapolation of nuclear observables.** Phys. Rev. C 98, 034318 (2018); GP/BNN residual correction, historical post-2003 test, calibrated intervals.  
https://doi.org/10.1103/PhysRevC.98.034318

**[R10] J. D. McDonnell et al., Uncertainty Quantification for Nuclear Density Functional Theory.** Phys. Rev. Lett. 114, 122501 (2015); Bayesian inference, GP emulation, uncertainty propagation.  
https://doi.org/10.1103/PhysRevLett.114.122501

**[R11] M. R. Mumpower et al., Physically interpretable machine learning for nuclear masses.** Phys. Rev. C 106, L021301 (2022); physically structured and interpretable ML.  
https://doi.org/10.1103/PhysRevC.106.L021301

**[R12] A. E. Lovell et al., Nuclear masses learned from a probabilistic neural network.** Phys. Rev. C 106, 014305 (2022); probabilistic neural modeling and UQ for masses.  
https://doi.org/10.1103/PhysRevC.106.014305

**[R13] W. Ye and N. Wan, Simultaneous improvements of nuclear mass and charge radius predictions using multitask Gaussian processes.** Phys. Rev. C 113, 024304 (2026); joint mass/radius prediction with reported 0.136 MeV and 0.007 fm overall RMS deviations.  
https://doi.org/10.1103/1mgv-jypl

**[R14] Z. Li et al., Machine-learning predictions for the nuclear charge radius.** Phys. Rev. C (2025); chronological charge-radius evaluation using SVGP and LightGBM.  
https://doi.org/10.1103/vj25-zwd3

**[R15] H.-X. Liu, S. Manzhos, and X.-H. Wu, Nuclear mass predictions using a neural network with additive Gaussian-process-optimized activation functions.** Phys. Rev. C 113, 014305 (2026); emphasizes different hyperparameters for interpolation and extrapolation.  
https://doi.org/10.1103/4qqn-ry4n

**[R16] A. Belley, J. M. Munoz, and R. F. Garcia Ruiz, Global Framework for Emulation of Nuclear Calculations.** Phys. Rev. Lett. 136, 082501 (2026); hierarchical Bayesian neural emulator for ab-initio many-body calculations and uncertainty quantification.  
https://doi.org/10.1103/mvc3-qdtc

**[R17] D. Lay et al., Neural network emulation of spontaneous fission.** Phys. Rev. C 109, 044305 (2024); neural emulation of HFB potential-energy surfaces and collective inertia.  
https://doi.org/10.1103/PhysRevC.109.044305

**[R18] T. Duguet et al., Colloquium: Eigenvector continuation and projection-based emulators.** Rev. Mod. Phys. 96, 031002 (2024); reduced-basis emulation for parametric quantum problems.  
https://doi.org/10.1103/RevModPhys.96.031002

**[R19] Q.-Y. Luo et al., Emulating the generator coordinate method with extended eigenvector continuation.** Phys. Rev. C 110, 014309 (2024); EC acceleration for nuclear collective calculations.  
https://doi.org/10.1103/PhysRevC.110.014309

**[R20] L. Hascoet et al., HFBTHO-AD: Differentiation of a nuclear energy density functional code.** 2025 preprint; automatic differentiation of HFBTHO for gradient-based optimization and UQ.  
https://arxiv.org/abs/2508.11910

**[R21] R. Navarro Perez et al., HFBTHO v3.00.** Computer Physics Communications 220 (2017) 363-375; Skyrme/Gogny HFB solver, MPI, deformation and fission-related capabilities.  
https://doi.org/10.1016/j.cpc.2017.06.022

**[R22] J. Dobaczewski et al., HFODD v3.06h.** Journal of Physics G 48 (2021) 102001; general Cartesian deformed-basis nuclear EDF solver.  
https://doi.org/10.1088/1361-6471/ac0a82

**[R23] H. Liu, J. Lei, and Z. Ren, Kolmogorov-Arnold networks in nuclear binding energy prediction.** Phys. Rev. C 111, 024316 (2025); interpretable KAN and symbolic-regression analysis.  
https://doi.org/10.1103/PhysRevC.111.024316

**[R24] Y. Saito et al., Uncertainty quantification of mass models using ensemble methods.** Phys. Rev. C 109, 054301 (2024); Bayesian model averaging/selection and model uncertainty.  
https://doi.org/10.1103/PhysRevC.109.054301

**[R25] L. Neufcourt et al., Quantified limits of the nuclear landscape.** Phys. Rev. C 101, 044307 (2020); quantified extrapolation toward nuclear driplines.  
https://doi.org/10.1103/PhysRevC.101.044307

**[R26] S. E. Agbemava et al., Extension of the nuclear landscape to hyperheavy nuclei.** Phys. Rev. C 99, 034316 (2019); CDFT prediction of hyperheavy stability regions including Z=154, N=308 shell gaps.  
https://doi.org/10.1103/PhysRevC.99.034316

**[R27] S. E. Agbemava et al., Hyperheavy spherical and toroidal nuclei: The role of shell structure.** Phys. Rev. C 103, 034323 (2021); robust shell gaps at Z=154,186 and N=228,308,406 across covariant EDFs.  
https://doi.org/10.1103/PhysRevC.103.034323

**[R28] S. A. Giuliani et al., Colloquium: Superheavy elements: Oganesson and beyond.** Rev. Mod. Phys. 91, 011001 (2019); review of superheavy nuclear/atomic theory and experiment.  
https://doi.org/10.1103/RevModPhys.91.011001

**[R29] J. J. Cowan et al., Origin of the heaviest elements: The rapid neutron-capture process.** Rev. Mod. Phys. 93, 015002 (2021); heavy-element nucleosynthesis and dependence on theoretical nuclear data.  
https://doi.org/10.1103/RevModPhys.93.015002

**[R30] GRASP - General-purpose Relativistic Atomic Structure Package.** Fully relativistic atomic electronic-structure calculations; candidate future atomic-layer solver.  
https://github.com/compas/grasp

**[R31] DIRAC - Program for Atomic and Molecular Direct Iterative Relativistic All-electron Calculations.** Relativistic quantum chemistry platform; DIRAC26 documentation current in 2026.  
https://www.diracprogram.org/

**[R32] J. Chen et al., Physics-embedded Bayesian neural network for fission product yields.** Phys. Rev. C 113 (2026); physics-embedded Bayesian ML for structured nuclear observables.  
https://doi.org/10.1103/w3y1-6xw1

**[R33] X.-H. Wu et al., Nuclear mass predictions with anisotropic kernel ridge approaches.** Phys. Rev. C 110, 034322 (2024); kernel methods designed to avoid degrading baseline predictions.  
https://doi.org/10.1103/PhysRevC.110.034322
