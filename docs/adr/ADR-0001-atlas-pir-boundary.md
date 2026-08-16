# ADR-0001 — Atlas PIR is the evidence kernel

Status: Accepted
Date: 2026-08-15

## Decision

Atlas owns generic scientific evidence infrastructure. ElementZero consumes
Atlas PIR through a commit-pinned dependency and `elementzero.evidence.atlas_adapter`.

ElementZero MUST NOT copy, fork, or silently modify Atlas PIR source.

## Consequences

- Production imports of Atlas research modules (`b1_*`, `b4_*`, `generator`,
  `canon`, `atlas_engine`, ...) are forbidden unless an ADR names the exception.
- Atlas packaging (`sovrance-atlas-pir`) is an upstream prerequisite. Until that
  merge exists, `tools/ensure_atlas_pir.py` installs the pinned SHA with a local
  packaging overlay. The overlay is not vendored into ElementZero.
- The overlay is a formally approved temporary exception, not the target
  architecture: see `docs/migrations/WO-04-atlas-packaging-exception.md`
  (`WO-04-ATLAS-PACKAGING-OVERLAY-EXCEPTION-v1`). The upstream Atlas packaging PR
  is blocked on write access, the pin stays at
  `31d76d094f1206e64a6920da4775d0a684618357`, and WO-05 and later work orders may
  proceed under the exception. `tools/ensure_atlas_pir.py --no-overlay` is the
  verifier-only mode that refuses to write packaging metadata.
- Atlas scientific conjectures are not ElementZero priors.
