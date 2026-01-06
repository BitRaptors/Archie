"""Analysis domain entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Self
import uuid
from config.constants import AnalysisStatus


@dataclass
class Analysis:
    """Analysis domain entity."""

    id: str
    repository_id: str
    status: str
    progress_percentage: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None = None

    @classmethod
    def create(cls, repository_id: str) -> Self:
        """Factory method for creating new analyses."""
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            repository_id=repository_id,
            status=AnalysisStatus.PENDING,
            progress_percentage=0,
            error_message=None,
            started_at=None,
            completed_at=None,
            created_at=now,
        )

    def start(self) -> None:
        """Mark analysis as started."""
        self.status = AnalysisStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def update_progress(self, percentage: int) -> None:
        """Update analysis progress."""
        self.progress_percentage = min(100, max(0, percentage))
        self.updated_at = datetime.utcnow()

    def complete(self) -> None:
        """Mark analysis as completed."""
        self.status = AnalysisStatus.COMPLETED
        self.progress_percentage = 100
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def fail(self, error_message: str) -> None:
        """Mark analysis as failed."""
        self.status = AnalysisStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


