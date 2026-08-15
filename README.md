# ElementZero

ElementZero is nuclear-mass research for the superheavy / hyperheavy landscape.
It consumes [Sovrance/Atlas](https://github.com/Sovrance/Atlas) PIR as a
commit-pinned evidence kernel and does not copy Atlas source.

v0.2 implements **EZ-B001 — Historical Nuclear Mass Prediction** (legacy alias
`ZME-B001`) with a no-leakage prepare / freeze / predict / finalize / score
protocol.

## Install

```bash
python -m pip install --upgrade pip
python tools/ensure_atlas_pir.py
python -m pip install numpy scipy scikit-learn pytest ruff
python -m pip install -e . --no-deps
```

`tools/ensure_atlas_pir.py` clones the immutable SHA in `atlas.lock.json`.
Atlas at the reviewed baseline is not yet an installable package; the tool
writes the recommended `sovrance-atlas-pir` packaging overlay into the clone
only. Do not copy `pir/` into this repository. Do not depend on Atlas `main`.

## EZ-B001

```bash
elementzero benchmark prepare-targets --benchmark EZ-B001 --later-source later.mas --edition AME2020 --known-source old.mas --known-edition AME2003 --output targets.json
elementzero benchmark freeze --benchmark EZ-B001 --training-source old.mas --edition AME2003 --targets targets.json --output freeze.json
elementzero benchmark predict --benchmark EZ-B001 --freeze freeze.json --targets targets.json --training-source old.mas --out run/prediction/
elementzero benchmark finalize --run run/prediction/
elementzero benchmark score --run run/prediction/ --truth-source later.mas --out run/scoring/
```

### Three-model suite

The frozen suite is the ordered set `EZ-SEMF-LS-v1`, `EZ-GP-DIRECT-v1`,
`EZ-SEMF-GP-RESIDUAL-v1`. Every model shares one KnowledgeFreeze, one target
set, one feature policy, and one set of source hashes, and each gets its own
sealed run directory.

```bash
elementzero benchmark suite-predict --freeze freeze.json --targets targets.json --training-source old.mas --out run/EZ-B001-A/
elementzero benchmark suite-score --suite run/EZ-B001-A/ --truth-source later.mas
```

`suite-score` writes `model_comparison.json` and `model_comparison.md`. No model
is labelled "best"; the report emits every metric for every model and states its
(empty) ranking rule explicitly.

### Scored metrics (v0.3)

```text
error_i = prediction_i - truth_i

MAE_keV   = mean(abs(error_i))
MedAE_keV = median(abs(error_i))
RMSE_keV  = sqrt(mean(error_i^2))

NLPD_i    = 0.5*log(2*pi*sigma_i^2) + 0.5*((truth_i - prediction_i)/sigma_i)^2
NLPD      = mean(NLPD_i)

coverage_90  = count(truth_i inside interval_90_i) / n
coverage_95  = count(truth_i inside interval_95_i) / n
cal_error_90 = abs(coverage_90 - 0.90)
cal_error_95 = abs(coverage_95 - 0.95)

d_L1 = abs(Z_target - Z_train) + abs(N_target - N_train)
nearest_training_L1 = min over training nuclei
I    = (N - Z) / A
```

sigma_i is the model's own predictive standard deviation, persisted in
`predictions.json` and in every prediction certificate. It is never
reconstructed from truth or from rounded intervals. Results are grouped into the
preregistered distance buckets `d=1`, `d=2`, `d=3-4`, `d>=5` and Z bands
`light` (Z<20), `medium` (20<=Z<50), `heavy` (50<=Z<82), `very_heavy` (Z>=82);
an empty group is reported with `n = 0` rather than dropped.

### Evidence graph

Each prediction run persists the Atlas lineage under `<run>/atlas/`:

```text
raw artifact -> training dataset -> knowledge freeze -> model fit
             -> prediction (one per target) -> prediction set -> finalization
                                                             -> validation (scoring)
```

`predict` writes `artifacts.json`, `events.json`, `facts.json`,
`provenance.json`; `finalize` adds `finalization_facts.json` /
`finalization_provenance.json`; `score` writes `scoring_facts.json` /
`scoring_provenance.json` beside the metrics. Bundles use Atlas canonical JSON,
so a rehydrated fact re-derives the Atlas content ID it was stored under.

## Architecture rule

```text
Atlas owns generic scientific evidence infrastructure.
ElementZero consumes Atlas through a pinned dependency and a thin adapter.
ElementZero MUST NOT copy, fork, or silently modify Atlas PIR source.
```

## Research baseline and work orders

- Canonical research basis: `docs/research/ElementZero_Initial_Research_Baseline_v0.1.md`
- Engineering work orders: `docs/work_orders/v0.3/` (start at `00_MASTER_EXECUTION_ORDER.md`)
- Agent handoff docs / task graph: `docs/00_EXECUTIVE_HANDOFF.md`, `agents/task_manifest.json`
- Superseded ZME/PEC engineering docs: `docs/legacy/` (non-normative)
- Legacy scaffolds under `scaffold/` remain for `python scripts/validate_bundle.py` smoke only
