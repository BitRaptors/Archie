"""Data models for the local analysis engine."""
from __future__ import annotations
from pydantic import BaseModel, Field

class FileEntry(BaseModel):
    """A single file in the scanned repository."""
    path: str
    size: int = 0
    last_modified: float = 0.0
    extension: str = ""

class DependencyEntry(BaseModel):
    """A parsed dependency from a manifest file."""
    name: str
    version: str = ""
    source: str = ""

class FrameworkSignal(BaseModel):
    """A detected framework or library with confidence."""
    name: str
    version: str = ""
    confidence: float = 1.0
    evidence: list[str] = Field(default_factory=list)

class RawScan(BaseModel):
    """Complete output of the local analysis engine."""
    file_tree: list[FileEntry] = Field(default_factory=list)
    token_counts: dict[str, int] = Field(default_factory=dict)
    dependencies: list[DependencyEntry] = Field(default_factory=list)
    framework_signals: list[FrameworkSignal] = Field(default_factory=list)
    config_patterns: dict[str, str] = Field(default_factory=dict)
    import_graph: dict[str, list[str]] = Field(default_factory=dict)
    directory_structure: dict[str, list[str]] = Field(default_factory=dict)
    file_hashes: dict[str, str] = Field(default_factory=dict)
    entry_points: list[str] = Field(default_factory=list)
