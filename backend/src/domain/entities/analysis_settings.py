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
    "Flutter",
    "Google Firebase",
    "iOS",
    "JavaScript",
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
    "dependency_injection",
    "edge_functions",
    "error_tracking",
    "graphql",
    "hosting",
    "image_processing",
    "monitoring",
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
    "state_management",
    "storage",
    "sync",
    "websocket",
])


# Default discovery ignored directories — used when DB is unavailable.
DEFAULT_IGNORED_DIRS: set[str] = {
    "node_modules", "Pods", "Carthage", ".build", "DerivedData",
    "vendor", ".bundle", "bower_components", "flutter_build", ".dart_tool",
    ".gradle", "build", "dist", "target", ".next", ".nuxt", ".output",
    "venv", ".venv", "env", "__pycache__", ".git", ".idea",
    "coverage", ".nyc_output",
}

# Default library capability mapping — used when DB is unavailable.
DEFAULT_LIBRARY_CAPABILITIES: dict[str, dict] = {
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
