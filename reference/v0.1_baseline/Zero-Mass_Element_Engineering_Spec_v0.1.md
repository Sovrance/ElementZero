# Zero-Mass Element
## Engineering Architecture and Benchmark Specification
**Version:** 0.1  
**Date:** 15 August 2026  
**Status:** Implementation baseline  
**Primary release:** Nuclear Mass Oracle  
**Research companion:** Zero-Mass Element Research Dossier v0.1

---

## 1. Purpose

This document specifies an implementable software architecture for **Zero-Mass Element**, a validation-first computational platform for nuclear-property prediction. The v0.1 system is intentionally restricted to nuclear masses/mass excess and mass-derived separation energies. Later phases expand to charge radii, deformation, shell structure, decay, fission, superheavy prediction, relativistic atomic structure and ultimately hyperheavy exploration.

The software is designed around one rule:

> No model may generate production unknown-territory claims until it has passed the benchmark gates defined in this specification.

The project is computational only. It does not define experimental synthesis, radioactive-target preparation, accelerator operation or other physical production procedures.

---

## 2. v0.1 Mission and Non-Goals

### Mission

Build a reproducible engine that can answer:

1. Given only data available before a historical cutoff, how accurately can we predict later eligible nuclear masses?
2. Do uncertainty intervals remain calibrated as predictions move farther from training support?
3. Can physics-residual AI beat conventional baselines without degrading trusted regions?
4. Can a feature-restricted discovery model reconstruct hidden shell behavior?
5. Can every result be reproduced from immutable source snapshots, code commit and model configuration?

### Non-goals for v0.1

- predicting chemistry;
- modeling element synthesis;
- operational accelerator/reaction planning;
- replacing evaluated nuclear databases;
- claiming stable undiscovered elements;
- high-fidelity fission or decay simulation;
- training an LLM as the numerical predictor.

---

## 3. System Context

```text
                   +----------------------+
                   | Authoritative Data   |
                   | AME / NUBASE         |
                   +----------+-----------+
                              |
                              v
                   +----------------------+
                   | Data Provenance Core |
                   | snapshots + flags    |
                   +----------+-----------+
                              |
                +-------------+--------------+
                |                            |
                v                            v
       +----------------+          +------------------+
       | Physics Models |          | Direct ML Models |
       +-------+--------+          +--------+---------+
               |                            |
               v                            |
       +----------------+                   |
       | Residual/UQ ML |<------------------+
       +-------+--------+
               |
               v
       +---------------------+
       | Benchmark Orchestr. |
       +----------+----------+
                  |
        +---------+----------+
        |                    |
        v                    v
+---------------+   +-------------------+
| Score/Calib.  |   | Prediction Ledger |
+-------+-------+   +---------+---------+
        |                     |
        +----------+----------+
                   v
            +-------------+
            | Gate Engine |
            +------+------+ 
                   |
            PASS --+-- FAIL
                   |
                   v
         Future extrapolation mode
```

---

## 4. Repository Layout

```text
zero-mass-element/
├── README.md
├── pyproject.toml
├── LICENSE
├── CITATION.cff
├── configs/
│   ├── datasets/
│   ├── benchmarks/
│   ├── models/
│   └── gates/
├── data/
│   ├── raw/              # immutable downloaded snapshots
│   ├── normalized/       # canonical parquet/arrow tables
│   ├── manifests/        # hashes, licenses, retrieval metadata
│   └── derived/          # separation energies, split indices
├── src/zero_mass_element/
│   ├── ingest/
│   ├── schema/
│   ├── features/
│   ├── physics/
│   ├── models/
│   ├── uncertainty/
│   ├── benchmarks/
│   ├── metrics/
│   ├── ledger/
│   ├── gates/
│   └── reporting/
├── experiments/
│   ├── time_machine/
│   ├── geographic/
│   ├── isotope_chain/
│   └── hidden_shell/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── data_contracts/
│   └── leakage/
├── notebooks/            # analysis only; never source of production results
└── reports/
```

