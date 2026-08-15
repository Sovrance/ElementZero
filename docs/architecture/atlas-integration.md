# Atlas integration

```text
Atlas PIR v0.1  --commit-pinned-->  ElementZero AtlasEvidenceAdapter
                                              |
                         +--------------------+--------------------+
                         |                    |                    |
                    AME ingest           SEMF + GP              EZ-B001
                    + freezes                                   time machine
```

Atlas tells ElementZero how to represent, trace, downgrade, and discriminate
evidence. ElementZero remains responsible for nuclear physics and whether
predictions survive blind validation.

Pinned ref: see `atlas.lock.json`.
Public adapter: `src/elementzero/evidence/atlas_adapter.py`.

## Packaging status

The pinned Atlas commit does not ship `pyproject.toml`, so
`tools/ensure_atlas_pir.py` installs the pin through a local packaging overlay
inside `.cache/atlas-pir/<sha>/`. That overlay runs under the approved temporary
exception in `docs/migrations/WO-04-atlas-packaging-exception.md`: it warns on
every run, stamps `.elementzero_overlay_exception` in the clone, never vendors
`pir/` into ElementZero, and never accepts a mutable Atlas ref. When an upstream
commit carries its own packaging metadata, the same tool installs it unchanged;
`--no-overlay` enforces that mode and exits non-zero rather than mutating the
clone.
