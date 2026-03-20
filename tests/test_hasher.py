"""Tests for archie.engine.hasher."""
from __future__ import annotations
from pathlib import Path


from archie.engine.hasher import count_tokens, hash_files
from archie.engine.models import FileEntry


def test_hash_files_deterministic(tmp_path: Path) -> None:
    """Same content produces the same SHA-256 hash (length 64 hex chars)."""
    (tmp_path / "a.txt").write_text("hello world")
    entries = [FileEntry(path="a.txt", size=11)]

    result1 = hash_files(tmp_path, entries)
    result2 = hash_files(tmp_path, entries)

    assert result1 == result2
    assert len(result1["a.txt"]) == 64


def test_hash_files_different_content(tmp_path: Path) -> None:
    """Different file contents produce different hashes."""
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("world")
    entries = [
        FileEntry(path="a.txt", size=5),
        FileEntry(path="b.txt", size=5),
    ]

    result = hash_files(tmp_path, entries)

    assert result["a.txt"] != result["b.txt"]


def test_hash_files_missing_file(tmp_path: Path) -> None:
    """Missing files are silently skipped; result is empty."""
    entries = [FileEntry(path="nonexistent.txt", size=0)]

    result = hash_files(tmp_path, entries)

    assert result == {}


def test_count_tokens(tmp_path: Path) -> None:
    """Basic Python code produces a positive token count."""
    code = "def hello():\n    return 'world'\n"
    (tmp_path / "main.py").write_text(code)
    entries = [FileEntry(path="main.py", size=len(code))]

    result = count_tokens(tmp_path, entries)

    assert "main.py" in result
    assert result["main.py"] > 0


def test_count_tokens_empty_file(tmp_path: Path) -> None:
    """Empty file yields 0 tokens."""
    (tmp_path / "empty.py").write_text("")
    entries = [FileEntry(path="empty.py", size=0)]

    result = count_tokens(tmp_path, entries)

    assert result["empty.py"] == 0