The CLI and service/API layers should be thin wrappers around the same Python library so benchmark logic cannot diverge between interactive and automated use.

---

## 5. Canonical Data Model

### 5.1 Nuclide identity

```json
{
  "nuclide_id": "Z082-N126-gs",
  "Z": 82,
  "N": 126,
  "A": 208,
  "state": "ground",
  "isomer_index": 0
}
```

### 5.2 Observable record

```json
{
  "nuclide_id": "Z082-N126-gs",
  "observable": "mass_excess",
  "value": -21.748,
  "uncertainty": 0.001,
  "unit": "MeV",
  "source_family": "AME",
  "source_edition": "AME2020",
  "source_record_id": "...",
  "evaluation_status": "experimental_or_evaluated",
  "is_extrapolated": false,
  "publication_date": "2021-03-01",
  "retrieved_at": "...",
  "raw_snapshot_sha256": "..."
}
```

Exact values above are illustrative schema examples, not authoritative database entries.

### 5.3 Required provenance fields

Every normalized record MUST include:

- source family;
- source edition/version;
- canonical source URL or identifier;
- raw file hash;
- retrieval timestamp;
- parser version;
- evaluation/measurement status;
- original uncertainty;
- original flags preserved in machine-readable form.

No preprocessing step may discard provenance.

---

## 6. Data Snapshot and Immutability Policy

### 6.1 Raw snapshots

Every external dataset acquisition creates:

```text
data/raw/<source>/<edition>/<filename>
data/manifests/<source>-<edition>.json
```

The manifest records:

```json
{
  "source": "AMDC",
  "edition": "AME2016",
  "retrieved_at": "...",
  "urls": ["..."],
  "files": [
    {"path": "...", "sha256": "...", "bytes": 0}
  ],
  "parser_commit": "git-sha",
  "license_notes": "..."
}
```

### 6.2 No silent updates

If an upstream source changes, create a new snapshot. Never overwrite a benchmarked snapshot.

### 6.3 Ground-truth eligibility

A truth-policy module decides whether each record can be used as experimental/evaluated ground truth for a given benchmark. Inputs include edition date, measurement/evaluation status and historical availability.

Estimated/extrapolated values are retained but excluded from measured-truth scoring unless a benchmark explicitly studies evaluation quality.

---

## 7. Historical No-Leakage Rules

The Time-Machine benchmark is invalid if information from after the cutoff enters through any channel.

### Forbidden leakage channels

- later AME/NUBASE values;
- features computed from later evaluations;
- hyperparameters selected using later test nuclei;
- a physics model whose parameters were calibrated using post-cutoff measurements, unless the benchmark explicitly labels it as a modern-theory counterfactual;
- precomputed tables trained on full modern data;
- target normalization statistics calculated using held-out data;
- model selection based on final benchmark scores.

### Two historical modes

**Strict Historical Mode**  
Uses only data and model parameterizations available by the cutoff date.

**Data-Historical / Modern-Theory Mode**  
Freezes experimental data at the historical date but permits a modern physics model. This is scientifically useful but MUST NOT be reported as a pure historical prediction.

Every report labels the mode prominently.

---

## 8. v0.1 Feature Sets

### 8.1 Discovery-minimal feature set

```text
Z
N
A = Z + N
asymmetry = (N - Z) / A
Z parity
N parity
A parity
```

For the strict Hidden Shell challenge, even parity features may be separately ablated.

### 8.2 Production physics feature set

May add:

- distances to established proton/neutron shell closures;
- valence counts relative to closures;
- pairing indicators;
- liquid-drop terms;
- physics-model prediction(s);
- local residual descriptors derived only from eligible training data.

Feature manifests are versioned and hashed.

### 8.3 Forbidden target leakage

No feature may use the target nuclide's later measured mass, derived later separation energy, or any statistic incorporating held-out ground truth.

