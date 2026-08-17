"""Family-specific solver adapters.

Each module isolates one external scientific code behind the WO-15
backend contract. Adapters translate identities and parameter artifacts
into solver input and translate solver output back into predictions with
convergence evidence — they never edit upstream source.
"""

from __future__ import annotations
