# Real AME historical ingestion

EZ-B001 is ready to consume official AMDC mass tables once they are placed
on disk. ElementZero does not vendor copyrighted AME source files.

```text
AME2003  mass.mas03  -> training freeze
AME2012 / AME2016 / AME2020  -> later identity-only targets + scoring truth
```

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

Target selection for the first falsifiable run should be the nuclides that
are ground-truth eligible in the later edition and absent from the training
freeze. The adapters already distinguish experimental/evaluated rows from
`#`-marked extrapolated estimates.
