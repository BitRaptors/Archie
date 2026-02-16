"""Response DTOs."""
from pydantic import BaseModel
from datetime import datetime
from typing import Any


class RepositoryResponse(BaseModel):
    """Repository response."""
    id: str
    owner: str
    name: str
    full_name: str
    url: str
    description: str | None
    language: str | None
    default_branch: str
    created_at: datetime | str | None


class AnalysisResponse(BaseModel):
    """Analysis response."""
    id: str
    repository_id: str
    status: str
    progress_percentage: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class AnalysisEventResponse(BaseModel):
    """Analysis event response."""
    id: str
    analysis_id: str
    event_type: str
    message: str
    details: dict[str, Any] | None = None
    created_at: datetime


class BlueprintResponse(BaseModel):
    """Blueprint response."""
    id: str
    repository_id: str
    analysis_id: str
    blueprint_path: str
    created_at: datetime


class UnifiedBlueprintResponse(BaseModel):
    """Unified blueprint response."""
    id: str
    user_id: str
    name: str
    description: str | None
    blueprint_path: str
    repository_ids: list[str]
    created_at: datetime
    updated_at: datetime | None


class PromptResponse(BaseModel):
    """Prompt response."""
    id: str
    user_id: str | None = None
    name: str
    description: str | None = None
    category: str
    prompt_template: str
    variables: list[str]
    is_default: bool
    created_at: datetime
    updated_at: datetime | None = None
    key: str | None = None
    type: str = "prompt"


class PromptRevisionResponse(BaseModel):
    """Prompt revision response."""
    id: str
    prompt_id: str
    revision_number: int
    prompt_template: str
    variables: list[str]
    name: str | None = None
    description: str | None = None
    change_summary: str | None = None
    created_by: str | None = None
    created_at: datetime
