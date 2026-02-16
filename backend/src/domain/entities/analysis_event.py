from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Self
import uuid


@dataclass
class AnalysisEvent:
    """Domain entity for an analysis event."""
    id: str
    analysis_id: str
    event_type: str
    message: str
    details: dict[str, Any] | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        analysis_id: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> Self:
        """Create a new analysis event."""
        return cls(
            id=str(uuid.uuid4()),
            analysis_id=analysis_id,
            event_type=event_type,
            message=message,
            details=details,
            created_at=datetime.now(timezone.utc),
        )


