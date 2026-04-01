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
    mode: str = Field(default="full", description="'full' or 'incremental'")


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
    change_summary: str | None = None


class UpdateIgnoredDirsRequest(BaseModel):
    """Replace all ignored directories."""
    directories: list[str] = Field(..., description="List of directory names to ignore")


class LibraryCapabilityInput(BaseModel):
    """A single library entry for bulk update."""
    library_name: str
    ecosystem: str = ""
    capabilities: list[str] = Field(default_factory=list)


class UpdateLibraryCapabilitiesRequest(BaseModel):
    """Replace all library capabilities."""
    libraries: list[LibraryCapabilityInput] = Field(..., description="List of library capability mappings")


