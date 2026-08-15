# ElementZero - Visual Element Table Supplemental Engineering Plan v0.1

Status: Supplemental engineering plan
Date: 2026-08-15
Canonical project: ElementZero
Upstream evidence substrate: Sovrance/Atlas PIR

## 0. Purpose

This plan defines a visual "Element Table" that helps users see project progress over time.

The table must not be a hand-maintained illustration.

It must be generated directly from ElementZero application artifacts, especially:

- test and CI results,
- benchmark manifests,
- prediction certificates,
- scoring outputs,
- validation reports.

The design goal is:

    application outputs
        ->
    normalized visual events
        ->
    element-level progress state
        ->
    rendered extended periodic table

The visual is complementary to the scientific engine. It does not replace benchmark reports or prediction ledgers. It summarizes them.

## 1. Product outcome

ElementZero will gain a project visualization subsystem that can answer:

- Which known elements have eligible nuclear data in our system?
- Which elements have participated in historical validation?
- Which elements were included in geographic holdout benchmarks?
- Which elements contributed to shell-rediscovery benchmarks?
- Which superheavy or hyperheavy elements have only been predicted?
- Which elements are associated with candidate future island investigations?
- Is the underlying benchmark/test pipeline currently healthy?

The subsystem should render at least:

1. an extended periodic table view,
2. a machine-readable JSON state bundle,
3. an HTML page for local inspection,
4. an SVG suitable for documentation,
5. optional PNG export later.

## 2. Guiding rule

The visual table must be derived from tests and benchmark artifacts, not manually edited.

No engineer should fill tiles by hand.

Every tile status must be reproducible from committed inputs.

## 3. Relationship to current ElementZero repository

The current repository already contains the load-bearing scientific outputs that the visual system should consume.

Relevant existing paths:

    src/elementzero/benchmark/
        b001_prepare.py
        b001_freeze.py
        b001_predict.py
        b001_finalize.py
        b001_score.py
        metrics.py

    src/elementzero/data/
        identity.py
        observations.py
        source_manifest.py

    src/elementzero/evidence/
        atlas_adapter.py
        certificates.py
        freezes.py
        ledger.py

    tests/
        unit/
        integration/
        leakage/

Existing artifacts and future versions of these artifacts should become the canonical visual data sources.

## 4. Scope

In scope:

- element metadata and extended-table layout
- event extraction from benchmark/test artifacts
- element progress aggregation
- JSON state bundle
- deterministic SVG/HTML rendering
- CI publication
- local CLI commands

Out of scope for v0.1:

- real-time collaborative editing
- manual drag-and-drop tile editing
- canvas-only design tools
- changing scientific benchmark logic
- chemical-property visualization
- isotopic chart rendering beyond summary counters

A later project may add an isotope chart, but the first deliverable is an element-level progress table.

## 5. Visual model

The table should represent element-level progress, not only existence.

Each tile has two conceptually separate dimensions.

### Dimension A - Scientific existence / known status

This is primarily static at the element level.

For Z = 1..118:

    known_status = "known_element"

For Z > 118:

    known_status = "unknown_element"

This dimension should not be altered by benchmark performance.

### Dimension B - ElementZero project progress

This is dynamic and derived from artifacts.

Recommended progress stages:

    not_touched
    data_ingested
    benchmark_targeted
    historically_validated
    geographic_holdout_validated
    shell_challenge_participant
    shell_rediscovery_validated
    frontier_predicted
    candidate_island_focus

A tile may also show multiple badges, but one canonical primary stage must be selected by rule.

## 6. Extended periodic layout to Z = 200

The standard periodic table is well-defined through element 118.

For elements 119..200, the layout is a project visualization, not a claim of accepted chemical placement.

Therefore the layout must be versioned and labeled as:

    layout_profile = "extended_200_project_v1"

The UI should also support:

    layout_profile = "standard_118"

Recommended rule:

