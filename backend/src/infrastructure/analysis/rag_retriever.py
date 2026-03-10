"""RAG-based code retriever for semantic code search."""
import asyncio
import logging
from pathlib import Path
from typing import Any
from config.settings import get_settings
from infrastructure.analysis.shared_embedder import get_model
from domain.interfaces.database import DatabaseClient
from application.services.analysis_data_collector import analysis_data_collector

logger = logging.getLogger("rag_retriever")


# Phase-specific chunk type preferences for retrieval reordering
PHASE_CHUNK_PREFERENCES: dict[str, list[str]] = {
    "discovery": ["module"],             # Entry points, top-level files
    "layers": ["class", "module"],       # Service/repo classes, module structure
    "patterns": ["class", "function"],   # Design pattern implementations
    "communication": ["function", "class"],  # API handlers, event publishers
    "technology": ["module"],            # Config files, build scripts
    "frontend": ["module", "class"],     # UI components, views
    "implementation": ["class", "function"],  # Implementation details
}


class RAGRetriever:
    """Retrieval-Augmented Generation retriever for semantic code search.

    This class provides methods to:
    1. Generate embeddings for code chunks
    2. Search for semantically similar code
    3. Retrieve relevant code for specific analysis tasks
    """

    def __init__(self, db_client: DatabaseClient, progress_callback=None):
        """Initialize RAG retriever.

        Args:
            db_client: DatabaseClient for database access (Supabase or Postgres)
            progress_callback: Optional async callback function(analysis_id, event_type, message) for progress logging
        """
        self._model = None  # Lazy — loaded on first use via _get_model()
        self._db = db_client
        self._embedding_dim = 384  # all-MiniLM-L6-v2 dimension
        self._progress_callback = progress_callback
        self._custom_queries = {}  # Custom queries from observation phase

    def _get_model(self):
        """Return the embedding model, loading it on first use."""
        if self._model is None:
            self._model = get_model()
        return self._model
    
    def set_custom_queries(self, custom_queries: dict[str, list[str]]) -> None:
        """Set custom queries generated from observation phase.
        
        These queries are specific to the observed architecture style
        and will be used instead of (or in addition to) default queries.
        
        Args:
            custom_queries: Dictionary of phase -> list of custom query strings
        """
        self._custom_queries = custom_queries or {}

    async def index_repository(self, repository_id: str, repo_path: Path, analysis_id: str | None = None, discovery_ignored_dirs: set[str] | None = None) -> dict[str, Any]:
        """Index a repository by generating embeddings for all code files.

        Uses chunking strategy:
        - Small files (<200 lines): Single chunk
        - Medium files (200-500 lines): Split by functions/classes if possible
        - Large files (>500 lines): Split into overlapping chunks

        Args:
            repository_id: UUID of the repository
            repo_path: Path to the cloned repository
            analysis_id: For progress logging
            discovery_ignored_dirs: User-configured directories to skip.

        Returns:
            Statistics about indexed files and chunks
        """
        stats = {"files": 0, "chunks": 0, "total_lines": 0}

        # Wipe stale embeddings for this repository before re-indexing.
        # Prevents leftover entries (e.g. from previously un-ignored dirs like Pods)
        # from polluting retrieval results.
        try:
            await self._db.table("embeddings").delete().eq(
                "repository_id", repository_id
            ).execute()
        except Exception as del_err:
            logger.warning("Failed to delete stale embeddings for repo %s: %s", repository_id, del_err)

        code_files = await asyncio.to_thread(self._find_code_files, repo_path, discovery_ignored_dirs)
        total_files = len(code_files)

        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", f"Found {total_files} code files to index")

        # Batch-read all file contents in a thread to avoid blocking the event loop
        file_contents = await asyncio.to_thread(self._read_all_files, code_files, repo_path)

        # Collect ALL chunks across all files first, then batch-encode them.
        # GPU (MPS/CUDA) and even CPU benefit massively from batched encoding
        # vs the previous one-at-a-time loop.
        all_chunk_records: list[dict] = []  # {repository_id, file_path, chunk_type, content, metadata}

        for idx, file_path in enumerate(code_files):
            try:
                content = file_contents.get(file_path)
                if content is None:
                    continue
                relative_path = str(file_path.relative_to(repo_path))

                chunks = self._chunk_file(content, relative_path)

                for chunk in chunks:
                    all_chunk_records.append({
                        "repository_id": repository_id,
                        "file_path": relative_path,
                        "chunk_type": chunk["type"],
                        "content": chunk["content"],
                        "metadata": {
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "content_preview": chunk["content"][:200],
                            "context": chunk.get("context", ""),
                        },
                    })

                stats["files"] += 1
                stats["total_lines"] += len(content.splitlines())
                stats["chunks"] += len(chunks)

                if self._progress_callback and analysis_id:
                    if stats["files"] % 20 == 0 or idx == 0:
                        await self._progress_callback(
                            analysis_id, "INFO",
                            f"Chunked file {stats['files']}/{total_files}: {relative_path} ({len(chunks)} chunks)"
                        )

            except Exception as file_err:
                logger.debug("Skipping file during indexing %s: %s", file_path, file_err)
                continue

        # Batch-encode all chunks at once — this is the main speedup.
        # sentence-transformers encode() accepts a list and processes in
        # GPU-friendly batches internally.
        if all_chunk_records:
            if self._progress_callback and analysis_id:
                await self._progress_callback(
                    analysis_id, "INFO",
                    f"Encoding {len(all_chunk_records)} chunks (batched)..."
                )

            all_texts = [r["content"] for r in all_chunk_records]
            all_embeddings = await asyncio.to_thread(
                self._get_model().encode, all_texts,
                batch_size=64, show_progress_bar=False,
            )

            if self._progress_callback and analysis_id:
                await self._progress_callback(
                    analysis_id, "INFO",
                    f"Encoding complete, inserting into database..."
                )

            # Build DB records and batch-insert
            embeddings_batch = []
            for record, embedding in zip(all_chunk_records, all_embeddings):
                embeddings_batch.append({
                    "repository_id": record["repository_id"],
                    "file_path": record["file_path"],
                    "chunk_type": record["chunk_type"],
                    "embedding": embedding.tolist(),
                    "metadata": record["metadata"],
                })

                if len(embeddings_batch) >= 100:
                    await self._batch_insert_embeddings(embeddings_batch)
                    embeddings_batch = []

            if embeddings_batch:
                await self._batch_insert_embeddings(embeddings_batch)

            if self._progress_callback and analysis_id:
                await self._progress_callback(
                    analysis_id, "INFO",
                    f"Saved {len(all_chunk_records)} embeddings to database"
                )
        
        if self._progress_callback and analysis_id:
            await self._progress_callback(
                analysis_id, 
                "INFO", 
                f"Indexing complete: {stats['files']} files, {stats['chunks']} chunks, {stats['total_lines']} total lines"
            )
        
        # Capture RAG stats
        if analysis_id:
            await analysis_data_collector.capture_rag_stats(analysis_id, stats)
        
        return stats

    async def retrieve_for_query(
        self,
        query: str,
        repository_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve code chunks relevant to a query.
        
        Args:
            query: Natural language query (e.g., "authentication logic")
            repository_id: UUID of the repository
            limit: Maximum number of chunks to return
            
        Returns:
            List of relevant code chunks with similarity scores
        """
        # Generate query embedding
        query_embedding = self._get_model().encode(query, show_progress_bar=False).tolist()
        
        # Search using pgvector similarity
        return await self._search_similar(query_embedding, repository_id, limit)

    async def retrieve_for_phase(
        self,
        phase: str,
        repository_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve code chunks relevant to a specific analysis phase.
        
        Each phase has specific retrieval queries optimized for its purpose:
        - discovery: Project structure, entry points, main modules
        - layers: Service classes, repositories, controllers, routes
        - patterns: Design patterns, dependency injection, factories
        - communication: API endpoints, event handlers, message queues
        - technology: Framework usage, library imports, configuration
        
        Args:
            phase: Analysis phase name
            repository_id: UUID of the repository
            context: Additional context from previous phases
            
        Returns:
            List of relevant code chunks
        """
        phase_queries = self._get_phase_queries(phase, context)
        
        all_results = []
        seen_paths = set()
        
        for query in phase_queries:
            results = await self.retrieve_for_query(query, repository_id, limit=5)

            for result in results:
                # Deduplicate by file path and line range
                key = f"{result['file_path']}:{result.get('start_line', 0)}"
                if key not in seen_paths:
                    seen_paths.add(key)
                    all_results.append(result)

        # Reorder by chunk type preference for this phase
        preferred_types = PHASE_CHUNK_PREFERENCES.get(phase)
        if preferred_types and all_results:
            preferred = [r for r in all_results if r.get("chunk_type") in preferred_types]
            other = [r for r in all_results if r.get("chunk_type") not in preferred_types]
            all_results = preferred + other

        return all_results[:20]  # Return top 20 unique results

    async def get_file_registry(self, repository_id: str) -> list[str]:
        """Return all unique file paths indexed for a repository.

        Uses a SELECT DISTINCT on the embeddings table — no vector search needed.
        """
        try:
            result = await self._db.table("embeddings") \
                .select("file_path") \
                .eq("repository_id", repository_id) \
                .execute()
            if result.data:
                return sorted(set(row["file_path"] for row in result.data))
        except Exception as reg_err:
            logger.warning("Failed to query file registry: %s", reg_err)
        return []

    def _get_file_content_sync(
        self,
        file_path: str,
        repo_path: Path,
    ) -> str | None:
        """Get full content of a specific file (sync I/O)."""
        full_path = repo_path / file_path
        if full_path.exists() and full_path.is_file():
            try:
                return full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return None
        return None

    async def get_file_content(
        self,
        repository_id: str,
        file_path: str,
        repo_path: Path,
    ) -> str | None:
        """Get full content of a specific file.

        Args:
            repository_id: UUID of the repository
            file_path: Relative path to the file
            repo_path: Path to the cloned repository

        Returns:
            File content or None if not found
        """
        return await asyncio.to_thread(self._get_file_content_sync, file_path, repo_path)

    async def retrieve_files_for_phase(
        self,
        phase: str,
        repository_id: str,
        repo_path: Path,
        context: dict[str, Any] | None = None,
        max_files: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve full file contents relevant to a phase using semantic search.

        Uses chunk-level RAG to identify the most relevant files,
        then returns full file contents (deduplicated at file level).
        """
        chunks = await self.retrieve_for_phase(phase, repository_id, context)

        # Deduplicate: group by file_path, keep highest similarity
        file_scores: dict[str, float] = {}
        for chunk in chunks:
            fp = chunk["file_path"]
            sim = chunk.get("similarity", 0)
            if fp not in file_scores or sim > file_scores[fp]:
                file_scores[fp] = sim

        # Sort by similarity, take top N
        ranked = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)[:max_files]

        results = []
        for file_path, similarity in ranked:
            content = await self.get_file_content(repository_id, file_path, repo_path)
            if content:
                results.append({
                    "file_path": file_path,
                    "content": content,
                    "similarity": similarity,
                })

        return results

    def _read_all_files(self, code_files: list[Path], repo_path: Path) -> dict[Path, str]:
        """Read all code files and return their contents (sync I/O)."""
        contents: dict[Path, str] = {}
        for file_path in code_files:
            try:
                contents[file_path] = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
        return contents

    def _find_code_files(self, repo_path: Path, discovery_ignored_dirs: set[str] | None = None) -> list[Path]:
        """Find all code files in repository."""
        from domain.entities.analysis_settings import SOURCE_CODE_EXTENSIONS

        ignore_patterns = discovery_ignored_dirs or set()

        code_files = []
        for ext in SOURCE_CODE_EXTENSIONS:
            for file_path in repo_path.rglob(f"*{ext}"):
                try:
                    rel_parts = file_path.relative_to(repo_path).parts
                except ValueError:
                    continue
                if not any(part in ignore_patterns for part in rel_parts):
                    code_files.append(file_path)

        return code_files

    def _chunk_file(self, content: str, file_path: str) -> list[dict[str, Any]]:
        """Chunk a file into meaningful segments.
        
        Strategy:
        1. Small files (<200 lines): Single module chunk
        2. Medium/Large files: Split by logical boundaries
           - Python: functions, classes
           - JS/TS: functions, classes, exports
        3. Add context (imports, surrounding code) to each chunk
        """
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Small file - single chunk
        if total_lines < 200:
            return [{
                "type": "module",
                "content": content,
                "start_line": 1,
                "end_line": total_lines,
                "context": "",
            }]
        
        # Determine file type and chunk accordingly
        ext = Path(file_path).suffix.lower()
        
        if ext == ".py":
            return self._chunk_python_file(content, lines)
        elif ext in {".js", ".ts", ".tsx", ".jsx"}:
            return self._chunk_js_ts_file(content, lines)
        else:
            # Generic chunking by line count
            return self._chunk_by_lines(content, lines, chunk_size=150, overlap=20)

    def _chunk_python_file(self, content: str, lines: list[str]) -> list[dict[str, Any]]:
        """Chunk Python file by functions and classes."""
        chunks = []
        
        # Extract imports as context
        import_lines = []
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append(line)
            elif line.strip() and not line.strip().startswith('#'):
                break
        
        import_context = '\n'.join(import_lines) if import_lines else ""
        
        # Find function and class definitions
        current_chunk_start = 0
        current_chunk_type = "module"
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check for class or function definition
            if stripped.startswith('class ') or stripped.startswith('def '):
                # Save previous chunk if substantial
                if i > current_chunk_start + 5:
                    chunk_content = '\n'.join(lines[current_chunk_start:i])
                    if chunk_content.strip():
                        chunks.append({
                            "type": current_chunk_type,
                            "content": chunk_content,
                            "start_line": current_chunk_start + 1,
                            "end_line": i,
                            "context": import_context,
                        })
                
                current_chunk_start = i
                current_chunk_type = "class" if stripped.startswith('class ') else "function"
        
        # Add final chunk
        if current_chunk_start < len(lines):
            chunk_content = '\n'.join(lines[current_chunk_start:])
            if chunk_content.strip():
                chunks.append({
                    "type": current_chunk_type,
                    "content": chunk_content,
                    "start_line": current_chunk_start + 1,
                    "end_line": len(lines),
                    "context": import_context,
                })
        
        # If no meaningful chunks, return whole file as module
        if not chunks:
            return [{
                "type": "module",
                "content": content,
                "start_line": 1,
                "end_line": len(lines),
                "context": "",
            }]
        
        return chunks

    def _chunk_js_ts_file(self, content: str, lines: list[str]) -> list[dict[str, Any]]:
        """Chunk JavaScript/TypeScript file by functions and exports."""
        chunks = []
        
        # Extract imports as context
        import_lines = []
        for i, line in enumerate(lines):
            if 'import ' in line or 'require(' in line:
                import_lines.append(line)
        
        import_context = '\n'.join(import_lines[:20]) if import_lines else ""  # Limit imports
        
        # Find function, class, and export definitions
        current_chunk_start = 0
        current_chunk_type = "module"
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check for various JS/TS constructs
            is_boundary = any([
                stripped.startswith('export '),
                stripped.startswith('function '),
                stripped.startswith('class '),
                stripped.startswith('const ') and ('=' in stripped and ('=>' in stripped or 'function' in stripped)),
                stripped.startswith('async function'),
            ])
            
            if is_boundary and i > current_chunk_start + 5:
                chunk_content = '\n'.join(lines[current_chunk_start:i])
                if chunk_content.strip():
                    chunks.append({
                        "type": current_chunk_type,
                        "content": chunk_content,
                        "start_line": current_chunk_start + 1,
                        "end_line": i,
                        "context": import_context,
                    })
                
                current_chunk_start = i
                current_chunk_type = "function" if 'function' in stripped else "export"
        
        # Add final chunk
        if current_chunk_start < len(lines):
            chunk_content = '\n'.join(lines[current_chunk_start:])
            if chunk_content.strip():
                chunks.append({
                    "type": current_chunk_type,
                    "content": chunk_content,
                    "start_line": current_chunk_start + 1,
                    "end_line": len(lines),
                    "context": import_context,
                })
        
        if not chunks:
            return [{
                "type": "module",
                "content": content,
                "start_line": 1,
                "end_line": len(lines),
                "context": "",
            }]
        
        return chunks

    def _chunk_by_lines(
        self,
        content: str,
        lines: list[str],
        chunk_size: int = 150,
        overlap: int = 20,
    ) -> list[dict[str, Any]]:
        """Generic chunking by line count with overlap."""
        chunks = []
        start = 0
        
        while start < len(lines):
            end = min(start + chunk_size, len(lines))
            chunk_content = '\n'.join(lines[start:end])
            
            chunks.append({
                "type": "chunk",
                "content": chunk_content,
                "start_line": start + 1,
                "end_line": end,
                "context": "",
            })
            
            # Move start with overlap
            start = end - overlap if end < len(lines) else len(lines)
        
        return chunks

    def _get_phase_queries(self, phase: str, context: dict[str, Any] | None) -> list[str]:
        """Get optimized queries for each analysis phase.
        
        If custom queries were set from the observation phase, use those.
        Otherwise fall back to default queries.
        """
        # Check for custom queries from observation phase
        if self._custom_queries and phase in self._custom_queries:
            custom = self._custom_queries[phase]
            if custom:
                # Combine custom queries with a few defaults for robustness
                default_fallbacks = {
                    "discovery": ["main entry point", "configuration"],
                    "layers": ["service", "repository", "controller"],
                    "patterns": ["pattern implementation", "factory"],
                    "communication": ["API endpoint", "event handler"],
                    "technology": ["import from require"],
                }
                return custom + default_fallbacks.get(phase, [])[:2]
        
        # Default queries (for traditional architectures or when no custom queries)
        queries = {
            "discovery": [
                "main entry point application startup initialization",
                "configuration settings environment variables",
                "project structure module organization",
                "README documentation overview purpose",
            ],
            "layers": [
                "service layer business logic orchestration",
                "repository data access database operations",
                "controller route handler API endpoint",
                "domain entity model data structure",
                "infrastructure external integration client",
            ],
            "patterns": [
                "dependency injection container factory provider",
                "repository pattern interface implementation",
                "service pattern business logic",
                "decorator middleware authentication authorization",
                "error handling exception try catch",
            ],
            "communication": [
                "API endpoint route handler request response",
                "event publisher subscriber message queue",
                "websocket realtime connection handler",
                "HTTP client fetch axios request",
                "middleware interceptor filter",
            ],
            "technology": [
                "import from require module dependency",
                "framework library package version",
                "database connection ORM query",
                "authentication JWT token session",
                "logging monitoring observability",
            ],
        }
        
        base_queries = queries.get(phase, queries["discovery"])
        
        # Enhance with context from previous phases if available
        if context:
            # Add queries based on discovered technologies
            if "technologies" in context:
                for tech in context.get("technologies", [])[:3]:
                    base_queries.append(f"{tech} usage implementation")
            
            # Add queries based on discovered patterns
            if "patterns" in context:
                for pattern in context.get("patterns", [])[:3]:
                    base_queries.append(f"{pattern} pattern implementation")
        
        return base_queries

    async def _search_similar(
        self,
        query_embedding: list[float],
        repository_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Search for similar embeddings using pgvector."""
        try:
            result = await self._db.rpc(
                'match_embeddings',
                {
                    'query_embedding': query_embedding,
                    'match_count': limit,
                    'filter_repository_id': repository_id,
                }
            )

            if result.data:
                return [
                    {
                        "file_path": row["file_path"],
                        "chunk_type": row["chunk_type"],
                        "similarity": row.get("similarity", 0),
                        "start_line": row.get("metadata", {}).get("start_line", 0),
                        "end_line": row.get("metadata", {}).get("end_line", 0),
                        "content_preview": row.get("metadata", {}).get("content_preview", ""),
                    }
                    for row in result.data
                ]
        except Exception as rpc_err:
            logger.warning("pgvector RPC search failed: %s", rpc_err)

        return []

    async def _batch_insert_embeddings(self, embeddings: list[dict[str, Any]]) -> None:
        """Batch insert embeddings into database."""
        if not embeddings:
            return

        try:
            # Delete existing embeddings for these files to avoid duplicates
            repository_id = embeddings[0]["repository_id"]
            file_paths = list(set(e["file_path"] for e in embeddings))

            await self._db.table("embeddings").delete().eq(
                "repository_id", repository_id
            ).in_("file_path", file_paths).execute()

            # Insert new embeddings
            await self._db.table("embeddings").insert(embeddings).execute()
        except Exception as batch_err:
            logger.error("Failed to batch insert %d embeddings: %s", len(embeddings), batch_err)

