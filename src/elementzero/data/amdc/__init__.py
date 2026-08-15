"""AMDC AME edition adapters."""

from __future__ import annotations

from elementzero.data.amdc.ame2003 import EDITION as AME2003
from elementzero.data.amdc.ame2003 import load as load_ame2003
from elementzero.data.amdc.ame2012 import EDITION as AME2012
from elementzero.data.amdc.ame2012 import load as load_ame2012
from elementzero.data.amdc.ame2016 import EDITION as AME2016
from elementzero.data.amdc.ame2016 import load as load_ame2016
from elementzero.data.amdc.ame2020 import EDITION as AME2020
from elementzero.data.amdc.ame2020 import load as load_ame2020
from elementzero.data.amdc.common import EditionSpec, format_ame_line, parse_ame_mass_table

EDITIONS = {
    "AME2003": (AME2003, load_ame2003),
    "AME2012": (AME2012, load_ame2012),
    "AME2016": (AME2016, load_ame2016),
    "AME2020": (AME2020, load_ame2020),
}


def load_edition(edition_id: str, path: str):
    try:
        _spec, loader = EDITIONS[edition_id]
    except KeyError as exc:
        raise ValueError(f"unknown AME edition {edition_id!r}") from exc
    return loader(path)


__all__ = [
    "EDITIONS",
    "EditionSpec",
    "format_ame_line",
    "load_ame2003",
    "load_ame2012",
    "load_ame2016",
    "load_ame2020",
    "load_edition",
    "parse_ame_mass_table",
]
