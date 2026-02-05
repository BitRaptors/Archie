"""Base worker class for all agent workers."""
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from domain.entities.worker_assignment import WorkerAssignment, WorkerStatus
from infrastructure.prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Base class for all worker agents.
    
    Workers have full tool access to inspect codebases:
    - File reading
    - Code search
    - Directory listing
    - Command execution (for sync worker)
    """
    
    def __init__(
        self,
        ai_client: AsyncAnthropic | None,
        prompt_loader: PromptLoader,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize base worker.
        
        Args:
            ai_client: Anthropic client for AI calls
            prompt_loader: Loader for prompts from prompts.json
            model: AI model to use
        """
        self._ai_client = ai_client
        self._prompt_loader = prompt_loader
        self._model = model
    
    @abstractmethod
    async def execute(
        self,
        assignment: WorkerAssignment,
        repo_path: Path,
    ) -> dict[str, Any]:
        """Execute the worker assignment.
        
        Args:
            assignment: The work assignment from orchestrator
            repo_path: Path to the repository
            
        Returns:
            Result dictionary specific to worker type
        """
        pass
    
    async def read_file(self, file_path: Path) -> str | None:
        """Read a file's content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File content or None if cannot read
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Cannot read file {file_path}: {e}")
            return None
    
    async def read_files(
        self,
        file_paths: list[str],
        repo_path: Path,
        max_chars_per_file: int = 10_000,
    ) -> dict[str, str]:
        """Read multiple files.
        
        Args:
            file_paths: List of relative file paths
            repo_path: Base repository path
            max_chars_per_file: Max characters to read per file
            
        Returns:
            Dictionary mapping file path to content
        """
        result = {}
        for rel_path in file_paths:
            full_path = repo_path / rel_path
            content = await self.read_file(full_path)
            if content:
                # Truncate if needed
                if len(content) > max_chars_per_file:
                    content = content[:max_chars_per_file] + "\n... (truncated)"
                result[rel_path] = content
        return result
    
    async def list_directory(self, dir_path: Path, max_depth: int = 3) -> list[str]:
        """List files in a directory.
        
        Args:
            dir_path: Directory to list
            max_depth: Maximum depth to traverse
            
        Returns:
            List of relative file paths
        """
        files = []
        
        def walk(current: Path, depth: int):
            if depth > max_depth:
                return
            
            try:
                for item in current.iterdir():
                    if item.name.startswith("."):
                        continue
                    
                    try:
                        rel_path = str(item.relative_to(dir_path))
                        if item.is_file():
                            files.append(rel_path)
                        elif item.is_dir():
                            walk(item, depth + 1)
                    except ValueError:
                        continue
            except PermissionError:
                pass
        
        walk(dir_path, 0)
        return files
    
    async def search_in_files(
        self,
        pattern: str,
        file_paths: list[str],
        repo_path: Path,
    ) -> list[dict[str, Any]]:
        """Search for a pattern in files.
        
        Args:
            pattern: Text pattern to search for
            file_paths: Files to search in
            repo_path: Base repository path
            
        Returns:
            List of matches with file, line number, and content
        """
        import re
        
        matches = []
        pattern_re = re.compile(pattern, re.IGNORECASE)
        
        for rel_path in file_paths:
            content = await self.read_file(repo_path / rel_path)
            if not content:
                continue
            
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if pattern_re.search(line):
                    matches.append({
                        "file": rel_path,
                        "line_number": i,
                        "line": line.strip()[:200],
                    })
        
        return matches
    
    def _build_dependency_graph(
        self,
        file_contents: dict[str, str],
    ) -> dict[str, dict[str, list[str]]]:
        """Build a dependency graph from file contents.
        
        Args:
            file_contents: Dictionary mapping file path to content
            
        Returns:
            Dictionary mapping file to imports and imported_by
        """
        import re
        
        graph: dict[str, dict[str, list[str]]] = {}
        
        # Patterns for different import styles
        python_import_patterns = [
            r'^import\s+([\w.]+)',
            r'^from\s+([\w.]+)\s+import',
        ]
        
        js_import_patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^"\']+)[\'"]',
            r'require\s*\(\s*[\'"]([^"\']+)[\'"]\s*\)',
        ]
        
        # Initialize graph
        for file_path in file_contents:
            graph[file_path] = {"imports": [], "imported_by": []}
        
        # Extract imports
        for file_path, content in file_contents.items():
            imports = set()
            
            # Check file extension for appropriate patterns
            if file_path.endswith(".py"):
                for pattern in python_import_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE)
                    imports.update(matches)
            elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
                for pattern in js_import_patterns:
                    matches = re.findall(pattern, content)
                    imports.update(matches)
            
            graph[file_path]["imports"] = list(imports)
        
        # Build imported_by relationships
        for file_path, deps in graph.items():
            for imp in deps["imports"]:
                # Try to match import to file
                for other_file in file_contents:
                    # Check if import matches file
                    if self._import_matches_file(imp, other_file):
                        if other_file in graph:
                            if file_path not in graph[other_file]["imported_by"]:
                                graph[other_file]["imported_by"].append(file_path)
        
        return graph
    
    def _import_matches_file(self, import_path: str, file_path: str) -> bool:
        """Check if an import path matches a file path.
        
        Args:
            import_path: The import string
            file_path: The file path
            
        Returns:
            True if they match
        """
        # Normalize paths
        import_normalized = import_path.replace(".", "/").replace("@", "")
        file_normalized = file_path.replace("\\", "/")
        
        # Remove extension from file
        for ext in [".py", ".js", ".ts", ".jsx", ".tsx"]:
            if file_normalized.endswith(ext):
                file_normalized = file_normalized[:-len(ext)]
                break
        
        # Check if import is suffix of file
        return (
            file_normalized.endswith(import_normalized) or
            import_normalized.endswith(file_normalized) or
            file_normalized.endswith("/" + import_normalized) or
            import_normalized == file_normalized
        )
    
    async def _call_ai(
        self,
        prompt: str,
        max_tokens: int = 4000,
    ) -> str | None:
        """Call the AI model with a prompt.
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens for response
            
        Returns:
            AI response text or None if failed
        """
        if not self._ai_client:
            logger.warning("No AI client available, returning None")
            return None
        
        try:
            response = await self._ai_client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return None
    
    def _extract_json_from_response(self, response: str) -> dict[str, Any] | list[Any] | None:
        """Extract JSON from AI response.
        
        Args:
            response: The AI response text
            
        Returns:
            Parsed JSON or None if cannot parse
        """
        # Try to find JSON in the response
        try:
            # First try direct parse
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON block
        import re
        
        # Look for ```json ... ``` block
        json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Look for { ... } or [ ... ]
        for pattern in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
            match = re.search(pattern, response)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        
        logger.warning("Could not extract JSON from response")
        return None
    
    def _format_files_for_prompt(
        self,
        file_contents: dict[str, str],
        max_total_chars: int = 50_000,
    ) -> str:
        """Format file contents for inclusion in a prompt.
        
        Args:
            file_contents: Dictionary mapping file path to content
            max_total_chars: Maximum total characters
            
        Returns:
            Formatted string
        """
        result_parts = []
        total_chars = 0
        
        for file_path, content in file_contents.items():
            # Calculate how much space we have
            remaining = max_total_chars - total_chars
            if remaining <= 0:
                break
            
            # Format this file
            header = f"\n### {file_path}\n```\n"
            footer = "\n```\n"
            available = remaining - len(header) - len(footer)
            
            if available <= 0:
                break
            
            truncated_content = content[:available]
            if len(content) > available:
                truncated_content += "\n... (truncated)"
            
            part = header + truncated_content + footer
            result_parts.append(part)
            total_chars += len(part)
        
        return "".join(result_parts)
