"""Domain entities and defaults for analysis settings."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


# Predefined capability enum — the only valid values for library capabilities.
ECOSYSTEM_OPTIONS: list[str] = sorted([
    "Android",
    "Android Jetpack",
    "Apple",
    "Auth0",
    "AWS",
    "Clerk",
    "Cloudinary",
    "Cross-platform",
    "Flutter",
    "Google Firebase",
    "iOS",
    "JavaScript",
    "Kotlin Multiplatform",
    "Mixpanel",
    "MongoDB Realm",
    "Node.js",
    "Node.js/MongoDB",
    "OneSignal",
    "Python",
    "React",
    "Sentry",
    "Stripe",
    "Supabase",
])


# Predefined capability enum — the only valid values for library capabilities.
CAPABILITY_OPTIONS: list[str] = sorted([
    "analytics",
    "api",
    "authentication",
    "cloud_functions",
    "concurrency",
    "dependency_injection",
    "edge_functions",
    "error_tracking",
    "graphql",
    "hosting",
    "image_loading",
    "image_processing",
    "logging",
    "monitoring",
    "navigation",
    "networking",
    "odm",
    "offline_first",
    "offline_storage",
    "orm",
    "payments",
    "persistence",
    "push_notifications",
    "reactive_programming",
    "realtime",
    "serialization",
    "state_management",
    "storage",
    "sync",
    "ui_framework",
    "websocket",
])


# Canonical set of source code file extensions — used by file registry,
# signature extraction, budget calculation, supplementary reading, and RAG indexing.
SOURCE_CODE_EXTENSIONS: frozenset[str] = frozenset({
    # General
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".rb", ".php", ".cs", ".cpp", ".c", ".h", ".hpp", ".scala",
    # iOS / macOS
    ".swift", ".m", ".mm",
    # Android / Kotlin
    ".kt", ".kts",
    # Flutter / Dart
    ".dart",
    # Config-as-code (build scripts, manifests, layouts)
    ".xml", ".gradle",
})


# Seed defaults for the "reset to defaults" API endpoints only.
# These are NOT used as runtime fallbacks — if the DB is unavailable,
# the system operates with empty sets (no silent defaults).
SEED_IGNORED_DIRS: set[str] = {
    "node_modules", "Pods", "Carthage", ".build", "DerivedData",
    "vendor", ".bundle", "bower_components", "flutter_build", ".dart_tool",
    ".gradle", "build", "dist", "target", ".next", ".nuxt", ".output",
    "venv", ".venv", "env", "__pycache__", ".git", ".idea",
    "coverage", ".nyc_output",
}

SEED_LIBRARY_CAPABILITIES: dict[str, dict] = {
    "firebase": {"capabilities": ["persistence", "authentication", "analytics", "push_notifications", "cloud_functions", "hosting", "storage"], "ecosystem": "Google Firebase"},
    "supabase": {"capabilities": ["persistence", "authentication", "storage", "realtime", "edge_functions"], "ecosystem": "Supabase"},
    "realm": {"capabilities": ["persistence", "sync", "offline_first"], "ecosystem": "MongoDB Realm"},
    "coredata": {"capabilities": ["persistence", "offline_storage"], "ecosystem": "Apple"},
    "alamofire": {"capabilities": ["networking"], "ecosystem": "iOS"},
    "retrofit": {"capabilities": ["networking"], "ecosystem": "Android"},
    "axios": {"capabilities": ["networking"], "ecosystem": "JavaScript"},
    "redux": {"capabilities": ["state_management"], "ecosystem": "React"},
    "prisma": {"capabilities": ["persistence", "orm"], "ecosystem": "Node.js"},
    "sqlalchemy": {"capabilities": ["persistence", "orm"], "ecosystem": "Python"},
    "apollo": {"capabilities": ["networking", "state_management", "graphql"], "ecosystem": "JavaScript"},
    "sentry": {"capabilities": ["error_tracking", "monitoring"], "ecosystem": "Sentry"},
}


class IgnoredDirectory(BaseModel):
    """A single ignored directory entry."""
    id: str = ""
    directory_name: str = ""
    created_at: datetime | None = None


class LibraryCapability(BaseModel):
    """A library with its capabilities and ecosystem."""
    id: str = ""
    library_name: str = ""
    ecosystem: str = ""
    capabilities: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
