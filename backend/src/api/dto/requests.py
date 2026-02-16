"""Request DTOs."""
from pydantic import BaseModel, Field


class GitHubAuthRequest(BaseModel):
    """GitHub authentication request."""
    token: str = Field(..., description="GitHub personal access token")


class CreateRepositoryRequest(BaseModel):
    """Create repository request."""
    owner: str = Field(..., description="Repository owner")
    name: str = Field(..., description="Repository name")


class StartAnalysisRequest(BaseModel):
    """Start analysis request."""
    prompt_config: dict[str, str] | None = Field(
        default=None,
        description="Custom prompt configuration per category"
    )


class CreateUnifiedBlueprintRequest(BaseModel):
    """Create unified blueprint request."""
    repository_ids: list[str] = Field(..., description="Repository IDs to include")
    name: str = Field(..., description="Unified blueprint name")
    description: str | None = Field(default=None, description="Description")


class CreatePromptRequest(BaseModel):
    """Create prompt request."""
    name: str = Field(..., description="Prompt name")
    description: str | None = Field(default=None)
    category: str = Field(..., description="Prompt category")
    prompt_template: str = Field(..., description="Prompt template with variables")
    variables: list[str] = Field(default=[], description="Variable names")


class UpdatePromptRequest(BaseModel):
    """Update prompt request."""
    name: str | None = None
    description: str | None = None
    prompt_template: str | None = None
    variables: list[str] | None = None