- Z = 1..118 use conventional positions
- Z = 119..200 use project-defined extension rows
- unknown placement is a display convenience only

Every rendered asset must embed:

    "Elements 119-200 are project placeholders for progress visualization,
     not official IUPAC placement."

## 7. Architecture overview

    ElementZero tests and benchmarks
             |
             v
    visual event extractors
             |
             v
    visual event log (JSONL)
             |
             v
    element progress aggregator
             |
             v
    element table state bundle (JSON)
             |
       +-----+-----+
       |           |
       v           v
    HTML render   SVG render
       |
       v
    CI / docs publication

## 8. Proposed new repository structure

Create:

    src/elementzero/visuals/
        __init__.py
        metadata.py
        event_types.py
        ingest.py
        aggregate.py
        render_html.py
        render_svg.py
        palette.py
        status.py
        labels.py

    src/elementzero/visuals/layouts/
        standard_118.json
        extended_200_project_v1.json

    schemas/
        element_progress_event.schema.json
        element_table_state.schema.json
        visual_render_bundle.schema.json

    scripts/
        build_element_table.py

    tests/unit/
        test_visual_metadata.py
        test_visual_event_ingest.py
        test_visual_aggregate.py
        test_visual_render_svg.py
        test_visual_layouts.py

    tests/integration/
        test_visual_from_synthetic_b001.py
        test_visual_from_ci_artifacts.py

    reports/visuals/
        .gitkeep

## 9. Canonical inputs

The visual subsystem should consume existing or soon-to-exist application outputs.

### 9.1 Test and CI health inputs

Primary inputs:

- pytest JSON report or JUnit XML
- GitHub Actions run summary
- benchmark report status files

Recommended v0.1 normalized source:

    .artifacts/tests/pytest-report.json

If this file does not yet exist, add it to CI using:

    pytest --json-report --json-report-file .artifacts/tests/pytest-report.json

Alternative allowed input:

    .artifacts/tests/junit.xml

But the visual extractor should normalize both into one internal format.

### 9.2 Benchmark inputs

Primary benchmark artifacts:

    experiments/EZ-B001-*/protocol.json
    experiments/EZ-B001-*/targets.json
    results/EZ-B001-*/<model_id>/scored_predictions.json
    results/EZ-B001-*/<model_id>/metrics.json
    results/EZ-B001-*/model_comparison.json

Later:

    experiments/EZ-B002-*/regions.json
    results/EZ-B002-*/...
    experiments/EZ-B003-*/...
    results/EZ-B003-*/...

### 9.3 Metadata inputs

Static metadata:

- element names and symbols
- Z number
- known/unknown classification
- tile coordinates in chosen layout
- optional project notes

Create a repository-controlled metadata file rather than inferring names from scattered code.

## 10. Element metadata file

Create:

    src/elementzero/visuals/layouts/element_metadata_v1.json

Each record should contain at least:

    Z
    symbol
    name
    known_status
    display_group
    display_period
    series
    row
    column
    layout_profile

For Z = 1..118, use the known element names and symbols.

For Z = 119..200, use project placeholders unless and until names exist.

Recommended placeholder naming:

    symbol = "E119", "E120", ...
    name = "Element 119", "Element 120", ...

This avoids embedding speculative naming conventions as though they were official.

## 11. Visual event model

Do not compute the visual directly from raw benchmark files in the renderer.

First normalize all source artifacts into event records.

Create:

    element_progress_event.schema.json

Required fields:

    event_id
    event_type
    event_time
    project_version
    source_kind
    source_path
    source_hash
    benchmark_id
    benchmark_stage
    model_id
    element_Z
    nuclide_id
    status
    payload

Recommended event types:

    TEST_SUITE_PASS
    TEST_SUITE_FAIL
    DATA_INGESTED
    HISTORICAL_TARGET_CREATED
    HISTORICAL_PREDICTION_SEALED
    HISTORICAL_VALIDATION_SCORED
    REGION_TARGET_CREATED
    REGION_VALIDATION_SCORED
    SHELL_TARGET_CREATED
    SHELL_VALIDATION_SCORED
    FRONTIER_PREDICTION_CREATED
    CANDIDATE_ISLAND_MARKED

