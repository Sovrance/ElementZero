# Real AME historical ingestion

EZ-B001 consumes official AMDC mass tables once they are placed on disk.
ElementZero does not vendor copyrighted full AME source files. Minimal public
excerpts under `tests/fixtures/amdc/` are golden software tests only.

```text
AME2003  mass.mas03  -> training freeze
AME2012 / AME2016 / AME2020  -> later identity-only targets + scoring truth
```

Edition adapters use explicit fixed-width column maps. AME2020 uses wider
mass/uncertainty fields (`f14.6` / `f12.6`) than AME2003–2016 (`f13.5` / `f11.5`).

AME `#` markers become `evaluated_estimated` (or `extrapolated` when the origin
field indicates systematics). Non-`#` AME rows are `evaluated_non_estimated`.
AME adapters never emit `direct_measurement`.

EZ-B001 v1 ground-truth rule:

```text
ground_truth_eligible = (source_record_status == evaluated_non_estimated)
```

Target selection subtracts only **eligible** old identities. An old estimated
row may become a later target when the later edition has a non-estimated value.

Download the official tables from AMDC, then:

```bash
elementzero benchmark prepare-targets --benchmark EZ-B001 \
  --later-source data/ame/mass.mas20 --edition AME2020 \
  --known-source data/ame/mass.mas03 --known-edition AME2003 \
  --output targets.json
elementzero benchmark freeze --benchmark EZ-B001 \
  --training-source data/ame/mass.mas03 --edition AME2003 \
  --targets targets.json --output freeze.json
```
