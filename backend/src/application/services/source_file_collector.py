"""Copy the cloned repository to persistent storage.

After analysis the temp clone is deleted. This module copies the entire repo
tree to persistent storage so that MCP tools and the frontend can serve any
file after the clone is gone.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from domain.entities.analysis_settings import DEFAULT_IGNORED_DIRS

logger = logging.getLogger(__name__)

# Re-export so tests can reference it; used as fallback only.
IGNORED_DIRS = DEFAULT_IGNORED_DIRS


def _make_ignore_callback(ignored: set[str]):
    """Create a shutil.copytree ignore callback for the given directory names."""
    def _ignore(directory: str, contents: list[str]) -> set[str]:
        return {c for c in contents if c in ignored}
    return _ignore


class SourceFileCollector:
    """Copy the full repository tree to persistent storage."""

    def copy_repo(
        self,
        temp_repo_dir: Path,
        dest_dir: Path,
        ignored_dirs: set[str] | None = None,
    ) -> dict:
        """Copy the repository tree and return a manifest.

        Args:
            temp_repo_dir: Path to the cloned repository (still on disk).
            dest_dir: Destination directory in persistent storage
                      (e.g. ``storage/repos/{repo_id}``).
            ignored_dirs: Directory names to skip (user-configured from DB).
                          Falls back to DEFAULT_IGNORED_DIRS when not provided.

        Returns:
            Manifest dict with file list and total size.
        """
        effective_ignored = ignored_dirs if ignored_dirs is not None else DEFAULT_IGNORED_DIRS

        # Remove old copy if it exists
        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        # Copy entire tree, skipping configured ignored directories
        shutil.copytree(
            temp_repo_dir,
            dest_dir,
            ignore=_make_ignore_callback(effective_ignored),
            dirs_exist_ok=False,
        )

        # Walk the destination and build a manifest
        manifest_files: dict[str, int] = {}
        total_size = 0
        for root, _dirs, files in os.walk(dest_dir):
            for fname in files:
                full = Path(root) / fname
                try:
                    size = full.stat().st_size
                except OSError:
                    continue
                rel = str(full.relative_to(dest_dir))
                manifest_files[rel] = size
                total_size += size

        manifest = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(manifest_files),
            "total_size": total_size,
            "files": manifest_files,
        }

        # Write manifest next to the repo copy
        manifest_path = dest_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        logger.info(
            "Copied %d files (%d bytes) for repo at %s",
            len(manifest_files),
            total_size,
            dest_dir,
        )

        return manifest
