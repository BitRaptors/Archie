from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class PromptBase(BaseModel):
    name: str
    description: Optional[str] = None
    system_prompt: str
    user_prompt: str
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    response_format: Optional[dict] = None
    available_variables: List[str] = []


class PromptUpdate(PromptBase):
    """Used when updating a prompt - creates a new version."""
    pass


class Prompt(PromptBase):
    id: UUID
    slug: str
    version: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PromptTestRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class PromptTestResponse(BaseModel):
    response: str
    provider: str
    model: str
    usage: Optional[dict] = None
