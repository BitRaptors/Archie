"""Vector store interface and implementation."""
from abc import ABC, abstractmethod
from typing import Any


class IVectorStore(ABC):
    """Vector store interface."""

    @abstractmethod
    async def add_embeddings(self, embeddings: list[dict[str, Any]]) -> None:
        """Add embeddings to vector store."""
        ...

    @abstractmethod
    async def search_similar(
        self,
        query_embedding: list[float],
        repository_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for similar embeddings."""
        ...

    @abstractmethod
    async def search_by_pattern(
        self,
        pattern_query: str,
        repository_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for pattern-specific embeddings."""
        ...


class PgVectorStore(IVectorStore):
    """PostgreSQL with pgvector implementation."""

    def __init__(self, supabase_client):
        """Initialize pgvector store."""
        self._client = supabase_client

    async def add_embeddings(self, embeddings: list[dict[str, Any]]) -> None:
        """Add embeddings to pgvector."""
        # Convert embeddings to database format
        records = []
        for emb in embeddings:
            records.append({
                "repository_id": emb["repository_id"],
                "file_path": emb["file_path"],
                "chunk_type": emb["chunk_type"],
                "embedding": emb["embedding"],  # Will be converted to vector type
                "metadata": emb.get("metadata", {}),
            })
        
        # Batch insert (await the async operation)
        if records:
            await self._client.table("embeddings").insert(records).execute()

    async def search_similar(
        self,
        query_embedding: list[float],
        repository_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for similar embeddings using cosine similarity."""
        # For now, return empty results since match_embeddings function doesn't exist yet
        # TODO: Create the match_embeddings database function for proper vector search
        return []

    async def search_by_pattern(
        self,
        pattern_query: str,
        repository_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search by pattern (uses semantic search)."""
        # This would use query_embedder to convert pattern_query to embedding
        # For now, simplified implementation
        return await self.search_similar(
            query_embedding=[],  # Would be generated from pattern_query
            repository_id=repository_id,
            limit=limit,
        )


