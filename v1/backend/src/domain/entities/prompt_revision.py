"""Prompt revision domain entity."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self
import uuid


@dataclass
class PromptRevision:
    """Stores a snapshot of a prompt before each edit."""

    id: str
    prompt_id: str
    revision_number: int
    prompt_template: str
    variables: list[str]
    name: str | None
    description: str | None
    change_summary: str | None
    created_by: str | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        prompt_id: str,
        revision_number: int,
        prompt_template: str,
        variables: list[str] | None = None,
        name: str | None = None,
        description: str | None = None,
        change_summary: str | None = None,
        created_by: str | None = None,
    ) -> Self:
        """Factory method for creating new revisions."""
        return cls(
            id=str(uuid.uuid4()),
            prompt_id=prompt_id,
            revision_number=revision_number,
            prompt_template=prompt_template,
            variables=variables or [],
            name=name,
            description=description,
            change_summary=change_summary,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
