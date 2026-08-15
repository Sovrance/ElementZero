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
