"""RAG-based code retriever for semantic code search."""
from pathlib import Path
from typing import Any
from sentence_transformers import SentenceTransformer
from config.settings import get_settings
from application.services.debug_collector import debug_collector


class RAGRetriever:
    """Retrieval-Augmented Generation retriever for semantic code search.
    
    This class provides methods to:
    1. Generate embeddings for code chunks
    2. Search for semantically similar code
    3. Retrieve relevant code for specific analysis tasks
    """

    def __init__(self, supabase_client, progress_callback=None):
        """Initialize RAG retriever.
        
        Args:
            supabase_client: Supabase client for database access
            progress_callback: Optional async callback function(analysis_id, event_type, message) for progress logging
        """
        settings = get_settings()
        self._model = SentenceTransformer(settings.embedding_model)
        self._client = supabase_client
        self._embedding_dim = 384  # all-MiniLM-L6-v2 dimension
        self._progress_callback = progress_callback

    async def index_repository(self, repository_id: str, repo_path: Path, analysis_id: str | None = None) -> dict[str, Any]:
        """Index a repository by generating embeddings for all code files.
        
        Uses chunking strategy:
        - Small files (<200 lines): Single chunk
        - Medium files (200-500 lines): Split by functions/classes if possible
        - Large files (>500 lines): Split into overlapping chunks
        
        Args:
            repository_id: UUID of the repository
            repo_path: Path to the cloned repository
            
        Returns:
            Statistics about indexed files and chunks
        """
        stats = {"files": 0, "chunks": 0, "total_lines": 0}
        embeddings_batch = []
        
        code_files = self._find_code_files(repo_path)
        total_files = len(code_files)
        
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", f"Found {total_files} code files to index")
        
        for idx, file_path in enumerate(code_files):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                relative_path = str(file_path.relative_to(repo_path))
                
                # Generate chunks with context
                chunks = self._chunk_file(content, relative_path)
                
                for chunk in chunks:
                    # Generate embedding
                    embedding = self._model.encode(chunk["content"], show_progress_bar=False)
                    
                    embeddings_batch.append({
                        "repository_id": repository_id,
                        "file_path": relative_path,
                        "chunk_type": chunk["type"],
                        "embedding": embedding.tolist(),
                        "metadata": {
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "content_preview": chunk["content"][:200],
                            "context": chunk.get("context", ""),
                        },
                    })
                    stats["chunks"] += 1
                
                stats["files"] += 1
                stats["total_lines"] += len(content.splitlines())
                
                # Log progress for every 10 files or important files
                if self._progress_callback and analysis_id:
                    if stats["files"] % 10 == 0 or idx == 0:
                        relative_path = str(file_path.relative_to(repo_path))
                        await self._progress_callback(
                            analysis_id, 
                            "INFO", 
                            f"Indexing file {stats['files']}/{total_files}: {relative_path} ({len(chunks)} chunks)"
                        )
                
                # Batch insert every 100 embeddings to avoid memory issues
                if len(embeddings_batch) >= 100:
                    await self._batch_insert_embeddings(embeddings_batch)
                    if self._progress_callback and analysis_id:
                        await self._progress_callback(analysis_id, "INFO", f"Saved {len(embeddings_batch)} embeddings to database")
                    embeddings_batch = []
                    
            except Exception:
                # Skip files that can't be read
                continue
        
        # Insert remaining embeddings
        if embeddings_batch:
            await self._batch_insert_embeddings(embeddings_batch)
            if self._progress_callback and analysis_id:
                await self._progress_callback(analysis_id, "INFO", f"Saved final batch of {len(embeddings_batch)} embeddings")
        
        if self._progress_callback and analysis_id:
            await self._progress_callback(
                analysis_id, 
                "INFO", 
                f"Indexing complete: {stats['files']} files, {stats['chunks']} chunks, {stats['total_lines']} total lines"
            )
        
        # Capture debug stats
        if analysis_id:
            debug_collector.capture_rag_stats(analysis_id, stats)
        
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
        query_embedding = self._model.encode(query, show_progress_bar=False).tolist()
        
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
        
        return all_results[:20]  # Return top 20 unique results

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
        full_path = repo_path / file_path
        if full_path.exists() and full_path.is_file():
            try:
                return full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return None
        return None

    def _find_code_files(self, repo_path: Path) -> list[Path]:
        """Find all code files in repository."""
        code_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
            ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
            ".kt", ".scala", ".clj", ".sh", ".bash", ".zsh",
        }
        
        ignore_patterns = {
            "node_modules", ".git", "venv", "__pycache__", ".next",
            "dist", "build", "target", ".gradle", ".idea", ".venv",
            "env", ".env", "vendor", "coverage", ".nyc_output",
        }
        
        code_files = []
        for ext in code_extensions:
            for file_path in repo_path.rglob(f"*{ext}"):
                if not any(pattern in str(file_path) for pattern in ignore_patterns):
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
        """Get optimized queries for each analysis phase."""
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
            # Use Supabase RPC for vector similarity search
            result = await self._client.rpc(
                'match_embeddings',
                {
                    'query_embedding': query_embedding,
                    'match_count': limit,
                    'filter_repository_id': repository_id,
                }
            ).execute()
            
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
        except Exception:
            # Fallback: Return empty if RPC doesn't exist yet
            pass
        
        return []

    async def _batch_insert_embeddings(self, embeddings: list[dict[str, Any]]) -> None:
        """Batch insert embeddings into database."""
        if not embeddings:
            return
        
        try:
            # Delete existing embeddings for these files to avoid duplicates
            repository_id = embeddings[0]["repository_id"]
            file_paths = list(set(e["file_path"] for e in embeddings))
            
            await self._client.table("embeddings").delete().eq(
                "repository_id", repository_id
            ).in_("file_path", file_paths).execute()
            
            # Insert new embeddings
            await self._client.table("embeddings").insert(embeddings).execute()
        except Exception:
            # Log error but don't fail the whole process
            pass

