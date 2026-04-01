# analysis/
> Semantic code search and repository indexing via embeddings; singleton model prevents 400MB duplication.

## Patterns

- Lazy singleton for embedding model (_model = None, load on first use) across all consumers
- Batch encoding all chunks at once (encode list, batch_size=64) instead of one-at-a-time loop
- Chunking strategy: <200 lines = single chunk; 200-500 = split by functions; >500 = overlapping chunks
- Phase-specific chunk reordering via PHASE_CHUNK_PREFERENCES dict — discovery prefers modules, patterns prefer functions
- Custom queries from observation phase set via set_custom_queries(), used instead of defaults per phase
- Async-to-thread pattern for I/O (asyncio.to_thread) to avoid blocking event loop on file reads and encoding

## Navigation

**Parent:** [`infrastructure/`](../CLAUDE.md)
**Peers:** [`events/`](../events/CLAUDE.md) | [`external/`](../external/CLAUDE.md) | [`mcp/`](../mcp/CLAUDE.md) | [`persistence/`](../persistence/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md) | [`storage/`](../storage/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `shared_embedder.py` | Singleton embedding model loader; release_model() frees 400MB after analysis | All embedding calls go through get_model(). Never instantiate SentenceTransformer directly. |
| `rag_retriever.py` | Repository indexing, chunking, embedding, and semantic retrieval for code search | Batch-encode chunks before DB insert. Wipe stale embeddings before re-indexing. Use phase preferences for reordering. |
| `query_embedder.py` | Convert user query text to embedding vector for retrieval | Reuses shared_embedder.get_model(). Returns list[float] for cosine similarity matching. |
| `structure_analyzer.py` | Parse file tree, detect tech stack, analyze directory structure | Run analysis in thread via asyncio.to_thread. Respect discovery_ignored_dirs. Log items checked/added/skipped. |

## Key Imports

- `from infrastructure.analysis.shared_embedder import get_model`
- `from infrastructure.analysis.query_embedder import QueryEmbedder`
- `from infrastructure.analysis.rag_retriever import RAGRetriever`

## Add new retrieval phase or customize chunk preferences

1. Add phase name + chunk type list to PHASE_CHUNK_PREFERENCES dict
2. Set custom_queries via retriever.set_custom_queries(phase_dict) if phase-specific
3. Retriever reorders results by chunk type preference; no code changes needed

## Usage Examples

### Lazy load shared embedding model
```python
def _get_model(self):
    if self._model is None:
        self._model = get_model()
    return self._model
```

## Don't

- Don't create multiple SentenceTransformer instances — always use get_model() from shared_embedder
- Don't encode chunks one-at-a-time in a loop — batch all texts, call encode(list, batch_size=64) once
- Don't skip wipe-stale-embeddings before re-indexing — leftover entries from ignored dirs pollute retrieval results

## Testing

- Verify batch encoding: all_embeddings length == len(all_chunk_records) and embedding dim == 384
- Check stale wipe: embeddings table should have 0 records for repository_id after re-index start

## Why It's Built This Way

- Lazy singleton model — 400 MB PyTorch load deferred until first embed call; release_model() for cleanup
- Batch encoding in GPU-friendly chunks (batch_size=64) gives massive speedup vs loop iteration

## Dependencies

**Depends on:** `Domain Layer`
**Exposes to:** `Application Layer`, `DI Container`