---

## 9. Baseline Models

Every release MUST include simple baselines.

### B0: Constant/local mean sanity baseline

Purpose: verify benchmark mechanics.

### B1: Refit semi-empirical mass formula

Fit liquid-drop-like coefficients only on the current training split/snapshot.

Purpose: physics-informed minimum bar.

### B2: Direct Gaussian process

Input: discovery-minimal or production feature set.  
Output: predictive distribution for mass excess/binding energy.

Purpose: probabilistic non-residual control.

### B3: Physics + GP residual

```text
prediction = SEMF_or_other_physics_baseline + GP(residual)
```

This is the preferred v0.1 candidate because residual GP correction is well grounded in published nuclear extrapolation/UQ work. [R9, R10]

### B4: Kernel/tree comparator

A non-neural comparator such as kernel ridge or gradient-boosted trees. It is used to detect when claimed gains come merely from feature engineering rather than architecture. [R14, R33]

### B5: Probabilistic neural challenger

Not a release dependency. Added after B0-B4 and the benchmark harness are stable. [R12, R15]

---

## 10. Physics Adapter Interface

The physics layer must support both inexpensive formulas and external high-fidelity solvers.

```python
class PhysicsModel(Protocol):
    model_id: str
    version: str

    def predict(self, nuclides, observables): ...
    def metadata(self) -> dict: ...
    def supports_gradients(self) -> bool: ...
    def gradients(self, nuclides, parameters=None): ...
```

Initial adapter:

- `SEMFAdapter`

Future adapters:

- imported global mass-model predictions;
- HFBTHO [R21];
- HFODD [R22];
- differentiable HFBTHO-AD [R20];
- covariant EDF solvers for hyperheavy studies.

Solver execution must be sandboxed from benchmark orchestration so a solver cannot access held-out truth data.

---

## 11. Probabilistic Model Interface

```python
class PredictiveModel(Protocol):
    def fit(self, train_dataset, feature_manifest, seed): ...
    def predict_distribution(self, X): ...
    def save(self, artifact_dir): ...
    def load(self, artifact_dir): ...
```

A predictive distribution MUST expose at minimum:

```text
mean or median
standard deviation or equivalent scale
quantiles: 0.025, 0.05, 0.16, 0.50, 0.84, 0.95, 0.975
```

If a model cannot natively provide uncertainty, it cannot become the sole production model. It may participate as a point-prediction comparator.

---

## 12. Benchmark Orchestrator

All benchmark definitions are declarative YAML/JSON and immutable once a release candidate begins.

Example:

```yaml
benchmark_id: time_machine_2012_to_2020_v1
mode: strict_historical
train:
  source: AME2012
  eligibility: measured_or_evaluated_non_extrapolated
validation:
  strategy: blocked_region_cv
score:
  source: AME2020
  require_not_available_in_training_snapshot: true
metrics:
  - rmse
  - mae
  - crps
  - coverage_68
  - coverage_90
  - coverage_95
```

The orchestrator creates explicit immutable `train_ids`, `validation_ids`, and `test_ids` files. Models receive only the train partition.

---

## 13. Benchmark Families

### 13.1 Random Blind

- Group by nuclide ID.
- Multiple fixed seeds.
- Lowest release weight.

### 13.2 Isotope-Chain Blind

Hold out entire chains or contiguous segments.

Report error versus distance from nearest training isotope.

### 13.3 Geographic Blind

Hold out contiguous regions in (Z,N) space.

Recommended shapes:

- rectangles;
- Manhattan-radius diamonds;
- shell-neighborhood masks.

### 13.4 Time-Machine

At minimum implement AME2003, AME2012, AME2016 and AME2020 adapters where usable from AMDC historical files. [R1-R3]

The first release should include at least two historical transitions with verified record-level eligibility.

### 13.5 Hidden Shell Challenge

A separate benchmark suite masks several known shell neighborhoods and scores whether a restricted-feature model reconstructs the expected local structure in separation energies.

