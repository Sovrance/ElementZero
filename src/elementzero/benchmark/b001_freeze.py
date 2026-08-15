"""Freeze stage: hash the old source and the identity-only target holdout."""

from __future__ import annotations

import json
from pathlib import Path

from elementzero.benchmark.b001_predict import load_targets
from elementzero.data.amdc import load_edition
from elementzero.evidence.freezes import KnowledgeFreeze, build_freeze
from elementzero.evidence.hashing import canonical_json, sha256_file


def freeze_training(
    *,
    training_source: str | Path,
    training_edition_id: str,
    targets_path: str | Path,
    output: str | Path | None = None,
    benchmark_id: str = "EZ-B001",
    forbidden_source_hashes: list[str] | None = None,
) -> KnowledgeFreeze:
    if benchmark_id != "EZ-B001":
        raise ValueError(f"unsupported benchmark {benchmark_id}; new code uses EZ-B001")
    training_source = Path(training_source)
    targets = load_targets(targets_path)
    observations = [
        obs
        for obs in load_edition(training_edition_id, str(training_source))
        if obs.ground_truth_eligible
    ]
    cutoff = observations[0].source_release_date if observations else "1970-01-01"
    freeze = build_freeze(
        training=observations,
        targets=targets,
        cutoff_date=cutoff,
        edition_id=training_edition_id,
        raw_source_hash=sha256_file(training_source),
        forbidden_source_hashes=forbidden_source_hashes or (),
    )
    if output is not None:
        Path(output).write_text(canonical_json(freeze.to_dict()) + "\n", encoding="utf-8")
    return freeze


def load_freeze(path: str | Path) -> KnowledgeFreeze:
    return KnowledgeFreeze.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
