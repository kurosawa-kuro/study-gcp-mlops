"""Backward-compat shim — Phase B-2 split this module.

* :class:`BigQuerySemanticSearch` →
  :mod:`app.services.adapters.bigquery_semantic_search`
* :class:`VertexVectorSearchSemantic` →
  :mod:`app.services.adapters.vertex_vector_search_semantic`
"""

from app.services.adapters.bigquery_semantic_search import BigQuerySemanticSearch
from app.services.adapters.vertex_vector_search_semantic import VertexVectorSearchSemantic

__all__ = ["BigQuerySemanticSearch", "VertexVectorSearchSemantic"]