The event log becomes the stable API between benchmark outputs and the visual layer.

## 12. Event extraction rules

### 12.1 Data-ingested event

For every eligible observation in a parsed AME dataset:

    event_type = DATA_INGESTED
    element_Z = observation.Z
    nuclide_id = observation.nuclide_id

Do not emit one event per raw line in the final state bundle; deduplicate by source hash and nuclide identity during aggregation.

### 12.2 Historical target event

For every target in EZ-B001 targets.json:

    event_type = HISTORICAL_TARGET_CREATED
    element_Z = target.Z
    nuclide_id = target.nuclide_id
    benchmark_id = EZ-B001-<epoch>

### 12.3 Historical prediction sealed

For every prediction certificate after finalization:

    event_type = HISTORICAL_PREDICTION_SEALED
    element_Z = target.Z
    nuclide_id = target.nuclide_id
    model_id = ...

### 12.4 Historical validation scored

For every scored prediction:

    event_type = HISTORICAL_VALIDATION_SCORED
    element_Z = target.Z
    nuclide_id = target.nuclide_id
    payload includes:
        abs_error_keV
        interval_hit_90
        interval_hit_95
        nearest_training_L1

### 12.5 Geographic and shell events

Same normalization pattern, using EZ-B002 and EZ-B003 identifiers.

### 12.6 Frontier prediction

For any future prediction run involving Z > 118:

    event_type = FRONTIER_PREDICTION_CREATED
    element_Z = target.Z

A frontier prediction should not upgrade the tile to "validated."

It remains a prediction-state badge.

## 13. Element progress aggregation

Aggregation consumes the event log and produces one row per element.

Create:

    element_table_state.schema.json

Required fields per element:

    Z
    symbol
    name
    known_status
    layout_profile
    row
    column

    project_primary_stage
    badges
    counts
    last_event_time
    contributing_sources
    health

Recommended `counts` fields:

    eligible_observation_count
    historical_target_count
    historical_scored_count
    geographic_target_count
    geographic_scored_count
    shell_target_count
    shell_scored_count
    frontier_prediction_count

Recommended `health` fields:

    unit_tests_green
    integration_tests_green
    leakage_tests_green
    benchmark_suite_green

## 14. Primary-stage selection rule

A deterministic priority rule is required so the same element always resolves to one primary stage.

Recommended priority from highest to lowest:

    candidate_island_focus
    shell_rediscovery_validated
    geographic_holdout_validated
    historically_validated
    frontier_predicted
    benchmark_targeted
    data_ingested
    not_touched

Refinements:

- `frontier_predicted` applies only when Z > 118 or when known elements are used in explicit frontier-mode runs
- `candidate_island_focus` should be triggered only by an explicit event, not inferred from all frontier predictions

## 15. Candidate island focus rule

The visual must not infer that any element is an "island element" merely because one model predicted an isotope there.

Add an explicit project event:

    CANDIDATE_ISLAND_MARKED

This event should be emitted only by a separate aggregation or consensus tool when project governance explicitly marks an element or region as a focus area.

Recommended payload:

    region_id
    rationale
    supporting_models
    supporting_run_ids
    review_status

Until such governance exists, do not emit this event automatically.

## 16. Test-health overlay

The user asked that the visual get results directly from application tests.

Therefore each table render should include a project health summary derived from the current test run.

Recommended extraction from pytest report:

- overall test run pass/fail
- unit test summary
- integration test summary
- leakage test summary

Map these to a small dashboard area above or below the table, for example:

    Unit tests: PASS
    Integration tests: PASS
    Leakage tests: PASS
    Visual pipeline: PASS