The hidden region definitions are frozen before model tuning.

### 13.6 Future Superheavy Blind Challenge

Not enabled in v0.1. Later versions will train below predefined Z boundaries and score known heavier nuclei before any unknown extrapolation.

---

## 14. Derived Observables

Given mass predictions, calculate consistent derived quantities from the same sampled predictive draws rather than plugging only posterior means into formulas.

Required v0.1 derived outputs:

- one-neutron separation energy S_n;
- two-neutron separation energy S_2n;
- one-proton separation energy S_p;
- two-proton separation energy S_2p.

Uncertainty propagation MUST preserve correlations when the model supplies them. If covariance is unavailable, the report must state the approximation.

Derived-observable tests are critical because shell closures may be more visible in separation-energy trends than in absolute mass error.

---

## 15. Metrics

### Point metrics

- RMSE;
- MAE;
- median absolute error;
- 90th/95th percentile absolute error;
- per-region RMSE;
- error stratified by even-even/even-odd/odd-even/odd-odd.

### Probabilistic metrics

- 68/90/95% interval coverage;
- interval width/sharpness;
- CRPS;
- negative log predictive density where defined;
- calibration curve deviation.

### Extrapolation metrics

- error versus nearest-training distance in (Z,N);
- error versus model OOD score;
- calibration versus distance;
- slope of uncertainty growth with distance;
- catastrophic-error rate beyond a chosen mass-error threshold.

### Hidden Shell metrics

- shell-location error in Z/N;
- local separation-energy discontinuity contrast;
- rank of the true hidden closure among candidate regions;
- uncertainty-aware localization score.

---

## 16. Out-of-Distribution Detection

Every prediction receives an OOD record composed from multiple signals:

```text
nearest-neighbor distance in standardized physics feature space
Mahalanobis-like distance where meaningful
GP predictive variance / epistemic proxy
ensemble disagreement
physics-model disagreement
historical support density
```

The system maps these to a qualitative risk label:

```text
LOW / MODERATE / HIGH / EXTREME
```

The mapping is calibrated on known holdouts. It is not a manually assigned aesthetic label.

---

## 17. Uncertainty and Model Mixing

### 17.1 Separate uncertainty channels

Prediction artifacts should retain:

```json
{
  "measurement_component": null,
  "statistical_model_component": 0.0,
  "physics_parameter_component": null,
  "emulator_component": null,
  "model_form_component": null,
  "ensemble_disagreement": 0.0,
  "combined_interval_method": "..."
}
```

Not every component exists in v0.1, but the schema is forward compatible.

### 17.2 Model mixing

Later versions may use Bayesian model averaging/mixing after individual model calibration. [R24]

Models with systematically poor calibration in a region should not receive high weight simply because their mean predictions happen to be close on average.

---

## 18. Prediction Ledger

Every scored or unknown prediction is immutable.

### Required ledger fields

```json
{
  "prediction_id": "uuid",
  "created_at": "timestamp",
  "model_id": "...",
  "model_artifact_sha256": "...",
  "code_commit": "git-sha",
  "environment_digest": "...",
  "dataset_manifest_ids": ["..."],
  "feature_manifest_id": "...",
  "benchmark_id": "...",
  "training_cutoff": "...",
  "random_seed": 0,
  "nuclide_id": "...",
  "observable": "mass_excess",
  "predictive_summary": {
    "mean": 0.0,
    "q05": 0.0,
    "q50": 0.0,
    "q95": 0.0
  },
  "ood": {"score": 0.0, "risk": "..."}
}
```

When future experimental truth becomes available, append an evaluation record. Never alter the original prediction.

---

## 19. Gate Engine

The gate engine prevents premature extrapolation.

### Gate G0 - Data integrity

PASS when:

- all raw files hashed;
- parsers reproduce row counts and key checks;
- flags/uncertainties preserved;
- no duplicated canonical nuclide-observable keys without explicit resolution.

