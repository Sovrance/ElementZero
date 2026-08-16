# Visual Element Table - Coding Agent Prompt

Read:

1. ElementZero_Visual_Element_Table_Supplemental_Engineering_Plan_v0.1.md
2. element_progress_event.schema.json
3. element_table_state.schema.json
4. visual_render_bundle.schema.json

Implement in phases:

    VET-01 metadata and layouts
    VET-02 event extraction
    VET-03 aggregation
    VET-04 rendering
    VET-05 CLI and CI integration
    VET-06 EZ-B002 and EZ-B003 integration

Non-negotiable rules:

- Derive tile state from application artifacts, not manual edits.
- Do not treat prediction-only runs as validated.
- Do not imply official placement for elements 119-200.
- Do not infer candidate island focus automatically from one prediction.
- Keep all normative outputs deterministic and hashable.
- Prefer static HTML + SVG + JSON over framework-heavy frontends for v0.1.
