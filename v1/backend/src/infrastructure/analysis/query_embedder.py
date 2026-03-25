"""Query embedder for converting prompts to embeddings."""
from infrastructure.analysis.shared_embedder import get_model


class QueryEmbedder:
    """Converts prompt text to query embeddings."""

    def __init__(self):
        """Initialize query embedder."""
        self._model = None  # Lazy — loaded on first use

    def _get_model(self):
        if self._model is None:
            self._model = get_model()
        return self._model

    async def embed_query(self, query_text: str) -> list[float]:
        """Convert query text to embedding."""
        embedding = self._get_model().encode(query_text, show_progress_bar=False)
        return embedding.tolist()


