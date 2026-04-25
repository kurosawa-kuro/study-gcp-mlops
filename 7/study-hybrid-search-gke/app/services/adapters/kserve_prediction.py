"""Backward-compat shim — Phase B-2 split this module.

* ``KServeEncoder`` lives in :mod:`app.services.adapters.kserve_encoder`.
* ``KServeReranker`` lives in :mod:`app.services.adapters.kserve_reranker`.
* Shared helpers live in :mod:`app.services.adapters._kserve_common`.

Kept as a re-export so any external consumer importing from
``app.services.adapters.kserve_prediction`` keeps working.
"""

from app.services.adapters._kserve_common import EXPECTED_EMBEDDING_DIM
from app.services.adapters.kserve_encoder import KServeEncoder
from app.services.adapters.kserve_reranker import KServeReranker

__all__ = [
    "EXPECTED_EMBEDDING_DIM",
    "KServeEncoder",
    "KServeReranker",
]
