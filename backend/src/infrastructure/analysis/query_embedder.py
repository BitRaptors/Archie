"""Query embedder for converting prompts to embeddings."""
from sentence_transformers import SentenceTransformer
from config.settings import get_settings


class QueryEmbedder:
    """Converts prompt text to query embeddings."""

    def __init__(self):
        """Initialize query embedder."""
        settings = get_settings()
        self._model = SentenceTransformer(settings.embedding_model)

    async def embed_query(self, query_text: str) -> list[float]:
        """Convert query text to embedding."""
        embedding = self._model.encode(query_text, show_progress_bar=False)
        return embedding.tolist()

    async def extract_keywords(self, prompt_text: str) -> list[str]:
        """Extract keywords from prompt for better search."""
        # Simplified - would use NLP to extract keywords
        words = prompt_text.lower().split()
        # Filter common words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords


