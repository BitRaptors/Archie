"""File tree scanner that walks a repository directory."""
from __future__ import annotations

import os
from pathlib import Path

from archie.engine.models import FileEntry

SKIP_DIRS: set[str] = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "coverage",
    ".nyc_output",
    ".turbo",
    ".parcel-cache",
    "vendor",
    "Pods",
    ".gradle",
    ".idea",
    ".vscode",
}

SKIP_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
    ".lock", ".sum",
}

ALLOWED_HIDDEN_FILES: set[str] = {
    ".env.example",
    ".gitignore",
    ".dockerignore",
}


def scan_directory(root: str | Path) -> list[FileEntry]:
    """Walk *root* and return a sorted list of FileEntry for all relevant files.

    Directories in SKIP_DIRS are pruned in-place so os.walk never descends
    into them.  Hidden files (name starts with ``"."``) are skipped unless
    they appear in ALLOWED_HIDDEN_FILES.  Files whose extension is in
    SKIP_EXTENSIONS are also skipped.
    """
    root = Path(root).resolve()
    entries: list[FileEntry] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # In-place prune of directories we never want to enter.
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and (not d.startswith(".") or d in SKIP_DIRS)
        ]
        # Also drop hidden directories that aren't in SKIP_DIRS
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for fname in filenames:
            # Skip hidden files unless explicitly allowed.
            if fname.startswith(".") and fname not in ALLOWED_HIDDEN_FILES:
                continue

            ext = os.path.splitext(fname)[1].lower()
            if ext in SKIP_EXTENSIONS:
                continue

            full = os.path.join(dirpath, fname)
            try:
                stat = os.stat(full)
            except OSError:
                continue

            rel = os.path.relpath(full, root)
            entries.append(
                FileEntry(
                    path=rel,
                    size=stat.st_size,
                    last_modified=stat.st_mtime,
                    extension=ext,
                )
            )

    entries.sort(key=lambda e: e.path)
    return entries
