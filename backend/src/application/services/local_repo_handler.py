"""Local repository file I/O handler for reading and writing intent layer outputs."""
import os
from pathlib import Path

from application.services.delivery_service import _merge_markdown


class LocalRepoHandler:
    """Read from and write to a local repository on disk."""

    def __init__(self, repo_path: Path, ignored_dirs: set[str] | None = None):
        self.repo_path = repo_path.resolve()
        self._ignored = ignored_dirs or set()

    def build_file_tree(self) -> list[dict]:
        """Walk the local directory, return file tree in structure_analyzer format.

        Returns list of dicts with: name, path, type, size, extension
        """
        tree = []
        for root, dirs, files in os.walk(self.repo_path):
            # Filter ignored dirs in-place to prevent descending
            dirs[:] = [d for d in dirs if d not in self._ignored and not d.startswith('.')]

            for f in files:
                if f.startswith('.'):
                    continue
                full_path = Path(root) / f
                rel_path = str(full_path.relative_to(self.repo_path))
                ext = full_path.suffix.lstrip('.')
                try:
                    size = full_path.stat().st_size
                except OSError:
                    size = 0
                tree.append({
                    "name": f,
                    "path": rel_path,
                    "type": "file",
                    "size": size,
                    "extension": ext,
                })
        return tree

    def read_file(self, rel_path: str) -> str | None:
        """Read a file's content from the local repo. Returns None if not found or unreadable."""
        target = self.repo_path / rel_path
        if not target.is_file():
            return None
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return None

    def write_file(self, rel_path: str, content: str) -> None:
        """Write content to a file in the local repo, creating dirs as needed."""
        target = self.repo_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def write_merged_markdown(self, rel_path: str, content: str, repo_name: str) -> None:
        """Write markdown with gbr marker merge logic.

        If file exists, merges using gbr markers. Otherwise creates with markers.
        """
        target = self.repo_path / rel_path
        existing = None
        if target.is_file():
            try:
                existing = target.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                pass

        merged = _merge_markdown(existing, content, repo_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(merged, encoding="utf-8")
