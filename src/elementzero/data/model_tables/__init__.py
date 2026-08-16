"""External physics mass-table ingestion (WO-12).

Raw published tables stay out of git (``data/model_tables/`` is ignored, like
the AME tables); the repository commits their sha256 hashes, source manifests,
small golden fixtures, and the parsers. ``tools/fetch_model_tables.py``
re-downloads every registered table from its public host and verifies the
pinned hash.
"""

from __future__ import annotations

from elementzero.data.model_tables.manifests import (  # noqa: F401
    REGISTERED_TABLES,
    TABLES_RELPATH,
    source_manifest,
    table_path,
)
from elementzero.data.model_tables.parser import (  # noqa: F401
    MODEL_TABLE_PARSER_VERSION,
    parse_bskg_table,
    parse_frdm_ripl_table,
    table_value_to_mass_excess_keV,
)
