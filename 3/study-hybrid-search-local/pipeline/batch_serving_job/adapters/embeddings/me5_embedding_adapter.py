from __future__ import annotations

from pipeline.batch_serving_job.services.embeddings.me5_embedding_service import encode_queries


class ME5EmbeddingAdapter:
    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            return []
        return encode_queries([text])[0]
