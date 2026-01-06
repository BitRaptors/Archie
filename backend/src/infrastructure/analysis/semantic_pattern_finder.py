"""Semantic pattern finder using embeddings."""
from typing import Any
from infrastructure.analysis.vector_store import IVectorStore
from infrastructure.analysis.query_embedder import QueryEmbedder


class SemanticPatternFinder:
    """Finds patterns using semantic search."""

    def __init__(self, vector_store: IVectorStore, query_embedder: QueryEmbedder):
        """Initialize semantic pattern finder."""
        self._vector_store = vector_store
        self._query_embedder = query_embedder

    async def find_patterns(
        self,
        repository_id: str,
        prompt_config: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Find patterns using semantic search."""
        patterns = {}
        
        # Default pattern queries
        pattern_queries = [
            "service registry pattern with factory",
            "React context hook pattern with useContext",
            "repository pattern with interface",
            "query hook with TanStack Query",
            "mutation hook pattern",
            "CVA component pattern",
        ]
        
        # If custom prompts provided, extract queries from them
        if prompt_config:
            # Would extract queries from custom prompts
            pass
        
        # Search for each pattern
        for query in pattern_queries:
            query_embedding = await self._query_embedder.embed_query(query)
            results = await self._vector_store.search_similar(
                query_embedding=query_embedding,
                repository_id=repository_id,
                limit=10,
            )
            
            pattern_name = query.split()[0] + "_" + query.split()[1]  # Simplified
            patterns[pattern_name] = results
        
        return patterns


