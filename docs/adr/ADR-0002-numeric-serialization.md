# ADR-0002 — Canonical numeric serialization

Status: Accepted
Date: 2026-08-15

## Decision

ElementZero scientific artifacts are hashed from canonical JSON:

- sorted keys
- no incidental whitespace
- finite floats quantized to 12 significant digits (`float(format(x, '.12e'))`)
  and emitted as JSON numbers, not quoted strings

This is the documented exception to raw IEEE byte-for-byte float equality.
Reproducibility tests compare these canonical hashes, not native pickle bytes.

## Why

GP/SEMF residuals are floating-point. Silent weakening of reproducibility
tests is forbidden; a named serialization policy is required instead.
