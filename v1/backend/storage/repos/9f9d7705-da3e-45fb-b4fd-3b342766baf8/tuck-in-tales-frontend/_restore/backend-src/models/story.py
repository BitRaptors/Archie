from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, TypedDict

# Define a type for the structure of each page object in the DB/response
class StoryPageProgress(TypedDict):
    page: int
    description: Optional[str]
    text: Optional[str]
    image_prompt: Optional[str]
    image_url: Optional[str]
    characters_on_page: Optional[List[str]] # List of character names involved

# Removed StoryBase and StoryCreate as generation flow changes
# The Story model represents the full DB record and response
class Story(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    family_id: UUID # Link to the family
    title: Optional[str] = None # Make title optional
    input_prompt: Optional[str] = None # Store the original prompt if needed
    pages: List[StoryPageProgress] = [] # Store progress for each page
    language: str = "en" # Default to English
    target_age: Optional[int] = None # Optional target age
    character_ids: Optional[List[UUID]] = None # IDs of characters used
    status: str = 'INITIALIZING' # Track generation status (INITIALIZING, OUTLINING, GENERATING_PAGES, COMPLETED, FAILED)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True # Pydantic v2 setting 
        # If using Pydantic v1, use: orm_mode = True

# --- Request Model for Triggering Generation ---

class StoryGenerationRequest(BaseModel):
    """Request body for triggering story generation."""
    character_ids: List[UUID] = Field(..., description="List of character IDs to include in the story.")
    prompt: Optional[str] = Field(None, description="Optional user prompt to guide the story.", max_length=1000)
    language: Optional[str] = Field(None, description="Language for the story (e.g., 'en', 'es'). Defaults to None.")
    target_age: Optional[int] = None
    # websocket_client_id: Optional[str] = None # Removed

# Optional: A simpler response if needed, e.g., for listing stories
class StoryBasic(BaseModel):
     """Basic information about a story for listing."""
     id: UUID
     title: Optional[str] = None # Make title optional here too
     language: str
     status: str # Include status in basic info
     created_at: datetime
     # Add character names/avatars later if needed for list view

     class Config:
        from_attributes = True 