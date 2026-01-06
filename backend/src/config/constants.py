"""Application constants."""

# Analysis Status
class AnalysisStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Prompt Categories
class PromptCategory:
    STRUCTURE = "structure"
    PATTERNS = "patterns"
    PRINCIPLES = "principles"
    BLUEPRINT_SYNTHESIS = "blueprint_synthesis"
    DIRECTORY_SUMMARY = "directory_summary"
    PATTERN_DEEP_DIVE = "pattern_deep_dive"


# Chunk Types for Embeddings
class ChunkType:
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    DIRECTORY = "directory"


# Storage Paths
class StoragePaths:
    BLUEPRINTS = "blueprints"
    UNIFIED_BLUEPRINTS = "blueprints/unified"
    ANALYSIS_DATA = "analysis_data"


