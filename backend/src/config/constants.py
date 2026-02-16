"""Application constants."""


# Analysis Status
class AnalysisStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Chunk Types for Embeddings
class ChunkType:
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    DIRECTORY = "directory"


# Storage Paths
class StoragePaths:
    BLUEPRINTS = "blueprints"
    ANALYSIS_DATA = "analysis_data"


