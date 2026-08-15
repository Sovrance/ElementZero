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
python -m pip install -e '.[dev]'
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

## Architecture rule

```text
Atlas owns generic scientific evidence infrastructure.
ElementZero consumes Atlas through a pinned dependency and a thin adapter.
ElementZero MUST NOT copy, fork, or silently modify Atlas PIR source.
```
