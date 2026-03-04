"""Intent Layer domain models for per-folder CLAUDE.md generation."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FolderNode(BaseModel):
    """Represents a folder in the repository hierarchy."""
    path: str                    # "src/api/routes" (relative from repo root)
    name: str                    # "routes"
    depth: int                   # 0 = root
    parent_path: str = ""
    files: list[str] = []       # Direct files in this folder
    file_count: int = 0         # Recursive file count
    children: list[str] = []    # Child folder paths
    extensions: list[str] = []  # Unique extensions found


class FolderContext(BaseModel):
    """AI-generated context for a folder (used by optional AI enrichment mode)."""
    path: str
    purpose: str = ""
    scope: str = ""
    key_files: list[dict[str, str]] = []    # [{file, description}]
    patterns: list[str] = []
    anti_patterns: list[str] = []
    cross_references: list[dict[str, str]] = []  # [{path, relationship}]
    downlinks: list[dict[str, str]] = []    # [{path, summary}]


class FolderBlueprint(BaseModel):
    """Blueprint data projected onto a single folder. Deterministic, not AI-generated."""
    path: str
    # Component
    component_name: str = ""
    component_responsibility: str = ""
    depends_on: list[str] = []
    exposes_to: list[str] = []
    key_interfaces: list[dict[str, Any]] = []     # [{name, methods, description}]
    key_files: list[dict[str, str]] = []           # [{file, description}]
    # Architecture rules
    file_placement_rules: list[dict[str, str]] = []  # [{component_type, naming_pattern, example, description}]
    naming_conventions: list[dict[str, str]] = []    # [{scope, pattern, examples}]
    # Quick reference
    where_to_put: dict[str, str] = {}              # {code_type: location}
    # Developer guidance (Cartographer-inspired navigation)
    recipes: list[dict[str, Any]] = []             # [{task, files, steps}]
    pitfalls: list[dict[str, str]] = []            # [{area, description, recommendation}]
    implementation_guidelines: list[dict[str, Any]] = []  # [{capability, libraries, pattern_description}]
    # Contracts & communication
    contracts: list[dict[str, Any]] = []           # [{interface_name, methods}]
    communication_patterns: list[dict[str, str]] = []  # [{name, when_to_use, how_it_works}]
    # Templates
    templates: list[dict[str, str]] = []           # [{component_type, file_path_template, code}]
    # Hierarchy & Navigation
    children_summaries: list[dict[str, str]] = []  # [{path, component_name, responsibility}]
    peer_paths: list[str] = []                      # Sibling folder paths (same parent)
    parent_path: str = ""                           # Parent folder path (for uplink)
    parent_component: str = ""
    has_blueprint_coverage: bool = False


class KeyFileGuide(BaseModel):
    """AI-produced guide for a key file in a folder."""
    file: str                    # Actual filename from folder listing
    purpose: str                 # What this file does (1 sentence)
    modification_guide: str      # How to modify it correctly (imperative)


class CommonTask(BaseModel):
    """Most common modification task for a folder."""
    task: str                    # e.g., "Add a new API endpoint"
    steps: list[str]             # Imperative numbered steps


class FolderEnrichment(BaseModel):
    """AI-produced compound learning for a single folder.

    Reads like auto-memory notes from an experienced developer:
    patterns discovered, mistakes to avoid, debugging insights, historical decisions.
    """
    path: str
    purpose: str = ""            # 1-line: what this folder IS + its key constraint
    patterns: list[str] = []    # Coding patterns discovered from actual code
    key_file_guides: list[KeyFileGuide] = []
    anti_patterns: list[str] = []  # "Don't X -- Y instead" format
    common_task: CommonTask | None = None
    testing: list[str] = []     # How to test code in this folder
    debugging: list[str] = []   # Debugging insights and common issues
    decisions: list[str] = []   # Why things are built this way
    has_ai_content: bool = False


class FolderManifestEntry(BaseModel):
    """Content hash for a single generated file."""
    path: str
    content_hash: str


class GenerationManifest(BaseModel):
    """Tracks blueprint hash + content hashes for incremental updates."""
    blueprint_hash: str = ""
    entries: list[FolderManifestEntry] = []


class IntentLayerConfig(BaseModel):
    """Configuration for intent layer generation."""
    max_depth: int = 99
    min_files: int = 2
    max_concurrent: int = 5
    excluded_dirs: set[str] = Field(default_factory=set)
    output_claude_md: bool = True
    ai_model: str = ""  # Empty = use default_ai_model
    enable_ai_enrichment: bool = True
    enrichment_model: str = ""  # Empty = use default_ai_model
    generate_codebase_map: bool = True


class IntentLayerOutput(BaseModel):
    """Output of the intent layer generation process."""
    claude_md_files: dict[str, str] = {}   # rel_path -> content
    codebase_map: str = ""                  # CODEBASE_MAP.md content
    folder_contexts: dict[str, FolderContext] = {}
    folder_count: int = 0
    total_ai_calls: int = 0
    generation_time_seconds: float = 0.0