Optionally, the element tiles can include a subtle warning border if the latest benchmark run for that element exists but the overall pipeline health is red.

Do not let test failures silently coexist with "green" visual badges.

## 17. Renderer outputs

### 17.1 HTML renderer

Create:

    reports/visuals/element_table.html

Requirements:

- self-contained static HTML
- no backend server required
- load state JSON embedded or nearby
- supports hover tooltip for each tile
- shows:
    Z
    symbol
    project primary stage
    count summary
    latest relevant benchmark IDs

### 17.2 SVG renderer

Create:

    reports/visuals/element_table.svg

Requirements:

- deterministic output
- no raster dependencies
- suitable for GitHub Pages or documentation
- tile fill determined only by aggregated state
- legend included in the SVG

### 17.3 JSON bundle

Create:

    reports/visuals/element_table_state.json
    reports/visuals/element_progress_events.jsonl
    reports/visuals/visual_render_bundle.json

The render bundle should include hashes of the inputs used to generate the visual.

## 18. Color and icon system

Use a small stable palette.

Recommended primary colors:

    known element background            = neutral blue-gray
    unknown element background          = light gray
    data_ingested                       = blue
    benchmark_targeted                  = purple
    historically_validated              = green
    geographic_holdout_validated        = teal
    shell_rediscovery_validated         = gold
    frontier_predicted                  = orange
    candidate_island_focus              = red outline + amber fill

Do not encode meaning using color alone.

Add icons or text abbreviations, such as:

    D  = data ingested
    H  = historical validation
    G  = geographic holdout
    S  = shell rediscovery
    F  = frontier prediction
    I  = island focus

## 19. Tooltips and details

Each tile tooltip should show at minimum:

    Element symbol and name
    Z number
    known/unknown status
    primary stage
    counts:
        observations
        historical targets/scored
        geographic scored
        shell scored
        frontier predictions
    latest benchmark IDs
    latest contributing source hash or bundle hash

This keeps the table useful as a project-progress interface, not just decorative output.

## 20. CLI commands

Add CLI subcommands under the existing ElementZero CLI.

Recommended:

    elementzero visual extract-events
        --input-root <repo or artifact dir>
        --output reports/visuals/element_progress_events.jsonl

    elementzero visual aggregate
        --events reports/visuals/element_progress_events.jsonl
        --layout extended_200_project_v1
        --output reports/visuals/element_table_state.json

    elementzero visual render-html
        --state reports/visuals/element_table_state.json
        --output reports/visuals/element_table.html

    elementzero visual render-svg
        --state reports/visuals/element_table_state.json
        --output reports/visuals/element_table.svg

    elementzero visual build
        --input-root .
        --layout extended_200_project_v1
        --output-root reports/visuals/

The `build` command should orchestrate extract -> aggregate -> render.

## 21. CI integration

Add a new CI or post-benchmark step.

Recommended sequence:

1. run tests
2. run benchmarks if configured
3. export pytest JSON report
4. run `elementzero visual build`
5. publish `reports/visuals/*` as artifacts

GitHub Actions artifacts:

    elementzero-visual-table
        element_table_state.json
        element_progress_events.jsonl
        element_table.html
        element_table.svg
        visual_render_bundle.json

If benchmark artifacts are not present, the visual should still render using available test and data-ingestion events.

## 22. Failure behavior

The visual system must fail loudly but informatively.

Examples:

- if the pytest report is missing:
    render the table but mark health as unknown
- if the benchmark state JSON is malformed:
    fail the build and report which file failed validation
- if an event references Z outside 1..200:
    fail aggregation unless an explicit layout extension is allowed
- if required metadata for an element is missing:
    fail render

Do not silently drop malformed events.

## 23. Synthetic test strategy

The first implementation should not require waiting for real historical runs.

Add synthetic fixtures that mimic:

- passing pytest report
- small EZ-B001 scored_predictions.json
- small EZ-B002 result
- small EZ-B003 result

Then test:

