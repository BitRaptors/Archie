"""File hashing and token counting."""
from __future__ import annotations
import hashlib
from pathlib import Path
from archie.engine.models import FileEntry

def hash_files(repo_path: Path, entries: list[FileEntry]) -> dict[str, str]:
    """Compute SHA-256 hash for each file. Skips missing files."""
    hashes: dict[str, str] = {}
    for entry in entries:
        full = repo_path / entry.path
        try:
            content = full.read_bytes()
        except OSError:
            continue
        hashes[entry.path] = hashlib.sha256(content).hexdigest()
    return hashes

def count_tokens(repo_path: Path, entries: list[FileEntry], max_file_size: int = 1_000_000) -> dict[str, int]:
    """Count tokens per file using tiktoken (cl100k_base)."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    counts: dict[str, int] = {}
    for entry in entries:
        if entry.size > max_file_size:
            continue
        full = repo_path / entry.path
        try:
            content = full.read_text(errors="ignore")
        except OSError:
            continue
        counts[entry.path] = len(enc.encode(content)) if content else 0
    return counts