### Gate G1 - Baseline sanity

PASS when:

- B0/B1 baselines reproduce expected qualitative trends;
- benchmark partitions are deterministic;
- units and derived-energy formulas pass unit tests.

### Gate G2 - Historical advantage

PASS when the preferred hybrid model beats the refit physics baseline on predefined Time-Machine metrics without materially worsening calibration.

### Gate G3 - Regional extrapolation

PASS when performance under geographic/isotope-chain holdouts remains within predefined error and coverage tolerances.

### Gate G4 - Calibration

Example initial requirement subject to tuning before final benchmark lock:

- nominal 90% interval empirical coverage between 85% and 95% overall;
- no major holdout region below 75% coverage without triggering HIGH/EXTREME OOD labeling.

### Gate G5 - Hidden Shell

PASS when the discovery model localizes a predefined fraction of hidden known shell neighborhoods within the benchmark's tolerance, without explicit shell-number features.

### Gate G6 - Reproducibility

A second clean environment reproduces all headline metrics within numerical tolerance from manifests only.

Unknown-territory mode remains disabled until the release's required gates pass.

---

## 20. Reporting Contract

Every model report contains:

1. dataset editions and hashes;
2. strict-historical vs modern-theory label;
3. exact split definition;
4. feature manifest;
5. physics baseline;
6. model and hyperparameters;
7. point metrics;
8. calibration metrics;
9. distance-stratified/OOD results;
10. failure examples;
11. model disagreement;
12. reproducibility IDs;
13. gate status.

Reports MUST show failures, not only aggregate wins.

LLM-generated narrative may summarize structured results but cannot invent or modify numerical outputs.

---

## 21. Test Strategy

### Unit tests

- nuclide identity parsing;
- mass/unit conversions;
- separation-energy calculations;
- feature calculations;
- uncertainty quantiles;
- hash/manifests.

### Data contract tests

- expected columns/types;
- nonnegative uncertainty;
- A = Z + N;
- no impossible negative Z/N;
- duplicate resolution policy;
- preserved source flags.

### Leakage tests

- a held-out target ID never appears in training payloads;
- later editions unavailable to historical feature code;
- feature lineage rejects post-cutoff source IDs;
- scalers/normalizers fit on train partition only.

### Statistical regression tests

Persist expected benchmark ranges rather than exact stochastic scores. Large unexpected improvements are treated as suspicious until leakage is ruled out.

---

## 22. Experiment Tracking

An experiment record should contain:

```text
experiment ID
objective
hypothesis
benchmark IDs
model IDs
predeclared primary metric
secondary metrics
seed list
start commit
artifact hashes
result
adjudication: accept / reject / inconclusive
```

This transforms model development from ad hoc tuning into a falsifiable experimental process.

---

## 23. v0.1 Implementation Milestones

### Milestone 1 - Data Foundation

Deliverables:

- AME historical ingestion;
- NUBASE metadata ingestion;
- canonical schema;
- snapshot manifests;
- unit/data-contract tests.

Exit: G0.

### Milestone 2 - Baseline Physics

Deliverables:

- SEMF fit/predict adapter;
- mass and separation-energy calculations;
- benchmark fixtures.

Exit: G1.

### Milestone 3 - Probabilistic ML

Deliverables:

- direct GP;
- residual GP;
- deterministic comparator;
- uncertainty API.

### Milestone 4 - Time-Machine

Deliverables:

- at least two chronological benchmark transitions;
- historical eligibility audit;
- calibration report.

Exit target: G2 + G4.

### Milestone 5 - Regional Extrapolation

Deliverables:

- isotope-chain masks;
- geographic masks;
- distance-stratified reports;
- OOD v1.

Exit target: G3.

### Milestone 6 - Hidden Shell

Deliverables:

- production/discovery feature manifests;
- hidden-region generator;
- shell-localization metrics.

Exit target: G5.

