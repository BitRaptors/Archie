"""Embedding generator for code."""
from pathlib import Path
from typing import Any
from sentence_transformers import SentenceTransformer
from config.settings import get_settings
from infrastructure.analysis.vector_store import IVectorStore


class EmbeddingGenerator:
    """Generates embeddings for code files."""

    def __init__(self, vector_store: IVectorStore):
        """Initialize embedding generator."""
        settings = get_settings()
        self._model = SentenceTransformer(settings.embedding_model)
        self._vector_store = vector_store

    async def generate_embeddings(self, repository_id: str, repo_path: Path) -> None:
        """Generate embeddings for all code files."""
        embeddings = []
        
        # Find all code files
        code_files = self._find_code_files(repo_path)
        
        for file_path in code_files:
            # Read file content
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            
            # Generate embeddings for different chunks
            file_embeddings = await self._generate_file_embeddings(
                repository_id=repository_id,
                file_path=str(file_path.relative_to(repo_path)),
                content=content,
            )
            
            embeddings.extend(file_embeddings)
        
        # Batch insert embeddings
        if embeddings:
            await self._vector_store.add_embeddings(embeddings)

    def _find_code_files(self, repo_path: Path, discovery_ignored_dirs: set[str] | None = None) -> list[Path]:
        """Find all code files in repository."""
        from domain.entities.analysis_settings import DEFAULT_IGNORED_DIRS

        code_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
            ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
            ".kt", ".scala", ".clj", ".sh", ".bash", ".zsh",
        }

        code_files = []
        for ext in code_extensions:
            code_files.extend(repo_path.rglob(f"*{ext}"))

        ignore_patterns = discovery_ignored_dirs or DEFAULT_IGNORED_DIRS

        filtered = []
        for file_path in code_files:
            try:
                rel_parts = file_path.relative_to(repo_path).parts
            except ValueError:
                continue
            if not any(part in ignore_patterns for part in rel_parts):
                filtered.append(file_path)

        return filtered

    async def _generate_file_embeddings(
        self,
        repository_id: str,
        file_path: str,
        content: str,
    ) -> list[dict[str, Any]]:
        """Generate embeddings for a file (module-level)."""
        # Generate module-level embedding
        embedding_vector = self._model.encode(content, show_progress_bar=False)
        
        return [{
            "repository_id": repository_id,
            "file_path": file_path,
            "chunk_type": "module",
            "embedding": embedding_vector.tolist(),
            "metadata": {
                "lines": len(content.splitlines()),
                "size": len(content),
            },
        }]


