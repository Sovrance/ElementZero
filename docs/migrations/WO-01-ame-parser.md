# Migration note — WO-01 AME data correctness

## Observation status vocabulary

| Previous | Current |
| --- | --- |
| `experimental` | `evaluated_non_estimated` |
| `evaluated` | `evaluated_non_estimated` |
| `estimated` | `evaluated_estimated` |
| `extrapolated` | `extrapolated` (unchanged; used when origin suggests systematics) |

`direct_measurement` is reserved and is **not** emitted by AME adapters.

EZ-B001 v1 eligibility:

```text
ground_truth_eligible = (source_record_status == evaluated_non_estimated)
```

## Target selection

`prepare_targets` subtracts only **eligible** identities from the known/old edition.
Old estimated rows no longer remove a nuclide from the later target set.

## Parser / normalizer versions

- `PARSER_VERSION = ame-parser-v3` (`#` is the Audi decimal-point marker, not a suffix to strip)
- `NORMALIZER_VERSION = ez-norm-v2`

## Schemas

`schemas/nuclear_observation.schema.json` enumerates the new statuses and optional
`estimated_mass`, `estimated_uncertainty`, and `source_origin` fields.
