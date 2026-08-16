"""ElementZero visual element-table subsystem."""

from __future__ import annotations

GENERATOR_VERSION = "visual-table-v0.1"
LAYOUT_STANDARD_118 = "standard_118"
LAYOUT_EXTENDED_200 = "extended_200_project_v1"
DEFAULT_LAYOUT = LAYOUT_EXTENDED_200
METADATA_VERSION = "element_metadata_v1"

DISCLAIMER_119_200 = (
    "Elements 119-200 are project placeholders for progress visualization, "
    "not official IUPAC placement."
)
HONESTY_NOTE = (
    "ElementZero visual states summarize project artifacts. "
    "They do not constitute experimental discovery claims."
)

__all__ = [
    "DEFAULT_LAYOUT",
    "DISCLAIMER_119_200",
    "GENERATOR_VERSION",
    "HONESTY_NOTE",
    "LAYOUT_EXTENDED_200",
    "LAYOUT_STANDARD_118",
    "METADATA_VERSION",
]
