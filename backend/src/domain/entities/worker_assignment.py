"""Worker assignment domain entity for orchestrator pattern."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Self
import uuid


class WorkerType(str, Enum):
    """Types of worker agents."""
    ANALYSIS = "analysis"      # Analyzes codebase, extracts architecture rules
    VALIDATION = "validation"  # Validates code against architecture rules
    SYNC = "sync"              # Detects changes, triggers incremental updates


class WorkerStatus(str, Enum):
    """Status of a worker assignment."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkerAssignment:
    """Assignment for a single worker agent.
    
    The orchestrator creates these to distribute work among workers.
    """
    
    id: str
    worker_type: WorkerType
    files: list[str]           # Files to analyze/validate
    token_budget: int          # Max tokens for this worker
    focus_areas: list[str]     # What to look for (e.g., ["dependencies", "conventions"])
    context: dict[str, Any]    # Shared context from orchestrator
    status: WorkerStatus = WorkerStatus.PENDING
    result: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    
    @classmethod
    def create_analysis_assignment(
        cls,
        files: list[str],
        token_budget: int = 150_000,
        focus_areas: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> Self:
        """Factory method for creating an analysis worker assignment."""
        return cls(
            id=str(uuid.uuid4()),
            worker_type=WorkerType.ANALYSIS,
            files=files,
            token_budget=token_budget,
            focus_areas=focus_areas or ["purpose", "dependency", "convention", "boundary"],
            context=context or {},
            created_at=datetime.now(timezone.utc),
        )
    
    @classmethod
    def create_validation_assignment(
        cls,
        files: list[str],
        context: dict[str, Any] | None = None,
    ) -> Self:
        """Factory method for creating a validation worker assignment."""
        return cls(
            id=str(uuid.uuid4()),
            worker_type=WorkerType.VALIDATION,
            files=files,
            token_budget=50_000,  # Validation needs less tokens
            focus_areas=["validate"],
            context=context or {},
            created_at=datetime.now(timezone.utc),
        )
    
    @classmethod
    def create_sync_assignment(
        cls,
        context: dict[str, Any] | None = None,
    ) -> Self:
        """Factory method for creating a sync worker assignment."""
        return cls(
            id=str(uuid.uuid4()),
            worker_type=WorkerType.SYNC,
            files=[],  # Sync worker determines files from git
            token_budget=20_000,  # Sync needs minimal tokens
            focus_areas=["detect_changes"],
            context=context or {},
            created_at=datetime.now(timezone.utc),
        )
    
    def start(self) -> None:
        """Mark assignment as started."""
        self.status = WorkerStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)
    
    def complete(self, result: dict[str, Any]) -> None:
        """Mark assignment as completed with result."""
        self.status = WorkerStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now(timezone.utc)
    
    def fail(self, error_message: str) -> None:
        """Mark assignment as failed."""
        self.status = WorkerStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now(timezone.utc)
    
    def is_completed(self) -> bool:
        """Check if assignment is completed (success or failure)."""
        return self.status in [WorkerStatus.COMPLETED, WorkerStatus.FAILED]
    
    def is_successful(self) -> bool:
        """Check if assignment completed successfully."""
        return self.status == WorkerStatus.COMPLETED
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "id": self.id,
            "worker_type": self.worker_type.value,
            "files_count": len(self.files),
            "token_budget": self.token_budget,
            "focus_areas": self.focus_areas,
            "status": self.status.value,
        }
        
        if self.started_at:
            result["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            result["completed_at"] = self.completed_at.isoformat()
        if self.error_message:
            result["error_message"] = self.error_message
            
        return result


@dataclass
class OrchestrationPlan:
    """Plan created by orchestrator for distributing work."""
    
    id: str
    repository_id: str
    total_files: int
    total_tokens: int
    assignments: list[WorkerAssignment] = field(default_factory=list)
    created_at: datetime | None = None
    
    @classmethod
    def create(
        cls,
        repository_id: str,
        total_files: int,
        total_tokens: int,
        assignments: list[WorkerAssignment],
    ) -> Self:
        """Factory method for creating an orchestration plan."""
        return cls(
            id=str(uuid.uuid4()),
            repository_id=repository_id,
            total_files=total_files,
            total_tokens=total_tokens,
            assignments=assignments,
            created_at=datetime.now(timezone.utc),
        )
    
    def get_pending_assignments(self) -> list[WorkerAssignment]:
        """Get all pending assignments."""
        return [a for a in self.assignments if a.status == WorkerStatus.PENDING]
    
    def get_completed_assignments(self) -> list[WorkerAssignment]:
        """Get all completed assignments."""
        return [a for a in self.assignments if a.status == WorkerStatus.COMPLETED]
    
    def get_failed_assignments(self) -> list[WorkerAssignment]:
        """Get all failed assignments."""
        return [a for a in self.assignments if a.status == WorkerStatus.FAILED]
    
    def is_complete(self) -> bool:
        """Check if all assignments are complete."""
        return all(a.is_completed() for a in self.assignments)
    
    def success_rate(self) -> float:
        """Calculate success rate of completed assignments."""
        completed = [a for a in self.assignments if a.is_completed()]
        if not completed:
            return 0.0
        successful = sum(1 for a in completed if a.is_successful())
        return successful / len(completed)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "total_files": self.total_files,
            "total_tokens": self.total_tokens,
            "assignments_count": len(self.assignments),
            "pending_count": len(self.get_pending_assignments()),
            "completed_count": len(self.get_completed_assignments()),
            "failed_count": len(self.get_failed_assignments()),
            "is_complete": self.is_complete(),
            "success_rate": self.success_rate(),
            "assignments": [a.to_dict() for a in self.assignments],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