### Milestone 7 - Release Candidate

Deliverables:

- clean-room reproduction;
- prediction ledger;
- complete benchmark report;
- v0.1 release artifact.

Exit: G6.

---

## 24. v0.2-v1.0 Architecture Extensions

### v0.2 Charge Radius

Add charge-radius truth ingestion and multitask GP experiments motivated by recent mass/radius results. [R13, R14]

### v0.3 Deformation / Shell Discovery

Add EDF-derived deformation observables and interpretability/symbolic-regression track. [R11, R23]

### v0.4 Decay

Ingest ENSDF/NUBASE decay information and introduce calibrated survival/decay models. [R3-R5]

### v0.5 Fission

Integrate HFB/PES solver adapters and neural/GP emulators; validate emulator-to-solver fidelity before experiment comparisons. [R17, R21, R22]

### v0.6 Superheavy Blind Challenge

Define progressive Z-boundary holdouts against known superheavy data.

### v1.0 Unknown Nuclear Landscape Explorer

Enable predictions beyond established data only with:

- mandatory OOD labels;
- multiple independent model families;
- model disagreement panels;
- immutable ledger entries;
- no single-number claims without intervals.

---

## 25. Solver/Emulator Roadmap

The solver layer should eventually support:

```text
HFBTHO / HFODD high-fidelity runs
        |
        +--> Gaussian-process emulator
        +--> neural emulator
        +--> eigenvector-continuation/reduced-basis emulator where applicable
        +--> differentiable pathway via HFBTHO-AD
```

Relevant research: HFBTHO/HFODD [R21, R22], neural fission emulation [R17], eigenvector continuation [R18, R19], and HFBTHO automatic differentiation [R20].

An active-learning controller may later request the next expensive solver point where expected information gain is largest. It must operate within a bounded computational simulation domain and record every acquisition decision.

---

## 26. Production vs Discovery Pipelines

```text
                     SAME TRUTH DATA
                           |
               +-----------+-----------+
               |                       |
               v                       v
       PRODUCTION PIPELINE       DISCOVERY PIPELINE
       known physics allowed     restricted features
       shell features allowed    hidden labels forbidden
       ensemble optimization     interpretability priority
               |                       |
               v                       v
        best calibrated          can it rediscover
        predictive result        known structure?
```

The two pipelines share benchmark splits but have separate feature manifests and gate criteria.

---

## 27. Reproducibility and Environment

Required:

- pinned Python environment;
- deterministic seeds where supported;
- container image digest for official runs;
- CPU/GPU/backend metadata;
- Git commit and dirty-tree status;
- serialized feature/data manifests;
- model artifact hashes;
- exact benchmark definition.

Notebooks may explore results but official metrics are generated only by package/CLI code in CI or controlled runs.

---

## 28. CI/CD Scientific Checks

Pull requests should run:

```text
format/lint
unit tests
data-contract fixtures
leakage tests
small deterministic benchmark
schema compatibility
ledger serialization round-trip
```

Nightly/weekly research CI may run heavier fixed benchmarks.

A model change that improves one aggregate score but harms historical calibration beyond tolerance should fail the release gate until adjudicated.

---

## 29. Security and Integrity Controls

Although this is an open scientific computational project, integrity matters:

- raw source snapshots read-only after ingestion;
- signed or hashed release manifests;
- no network access during official benchmark runs when feasible;
- isolated benchmark truth store inaccessible to model training code;
- least-privilege credentials for any external data retrieval;
- automatic redaction of secrets from experiment logs.

The goal is scientific contamination prevention as much as cybersecurity.

---

## 30. Initial API Surface

### CLI

```text
zme data fetch --source amdc --edition <edition>
zme data normalize --manifest <id>
zme benchmark build --config <file>
zme train --model <config> --benchmark <id>
zme score --run <id>
zme report --run <id>
zme gates evaluate --release <id>
zme ledger verify --prediction <id>
```