- event extraction
- aggregation
- deterministic primary-stage selection
- HTML render contains expected labels
- SVG contains expected tile fill classes
- JSON bundle validates against schema

## 24. Acceptance tests

Required tests:

    test_element_metadata_has_1_to_200
    test_standard_layout_positions_known_elements
    test_extended_layout_has_positions_1_to_200
    test_extract_data_ingested_events
    test_extract_historical_events
    test_extract_ci_health
    test_aggregate_counts_per_element
    test_primary_stage_priority
    test_frontier_prediction_does_not_equal_validation
    test_candidate_island_requires_explicit_event
    test_svg_render_deterministic
    test_html_render_contains_legend
    test_visual_bundle_schema_validates
    test_visual_build_from_synthetic_b001
    test_visual_build_without_benchmark_outputs
    test_invalid_Z_rejected
    test_missing_element_metadata_rejected

## 25. Suggested implementation phases

### Phase V1 - Foundation

- add metadata files
- add schemas
- add event classes
- add event extractors for pytest and EZ-B001
- add aggregator
- add JSON state bundle

### Phase V2 - Rendering

- add SVG renderer
- add HTML renderer
- add legends and tooltips
- add CLI orchestration

### Phase V3 - Benchmark expansion

- ingest EZ-B002
- ingest EZ-B003
- add candidate island event support
- add CI publishing

## 26. Recommended work orders for coding agents

### VET-01 - Element metadata and layouts
Deliver:
- element_metadata_v1.json
- standard_118.json
- extended_200_project_v1.json
- layout tests

### VET-02 - Event schemas and extraction
Deliver:
- event schema
- extractors for pytest and EZ-B001 artifacts
- synthetic extractor tests

### VET-03 - Aggregator and state bundle
Deliver:
- aggregation rules
- state schema
- deterministic primary-stage selection
- bundle validator

### VET-04 - SVG and HTML renderers
Deliver:
- SVG renderer
- HTML renderer
- legend
- tooltip template
- deterministic render tests

### VET-05 - CLI and CI integration
Deliver:
- CLI commands
- build script
- GitHub Actions artifact publication
- visual build smoke test

### VET-06 - EZ-B002 and EZ-B003 integration
Deliver:
- region and shell event extraction
- expanded badges
- candidate island governance event support

## 27. Recommended artifact contracts

### 27.1 element_progress_events.jsonl

One JSON event per line.

### 27.2 element_table_state.json

Top-level fields:

    project
    generated_at
    layout_profile
    input_hashes
    test_health
    legend
    elements[]

### 27.3 visual_render_bundle.json

Top-level fields:

    state_hash
    events_hash
    html_hash
    svg_hash
    generator_version
    elementzero_commit
    atlas_commit
    source_hashes

This makes the visual output fully traceable.

## 28. Governance notes

This visual must remain an honest summary tool.

It must not:

- imply chemical acceptance for elements >118
- imply validation from prediction-only runs
- imply discovery from poor or failed benchmarks
- imply "island of stability" status without explicit governance event

The UI should display a persistent note:

    "ElementZero visual states summarize project artifacts.
     They do not constitute experimental discovery claims."

## 29. Definition of done

This supplemental plan is fully implemented when:

- ElementZero can build a visual element table from committed test/benchmark artifacts,
- the build is deterministic,
- the table covers Z = 1..200,
- every tile status is traceable to events,
- the table publishes HTML, SVG, and JSON outputs,
- CI publishes those outputs automatically,
- failing tests or missing benchmark health are visible in the visual summary.

## 30. Immediate next step

The first coding sprint should be VET-01 and VET-02 only.

Do not start rendering before the metadata and event contracts are stable.

The shortest path to value is:

    metadata
    -> EZ-B001 event extraction
    -> state JSON
    -> simple SVG
    -> CI artifact publishing

That gives ElementZero a trustworthy progress map quickly, while preserving compatibility with future benchmark stages.
