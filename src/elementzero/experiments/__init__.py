"""Preregistered historical experiments of the EZ-B001 family.

The modules here own the artifacts that live under ``experiments/<id>/``:

    epochs.py        declared AME transitions (EZ-B001-A / -B / -C)
    protocol_code.py hash of the source files that define the protocol
    preregister.py   build, hash, and validate a preregistration
    runner.py        seal and score one experiment under its preregistration
    aggregate.py     longitudinal aggregate across scored experiments
"""

from __future__ import annotations

from elementzero.experiments.epochs import EPOCHS, EpochSpec, epoch_for
from elementzero.experiments.preregister import (
    EXPERIMENT_PROTOCOL_VERSION,
    PREREGISTRATION_FILES,
    PREREGISTRATION_HASH_FILE,
    preregistration_hash,
    validate_preregistration,
    write_preregistration,
)

__all__ = [
    "EPOCHS",
    "EXPERIMENT_PROTOCOL_VERSION",
    "EpochSpec",
    "PREREGISTRATION_FILES",
    "PREREGISTRATION_HASH_FILE",
    "epoch_for",
    "preregistration_hash",
    "validate_preregistration",
    "write_preregistration",
]
