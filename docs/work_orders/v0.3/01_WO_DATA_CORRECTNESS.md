# WO-01 - Data Correctness and AME Parser Certification

Priority: BLOCKER
Repository: ElementZero
Start condition: current main branch green
Blocks: WO-02 through WO-10

## Objective

Make AME ingestion sufficiently trustworthy that a parser bug cannot invalidate every downstream benchmark.

This work order has four mandatory outcomes:

1. edition-specific fixed-width parsing,
2. honest evaluation-status semantics,
3. correct historical target eligibility,
4. official-row golden tests.

## Current code to modify

Primary:

    src/elementzero/data/amdc/common.py
    src/elementzero/data/amdc/ame2003.py
    src/elementzero/data/amdc/ame2012.py
    src/elementzero/data/amdc/ame2016.py
    src/elementzero/data/amdc/ame2020.py
    src/elementzero/data/observations.py
    src/elementzero/benchmark/b001_prepare.py

Tests:

    tests/unit/test_ame_parser.py
    tests/helpers.py

Schemas likely affected:

    schemas/nuclear_observation.schema.json

Documentation:

    VERSION
    README.md
    docs/benchmarks/ame-historical.md

## 1. Edition-specific column maps

Do not reuse AME2020 columns for earlier editions.

The official AME2016 header states:

    format:
    a1,i3,i5,i5,i5,1x,a3,a4,1x,f13.5,f11.5,...

and explicitly says that this format is identical to AME2003 and AME2012.

The AME2020 format uses:

    a1,i3,i5,i5,i5,1x,a3,a4,1x,f14.6,f12.6,...

Required zero-based slices for the fields ElementZero currently consumes:

AME2003 / AME2012 / AME2016:

    N             = (4, 9)
    Z             = (9, 14)
    A             = (14, 19)
    element       = (20, 23)
    origin        = (23, 27)
    mass_excess   = (28, 41)
    mass_unc      = (41, 52)

AME2020:

    N             = (4, 9)
    Z             = (9, 14)
    A             = (14, 19)
    element       = (20, 23)
    origin        = (23, 27)
    mass_excess   = (28, 42)
    mass_unc      = (42, 54)

Create explicit constants:

    AME_MAS03_COLUMNS
    AME_MAS12_COLUMNS
    AME_MAS16_COLUMNS
    AME_MAS20_COLUMNS

Do not alias 2003/2012/2016 to AME_MAS20_COLUMNS.

## 2. Extend ColumnMap

Add at least:

    origin: tuple[int, int]

Optional but recommended:

    line_length_expected
    mass_precision
    uncertainty_precision

The parser should preserve raw origin text in the normalized observation.

## 3. Replace overstrong status labels

Current code uses values such as:

    experimental
    evaluated
    estimated
    extrapolated

For AME ingestion, the parser generally knows whether a value is marked estimated by "#", but that alone does not prove that the adopted value is a single direct measurement.

Use a conservative vocabulary.

Recommended:

    evaluated_non_estimated
    evaluated_estimated
    extrapolated

Reserve:

    direct_measurement

for a later data source whose provenance explicitly establishes direct measurement.

Required ground truth rule for EZ-B001 v1:

    ground_truth_eligible =
        source_record_status == "evaluated_non_estimated"

Do not map every row without "#" to "experimental".

## 4. Preserve estimation markers

The AME files replace the decimal point by "#" for non-experimental estimated values.

The normalized object should retain:

    estimated_mass: bool
    estimated_uncertainty: bool
    source_origin: str

At minimum the semantic result must survive normalization.

Do not erase the distinction after parsing.

## 5. Fix target selection

Current b001_prepare.py subtracts all nuclide identities present in the old edition.

That excludes a useful historical-prediction class:

    old edition: estimated value
    later edition: non-estimated evaluated value

For EZ-B001, old estimated rows are not training truth and MUST NOT automatically remove the identity from the target set.

Change the rule to:

    old_eligible_ids =
        ids of old observations where ground_truth_eligible == True

    targets =
        later eligible ids
        minus old_eligible_ids

This means a nucleus may exist as an estimated old record and still become a target when the later edition contains a non-estimated evaluated value.

Add a regression test for exactly this case.

## 6. Parser diagnostics

Add a structured parse report.

Recommended fields:

    edition_id
    raw_source_hash
    total_lines
    parsed_records
    skipped_headers
    malformed_candidate_rows
    estimated_records
    eligible_records
    duplicate_ids
    invalid_A_equals_Z_plus_N
    parser_version

Do not silently drop a large number of candidate rows without a report.

A parse with zero records already fails; additionally fail when the malformed fraction exceeds a configurable sanity limit.

## 7. Official-row golden fixtures

Synthetic format_ame_line round trips are necessary but NOT sufficient.

Create:

    tests/fixtures/amdc/ame2003_golden.txt
    tests/fixtures/amdc/ame2012_golden.txt
    tests/fixtures/amdc/ame2016_golden.txt
    tests/fixtures/amdc/ame2020_golden.txt

Each fixture should contain a very small number of real public rows copied from the corresponding authoritative AMDC ASCII file.

For every fixture create expected JSON with:

    Z
    N
    A
    element_symbol
    mass_excess_keV
    uncertainty_keV
    estimated flag
    expected eligibility

Keep the excerpt minimal.

Do not make CI depend on the network.

## 8. format_ame_line must become edition aware

The current formatter hardcodes older precision.

Required:

    if edition <= 2016:
        mass format = f13.5
        uncertainty = f11.5

    if edition == 2020:
        mass format = f14.6
        uncertainty = f12.6

The fixture writer must use the edition spec.

## 9. Rename cleanup included in this PR

Update root VERSION to:

    ElementZero: 0.2.0
    Atlas PIR: <current pinned version/SHA>
    Bundle schema: 1.0

Move obsolete engineering documents that describe the superseded copied PEC architecture under:

    docs/legacy/

Do not delete historical documents; mark them non-normative.

## Required tests

Add at least:

    test_ame2003_golden_rows
    test_ame2012_golden_rows
    test_ame2016_golden_rows
    test_ame2020_golden_rows
    test_ame2020_wider_mass_columns
    test_estimated_row_not_ground_truth
    test_non_estimated_ame_row_is_evaluated_not_direct_measurement
    test_old_estimated_later_measured_identity_is_target
    test_parser_report_counts
    test_A_must_equal_Z_plus_N
    test_round_trip_per_edition

Run:

    python -m pytest -q tests/unit/test_ame_parser.py
    python -m pytest -q tests/leakage
    python -m pytest -q

## Acceptance gates

PASS only if:

- all four editions have explicit specs,
- 2020 uses its wider numeric fields,
- official golden rows parse exactly within source precision,
- old estimated rows can become later targets,
- no AME row is mislabeled as direct_measurement,
- parser diagnostics are emitted,
- full test suite passes.

## Stop conditions

STOP and do not proceed to WO-05 if:

- any official golden row is misparsed,
- source hashes are not stable,
- target identity rule remains ambiguous,
- AME2020 shares the old numeric slices,
- parser tests only use synthetic generated lines.

## External primary references

AME 2020 portal:
https://amdc.impcas.ac.cn/web/masseval.html

AME 2020 file list:
https://amdc.impcas.ac.cn/masstables/Ame2020/filel.html

AME 2012 file list:
https://amdc.impcas.ac.cn/masstables/ame2012/filel.html

AME publication history:
https://amdc.impcas.ac.cn/web/ame-pub.html
