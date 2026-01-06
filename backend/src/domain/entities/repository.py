"""Repository domain entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Self
import uuid


@dataclass
class Repository:
    """Repository domain entity."""

    id: str
    user_id: str
    owner: str
    name: str
    full_name: str
    url: str
    description: str | None
    language: str | None
    default_branch: str
    created_at: datetime
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        user_id: str,
        owner: str,
        name: str,
        full_name: str,
        url: str,
        description: str | None = None,
        language: str | None = None,
        default_branch: str = "main",
    ) -> Self:
        """Factory method for creating new repositories."""
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            owner=owner,
            name=name,
            full_name=full_name,
            url=url,
            description=description,
            language=language,
            default_branch=default_branch,
            created_at=now,
        )


