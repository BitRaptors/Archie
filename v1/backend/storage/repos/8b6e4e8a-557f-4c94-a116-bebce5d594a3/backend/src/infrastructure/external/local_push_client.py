"""Local filesystem client for delivering architecture outputs to a local checkout."""
import os
from pathlib import Path

from domain.exceptions.domain_exceptions import ValidationError


class LocalPushClient:
    """Write architecture outputs directly to a local directory."""

    def __init__(self, base_dir: str):
        self._base_dir = Path(base_dir)
        if not self._base_dir.is_dir():
            raise ValidationError(f"Target directory does not exist: {base_dir}")

    def get_file_content(self, path: str) -> str | None:
        """Read a file from the local directory. Returns None if missing."""
        full = self._base_dir / path
        if not full.is_file():
            return None
        return full.read_text(encoding="utf-8")

    def write_files(
        self,
        files: dict[str, str],
        executable_paths: set[str] | None = None,
    ) -> list[str]:
        """Write files to the local directory, creating subdirectories as needed.

        Returns list of written file paths (relative).
        """
        executable_paths = executable_paths or set()
        written: list[str] = []
        for rel_path, content in files.items():
            full = self._base_dir / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            if rel_path in executable_paths:
                full.chmod(full.stat().st_mode | 0o111)
            written.append(rel_path)
        return written
