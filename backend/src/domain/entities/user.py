"""User domain entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Self
import uuid


@dataclass
class User:
    """User domain entity."""

    id: str
    github_token_encrypted: str
    created_at: datetime
    updated_at: datetime | None = None

    @classmethod
    def create(cls, github_token_encrypted: str) -> Self:
        """Factory method for creating new users."""
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            github_token_encrypted=github_token_encrypted,
            created_at=now,
        )

    def update_token(self, github_token_encrypted: str) -> None:
        """Update GitHub token with timestamp."""
        self.github_token_encrypted = github_token_encrypted
        self.updated_at = datetime.utcnow()