These command names are an engineering proposal; exact source fetch behavior must follow source licensing and robots/access requirements.

### Python

```python
from zero_mass_element import DatasetSnapshot, Benchmark, ModelRun
```

---

## 31. Acceptance Criteria for v0.1

The first public/internal v0.1 should not be released until:

- historical AME data is normalized with source flags intact;
- at least two Time-Machine transitions run end-to-end;
- a refit SEMF baseline exists for every benchmark;
- GP residual correction is implemented;
- uncertainty calibration is measured, not assumed;
- isotope-chain and geographic holdouts are implemented;
- Hidden Shell challenge exists with frozen masks;
- every prediction is ledgered with hashes;
- a clean environment reproduces headline results;
- known limitations and failure cases are published alongside successes.

Numerical performance thresholds should be locked only after the initial baseline sweep, **before** optimizing the preferred model on final test suites.

---

## 32. Definition of Done for the Research Program's First Scientific Claim

Zero-Mass Element's first legitimate scientific claim should be modest and falsifiable, for example:

> Under predefined historical and geographic holdouts, the hybrid physics-residual model improves nuclear mass prediction relative to its physics baseline while retaining calibrated uncertainty as a function of extrapolation distance.

That statement is much stronger than claiming an absolute low RMSE on a random split.

---

## 33. Route to Z approximately 154-156

The hyperheavy search is enabled only after v1.0 gates.

Future workflow:

```text
validated known-nuclei ensemble
        -> validated superheavy holdouts
        -> multiple EDF families
        -> emulator + UQ
        -> blinded unknown-landscape scan
        -> compare independent stability structures
        -> only then inspect Z≈154-156 region
```

Published covariant EDF work identifies shell structures around Z=154/N=308 and related hyperheavy regions, making them important comparison targets but not answers that the system is allowed to optimize toward. [R26, R27]

---

## 34. Recommended Immediate Build Order

1. Initialize repository and schemas.
2. Implement source-manifest/hashing layer.
3. Ingest one modern AME edition and one historical edition.
4. Build truth eligibility and leakage tests.
5. Implement SEMF baseline.
6. Implement direct GP and residual GP.
7. Build deterministic random and geographic benchmark fixtures.
8. Implement first Time-Machine transition.
9. Add calibration/OOD report.
10. Add prediction ledger.
11. Implement second historical transition.
12. Freeze Hidden Shell benchmark definitions.
13. Run baseline sweep and set release thresholds.
14. Begin production-vs-discovery comparison.

This ordering deliberately postpones sophisticated neural architectures until data lineage and benchmarking are trustworthy.

---

# Appendix A - Research-to-Engineering Decision Matrix

| Research finding | Engineering decision |
|---|---|
| Historical post-2003 mass tests are feasible [R9] | Time-Machine benchmark is a primary gate |
| GP residuals improve model extrapolation/UQ [R9, R10] | Physics + GP residual is v0.1 preferred model |
| Multitask mass/radius GP performs strongly [R13] | Reserve multitask interface for v0.2 |
| Interpolation/extrapolation hyperparameters differ [R15] | Tune on blocked extrapolation validation, not random CV only |
| Global hierarchical BNN emulation is viable [R16] | Research challenger after baseline maturity |
| Neural networks can emulate HFB fission surfaces [R17] | Separate solver-emulator validation layer in v0.5 |
| EC accelerates parametric quantum problems [R18, R19] | Support reduced-basis emulator adapter |
| HFBTHO can be differentiated [R20] | Future gradient/Jacobian-capable solver interface |
| Interpretability/symbolic regression can recover compact relations [R23] | Separate theory-discovery pipeline |
| Bayesian model mixing captures model-form uncertainty [R24] | Ensemble/mixing layer after individual calibration |
| Hyperheavy shell gaps are model predictions [R26, R27] | Treat Z≈154 as blinded comparison target, not optimization objective |

---

# Appendix B - References

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
