"""Analysis prompt domain entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
import uuid


@dataclass
class AnalysisPrompt:
    """Analysis prompt domain entity."""

    id: str
    user_id: str | None
    name: str
    description: str | None
    category: str
    prompt_template: str
    variables: list[str]
    is_default: bool
    created_at: datetime
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        name: str,
        category: str,
        prompt_template: str,
        user_id: str | None = None,
        description: str | None = None,
        variables: list[str] | None = None,
        is_default: bool = False,
    ) -> Self:
        """Factory method for creating new prompts."""
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            category=category,
            prompt_template=prompt_template,
            variables=variables or [],
            is_default=is_default,
            created_at=now,
        )

    def render(self, context: dict[str, Any]) -> str:
        """Render prompt template with context variables."""
        rendered = self.prompt_template
        for var in self.variables:
            value = context.get(var, "")
            rendered = rendered.replace(f"{{{var}}}", str(value))
        return rendered


