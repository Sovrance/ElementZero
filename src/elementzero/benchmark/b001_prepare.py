"""UNBLINDED preparation: later source -> identity-only target manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.data.amdc import load_edition
from elementzero.data.observations import MassObservation
from elementzero.errors import LeakageError
from elementzero.evidence.freezes import validate_target_record


def observations_to_targets(observations: list[MassObservation]) -> list[dict[str, int | str]]:
    targets = []
    for obs in observations:
        if not obs.ground_truth_eligible:
            continue
        targets.append(
            {
                "nuclide_id": obs.nuclide_id,
                "Z": obs.Z,
                "N": obs.N,
                "A": obs.A,
            }
        )
    return [validate_target_record(t) for t in targets]


def prepare_targets(
    *,
    later_source: str | Path,
    edition_id: str,
    output: str | Path | None = None,
    benchmark_id: str = "EZ-B001",
    known_source: str | Path | None = None,
    known_edition_id: str | None = None,
) -> dict[str, Any]:
    if benchmark_id != "EZ-B001":
        raise ValueError(f"unsupported benchmark {benchmark_id}; new code uses EZ-B001")
    later_source = Path(later_source)
    observations = load_edition(edition_id, str(later_source))
    targets = observations_to_targets(observations)
    if known_source is not None:
        if not known_edition_id:
            raise ValueError("known_edition_id is required when known_source is set")
        known_ids = {
            obs.nuclide_id for obs in load_edition(known_edition_id, str(known_source))
        }
        # Identity subtraction only. Known-source masses never enter the target file.
        targets = [t for t in targets if t["nuclide_id"] not in known_ids]
    # Target files are identity-only. Edition/hash metadata belongs on the freeze
    # and score report, never beside later truth values.
    manifest = {"targets": targets}
    # The on-disk target list itself must remain identity-only.
    for target in targets:
        if set(target) - {"nuclide_id", "Z", "N", "A"}:
            raise LeakageError("target record is not identity-only")
    if output is not None:
        from elementzero.evidence.hashing import canonical_json

        Path(output).write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return manifest
