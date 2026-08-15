"""Source-file manifests: edition identity plus immutable content hash."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from elementzero.evidence.hashing import sha256_file


@dataclass(frozen=True)
class SourceManifest:
    path: str
    edition_id: str
    release_date: str
    content_hash: str
    acquired_at: str
    source_uri: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "edition_id": self.edition_id,
            "release_date": self.release_date,
            "content_hash": self.content_hash,
            "acquired_at": self.acquired_at,
            "source_uri": self.source_uri,
        }


def manifest_for_file(
    path: str | Path,
    *,
    edition_id: str,
    release_date: str,
    acquired_at: str,
    source_uri: str | None = None,
) -> SourceManifest:
    path = Path(path)
    return SourceManifest(
        path=str(path),
        edition_id=edition_id,
        release_date=release_date,
        content_hash=sha256_file(path),
        acquired_at=acquired_at,
        source_uri=source_uri or path.resolve().as_uri(),
    )
