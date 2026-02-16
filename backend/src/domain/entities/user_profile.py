"""User profile entity."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UserProfile:
    """User profile with active repository selection and preferences.

    Single-row design for now. When multi-user support is added,
    a ``user_id`` field will be introduced.
    """

    id: str
    active_repo_id: str | None = None
    preferences: dict = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
